import re
import shutil
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import binaries
import formula_tools
import gemini_client
import history_store
import ingest_lib
import knowledge
import local_ai
import settings
import tts
from app_paths import CODE_DIR, DATA_DIR, INSTALLED

agent.disable_popups()          # the web page shows pictures and videos itself
history_store.init()

BASE = CODE_DIR                 # the program files (web page, logo)
app = FastAPI(title="RouSanGPT")

LOCAL_NAMES = ("127.0.0.1", "localhost", "[::1]")


@app.middleware("http")
async def only_this_computer(request: Request, call_next):
    """Answer only the app's own page. Without this, any web site open in the browser
    could send requests to the app (upload files, quit it), and a site that points
    its own name at 127.0.0.1 ("DNS rebinding") could even read the chats."""
    host = request.headers.get("host", "")
    if host.rsplit(":", 1)[0].lower() not in LOCAL_NAMES:
        return JSONResponse({"detail": "Only this computer can use RouSanGPT."}, status_code=403)
    origin = request.headers.get("origin")
    if origin is not None and origin.lower() not in (f"http://{host}".lower(), f"https://{host}".lower()):
        return JSONResponse({"detail": "Requests from other web sites are not allowed."}, status_code=403)
    return await call_next(request)


sessions = {}                   # chat id -> the tutor's memory of that chat
sessions_lock = threading.Lock()
jobs = {}                       # job id -> what is happening with it
JOB_KEEP = 3600                 # results nobody picked up are forgotten after an hour

# Voices for "Listen" (tried in this order)
VOICES_AR = ["ar-JO-SanaNeural", "ar-SA-ZariyahNeural", "ar-EG-SalmaNeural"]
VOICES_EN = ["en-US-AvaMultilingualNeural", "en-US-AriaNeural"]
ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")


def get_session(chat_id):
    with sessions_lock:
        if chat_id not in sessions:
            sessions[chat_id] = agent.Session(history=history_store.history_for_model(chat_id))
        return sessions[chat_id]


def new_job(message=""):
    """Start tracking a background job. Returns its id."""
    now = time.time()
    for old_id, old in list(jobs.items()):           # forget results nobody picked up
        if old["status"] != "working" and now - old.get("finished", now) > JOB_KEEP:
            jobs.pop(old_id, None)
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "working", "started": now, "message": message,
                    "event": threading.Event()}
    return job_id


def finish_job(job_id, status, **fields):
    """status: "done" (with result=...) or "error" (with error=...)."""
    job = jobs[job_id]
    job.update(status=status, finished=time.time(), **fields)
    job["event"].set()                               # wakes up a waiting /api/result


class ChatRequest(BaseModel):
    chat_id: str
    message: str
    language: str = "auto"
    backend: str = "auto"          # "auto", "gemini" or "local"


class FormulaToolRequest(BaseModel):
    name: str = ""
    description: str = ""
    params: list[dict] = []
    formula: str = ""
    unit: str = ""
    replace: bool = False          # True when editing a saved tool


class DraftRequest(BaseModel):
    idea: str


class ToolTestRequest(BaseModel):
    formula: str
    values: dict = {}


class RenameRequest(BaseModel):
    title: str


class SpeakRequest(BaseModel):
    text: str


class KeyRequest(BaseModel):
    key: str


class SettingsRequest(BaseModel):
    default_language: str | None = None
    default_backend: str | None = None
    local_model: str | None = None


class ModelRequest(BaseModel):
    model: str


class UrlRequest(BaseModel):
    url: str


@app.get("/")
def home():
    return FileResponse(BASE / "web" / "index.html")


@app.get("/api/status")
def status():
    running, models = agent.local_available()
    wanted = agent.local_model()
    s = settings.load()
    return {"ok": True, "app": "RouSanGPT", "app_mode": lifecycle.app_mode,
            "slides": len(agent.SOURCES["slides"]),
            "knowledge_files": sum(len(v) for k, v in agent.SOURCES.items() if k != "answers"),
            "has_key": bool(settings.api_key()),
            "default_language": s["default_language"], "default_backend": s["default_backend"],
            "local_running": running, "local_ready": running and local_ai.has_model(models, wanted),
            "local_model": wanted}


