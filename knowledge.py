"""The course materials database: which files the tutor knows, and searching them.

Shared by the tutor (agent.py), quizzes and videos, so that they all see the same
files, including the ones added in the app while it runs.
"""
import threading

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app_paths import DATA_DIR

ANSWER_KEY_WORDS = ["solution", "answer"]            # hidden from the tutor
HOMEWORK_WORDS = ["hw", "homework", "question"]      # labelled as homework
GROUPS = ("slides", "homework", "other", "answers")

# The model that turns text into numbers for searching (Chroma's default, the same
# one the database was made with). One copy for the whole app.
_embedder = DefaultEmbeddingFunction()
db = chromadb.PersistentClient(path=str(DATA_DIR / "course_db"))
collection = db.get_or_create_collection("course", embedding_function=_embedder)


def classify(name):
    n = name.lower()
    if n.endswith((".pptx", ".ppt")):
        return "slides"
    if any(w in n for w in ANSWER_KEY_WORDS):
        return "answers"
    if any(w in n for w in HOMEWORK_WORDS):
        return "homework"
    return "other"


SOURCES = {g: [] for g in GROUPS}        # group -> file names
PIECES = {}                              # file name -> number of pieces
_sources_lock = threading.Lock()


def refresh_sources():
    """Re-read which files are in the database (after adding or removing materials)."""
    counts = {}
    for m in collection.get(include=["metadatas"])["metadatas"]:
        counts[m["source"]] = counts.get(m["source"], 0) + 1
    groups = {g: [] for g in GROUPS}
    for name in sorted(counts):
        groups[classify(name)].append(name)
    with _sources_lock:
        SOURCES.clear()
        SOURCES.update(groups)
        PIECES.clear()
        PIECES.update(counts)


def materials():
    """The files in the database: [{name, group, pieces}], sorted by name."""
    with _sources_lock:
        return [{"name": n, "group": classify(n), "pieces": c} for n, c in sorted(PIECES.items())]


refresh_sources()

# ---- The search model ----
# It is loaded (and downloaded on the very first start) on first use. The lock makes
# sure two threads never load or download it at the same time.
_model_lock = threading.Lock()
_model_ready = False


def warm_up():
    """Load the search model now, so the first question is fast. Safe to call often."""
    global _model_ready
    if _model_ready:
        return
    with _model_lock:
        if not _model_ready:
            _embedder(["warm up"])
            _model_ready = True


def search(text, groups):
    """Search several groups of files with one question.
    groups: [(label, file names, how many pieces)]. Returns [(label, text, metadata)].
    The question is turned into numbers once and reused for every group."""
    groups = [(label, files, n) for label, files, n in groups if files and n > 0]
    if not groups:
        return []
    warm_up()
    embedding = _embedder([text])
    found = []
    for label, files, n in groups:
        r = collection.query(query_embeddings=embedding, n_results=n,
                             where={"source": {"$in": list(files)}})
        found.extend((label, doc, meta) for doc, meta in zip(r["documents"][0], r["metadatas"][0]))
    return found
