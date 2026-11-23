import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chats.db"
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _lock, closing(_connect()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                extra TEXT NOT NULL DEFAULT '{}',
                created REAL NOT NULL
            );
            """
        )


def _title_from(text):
    one_line = " ".join(text.split())
    if not one_line:
        return "New chat"
    return one_line[:40] + "..." if len(one_line) > 40 else one_line


def create_chat(title="New chat"):
    chat_id = uuid.uuid4().hex
    now = time.time()
    with _lock, closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO chats VALUES (?, ?, ?, ?)", (chat_id, title, now, now))
    return chat_id


def exists(chat_id):
    with _lock, closing(_connect()) as conn:
        return conn.execute("SELECT 1 FROM chats WHERE id = ?", (chat_id,)).fetchone() is not None


def list_chats():
    with _lock, closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, title, updated FROM chats "
            "WHERE id IN (SELECT DISTINCT chat_id FROM messages) "
            "ORDER BY updated DESC").fetchall()
    return [dict(r) for r in rows]


def get_messages(chat_id):
    with _lock, closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT role, text, extra FROM messages WHERE chat_id = ? ORDER BY id",
            (chat_id,)).fetchall()
    messages = []
    for r in rows:
        extra = json.loads(r["extra"] or "{}")
        messages.append({"role": r["role"], "text": r["text"], **extra})
    return messages


def add_exchange(chat_id, user_text, result):
    """Save one question and its answer. Returns the chat's title."""
    now = time.time()
    extra = json.dumps({
        "tools": result.get("tools", []),
        "sources": result.get("sources", []),
        "media": result.get("media", []),
    })
    with _lock, closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, text, extra, created) VALUES (?, 'user', ?, '{}', ?)",
            (chat_id, user_text, now))
        conn.execute(
            "INSERT INTO messages (chat_id, role, text, extra, created) VALUES (?, 'bot', ?, ?, ?)",
            (chat_id, result.get("reply", ""), extra, now + 0.001))
        row = conn.execute("SELECT title FROM chats WHERE id = ?", (chat_id,)).fetchone()
        title = row["title"] if row else "New chat"
        if title == "New chat":                       # name the chat after the first question
            title = _title_from(user_text)
            conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
        conn.execute("UPDATE chats SET updated = ? WHERE id = ?", (now, chat_id))
    return title


def rename_chat(chat_id, title):
    with _lock, closing(_connect()) as conn, conn:
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))


def delete_chat(chat_id):
    with _lock, closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


def history_for_model(chat_id, limit=30):
    """The last messages of a chat, so the tutor remembers it after a restart."""
    messages = get_messages(chat_id)[-limit:]
    while messages and messages[0]["role"] != "user":
        messages = messages[1:]
    return [{"role": "user" if m["role"] == "user" else "model", "text": m["text"]}
            for m in messages]