# ---------- Saved chats ----------

@app.get("/api/chats")
def list_chats():
    return history_store.list_chats()


@app.post("/api/chats")
def new_chat():
    return {"id": history_store.create_chat()}


@app.get("/api/chats/{chat_id}")
def chat_messages(chat_id: str):
    if not history_store.exists(chat_id):
        raise HTTPException(404, "Chat not found")
    return {"messages": history_store.get_messages(chat_id)}


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, req: RenameRequest):
    history_store.rename_chat(chat_id, req.title.strip()[:80] or "New chat")
    return {"ok": True}


@app.delete("/api/chats/{chat_id}")
def remove_chat(chat_id: str):
    history_store.delete_chat(chat_id)
    with sessions_lock:
        sessions.pop(chat_id, None)
    return {"ok": True}


# ---------- Asking the tutor ----------

def run_job(job_id, chat_id, text, language, backend):
    """Runs in the background so that long jobs (videos) cannot time out the page."""
    print(f"  (question received: {text[:60]!r}, language={language}, backend={backend})", flush=True)
    try:
        session = get_session(chat_id)
        def show(message):                  # for example "Gemini is busy, retrying..."
            jobs[job_id]["message"] = message
        with session.lock:                  # one question at a time per chat
            result = session.ask(text, language, backend, on_status=show)
        title = history_store.add_exchange(chat_id, text, result)
        print("  (answer ready)", flush=True)
        finish_job(job_id, "done", result={**result, "title": title})
    except Exception as e:
        traceback.print_exc()                # the full error, for debugging
        if gemini_client.is_busy(e):
            reason = "Gemini is very busy right now. Please try again in a minute."
        else:
            reason = str(e)[:200]
        finish_job(job_id, "error", error=f"The tutor could not answer: {reason}")


