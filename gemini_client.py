"""One place that makes Gemini clients, using the current API key.

The modules keep a module-level `client` as before, but it is a small stand-in that
builds the real client on first use and rebuilds it when the key changes in Settings.
"""
import threading

from google import genai
from google.genai import types

import settings

TEST_MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]


class NoApiKey(RuntimeError):
    def __init__(self):
        super().__init__("No Gemini API key yet. Open Settings and add your key "
                         "(free from aistudio.google.com).")


def _make(key, timeout_ms):
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


class LazyClient:
    """Acts like genai.Client (client.models..., client.chats...)."""

    def __init__(self, timeout_ms):
        self._timeout = timeout_ms
        self._key = None
        self._client = None
        self._lock = threading.Lock()

    def real(self):
        key = settings.api_key()
        if not key:
            raise NoApiKey()
        with self._lock:
            if self._client is None or key != self._key:
                self._client = _make(key, self._timeout)
                self._key = key
            return self._client

    def __getattr__(self, name):
        return getattr(self.real(), name)


def key_version():
    """Changes whenever the API key changes (so chats can start a fresh connection)."""
    return settings.api_key()[-8:]


def test_key(key):
    """Try a key with one tiny request. Returns (ok, message)."""
    key = (key or "").strip()
    if len(key) < 20:
        return False, "That does not look like a Gemini API key."
    client = _make(key, 30000)
    last = ""
    for model in TEST_MODELS:
        try:
            client.models.generate_content(
                model=model, contents="Reply with the single word OK.",
                config=types.GenerateContentConfig(max_output_tokens=5))
            return True, f"The key works ({model})."
        except Exception as e:
            last = str(e)
            low = last.lower()
            if "api key not valid" in low or "api_key_invalid" in low or "permission" in low \
                    or "401" in low or "403" in low:
                return False, "Google says this API key is not valid."
    return False, "Could not check the key: " + last[:200]
