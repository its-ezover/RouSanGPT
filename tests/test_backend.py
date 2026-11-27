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

# ---- cryptography tools: the worked examples from the course slides ----
import cipher_tools as ct  # noqa: E402
import finite_field_tools as ff  # noqa: E402
import number_theory_tools as nt  # noqa: E402

r = nt.extended_euclid(1759, 550)
check("extended Euclid: 1759x + 550y = 1 gives x = -111, y = 355",
      (r["gcd"], r["x"], r["y"]) == (1, -111, 355))
check("the inverse of 11 in Z26 is 19", nt.modular_inverse(11, 26)["inverse"] == 19)
check("6 has no inverse mod 26", nt.modular_inverse(6, 26)["has_inverse"] is False)
check("20^62 mod 77 = 15 and 8^-1 mod 17 = 15",
      nt.modular_power(20, 62, 77)["result"] == 15 and nt.modular_power(8, -1, 17)["result"] == 15)
r = nt.miller_rabin_test(1729, [671])
check("Miller-Rabin: 1729 with a = 671 is composite (k = 6, q = 27)",
      (r["k"], r["q"]) == (6, 27) and r["conclusion"].startswith("composite"))
check("phi(21) = 12", nt.euler_totient(21)["phi"] == 12)
check("CRT: x = 2 mod 3, 3 mod 5, 2 mod 7 gives 23", nt.chinese_remainder([2, 3, 2], [3, 5, 7])["x"] == 23)
check("big numbers given as text stay exact: gcd = 67",
      nt.gcd_euclid("521262320887169", "15068555596066421")["gcd"] == 67)
r = nt.extended_euclid("521262320887169", "15068555596066421")
check("big results go back as text, and a*x + b*y = 67",
      isinstance(r["y"], (int, str)) and 521262320887169 * int(r["x"]) + 15068555596066421 * int(r["y"]) == 67
      and all(not isinstance(v, int) or abs(v) < 2 ** 53 for row in r["table"] for v in row.values()))
check("bad input gives an error message, not a crash", "error" in nt.modular_power("abc", 2, 5))
r = ff.polynomial_arithmetic("x^3 + x^2 + 2", "x^2 - x + 1", "divide", 0)
check("polynomial division: quotient x + 2, remainder x", (r["quotient"], r["remainder"]) == ("x + 2", "x"))
check("x^3 + x + 1 is irreducible over GF(2)", ff.polynomial_arithmetic("x^3+x+1", "", "factor")["irreducible"])
r = ff.gf2n_arithmetic("x^5 + x^2 + x", "x^7 + x^4 + x^3 + x^2 + x", "multiply")
check("GF(2^8) product is x^5 + x^3 + x^2 + x + 1", r["result"]["polynomial"] == "x^5 + x^3 + x^2 + x + 1")
check("in GF(2^8) the inverse of x^5 is x^5 + x^4 + x^3 + x",
      ff.gf2n_arithmetic("x5", "", "inverse")["inverse"]["polynomial"] == "x^5 + x^4 + x^3 + x")
check("Caesar: meet me after the toga party", ct.caesar_cipher("meet me after the toga party", 3)["result"]
      == "PHHW PH DIWHU WKH WRJD SDUWB")
check("Vigenere with key deceptive", ct.vigenere_cipher("we are discovered save yourself", "deceptive")["result"]
      == "ZICVTWQNGRZGVTWAVZHCQYGLMGJ")
check("Playfair with key monarchy", ct.playfair_cipher("move forward", "monarchy")["result"] == "ON UF PH NZ RM BZ")
check("Hill cipher: paymoremoney", ct.hill_cipher("paymoremoney", "17 17 5 21 18 21 2 2 19")["result"]
      == "RRLMWBKASPDH")
check("Hill decryption gives the plaintext back",
      ct.hill_cipher("RRLMWBKASPDH", "17 17 5 21 18 21 2 2 19", "decrypt")["result"] == "paymoremoney")
check("rail fence of depth 2", ct.rail_fence_cipher("meet me after the toga party", 2)["result"]
      == "MEMATRHTGPRYETEFETEOAAT")
