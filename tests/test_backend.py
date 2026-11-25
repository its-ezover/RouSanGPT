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

print("\nproblems:", problems if problems else "none")
sys.exit(1 if problems else 0)
