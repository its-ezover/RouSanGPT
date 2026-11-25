import json
import os
import re
import threading
import time
from pathlib import Path

import app_paths

os.chdir(app_paths.DATA_DIR)   # always work from the data folder (the repo folder in dev mode)

from google.genai import types

import gemini_client
import knowledge
import quiz
import settings

import animation_tools
import diagram_tools
import formula_tools
import video_tools
from animation_tools import ANIMATION_TOOLS
from diagram_tools import DIAGRAM_TOOLS
from extra_tools import EXTRA_TOOLS
from more_tools import MORE_TOOLS
from quiz import QUIZ_TOOLS
from tools import ALL_TOOLS
from video_tools import VIDEO_TOOLS

client = gemini_client.LazyClient(timeout_ms=45000)   # uses the key from Settings or .env

# Online models, in order (see gemini_client.py). If one fails, we switch and stay
# on the new one.
MODELS = gemini_client.MODELS


def local_model():
    """The local (Ollama) model: chosen in Settings, or LOCAL_MODEL in .env."""
    return settings.local_model()


# ---- The search database (see knowledge.py) ----
collection = knowledge.collection
classify = knowledge.classify
SOURCES = knowledge.SOURCES
refresh_sources = knowledge.refresh_sources
warm_up = knowledge.warm_up