check("row transposition with key 4312567",
      ct.row_transposition_cipher("attack postponed until two am", "4312567", padding="xyz")["result"]
      == "TTNAAPTMTSUOAODWCOIXKNLYPETZ")
check("Caesar brute force finds key 3",
      ct.caesar_cipher("PHHW PH DIWHU WKH WRJD SDUWB", mode="brute_force")["most_likely"][0]["key"] == 3)
check("crypto lecture PDFs count as slides, homework PDFs do not",
      knowledge.classify("Ch02-Number Theory.pdf") == "slides" and knowledge.classify("Ch3 HW.pdf") == "homework"
      and knowledge.classify("Ch1_suggested_solution.pdf") == "answers")

# ---- fixes from the code review of the first version ----
import extra_tools  # noqa: E402
import more_tools  # noqa: E402
import tools  # noqa: E402

check("an answer key saved as slides stays hidden (Ch3_solutions.pptx, HW2_answers.ppt)",
      knowledge.classify("Ch3_solutions.pptx") == "answers" and knowledge.classify("HW2_answers.ppt") == "answers"
      and knowledge.classify("Lecture5.pptx") == "slides")
check("'resolution' is not 'solution': DNS_name_resolution.pdf is a book, HW2.pdf is homework",
      knowledge.classify("DNS_name_resolution.pdf") == "other"
      and knowledge.classify("ARP_address_resolution.pdf") == "other" and knowledge.classify("HW2.pdf") == "homework")
check("checksum: '1010' is binary, hex needs digits other than 0/1 or 0x",
      extra_tools._to_int("1010", 16) == 0b1010 and extra_tools._to_int("0x1010", 16) == 0x1010)
r = extra_tools.internet_checksum_calculate(["01011100", "01100101"])
check("checksum: the textbook's 8-bit example works", (r["word_size_bits"], r["checksum"]) == (8, "00111110"))
r = extra_tools.internet_checksum_calculate(["0110011001100000", "0101010101010101", "1000111100001100"])
check("checksum: Kurose's 16-bit example still works", r["checksum"] == "1011010100111101")
r = tools.split_into_subnets("10.0.0.0/24", 128)
check("128 subnets: 64 listed, and the reply says it is cut short",
      r["truncated"] and r["total_subnets"] == 128 and len(r["subnets"]) == 64)
check("2^24 subnets do not fill the memory", tools.split_into_subnets("10.0.0.0/8", 2 ** 24)["truncated"])
check("a link rate of 0 is an error message, not a crash", "error" in tools.delay_calculation(1000, 0, 10))
check("Dijkstra keeps the cheaper of two equal links",
      more_tools.dijkstra_shortest_paths(["A-B:1", "A-B:5"], "A")["shortest_distances"]["B"] == 1)
check("Dijkstra accepts names with hyphens",
      more_tools.dijkstra_shortest_paths(["R-1->R-2:3"], "R-1")["shortest_distances"]["R-2"] == 3)
check("the calculator refuses answers with millions of digits",
      "error" in extra_tools.calculator("((10**999)**1000)**1000") and "error" in extra_tools.calculator("(9**999)**999"))

# ---- every tool can be given to the AI (one broken tool breaks every chat) ----
import collections  # noqa: E402

import formula_tools  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types as genai_types  # noqa: E402
from ollama._utils import convert_function_to_tool  # noqa: E402


def as_ai_tools(tools):
    """Build the Gemini and the Ollama description of every tool; list what fails."""
    fake = genai.Client(api_key="test-key-not-used")
    broken = []
    for f in tools:
        try:
            genai_types.FunctionDeclaration.from_callable(client=fake, callable=f)
            convert_function_to_tool(f)
        except Exception as e:
            broken.append(f"{f.__name__}: {e}")
    return broken


# a formula tool made by a student, and one saved before a built-in tool took its name
FORMULA = {"description": "Queuing delay from the queue length and the link rate.",
           "params": [{"name": "packets", "description": "packets in the queue", "example": 3},
                      {"name": "L", "description": "bits per packet", "example": 8000},
                      {"name": "R", "description": "link rate in bits per second", "example": 1e6}],
           "formula": "packets * L / R", "unit": "s"}
