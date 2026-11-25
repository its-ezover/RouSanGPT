"""Checks of the app's inner parts, without a browser and without Gemini.

    python tests/test_backend.py

Runs on an empty, temporary data folder (your own data is never touched).
Exit code 0 means every check passed.
"""
import atexit
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

DATA = tempfile.mkdtemp(prefix="rousangpt-test-")
atexit.register(shutil.rmtree, DATA, ignore_errors=True)
os.environ["ROUSANGPT_DATA_DIR"] = DATA
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ingest_lib  # noqa: E402
import knowledge  # noqa: E402
import quiz  # noqa: E402
import server  # noqa: E402

problems = []


def check(what, ok):
    print(("PASS  " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        problems.append(what)


# ---- every chat has its own quiz ----
def play(state, answer, results):
    quiz.use_state(state)            # what agent.Session.ask does before each answer
    results.append(quiz.check_quiz_answer(1, answer))


chat_a, chat_b = quiz.new_state(), quiz.new_state()
chat_a["questions"] = [{"type": "multiple_choice", "question": "Layer of TCP?", "packet_capture": "",
                        "options": ["Transport", "Network"], "correct_answer": "Transport", "explanation": ""}]
chat_b["questions"] = [{"type": "fill_in_the_blank", "question": "Port of DNS?", "packet_capture": "",
                        "options": [], "correct_answer": "53", "explanation": ""}]
results_a, results_b = [], []
threads = [threading.Thread(target=play, args=(chat_a, "A", results_a)),
           threading.Thread(target=play, args=(chat_b, "53", results_b))]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("chat A checks its own quiz", results_a[0].get("correct") is True)
check("chat B checks its own quiz", results_b[0].get("correct") is True)
check("each chat keeps its own score", chat_a["answered"] == {1: True} and chat_b["answered"] == {1: True})
outside = quiz.check_quiz_answer(1, "A")
check("outside a chat there is no quiz from a chat", "error" in outside)

# ---- the counter of files being added is safe with many threads ----
counter = server.Counter()


def bump():
    for _ in range(20000):
        counter.add(1)
        counter.add(-1)


workers = [threading.Thread(target=bump) for _ in range(8)]
for w in workers:
    w.start()
for w in workers:
    w.join()
check("the counter is back at 0 after 320000 changes from 8 threads", counter.value == 0 and not counter)

# ---- course search: one embedding for all groups gives the same pieces ----
notes = Path(DATA) / "notes.txt"
notes.write_text("\n".join([
    "TCP opens a connection with a three-way handshake: SYN, SYN-ACK, ACK.",
    "UDP sends datagrams without a connection.", "", "",
    "DNS translates host names into IP addresses.",
    "A resolver asks root, TLD and authoritative servers.", "", "",
    "Dijkstra's algorithm finds the shortest paths from one router.",
    "OSPF uses it to build forwarding tables.", "", ""]), encoding="utf-8")
pieces = ingest_lib.add_file(knowledge.collection, notes)
knowledge.refresh_sources()
check(f"a text file is split into pieces ({pieces})", pieces == 3)
check("the materials list knows the file", knowledge.materials() == [
    {"name": "notes.txt", "group": "other", "pieces": 3}])
found = knowledge.search("How does name resolution work?", [("BOOK/OTHER", knowledge.SOURCES["other"], 2)])
old_way = knowledge.collection.query(query_texts=["How does name resolution work?"], n_results=2,
                                     where={"source": {"$in": ["notes.txt"]}})
check("the search finds the DNS piece first", "DNS" in found[0][1])
check("the search gives the same pieces as asking Chroma directly",
      [doc for _, doc, _ in found] == old_way["documents"][0])
check("groups without files are skipped", knowledge.search("x", [("SLIDES", [], 3)]) == [])

# ---- the key test: "Google is busy" is not "the key is wrong" ----
import gemini_client  # noqa: E402
from google.genai import errors  # noqa: E402

BUSY = errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE",
                                          "message": "This model is currently experiencing high demand."}})
BAD = errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                         "message": "API key not valid. Please pass a valid API key."}})
DENIED = errors.ClientError(403, {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "no"}})
GONE = errors.ClientError(404, {"error": {"code": 404, "status": "NOT_FOUND", "message": "model retired"}})
QUOTA = errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "slow down"}})


class FakeModels:
    def __init__(self, answers):
        self.answers, self.calls, self.models = list(answers), 0, []

    def generate_content(self, **kwargs):
        self.calls += 1
        self.models.append(kwargs["model"])
        answer = self.answers.pop(0) if self.answers else "OK"
        if isinstance(answer, Exception):
            raise answer
        return answer


waits, TESTED = [], gemini_client.TEST_MODELS


def try_key(answers):
    """Test a key while Google answers with `answers` (errors or "OK"), without waiting."""
    fake = FakeModels(answers)
    real_make, real_sleep = gemini_client._make, gemini_client.time.sleep
    gemini_client._make = lambda key, timeout: type("C", (), {"models": fake})()
    gemini_client.time.sleep = waits.append
    try:
        return gemini_client.test_key("AIza" + "x" * 35), fake.calls
    finally:
        gemini_client._make, gemini_client.time.sleep = real_make, real_sleep