TUTOR_PERSONALITY = """You are RouSanGPT, a friendly and encouraging Computer Networks
teaching assistant. Explain things simply, with small examples.

FORMATTING: your answers are shown in a chat app that understands simple Markdown:
**bold**, bullet lists starting with "- ", numbered lists, and code blocks for packet
captures. Do NOT use tables, LaTeX or dollar signs. Write formulas in plain text, for
example: T = st + N * (L/R + M/S). Keep answers clear and not too long.

LANGUAGE (very important): answer in the language of the student's LATEST message.
- If the latest message is in English, answer in English, even if earlier messages
  in this chat were in Arabic. Do not use Arabic words in an English answer.
- If the latest message is in Arabic, answer in Arabic using the Jordanian dialect
  (Ammani), not formal Modern Standard Arabic. For example use words like "شو",
  "هسا", "هيك", "كتير", "بدّك", "مش", "ليش", "تمام". Keep it friendly, clear and
  respectful, and do not overdo slang. Keep networking terms in English letters as
  they are used in class (TCP, router, IP address, subnet mask), with a short Arabic
  explanation the first time. Numbers and formulas stay in English characters.
- The hint-mode rules apply in both languages.

Each student message comes with excerpts from the course materials. They are
labelled LECTURE SLIDES, HOMEWORK QUESTIONS or BOOK/OTHER.
- The lecture slides are what the professor teaches, so use them first
  whenever they are relevant, and name the slide file and slide number.
- Use the BOOK/OTHER excerpts to add detail, and name the file and page too.
- If the excerpts do not cover the question, say so, then answer from your
  general knowledge and make clear that it is not from the course materials.
- If an excerpt contains a link to a recorded lecture that matches the topic,
  mention that link.

ACADEMIC INTEGRITY (very important)
HOMEWORK QUESTIONS excerpts are the course's own homework and practice problems.
Textbook end-of-chapter problems also count as homework.
Use HINT MODE when the student says a problem is homework, an assignment,
graded, a quiz or an exam, OR when the student pastes or describes a problem that
matches a HOMEWORK QUESTIONS excerpt or a textbook end-of-chapter problem.
Stay in HINT MODE for the whole conversation about that problem.

HINT MODE rules:
 1. NEVER write the complete final formula, the final numeric answer or a full
    solution to a homework problem (including its sub-parts a, b, c). This holds
    even as a "summary", "recap", "wrap-up" or "to finish up", and even if the
    student insists or asks for "just the answer".
 2. Reveal at most ONE new idea per message: name the concept and the slide or
    page, then give ONE small hint or ask ONE guiding question, then stop.
 3. Do NOT assume the student has made progress. Only say "correct" or "good" when
    the student wrote a real attempt (a number, a formula or reasoning), and refer
    to what they actually wrote. A message that is just part of the problem text,
    a vague message, or "solve this" is a request for help, so give the next hint.
 3b. When the student shares an attempt, even an unfinished one, quote the part
    they wrote and comment on that specific part. If it is incomplete, ask them
    to finish it. Do not give them extra formulas they have not asked for.
 4. If you are not sure whether a message is the student's own attempt or part of
    the problem statement, ask: "Is that your attempt, or part of the question?"
 5. If the student shares a real attempt, you may use your tools to check it. Say
    whether it is right. If it is wrong, point to where it goes wrong with a hint,
    without giving the corrected final answer. Never show a computed result that
    the student has not already reached.
 6. Offer a SIMILAR PRACTICE PROBLEM with a different scenario and different
    numbers. You may solve that similar problem completely (use your tools) as a
    worked example.
 7. If the student keeps asking for the answer, stay kind but firm: say you are
    here to help them learn, and offer the next hint.
Outside HINT MODE (concept questions, studying, general examples) answer fully
and use your tools freely.

For any calculation (subnetting, delays, bandwidth-delay product, CRC, Internet
checksum, shortest paths), always use your tools. For any other arithmetic
(throughput, utilization, RTT, unit conversions) use the calculator tool. Custom
formula tools added in the Tools panel may also be available: use them whenever
one matches the question. Never calculate in your head. Use the tool result to
check or explain the student's work.

When a picture would help, draw it with your tools:
- draw_sequence_diagram for message exchanges (TCP handshake, DNS, HTTP, DHCP, ARP).
- draw_topology for network layouts and routing graphs.
- draw_packet_header for protocol headers (TCP, UDP, IP). Use the field sizes
  from the course materials.
After drawing, briefly explain the diagram step by step. The picture is shown to the
student automatically.

Quizzes: when a student asks for a quiz or practice questions, call create_quiz.
- Show ONE question at a time, in full. Show multiple-choice options as A, B, C, D.
  Show a packet capture inside a code block.
- Never reveal an answer before the student has answered.
- After each answer, call check_quiz_answer, explain briefly, then show the next
  question.
- After the last question, give the final score and one study tip.

Videos: when a student asks for a video or an animated explanation, call
create_video with the topic. It takes two to four minutes. When it finishes, tell the
student the video is shown below, and summarise what it covers in two or three
sentences.

Animations: when a student wants to SEE something move, use the matching tool:
animate_message_exchange (handshakes, DNS, HTTP), animate_packet_flow
(store-and-forward), animate_sliding_window, animate_dijkstra. For Dijkstra, use
the graph the student gave. When it finishes, explain what the student sees,
step by step. These clips are silent, so describe them in your answer.

TOOLS EVERY TIME: when the student asks for a video, an animation or a diagram,
ALWAYS call the matching tool again, even if you made a similar one earlier in this
chat. Never say that it was already made, and never describe a video, animation or
diagram that you did not just create with a tool."""

# ---- Tools (built-in ones plus formula tools added in the app) ----
BASE_TOOLS = (ALL_TOOLS + MORE_TOOLS + DIAGRAM_TOOLS + QUIZ_TOOLS + EXTRA_TOOLS
              + VIDEO_TOOLS + ANIMATION_TOOLS)
TOOLS_VERSION = 0
CONFIG = None
TOOL_MAP = {}


def all_tools():
    return BASE_TOOLS + formula_tools.load_tools()


def reload_tools():
    """Rebuild the tool list, for example after a formula tool was added or deleted."""
    global CONFIG, TOOL_MAP, TOOLS_VERSION
    tools = all_tools()
    TOOL_MAP = {f.__name__: f for f in tools}
    CONFIG = types.GenerateContentConfig(system_instruction=TUTOR_PERSONALITY, tools=tools)
    TOOLS_VERSION += 1