formula_tools.add_spec({**FORMULA, "name": "queue_delay"}, set())
formula_tools.add_spec({**FORMULA, "name": "caesar_cipher"}, set())   # as if saved before today
tools_now = agent.all_tools()
names = [f.__name__ for f in tools_now]
check("every tool has a description for the AI",
      all(f.__doc__ and f.__doc__.strip() for f in tools_now))
check("no two tools share a name, even with an old formula tool called caesar_cipher",
      not [n for n, c in collections.Counter(names).items() if c > 1])
check("the built-in caesar_cipher wins, and the student's other formula tool still works",
      dict(zip(names, tools_now))["caesar_cipher"].__module__ == "cipher_tools")
check("the student's formula tool is offered to the AI", "queue_delay" in names)
broken = as_ai_tools(tools_now)
check(f"every tool converts for Gemini and for Ollama {broken}", not broken)
listing = server.list_tools()
check("the Tools panel marks the clashing formula tool as turned off",
      [t["clash"] for t in listing["custom"] if t["name"] == "caesar_cipher"] == [True]
      and [t["clash"] for t in listing["custom"] if t["name"] == "queue_delay"] == [False])
check("the Tools panel still lists the built-in caesar_cipher",
      any(t["name"] == "caesar_cipher" for t in listing["builtin"]))
try:
    server.add_tool(server.FormulaToolRequest(**FORMULA, name="caesar_cipher", replace=True))
    saved_over_builtin = True
except HTTPException:
    saved_over_builtin = False
check("a formula tool cannot be saved under a built-in tool's name, even when editing",
      not saved_over_builtin)
formula_tools.delete_spec("caesar_cipher")
formula_tools.delete_spec("queue_delay")
agent.reload_tools()

# ---- course pictures (explainers): every kind draws, with the slides' numbers ----
import explainers  # noqa: E402,F401
import video_tools  # noqa: E402
import visual_kit  # noqa: E402

broken = []
for kind_name in visual_kit.KINDS:
    try:
        visual = visual_kit.build(kind_name, [])
        for step in [None] + list(range(-1, visual["steps"])):     # the picture and every animation step
            img, d = visual_kit.canvas(visual["title"], visual_kit.DARK if step is not None else visual_kit.LIGHT)
            visual["draw"](d, visual_kit.DARK if step is not None else visual_kit.LIGHT, step)
    except Exception as e:
        broken.append(f"{kind_name}: {e}")
check(f"all {len(visual_kit.KINDS)} explainer kinds draw, as a picture and step by step {broken}", not broken)


def shown(kind_name, inputs=()):
    return visual_kit.build(kind_name, list(inputs))["result"]


check("explainer: Go-Back-N resends 2, 3, 4, 5 and Selective Repeat only 2 (the slides' example)",
      "4 retransmissions" in shown("go_back_n") and "1 retransmissions" in shown("selective_repeat"))
check("explainer: stop-and-wait U = 0.000267 with L = 8000, R = 1 Gbps, RTT = 30 ms",
      "U = 0.000267" in shown("stop_and_wait"))
check("explainer: RTT estimation follows the solutions manual (106.72 ms, DevRTT 14.57)",
      "106.72 + 4 x 14.57" in shown("tcp_rtt"))
check("explainer: TCP Reno goes to 9 after 3 dup ACKs at cwnd 12, Tahoe to 1 then 2, 4, 6",
      "reno: 1, 2, 4, 8, 9, 10, 11, 12, 9" in shown("tcp_congestion")
      and "tahoe: 1, 2, 4, 8, 9, 10, 11, 12, 1, 2, 4, 6" in shown("tcp_congestion"))
check("explainer: packet vs circuit switching gives 10 users and 0.0004",
      "supports 10 users" in shown("packet_vs_circuit") and "0.000424" in shown("packet_vs_circuit"))