@app.post("/api/chat")
def chat(req: ChatRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    if not history_store.exists(req.chat_id):
        raise HTTPException(404, "Chat not found")
    job_id = new_job()
    threading.Thread(target=run_job, args=(job_id, req.chat_id, text, req.language, req.backend),
                     daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/result/{job_id}")
def result(job_id: str, wait: float = 0):
    """The result of a background job. wait: seconds to wait for it to finish (at
    most 15) - the answer then arrives the moment it is ready, without asking again
    and again."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if job["status"] == "working" and wait > 0:
        # wait until the job is done, or its message changes (so "Gemini is busy,
        # retrying..." shows at once)
        message, until = job.get("message", ""), time.time() + min(wait, 15)
        while time.time() < until and job.get("message", "") == message:
            if job["event"].wait(min(0.5, max(0.0, until - time.time()))):
                break
    if job["status"] == "working":
        return {"status": "working", "seconds": int(time.time() - job["started"]),
                "message": job.get("message", "")}
    jobs.pop(job_id, None)
    if job["status"] == "error":
        return {"status": "error", "error": job["error"]}
    return {"status": "done", **job["result"]}


# ---------- Course materials ----------

MATERIALS = DATA_DIR / "materials"
ingest_lock = threading.Lock()          # add one file at a time


class Counter:
    """A number that several threads change safely (a plain "+= 1" can lose updates)."""

    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def add(self, n):
        with self._lock:
            self.value += n

    def __bool__(self):
        return self.value > 0


ingesting = Counter()                   # files being added right now (never quit during this)


@app.get("/api/materials")
def list_materials():
    return knowledge.materials()


def run_ingest(job_id, path):
    def progress(message):
        jobs[job_id]["message"] = message
    try:
        _run_ingest(job_id, path, progress)
    finally:
        ingesting.add(-1)


def _run_ingest(job_id, path, progress):
    try:
        if ingest_lock.locked():
            progress("waiting for the file before it")
        with ingest_lock:
            progress("reading")
            knowledge.warm_up()                 # load the search model safely, once
            pieces = ingest_lib.add_file(agent.collection, path, progress)
            agent.refresh_sources()
        if pieces == 0:
            raise ValueError("no text could be read from this file")
        finish_job(job_id, "done", result={
            "name": path.name, "pieces": pieces, "group": agent.classify(path.name)})
    except Exception as e:
        traceback.print_exc()
        finish_job(job_id, "error", error=f"Could not add {path.name}: {str(e)[:200]}")


@app.post("/api/materials")
def upload_material(file: UploadFile = File(...)):
    name = Path(file.filename or "").name
    if not name or Path(name).suffix.lower() not in ingest_lib.SUPPORTED:
        raise HTTPException(400, "Supported files: " + ", ".join(ingest_lib.SUPPORTED))
    MATERIALS.mkdir(exist_ok=True)
    path = MATERIALS / name
    with open(path, "wb") as out:               # copied in pieces, not all in memory
        shutil.copyfileobj(file.file, out, 1024 * 1024)
    job_id = new_job("reading")
    ingesting.add(1)
    threading.Thread(target=run_ingest, args=(job_id, path), daemon=True).start()
    return {"job_id": job_id}


@app.delete("/api/materials/{name}")
def delete_material(name: str):
    name = Path(name).name
    with ingest_lock:
        ingest_lib.remove_source(agent.collection, name)
        agent.refresh_sources()
        # The installed app keeps its own copy of every added file: delete it too.
        # (In dev mode the materials folder holds your original files, used by
        # ingest.py, so they are kept.)
        if INSTALLED:
            (MATERIALS / name).unlink(missing_ok=True)
    return {"ok": True}


# ---------- Formula tools ----------

@app.get("/api/tools")
def list_tools():
    custom = formula_tools.load_specs()
    custom_names = {s["name"] for s in custom}
    builtin = [{"name": f.__name__,
                "about": (f.__doc__ or "").strip().split("\n")[0]}
               for f in agent.BASE_TOOLS if f.__name__ not in custom_names]
    return {"custom": custom, "builtin": builtin}


@app.post("/api/tools")
def add_tool(req: FormulaToolRequest):
    raw = req.model_dump()
    name = req.name.strip()
    # only saved formula tools can be replaced, never the built-in ones
    replace = req.replace and any(s.get("name") == name for s in formula_tools.load_specs())
    taken = {f.__name__ for f in agent.all_tools()}
    try:
        spec = formula_tools.add_spec(raw, taken, replace=replace)
    except ValueError as e:
        raise HTTPException(400, str(e))
    agent.reload_tools()
    return spec


@app.post("/api/tools/draft")
def draft_tool(req: DraftRequest):
    idea = req.idea.strip()
    if len(idea) < 5:
        raise HTTPException(400, "Please describe the calculation in a few words first.")
    try:
        return formula_tools.draft_from_idea(idea, agent.client, agent.MODELS)
    except ValueError as e:
        raise HTTPException(502, str(e))


@app.post("/api/tools/test")
def test_tool(req: ToolTestRequest):
    try:
        return {"result": formula_tools.evaluate(req.formula, req.values)}
    except ZeroDivisionError:
        raise HTTPException(400, "Division by zero.")
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        raise HTTPException(400, f"The formula has a problem: {e}")


@app.delete("/api/tools/{name}")
def delete_tool(name: str):
    formula_tools.delete_spec(name)
    agent.reload_tools()
    return {"ok": True}


# ---------- Voice in and voice out ----------

@app.post("/api/transcribe")
def transcribe_audio(audio: UploadFile = File(...), language: str = Form("auto")):
    """Turn a voice recording from the browser into text."""
    data = audio.file.read()
    if not settings.api_key():
        raise HTTPException(400, str(gemini_client.NoApiKey()))
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "recording", Path(tmp) / "recording.wav"
        src.write_bytes(data)
        try:
            binaries.run_ffmpeg(["-i", str(src), "-ar", "16000", "-ac", "1", str(dst)])
        except binaries.ToolMissing as e:
            raise HTTPException(500, str(e))
        except RuntimeError:
            raise HTTPException(400, "Could not read the audio recording.")
        from voice import transcribe
        text = transcribe(dst.read_bytes(), language=language)
    if not text or text == "[no speech]":
        return {"text": ""}
    return {"text": text}


def clean_for_speech(text):
    """Remove the formatting symbols so the voice does not read them out."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_`#>|]", "", text)
    text = re.sub(r"^\s*[-\u2022]\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()[:1500]


@app.post("/api/speak")
def speak(req: SpeakRequest):
    """Read an answer aloud. Arabic text gets a Jordanian voice."""
    text = clean_for_speech(req.text)
    if not text:
        raise HTTPException(400, "Nothing to read")
    mostly_arabic = len(ARABIC_LETTER.findall(text)) > 0.3 * len(text)
    voices = VOICES_AR if mostly_arabic else VOICES_EN
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "speech.mp3"
        try:
            tts.synthesize(text, out, voices)
        except RuntimeError as e:
            raise HTTPException(502, str(e))
        return Response(out.read_bytes(), media_type="audio/mpeg")


# ---------- Settings ----------

LANGUAGES = ("auto", "english", "arabic")
BACKENDS = ("auto", "gemini", "local")


@app.get("/api/settings")
def get_settings():
    s = settings.load()
    key = settings.api_key()
    return {"has_key": bool(key), "key_source": settings.key_source(),
            "key_hint": ("..." + key[-4:]) if key else "",
            "default_language": s["default_language"], "default_backend": s["default_backend"],
            "local_model": agent.local_model(), "app_mode": lifecycle.app_mode,
            "data_dir": str(DATA_DIR)}


@app.post("/api/settings/key")
def set_key(req: KeyRequest):
    outcome, message = gemini_client.test_key(req.key)
    if outcome in (gemini_client.KEY_BAD, gemini_client.KEY_ERROR):
        raise HTTPException(400, message)
    settings.save({"gemini_api_key": req.key.strip()})
    if outcome == gemini_client.KEY_BUSY:      # saved, but not tested yet
        return {"ok": True, "tested": False, "message": message}
    return {"ok": True, "tested": True, "message": message + " Saved."}


@app.post("/api/settings")
def change_settings(req: SettingsRequest):
    changes = {}
    if req.default_language is not None:
        if req.default_language not in LANGUAGES:
            raise HTTPException(400, "Unknown language")
        changes["default_language"] = req.default_language
    if req.default_backend is not None:
        if req.default_backend not in BACKENDS:
            raise HTTPException(400, "Unknown AI choice")
        changes["default_backend"] = req.default_backend
    if req.local_model is not None:
        model = req.local_model.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,80}", model):
            raise HTTPException(400, "That is not a valid model name.")
        changes["local_model"] = model
    settings.save(changes)
    return get_settings()


# ---------- Local model (Ollama) ----------

@app.get("/api/local")
def local_status():
    return local_ai.status(agent.local_model())


@app.post("/api/local/start")
def local_start():
    try:
        return {"message": local_ai.start()}
    except (binaries.ToolMissing, RuntimeError) as e:
        raise HTTPException(500, str(e))


def run_pull(job_id, model):
    def progress(text, pct):
        jobs[job_id].update(message=text, percent=pct)
    try:
        local_ai.pull(model, progress)
        finish_job(job_id, "done", result={"model": model})
    except Exception as e:
        traceback.print_exc()
        finish_job(job_id, "error", error=f"Could not download {model}: {str(e)[:200]}")


@app.post("/api/local/pull")
def local_pull(req: ModelRequest):
    model = req.model.strip()
    if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,80}", model):
        raise HTTPException(400, "That is not a valid model name.")
    if local_ai.server_version() is None:
        raise HTTPException(400, "Ollama is not running. Start it first.")
    job_id = new_job("starting download")
    threading.Thread(target=run_pull, args=(job_id, model), daemon=True).start()
    return {"job_id": job_id}