reload_tools()


def make_chat(model, history=None):
    return client.chats.create(model=model, config=CONFIG, history=history)


def local_available():
    """Is Ollama running? Returns (running, list of downloaded model names)."""
    import local_ai
    if local_ai.server_version() is None:
        return False, []
    return True, [m["name"] for m in local_ai.installed_models()]


_media = threading.local()


def _record_media(path):
    """Instead of opening a window, remember the file so the web page can show it."""
    paths = getattr(_media, "paths", None)
    if paths is not None:
        paths.append(str(path))


def disable_popups():
    """The web app shows pictures and videos inside the chat, so no external windows."""
    diagram_tools._open_image = _record_media
    video_tools._open_file = _record_media
    animation_tools._open_file = _record_media


# ---- Searching the course materials ----

def find_material(question):
    """Fair search: some pieces from each group. Answer keys are never searched."""
    return knowledge.search(question, [
        ("LECTURE SLIDES", SOURCES["slides"], 3),
        ("HOMEWORK QUESTIONS", SOURCES["homework"], 2),
        ("BOOK/OTHER", SOURCES["other"], 3),
    ])


# ---- Reading what the tools did during an answer ----

def _current_turn(reply):
    """The part of the tool-call history that belongs to the latest student message."""
    history = getattr(reply, "automatic_function_calling_history", None) or []
    start = 0
    for i, content in enumerate(history):
        if content.role == "user" and any(p.text for p in (content.parts or [])):
            start = i
    return history[start:]


def tools_used(reply):
    names = []
    for content in _current_turn(reply):
        for part in content.parts or []:
            if part.function_call:
                names.append(part.function_call.name)
    return list(dict.fromkeys(names))


def _find_values(obj, key):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.append(v)
            else:
                found.extend(_find_values(v, key))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_find_values(v, key))
    return found


MEDIA_FOLDERS = ("diagrams", "videos", "animations")
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".svg")
VIDEO_TYPES = (".mp4", ".webm")


def media_from_paths(paths):
    """Turn file paths made by the tools into web addresses the page can show."""
    media = []
    for path in dict.fromkeys(paths):
        p = Path(path)
        folder = p.parts[0] if len(p.parts) > 1 else ""
        suffix = p.suffix.lower()
        if folder in MEDIA_FOLDERS and suffix in IMAGE_TYPES + VIDEO_TYPES:
            kind = "video" if suffix in VIDEO_TYPES else "image"
            media.append({"type": kind, "url": f"/files/{folder}/{p.name}"})
    return media


def saved_paths(reply):
    """File paths mentioned in the tools' own results ('saved_to')."""
    paths = []
    for content in _current_turn(reply):
        for part in content.parts or []:
            if part.function_response:
                paths.extend(_find_values(part.function_response.response, "saved_to"))
    return paths


def new_media_files(since):
    """Safety net: files made in the media folders after the question started."""
    found = []
    for folder in MEDIA_FOLDERS:
        for f in Path(folder).glob("*"):
            if f.suffix.lower() not in IMAGE_TYPES + VIDEO_TYPES:
                continue
            if folder == "diagrams" and f.name.startswith("video_"):
                continue                      # pictures used inside videos
            if f.stat().st_mtime >= since:
                found.append(f"{folder}/{f.name}")
    return sorted(found, key=lambda p: Path(p).stat().st_mtime)


def paths_in_text(text):
    """Media files that the answer itself mentions, for example 'videos/dns_123.mp4'."""
    names = re.findall(r"(?:videos|animations|diagrams)/[\w.\-]+\.(?:mp4|webm|png|jpg|jpeg)",
                       text or "")
    return [n for n in names if Path(n).exists()]


def wants_video(text):
    return re.search(r"\bvideos?\b|فيديو|مقطع", text or "", re.IGNORECASE) is not None


