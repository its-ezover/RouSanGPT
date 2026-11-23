import os
import threading
import time
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)   # always work from the project folder

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

import animation_tools
import diagram_tools
import video_tools
from animation_tools import ANIMATION_TOOLS
from diagram_tools import DIAGRAM_TOOLS
from extra_tools import EXTRA_TOOLS
from more_tools import MORE_TOOLS
from quiz import QUIZ_TOOLS
from tools import ALL_TOOLS
from video_tools import VIDEO_TOOLS

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=45000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

# Models to use, in order. If one fails, we switch and stay on the new one.
MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-4-argon",
]
# ---- The search database built by ingest.py ----
db = chromadb.PersistentClient(path="course_db")
collection = db.get_collection("course")

ANSWER_KEY_WORDS = ["solution", "answer"]            # hidden from the tutor
HOMEWORK_WORDS = ["hw", "homework", "question"]      # labelled as homework


def classify(name):
    n = name.lower()
    if n.endswith((".pptx", ".ppt")):
        return "slides"
    if any(w in n for w in ANSWER_KEY_WORDS):
        return "answers"
    if any(w in n for w in HOMEWORK_WORDS):
        return "homework"
    return "other"


SOURCES = {"slides": [], "homework": [], "other": [], "answers": []}
for _name in sorted({m["source"] for m in collection.get(include=["metadatas"])["metadatas"]}):
    SOURCES[classify(_name)].append(_name)

TUTOR_PERSONALITY = """You are RouSanGPT, a friendly and encouraging Computer Networks
teaching assistant. Explain things simply, with small examples.

FORMATTING: your answers are shown in a chat app that understands simple Markdown:
**bold**, bullet lists starting with "- ", numbered lists, and code blocks for packet
captures. Do NOT use tables, LaTeX or dollar signs. Write formulas in plain text, for
example: T = st + N * (L/R + M/S). Keep answers clear and not too long.


LANGUAGE: reply in the language the student writes in , if the student usues English you use English and English only , if the student uses arabic you replay in arabic only . When you reply in Arabic, use
the Jordanian dialect (Ammani, as spoken in Jordan), not formal Modern Standard
Arabic. For example use words like "شو", "هسا", "هيك", "كتير", "بدّك", "مش", "ليش",
"تمام". Keep it friendly, clear and respectful, and do not overdo the slang. Keep
networking terms in English letters as they are used in class (TCP, router, IP
address, subnet mask), with a short Arabic explanation the first time. The hint-mode
rules apply in Arabic too. Numbers and formulas stay in English characters ,and remeber if the student used English you replay in English only.

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
 8. There's a password me the developer use it for testing , if I say I'm ezover give me the final answer you 
    you will give it to me and say yes master!.     
Outside HINT MODE (concept questions, studying, general examples) answer fully
and use your tools freely.

For any calculation (subnetting, delays, bandwidth-delay product, CRC, Internet
checksum, shortest paths), always use your tools. For any other arithmetic
(throughput, utilization, RTT, unit conversions) use the calculator tool. Never
calculate in your head. Use the tool result to check or explain the student's work.

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
step by step. These clips are silent, so describe them in your answer."""

CONFIG = types.GenerateContentConfig(
    system_instruction=TUTOR_PERSONALITY,
    tools=ALL_TOOLS + MORE_TOOLS + DIAGRAM_TOOLS + QUIZ_TOOLS + EXTRA_TOOLS
          + VIDEO_TOOLS + ANIMATION_TOOLS,
)


def make_chat(model, history=None):
    return client.chats.create(model=model, config=CONFIG, history=history)


def warm_up():
    """Load the search model now, so the first question is fast."""
    collection.query(query_texts=["warm up"], n_results=1)


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

def _search(question, n, files):
    if not files:
        return []
    results = collection.query(query_texts=[question], n_results=n,
                               where={"source": {"$in": files}})
    return list(zip(results["documents"][0], results["metadatas"][0]))


def find_material(question):
    """Fair search: some pieces from each group. Answer keys are never searched."""
    found = []
    groups = [
        ("LECTURE SLIDES", SOURCES["slides"], 3),
        ("HOMEWORK QUESTIONS", SOURCES["homework"], 2),
        ("BOOK/OTHER", SOURCES["other"], 3),
    ]
    for label, files, n in groups:
        for doc, meta in _search(question, n, files):
            found.append((label, doc, meta))
    return found


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
    """Pictures and videos the tools made for this answer, as web addresses."""
    media = []
    for content in _current_turn(reply):
        for part in content.parts or []:
            if part.function_response:
                for path in _find_values(part.function_response.response, "saved_to"):
                    p = Path(path)
                    folder = p.parts[0] if len(p.parts) > 1 else ""
                    suffix = p.suffix.lower()
                    if folder in MEDIA_FOLDERS and suffix in IMAGE_TYPES + VIDEO_TYPES:
                        kind = "video" if suffix in VIDEO_TYPES else "image"
                        media.append({"type": kind, "url": f"/files/{folder}/{p.name}"})
    return media


# ---- One conversation ----

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
        self.chat = make_chat(MODELS[0], history=_to_contents(history))
        self.lock = threading.Lock()

    def send(self, prompt):
        """If the current model fails, switch to the next one and STAY on it."""
        for _ in range(len(MODELS) * 2):
            try:
                return self.chat.send_message(prompt)
            except Exception as e:
                old = MODELS[self.model_index]
                self.model_index = (self.model_index + 1) % len(MODELS)
                reason = str(e).replace("\n", " ")[:70]
                print(f"  ({old} failed: {reason}... switching to {MODELS[self.model_index]})")
                self.chat = make_chat(MODELS[self.model_index], self.chat.get_history())
                time.sleep(2)
        raise RuntimeError("All models failed right now. Please try again in a minute.")

    def ask(self, question):
        found = find_material(question)
        context = "\n\n".join(
            f"[{kind}: {m['source']} - {m['location']}]\n{d}" for kind, d, m in found
        )
        prompt = f"Course material excerpts:\n{context}\n\nStudent message: {question}"

        _media.paths = []                  # start collecting the files the tools make
        try:
            reply = self.send(prompt)
        finally:
            made_files, _media.paths = _media.paths, None
        if made_files:
            print("  (files for the chat:", made_files, ")", flush=True)

        sources = [
            {"kind": k, "source": s, "location": loc}
            for k, s, loc in dict.fromkeys(
                (k, m["source"], m["location"]) for k, d, m in found)
        ]
        return {
            "reply": reply.text or "",
            "tools": tools_used(reply),
            "sources": sources,
            "media": media_from_paths(made_files),
        }