# ---------- The app window: heartbeat, closing, quitting ----------

class Lifecycle:
    """In the desktop app, the server stops by itself when its window is closed.
    The page sends a heartbeat every 10 s and says "bye" when it closes. We stop
    10 s after a bye (so a reload is fine), or after 5 minutes without any
    heartbeat. In dev mode (python server.py) none of this is active."""
    BYE_GRACE = 10
    SILENCE = 300

    def __init__(self):
        self.app_mode = False
        self.on_shutdown = None
        self.pages = {}             # page id -> last heartbeat time
        self.last_bye = None
        self.started = time.time()
        self.stopping = False
        self.lock = threading.Lock()

    def enable(self, on_shutdown):
        self.app_mode = True
        self.on_shutdown = on_shutdown
        threading.Thread(target=self._watch, daemon=True, name="watchdog").start()

    def heartbeat(self, page):
        with self.lock:
            self.pages[page] = time.time()

    def bye(self, page):
        with self.lock:
            self.pages.pop(page, None)
            self.last_bye = time.time()

    def _reason_to_stop(self):
        now = time.time()
        with self.lock:
            for page, seen in list(self.pages.items()):
                if now - seen > self.SILENCE:
                    del self.pages[page]
            if self.pages:
                return None
            if self.last_bye is not None and now - self.last_bye >= self.BYE_GRACE:
                return "the window was closed"
            if now - max([self.started] + ([self.last_bye] if self.last_bye else [])) > self.SILENCE:
                return "no window has been open for 5 minutes"
        return None

    def _watch(self):
        while not self.stopping:
            time.sleep(1)
            reason = self._reason_to_stop()
            if reason and not ingesting:
                self.shutdown(reason)

    def shutdown(self, reason):
        if self.stopping:
            return
        self.stopping = True
        print(f"  (shutting down: {reason})", flush=True)
        while ingesting:                        # never stop while a file is being added
            time.sleep(0.5)
        with ingest_lock:
            local_ai.stop_if_started_by_us()
            if self.on_shutdown:
                self.on_shutdown()