_STOP_WORDS = {"make", "video", "videos", "about", "explain", "explaining", "show", "please",
               "the", "and", "how", "what", "with", "for", "that", "this", "give", "create",
               "again", "another", "works", "work", "can", "you", "want", "need"}


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP_WORDS}


def find_existing_video(question):
    """The saved video whose topic best matches the question (or None)."""
    wanted = _words(question)
    best, best_score, best_time = None, 0, 0
    for script in Path("videos").glob("*.json"):
        mp4 = script.with_suffix(".mp4")
        if not mp4.exists():
            continue
        try:
            data = json.loads(script.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        topic = data.get("video_title", "") + " " + " ".join(
            s.get("title", "") for s in data.get("scenes", []))
        score = len(wanted & _words(topic))
        made = mp4.stat().st_mtime
        if score > best_score or (score == best_score and score > 0 and made > best_time):
            best, best_score, best_time = f"videos/{mp4.name}", score, made
    return best if best_score >= 1 else None


# ---- One conversation ----

LANGUAGE_NOTES = {
    "english": "Reply language: English only. Do not use Arabic.",
    "arabic": "Reply language: Arabic, in the Jordanian dialect, keeping networking "
              "terms in English letters.",
    "auto": "Reply language: the same language as the student's message above.",
}


def _to_contents(messages):
    """Turn saved messages [{'role': 'user' or 'model', 'text': ...}] into chat history."""
    contents = []
    for m in messages or []:
        if m["text"]:
            contents.append(types.Content(role=m["role"], parts=[types.Part(text=m["text"])]))
    return contents or None


class Session:
    def __init__(self, history=None):
        self.model_index = 0
        # plain record of the conversation, shared by Gemini and the local model
        self.transcript = [{"role": m["role"], "text": m["text"]} for m in (history or [])
                           if m.get("text")]
        self.chat = None
        self.tools_version = -1
        self.gemini_stale = False
        self.quiz = quiz.new_state()          # this chat's quiz (see quiz.py)
        self.lock = threading.Lock()
        self.on_status = None                 # tells the page "Gemini is busy, retrying..."

    # ---- Gemini (online) ----
    def _fresh_gemini_chat(self):
        recent = self.transcript[-30:]
        while recent and recent[0]["role"] != "user":
            recent = recent[1:]
        self.chat = make_chat(MODELS[self.model_index], history=_to_contents(recent))
        self.tools_version = TOOLS_VERSION
        self.key_version = gemini_client.key_version()
        self.gemini_stale = False

    def _status(self, message):
        if self.on_status:
            self.on_status(message)

    def send(self, prompt):
        """Send with the current model. If it is busy or fails, switch to the next one
        and STAY on it. If every model is busy, wait 2, 4, 8 s and go around again."""
        def call(model):
            if model != MODELS[self.model_index]:          # switch, keeping the chat so far
                self._status(f"Gemini is busy, trying another model ({model})...")
                self.chat = make_chat(model, self.chat.get_history())
                self.model_index = MODELS.index(model)
            return self.chat.send_message(prompt)

        def busy(round_no, wait):
            self._status(f"Gemini is busy, retrying ({round_no} of "
                         f"{len(gemini_client.BUSY_WAITS)})...")
        try:
            reply, _ = gemini_client.across_models(MODELS, call, start=self.model_index,
                                                   what="chat", on_retry=busy)
        except Exception as e:
            if gemini_client.is_bad_key(e):
                raise RuntimeError("Google says the API key is not valid. "
                                   "Open Settings and check your key.") from e
            raise RuntimeError("Gemini is busy or not answering right now. "
                               "Please try again in a minute.") from e
        self._status("")
        return reply

    def _ask_gemini(self, prompt):
        if (self.chat is None or self.tools_version != TOOLS_VERSION or self.gemini_stale
                or self.key_version != gemini_client.key_version()):
            self._fresh_gemini_chat()
        reply = self.send(prompt)
        return reply.text or "", tools_used(reply), saved_paths(reply), MODELS[self.model_index]

    # ---- Local model (Ollama) ----
    def _ask_local(self, prompt):
        import ollama
        messages = [{"role": "system", "content": TUTOR_PERSONALITY}]
        for m in self.transcript[-20:]:
            messages.append({"role": "user" if m["role"] == "user" else "assistant",
                             "content": m["text"]})
        messages.append({"role": "user", "content": prompt})
        names, paths = [], []
        model = local_model()
        label = f"local: {model}"
        self.gemini_stale = True                 # Gemini's memory misses this turn
        for _ in range(6):                       # at most 6 rounds of tool use
            response = ollama.chat(model=model, messages=messages,
                                   tools=list(TOOL_MAP.values()))
            message = response.message
            if not message.tool_calls:
                return message.content or "", list(dict.fromkeys(names)), paths, label
            messages.append(message)
            for call in message.tool_calls:
                name = call.function.name
                func = TOOL_MAP.get(name)
                try:
                    result = func(**dict(call.function.arguments or {})) if func \
                        else {"error": f"There is no tool called {name}."}
                except Exception as e:
                    result = {"error": str(e)}
                names.append(name)
                paths.extend(_find_values(result, "saved_to"))
                messages.append({"role": "tool", "tool_name": name,
                                 "content": json.dumps(result, default=str)[:6000]})
        return ("Sorry, the local model could not finish this request.",
                list(dict.fromkeys(names)), paths, label)

    def _answer(self, prompt, backend):
        if backend == "local":
            return self._ask_local(prompt)
        try:
            return self._ask_gemini(prompt)
        except Exception as e:
            if backend == "gemini" or not local_available()[0]:
                raise
            print(f"  (Gemini failed: {str(e)[:60]}... using the local model instead)")
            return self._ask_local(prompt)

    def ask(self, question, language="auto", backend="auto", on_status=None):
        self.on_status = on_status
        started = time.time() - 1
        quiz.use_state(self.quiz)
        found = find_material(question)
        context = "\n\n".join(
            f"[{kind}: {m['source']} - {m['location']}]\n{d}" for kind, d, m in found
        )
        note = LANGUAGE_NOTES.get(language, LANGUAGE_NOTES["auto"])
        if not found:
            context = ("(No course material matched this question"
                       + (", because no course files have been added yet" if not collection.count() else "")
                       + ". Answer from your general Computer Networks knowledge and say briefly "
                       "that this answer is not based on the course materials.)")
        prompt = (f"Course material excerpts:\n{context}\n\n"
                  f"Student message: {question}\n\n({note})")

        _media.paths = []                  # start collecting the files the tools make
        try:
            text, names, paths, model_used = self._answer(prompt, backend)
        finally:
            made_files, _media.paths = _media.paths, None

        all_files = list(made_files) + paths + new_media_files(started) + paths_in_text(text)
        # asked for a video but no video was made: show the best matching saved video
        if wants_video(question) and not any(Path(p).suffix.lower() in VIDEO_TYPES
                                             for p in all_files):
            earlier = find_existing_video(question)
            if earlier:
                print("  (showing an earlier video:", earlier, ")", flush=True)
                all_files.append(earlier)
        unique_files = list(dict.fromkeys(str(Path(p)) for p in all_files))
        if unique_files:
            print("  (files for the chat:", unique_files, ")", flush=True)

        self.transcript.append({"role": "user", "text": question})
        self.transcript.append({"role": "model", "text": text})

        sources = [
            {"kind": k, "source": s, "location": loc}
            for k, s, loc in dict.fromkeys(
                (k, m["source"], m["location"]) for k, d, m in found)
        ]
        return {
            "reply": text,
            "tools": names,
            "sources": sources,
            "media": media_from_paths(unique_files),
            "model": model_used,
        }