check("explainer: Dijkstra least costs from u: v 2, w 3, x 1, y 2, z 4",
      shown("dijkstra_table").endswith("v 2, w 3, x 1, y 2, z 4"))
check("explainer: 200.23.24.170 goes to link 1 (the /24 beats the /21)", "link 1" in shown("longest_prefix_match"))
check("explainer: CRC of 101110 with G = 1001 is 011", shown("crc").startswith("R = 011"))
check("explainer: ciphers and number theory give the slides' answers",
      shown("playfair") == "ON UF PH NZ RM BZ" and shown("vigenere") == "ZICVTWQNGRZGVTWAVZHCQYGLMGJ"
      and "x = -111,  y = 355" in shown("extended_euclid") and "= 19" in shown("modular_inverse"))
check("explainer: the student's own numbers are used", "17^-1 mod 43 = 38" in shown("modular_inverse", ["17", "43"]))
check("explainer: a wrong kind is an error message, not a crash",
      "error" in explainers.draw_explainer("no_such_kind", []))
scene = video_tools.Scene(title="t", bullets=[], narration="n", diagram_type="anim_explainer",
                          explainer_kind="go_back_n", explainer_inputs=[], sequence_participants=[],
                          sequence_messages=[], header_fields=[], topology_dot="", flow_nodes=[], flow_packets=0,
                          window_total=0, window_size=0, graph_edges=[], graph_source="")
check("videos can use the explainers, built step by step", video_tools.make_scene_animation(scene) is not None)

# ---- device icons ----
import device_icons  # noqa: E402
import diagram_tools  # noqa: E402

blank = [k for k in device_icons.ICONS for t in ("light", "dark")
         if device_icons.icon_image(k, 64, t).getbbox() is None]
check(f"all {len(device_icons.ICONS)} icons draw in both themes {blank}", not blank)
expected = {"PC1": "pc", "Client": "pc", "Router 1": "router", "R2": "router", "Switch": "switch",
            "DNS server": "dns_server", "local DNS": "dns_server", "Web server": "web_server",
            "Proxy": "server", "Internet": "cloud", "Alice": "person", "Trudy": "attacker",
            "AP": "access_point", "Laptop": "laptop", "KDC": "ca", "Firewall": "firewall"}
wrong = {n: device_icons.icon_kind(n) for n, k in expected.items() if device_icons.icon_kind(n) != k}
check(f"device names get the right icons {wrong}", not wrong)
routing = diagram_tools._with_icons('graph { u -- v [label="2"]; v -- x [label="1"]; }')
check("topology: a link's cost label stays on the link (nodes keep their names u, v, x)",
      routing.count("IMG") == 3 and ">v<" in routing and ">x<" in routing and ">2<" not in routing)
check("topology: a flowchart keeps its boxes",
      "IMG" not in diagram_tools._with_icons('digraph { node [shape=box]; A [label="Encrypt message"]; A -> B; }'))
check("read-aloud skips emojis but keeps Arabic",
      server.clean_for_speech("💡 Tip ✅ شو ⚠️") == "Tip شو")

# ---- Settings > Look: Classic (flat) or Frutiger Aero ----
import animation_tools  # noqa: E402

check("the look starts as Classic", server.get_settings()["look"] == "classic" and not settings.aero())
try:
    server.change_settings(server.SettingsRequest(look="shiny"))
    refused = False
except HTTPException:
    refused = True
check("an unknown look is refused", refused)
flat_icon = device_icons.icon_image("router", 64, "light")
flat_frame = animation_tools.new_frame("t")[0].getpixel((640, 360))
server.change_settings(server.SettingsRequest(look="aero"))
check("choosing Frutiger Aero takes effect at once", settings.aero() and server.get_settings()["look"] == "aero")
check("Aero icons differ from the flat ones", device_icons.icon_image("router", 64, "light").tobytes() != flat_icon.tobytes())
check("Aero animation frames have the sky, not the flat background",
      animation_tools.new_frame("t")[0].getpixel((640, 360)) != flat_frame)