(outcome, _), calls = try_key(["OK"])
check("a working key is OK", outcome == gemini_client.KEY_OK and calls == 1)
waits.clear()
(outcome, message), calls = try_key([BUSY, BUSY, "OK"])
check("a busy model: the next model is tried at once, without waiting",
      outcome == gemini_client.KEY_OK and calls == 3 and waits == [] and TESTED[2] in message)
waits.clear()
(outcome, _), calls = try_key([BUSY] * len(TESTED) + ["OK"])
check("every model busy: wait 2 s, then go around again",
      outcome == gemini_client.KEY_OK and waits == [2] and calls == len(TESTED) + 1)
waits.clear()
(outcome, message), calls = try_key([BUSY] * 100)
check("still busy after 3 rounds: 'busy' (the key gets saved)",
      outcome == gemini_client.KEY_BUSY and calls == 4 * len(TESTED) and waits == [2, 4, 8]
      and "saved" in message)
check("the user never sees the raw error", "{" not in message and "503" not in message)
(outcome, _), _ = try_key([QUOTA] * 100)
check("429 too many requests counts as busy", outcome == gemini_client.KEY_BUSY)
(outcome, message), calls = try_key([BAD])
check("an invalid key is 'bad' at once, without retries",
      outcome == gemini_client.KEY_BAD and calls == 1 and message.startswith("This API key isn't valid"))
(outcome, _), _ = try_key([DENIED])
check("403 permission denied is 'bad'", outcome == gemini_client.KEY_BAD)
(outcome, _), _ = try_key([BUSY, BAD])
check("busy, then invalid: 'bad'", outcome == gemini_client.KEY_BAD)
(outcome, _), _ = try_key([GONE, "OK"])
check("a retired model (404) is skipped", outcome == gemini_client.KEY_OK)
waits.clear()
(outcome, _), _ = try_key([GONE] * 100)
check("every model gone (404): an error, without waiting",
      outcome == gemini_client.KEY_ERROR and waits == [])
check("the key test starts with the light model",
      TESTED[0] == "gemini-3.1-flash-lite" and len(set(TESTED)) == len(TESTED))
check("the chat has 6 different models",
      len(gemini_client.MODELS) == 6 and len(set(gemini_client.MODELS)) == 6)

# the /api/settings/key endpoint saves a key when Google was only busy
import settings  # noqa: E402
real_test = gemini_client.test_key
for outcome, saved in [(gemini_client.KEY_BUSY, True), (gemini_client.KEY_BAD, False)]:
    settings.save({"gemini_api_key": ""})
    gemini_client.test_key = lambda key, o=outcome: (o, "message")
    try:
        server.set_key(server.KeyRequest(key="AIza" + "y" * 35))
    except server.HTTPException:
        pass
    check(f"the key is {'saved' if saved else 'not saved'} when the test says '{outcome}'",
          (settings.get("gemini_api_key") == "AIza" + "y" * 35) == saved)
gemini_client.test_key = real_test
settings.save({"gemini_api_key": ""})


# ---- a chat switches model, then waits and retries, when Gemini is busy ----
class FakeChat:
    def __init__(self, model, answers):
        self.model, self.answers = model, answers

    def send_message(self, prompt):
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return (self.model, answer)

    def get_history(self):
        return []


agent = server.agent


def chat_with(answers):
    """Ask a chat while Gemini answers with `answers`. Returns (reply or error, notes, waits)."""
    session, shown, slept = agent.Session(), [], []
    session.chat = FakeChat(agent.MODELS[0], answers)
    session.on_status = shown.append
    real_make, real_sleep = agent.make_chat, gemini_client.time.sleep
    agent.make_chat = lambda model, history=None: FakeChat(model, answers)
    gemini_client.time.sleep = slept.append
    try:
        return session.send("hi"), shown, slept, session
    except RuntimeError as e:
        return str(e), shown, slept, session
    finally:
        agent.make_chat, gemini_client.time.sleep = real_make, real_sleep


reply, shown, slept, session = chat_with([BUSY, BUSY, "the answer"])
check("a busy chat switches to the next models and stays there",
      reply == (agent.MODELS[2], "the answer") and session.model_index == 2 and slept == [])
check("the page is told 'Gemini is busy, trying another model', then the note is cleared",
      shown[0].startswith("Gemini is busy, trying another model") and shown[-1] == "")
reply, shown, slept, _ = chat_with([BUSY] * len(agent.MODELS) + ["the answer"])
check("every model busy: the chat waits 2 s and retries",
      reply[1] == "the answer" and slept == [2] and any("retrying (1 of 3)" in m for m in shown))
reply, shown, slept, _ = chat_with([BUSY] * 100)
check("busy for too long: a friendly message, not the raw error",
      reply.startswith("Gemini is busy") and "{" not in reply and slept == [2, 4, 8])
reply, _, _, _ = chat_with([BAD])
check("a wrong key in a chat says so", "API key is not valid" in reply)

print("\nproblems:", problems if problems else "none")
sys.exit(1 if problems else 0)