lifecycle = Lifecycle()


async def _page_id(request):
    try:
        body = (await request.body()).decode(errors="ignore").strip()
    except Exception:
        body = ""
    if body.startswith("{"):
        import json
        try:
            body = str(json.loads(body).get("page", ""))
        except ValueError:
            body = ""
    return body[:64] or "page"


@app.post("/api/heartbeat")
async def heartbeat(request: Request):
    lifecycle.heartbeat(await _page_id(request))
    return {"ok": True}


@app.post("/api/bye")
async def bye(request: Request):
    lifecycle.bye(await _page_id(request))
    return {"ok": True}


@app.post("/api/quit")
def quit_app():
    if not lifecycle.app_mode:
        raise HTTPException(400, "Quit only works in the desktop app. Press Ctrl+C in the terminal.")
    threading.Thread(target=lifecycle.shutdown, args=("Quit was chosen",), daemon=True).start()
    return {"ok": True}


@app.post("/api/open-url")
def open_url(req: UrlRequest):
    """Open a web link in the computer's normal browser (used by the app window)."""
    if not re.match(r"^https?://", req.url):
        raise HTTPException(400, "Only web links can be opened.")
    binaries.open_file(req.url)
    return {"ok": True}


# The logo and other files of the web page
app.mount("/static", StaticFiles(directory=BASE / "web"), name="static")

# Pictures, videos and animations made by the tools
for folder in agent.MEDIA_FOLDERS:
    (DATA_DIR / folder).mkdir(exist_ok=True)
    app.mount(f"/files/{folder}", StaticFiles(directory=DATA_DIR / folder), name=folder)


if __name__ == "__main__":
    import uvicorn

    URL = "http://127.0.0.1:8000"
    print("Loading the search model (a few seconds)...")
    agent.warm_up()
    print(f"RouSanGPT is running at {URL}  (press Ctrl+C to stop)")
    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)