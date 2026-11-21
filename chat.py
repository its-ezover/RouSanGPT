import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import chromadb
from tools import ALL_TOOLS
from more_tools import MORE_TOOLS
from diagram_tools import DIAGRAM_TOOLS
from quiz import QUIZ_TOOLS
from extra_tools import EXTRA_TOOLS
from video_tools import VIDEO_TOOLS
from animation_tools import ANIMATION_TOOLS

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=45000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

# Models to use, in order. If one fails, we switch and stay on the new one.
MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]
model_index = 0

# Open the database we built with ingest.py
db = chromadb.PersistentClient(path="course_db")
collection = db.get_collection("course")

# ---- Sort the stored files into groups, using words in the file names ----
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
for name in sorted({m["source"] for m in collection.get(include=["metadatas"])["metadatas"]}):
    SOURCES[classify(name)].append(name)

print(f"Slides: {len(SOURCES['slides'])} | Homework files: {len(SOURCES['homework'])} "
      f"| Books/other: {len(SOURCES['other'])}")
print(f"Answer-key files hidden from the tutor: {len(SOURCES['answers'])}")

TUTOR_PERSONALITY = """You are Net.ai, a friendly and encouraging Computer Networks
teaching assistant. Explain things simply, with small examples.

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
    a vague message, or "solve this" is a request for help, so give the next hint ,
     3b. When the student shares an attempt, even an unfinished one, quote the part
    they wrote and comment on that specific part. If it is incomplete, ask them
    to finish it. Do not give them extra formulas they have not asked for..
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
(throughput, utilization, RTT, unit conversions) use the calculator tool. Never
calculate in your head. Use the tool result to check or explain the student's work.

When a picture would help, draw it with your tools:
- draw_sequence_diagram for message exchanges (TCP handshake, DNS, HTTP, DHCP, ARP).
- draw_topology for network layouts and routing graphs.
- draw_packet_header for protocol headers (TCP, UDP, IP). Use the field sizes
  from the course materials.
After drawing, briefly explain the diagram step by step.

Quizzes: when a student asks for a quiz or practice questions, call create_quiz.
- Show ONE question at a time, in full. Show multiple-choice options as A, B, C, D.
  Show a packet capture inside a code block.
- Never reveal an answer before the student has answered.
- After each answer, call check_quiz_answer, explain briefly, then show the next
  question.
- After the last question, give the final score and one study tip.

Videos: when a student asks for a video or an animated explanation, call
create_video with the topic. It takes about a minute. When it finishes, tell the
student it was saved and opened, and summarise what the video covers in two or
three sentences.


Animations: when a student wants to SEE something move, use the matching tool:
animate_message_exchange (handshakes, DNS, HTTP), animate_packet_flow
(store-and-forward), animate_sliding_window, animate_dijkstra. For Dijkstra, use
the graph the student gave. When it finishes, explain what the student sees,
step by step. These clips are silent, so describe them in your answer."""

CONFIG = types.GenerateContentConfig(
    system_instruction=TUTOR_PERSONALITY,
           tools=ALL_TOOLS + MORE_TOOLS + DIAGRAM_TOOLS + QUIZ_TOOLS + EXTRA_TOOLS + VIDEO_TOOLS + ANIMATION_TOOLS,
)


def make_chat(model, history=None):
    return client.chats.create(model=model, config=CONFIG, history=history)


chat = make_chat(MODELS[model_index])


def send_message(prompt):
    """Send a message. If the current model fails, switch to the next one and
    STAY on it for the rest of the chat (until it fails too)."""
    global chat, model_index
    for attempt in range(len(MODELS) * 2):
        try:
            return chat.send_message(prompt)
        except Exception as e:
            old = MODELS[model_index]
            model_index = (model_index + 1) % len(MODELS)
            reason = str(e).replace("\n", " ")[:70]
            print(f"  ({old} failed: {reason}... switching to {MODELS[model_index]})")
            chat = make_chat(MODELS[model_index], chat.get_history())
            time.sleep(2)
    raise RuntimeError("All models failed right now. Please try again in a minute.")


def tools_used(reply):
    """List the tools the AI called while answering the latest message."""
    history = getattr(reply, "automatic_function_calling_history", None) or []
    start = 0
    for i, content in enumerate(history):   # find the student's latest message
        if content.role == "user" and any(p.text for p in (content.parts or [])):
            start = i
    names = []
    for content in history[start:]:
        for part in content.parts or []:
            if part.function_call:
                names.append(part.function_call.name)
    return names


def search(question, n, files):
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
        for doc, meta in search(question, n, files):
            found.append((label, doc, meta))
    return found


def read_question():
    """Read what the student types. Type /paste first for multi-line text."""
    first = input("You: ")
    if first.strip().lower() == "/voice":
        from voice import record_until_enter, transcribe
        text = transcribe(record_until_enter())
        print("  You said:", text)
        if not text or text == "[no speech]":
            return ""
        return text    
    if first.strip().lower() == "/paste":
        print("Paste your text now, then type /end on a new line and press Enter.")
        lines = []
        while True:
            line = input()
            if line.strip().lower() == "/end":
                break
            lines.append(line)
        return "\n".join(lines)
    return first


print("\nNet.ai is ready!")
print("Type your question and press Enter.")
print("  /paste  - for text with several lines")
print("  /voice  - to ask with your microphone")
print("  quit    - to exit (or press Ctrl+C)")
print("Wait for the next 'You:' before typing again.\n")

try:
    while True:
        question = read_question()
        if question.strip().lower() == "quit":
            print("Bye!")
            break
        if not question.strip():
            continue

        found = find_material(question)
        context = "\n\n".join(
            f"[{kind}: {m['source']} - {m['location']}]\n{d}" for kind, d, m in found
        )
        prompt = f"Course material excerpts:\n{context}\n\nStudent message: {question}"

        try:
            reply = send_message(prompt)
            print("\nNet.ai:", reply.text)
            used = tools_used(reply)
            if used:
                print("\nTools used:", ", ".join(dict.fromkeys(used)))
            print("\nSearched in:")
            for kind, source, location in dict.fromkeys(
                (k, m["source"], m["location"]) for k, d, m in found
            ):
                print(f"  - [{kind}] {source} - {location}")
            print()
        except Exception as e:
            print("\nSomething went wrong:", str(e)[:200], "\n")
except (KeyboardInterrupt, EOFError):
    print("\nBye!")