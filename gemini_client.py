"""One place that makes Gemini clients, using the current API key.

The modules keep a module-level `client` as before, but it is a small stand-in that
builds the real client on first use and rebuilds it when the key changes in Settings.
"""
import threading
import time

import httpx
from google import genai
from google.genai import types

import settings

TEST_MODEL = "gemini-3.1-flash-lite"   # a light model, used only to test a key


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


# ---- Telling "Google is busy" apart from "this key is wrong" ----

BUSY_WAITS = (2, 4, 8)       # seconds to wait before each retry when Google is busy


def _code(e):
    """The HTTP status code of a Gemini error (503, 429, ...), or None."""
    code = getattr(e, "code", None)
    return code if isinstance(code, int) else None


def is_busy(e):
    """True for temporary problems on Google's side: overloaded (503 and other 5xx),
    too many requests (429) or a request that took too long (timeout)."""
    code = _code(e)
    if code is not None and (code == 429 or code >= 500):
        return True
    if isinstance(e, (TimeoutError, httpx.TimeoutException)):
        return True
    text = str(e).lower()
    return "unavailable" in text or "timed out" in text or "deadline" in text


def is_bad_key(e):
    """True when Google says the key itself is wrong (400 "API key not valid", 401, 403)."""
    code = _code(e)
    text = str(e).lower()
    if code in (401, 403):
        return True
    return "api key not valid" in text or "api_key_invalid" in text \
        or "permission_denied" in text or "unauthenticated" in text


def with_retries(call, what="Gemini request", on_retry=None):
    """Run call(). If Google is busy, wait 2, 4, then 8 seconds and try again (up to 3
    more times). Other errors, and the last busy error, are raised as they are.
    on_retry(attempt, wait) is called before each wait, for example to tell the user."""
    for attempt, wait in enumerate(BUSY_WAITS + (None,), start=1):
        try:
            return call()
        except Exception as e:
            if wait is None or not is_busy(e):
                raise
            print(f"  ({what}: Google is busy, retry {attempt} of {len(BUSY_WAITS)} "
                  f"in {wait}s. Details: {e!r})", flush=True)
            if on_retry:
                on_retry(attempt, wait)
            time.sleep(wait)


KEY_OK = "ok"            # the key works
KEY_BUSY = "busy"        # Google was too busy to test it (the key is probably fine)
KEY_BAD = "bad"          # Google says the key is wrong
KEY_ERROR = "error"      # something else went wrong (for example no internet)


def test_key(key):
    """Try a key with one tiny request. Returns (result, message), where result is
    KEY_OK, KEY_BUSY, KEY_BAD or KEY_ERROR. The message is meant for the user; the
    full error is printed to the console."""
    key = (key or "").strip()
    if len(key) < 20:
        return KEY_BAD, "That does not look like a Gemini API key."
    client = _make(key, 15000)
    try:
        with_retries(lambda: client.models.generate_content(
            model=TEST_MODEL, contents="Reply with the single word OK.",
            config=types.GenerateContentConfig(max_output_tokens=5)), what="key test")
        return KEY_OK, "The key works."
    except Exception as e:
        print(f"  (key test failed: {e!r})", flush=True)
        if is_bad_key(e):
            return KEY_BAD, "This API key isn't valid. Please check it and try again."
        if is_busy(e):
            return KEY_BUSY, ("Google's servers are busy right now. Your key was saved but "
                              "couldn't be tested yet. It should work once things calm down.")
        return KEY_ERROR, ("Could not reach Google to test the key. Check your internet "
                           "connection and try again.")
