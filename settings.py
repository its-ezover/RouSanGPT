"""The app's settings, kept in DATA_DIR/settings.json (never in the repo).

The Gemini API key is read from settings.json first, then from .env (dev mode).
"""
import json
import os
import threading

from dotenv import load_dotenv

from app_paths import CODE_DIR, SETTINGS_FILE

load_dotenv(CODE_DIR / ".env")        # dev mode: the repo's .env, if there is one

DEFAULTS = {
    "gemini_api_key": "",
    "local_model": "",
    "default_language": "auto",       # auto, english or arabic
    "default_backend": "auto",        # auto, gemini or local
}
_lock = threading.Lock()


def load():
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError):
        pass
    return data


def save(changes):
    """Update some settings and write the file (readable only by this user)."""
    with _lock:
        data = load()
        data.update(changes)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(SETTINGS_FILE)
    return data


def get(key):
    return load().get(key, DEFAULTS.get(key))


def api_key():
    return (get("gemini_api_key") or os.getenv("GEMINI_API_KEY") or "").strip()


def key_source():
    """Where the key comes from: 'settings', 'env' or ''."""
    if (get("gemini_api_key") or "").strip():
        return "settings"
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return "env"
    return ""


def local_model():
    return (get("local_model") or os.getenv("LOCAL_MODEL") or "qwen2.5:7b").strip()