broken = []
for kind_name in visual_kit.KINDS:
    try:
        visual = visual_kit.build(kind_name, [])
        img, d = visual_kit.canvas(visual["title"], visual_kit.LIGHT)
        visual["draw"](d, visual_kit.LIGHT, None)
    except Exception as e:
        broken.append(f"{kind_name}: {e}")
check(f"every explainer kind also draws in the Aero look {broken}", not broken)
slide = Path(DATA) / "slide.png"
video_tools.draw_slide("Title", ["one", "two"], 1, 2, slide)
aero_slide = slide.read_bytes()
server.change_settings(server.SettingsRequest(look="classic"))
video_tools.draw_slide("Title", ["one", "two"], 1, 2, slide)
check("video slides follow the look", slide.read_bytes() != aero_slide and not settings.aero())

# ---- Cybercore and Y2K: every part follows the look ----
import diagram_tools as dt2  # noqa: E402
import looks  # noqa: E402

drawn = {}
for look_name in ("cybercore", "y2k"):
    server.change_settings(server.SettingsRequest(look=look_name))
    broken = []
    for kind_name in visual_kit.KINDS:
        try:
            visual = visual_kit.build(kind_name, [])
            th = visual_kit.DARK if looks.still_theme() == "dark" else visual_kit.LIGHT
            img, d = visual_kit.canvas(visual["title"], th)
            visual["draw"](d, th, None)
            for step in range(-1, min(visual["steps"], 4)):
                img, d = visual_kit.canvas(visual["title"], visual_kit.DARK)
                visual["draw"](d, visual_kit.DARK, step)
        except Exception as e:
            broken.append(f"{kind_name}: {e}")
    check(f"every explainer kind draws in the {look_name} look {broken}", not broken)
    video_tools.draw_slide("n - 1 = 2^k * q", ["a^(q*2^j) mod n"], 1, 2, slide)
    drawn[look_name] = (slide.read_bytes(), device_icons.icon_image("switch", 64, "dark").tobytes(),
                        animation_tools.new_frame("t")[0].getpixel((640, 600)), dt2.draw_sequence_diagram(
                            "t", ["Alice", "Bob"], ["Alice -> Bob: hi"], "seq_" + look_name).get("saved_to"))
check("Cybercore and Y2K slides, icons and frames differ",
      drawn["cybercore"][0] != drawn["y2k"][0] and drawn["cybercore"][1] != drawn["y2k"][1]
      and drawn["cybercore"][2] != drawn["y2k"][2])
check("the sequence diagrams are drawn in both looks", all(v[3] for v in drawn.values()))
check("the Graphviz colours follow the look", "-Gbgcolor=#05010d" in looks.graphviz_args("cybercore")
      and looks.graphviz_args("classic") == [])
server.change_settings(server.SettingsRequest(look="classic"))
check("back to Classic", not settings.aero() and settings.look() == "classic")

# ---- math shown as math ----
import rich_text  # noqa: E402

check("pictures: 2^6 * 27 becomes 2, a raised 6, then · 27",
      rich_text.parts("2^6 * 27") == [("2", 0), ("6", 1), (" · 27", 0)])
check("pictures: a nested power a^(q*2^j) and indices x_(i-2)",
      rich_text.parts("a^(q*2^j)") == [("a", 0), ("q·2ʲ", 1)]
      and rich_text.parts("x_(i-2)") == [("x", 0), ("i-2", -1)])
check("pictures: file names, *italics* and the *** of an address range stay as they are",
      rich_text.parts("Ch1_suggested_solution.pdf") == [("Ch1_suggested_solution.pdf", 0)]
      and rich_text.parts("00010*** ****") == [("00010*** ****", 0)]
      and rich_text.parts("use *this* now") == [("use *this* now", 0)])
check("titles: 2^k * q becomes 2ᵏ · q", rich_text.unicode("n - 1 = 2^k * q") == "n - 1 = 2ᵏ · q")
check("read-aloud says the math", server.clean_for_speech("2^k * q") == "2 to the power k times q")

print("\nproblems:", problems if problems else "none")
sys.exit(1 if problems else 0)
