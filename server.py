import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import history_store

agent.disable_popups()          # the web page shows pictures and videos itself
history_store.init()

BASE = Path(__file__).resolve().parent
app = FastAPI(title="RouSanGPT")

sessions = {}                   # chat id -> the tutor's memory of that chat
sessions_lock = threading.Lock()
jobs = {}                       # job id -> what is happening with it

# Voices for "Listen" (tried in this order)
VOICES_AR = ["ar-JO-SanaNeural", "ar-JO-TaimNeural", "ar-EG-SalmaNeural"]
VOICES_EN = ["en-US-AvaMultilingualNeural", "en-US-AriaNeural"]
ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")


def get_session(chat_id):
    with sessions_lock:
        if chat_id not in sessions:
            sessions[chat_id] = agent.Session(history=history_store.history_for_model(chat_id))
        return sessions[chat_id]


class ChatRequest(BaseModel):
    chat_id: str
    message: str


class RenameRequest(BaseModel):
    title: str


class SpeakRequest(BaseModel):
    text: str


@app.get("/")
def home():
    return FileResponse(BASE / "web" / "index.html")


@app.get("/api/status")
def status():
    return {"ok": True, "slides": len(agent.SOURCES["slides"])}


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

def run_job(job_id, chat_id, text):
    """Runs in the background so that long jobs (videos) cannot time out the page."""
    print(f"  (question received: {text[:60]!r})", flush=True)
    try:
        session = get_session(chat_id)
        with session.lock:                  # one question at a time per chat
            result = session.ask(text)
        title = history_store.add_exchange(chat_id, text, result)
        print("  (answer ready)", flush=True)
        jobs[job_id].update(status="done", result={**result, "title": title})
    except Exception as e:
        traceback.print_exc()
        jobs[job_id].update(status="error",
                            error=f"The tutor could not answer: {str(e)[:200]}")


@app.post("/api/chat")
def chat(req: ChatRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    if not history_store.exists(req.chat_id):
        raise HTTPException(404, "Chat not found")
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "working", "started": time.time()}
    threading.Thread(target=run_job, args=(job_id, req.chat_id, text), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/result/{job_id}")
def result(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if job["status"] == "working":
        return {"status": "working", "seconds": int(time.time() - job["started"])}
    jobs.pop(job_id, None)
    if job["status"] == "error":
        return {"status": "error", "error": job["error"]}
    return {"status": "done", **job["result"]}


# ---------- Voice in and voice out ----------

@app.post("/api/transcribe")
def transcribe_audio(audio: UploadFile = File(...)):
    """Turn a voice recording from the browser into text."""
    data = audio.file.read()
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "recording", Path(tmp) / "recording.wav"
        src.write_bytes(data)
        converted = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-ar", "16000", "-ac", "1", str(dst)],
            capture_output=True, text=True,
        )
        if converted.returncode != 0:
            raise HTTPException(400, "Could not read the audio recording.")
        from voice import transcribe
        text = transcribe(dst.read_bytes())
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
        for voice in voices:
            done = subprocess.run(
                [sys.executable, "-m", "edge_tts", "--voice", voice,
                 f"--text={text}", "--write-media", str(out)],
                capture_output=True, text=True, timeout=120,
            )
            if done.returncode == 0 and out.exists():
                return Response(out.read_bytes(), media_type="audio/mpeg")
    raise HTTPException(502, "Text-to-speech failed (is the internet working?)")


# Pictures, videos and animations made by the tools
for folder in agent.MEDIA_FOLDERS:
    (BASE / folder).mkdir(exist_ok=True)
    app.mount(f"/files/{folder}", StaticFiles(directory=BASE / folder), name=folder)


if __name__ == "__main__":
    import uvicorn

    URL = "http://127.0.0.1:8000"
    print("Loading the search model (a few seconds)...")
    agent.warm_up()
    print(f"RouSanGPT is running at {URL}  (press Ctrl+C to stop)")
    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)