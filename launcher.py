"""RouSanGPT desktop app: starts the server and opens the app window.

    rousangpt                 (installed: ~/.local/bin/rousangpt)
    python launcher.py        (from the repo: uses the repo folder for data)

Options:
    --data-dir D  where to keep the data (same as ROUSANGPT_DATA_DIR; used by the
                  Windows shortcut, which cannot set environment variables)
    --no-window   start only the server (it still stops by itself, see server.Lifecycle)
    --browser X   force a window type: chromium, firefox, webview or default
    --console     print messages to the terminal instead of the log file
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

# --data-dir must be applied before app_paths is imported (it reads the variable once)
for _i, _arg in enumerate(sys.argv):
    if _arg == "--data-dir" and _i + 1 < len(sys.argv):
        os.environ["ROUSANGPT_DATA_DIR"] = sys.argv[_i + 1]
    elif _arg.startswith("--data-dir="):
        os.environ["ROUSANGPT_DATA_DIR"] = _arg.split("=", 1)[1]

from app_paths import DATA_DIR, LOG_DIR, ensure_dirs  # noqa: E402

APP_NAME = "RouSanGPT"
HOST = "127.0.0.1"
DEFAULT_PORT = 47860
SERVER_FILE = DATA_DIR / "server.json"
LOCK_FILE = DATA_DIR / "launcher.lock"
LOG_FILE = LOG_DIR / "rousangpt.log"
WINDOW_SIZE = (1220, 840)

CHROMIUM_BROWSERS = ["chromium", "chromium-browser", "google-chrome-stable", "google-chrome",
                     "brave", "brave-browser", "microsoft-edge-stable", "microsoft-edge",
                     "vivaldi-stable", "vivaldi"]
FIREFOX_BROWSERS = ["firefox", "firefox-esr", "librewolf"]
WINDOWS = sys.platform.startswith("win")
# Requests to our own server go straight to it, never through a system proxy
# (Windows proxy settings would otherwise apply to 127.0.0.1 too)
_local = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Where browsers live on Windows (they are usually not on PATH)
_WIN_BROWSERS = {
    "chromium": [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
                 r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                 r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                 r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                 r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
                 r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
                 r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
                 r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe",
                 r"%LOCALAPPDATA%\Chromium\Application\chrome.exe"],
    "firefox": [r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
                r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"],
}


def find_browser(kind):
    """(name, path) of the first browser of this kind, or (None, None)."""
    names = CHROMIUM_BROWSERS if kind == "chromium" else FIREFOX_BROWSERS
    for name in names:
        exe = shutil.which(name)
        if exe:
            return name, exe
    if WINDOWS:
        for place in _WIN_BROWSERS[kind]:
            exe = os.path.expandvars(place)
            if os.path.isfile(exe):
                return Path(exe).stem, exe
    return None, None


# ---------- Logging ----------

def start_logging():
    """Send all output to DATA_DIR/logs/rousangpt.log (the app has no terminal)."""
    ensure_dirs()
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 2_000_000:
        LOG_FILE.replace(LOG_FILE.with_suffix(".log.1"))
    log = open(LOG_FILE, "a", buffering=1, encoding="utf-8", errors="replace")
    sys.stdout = sys.stderr = log
    print(f"\n===== {APP_NAME} starting {time.strftime('%Y-%m-%d %H:%M:%S')} "
          f"(data: {DATA_DIR}) =====", flush=True)


def notify(text):
    if shutil.which("notify-send"):
        subprocess.Popen(["notify-send", "-a", APP_NAME, "-i", "rousangpt", "-t", "4000", APP_NAME, text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- One server at a time ----------

class InstanceLock:
    """Stops two launchers from starting two servers at the same moment."""

    def __enter__(self):
        self.f = open(LOCK_FILE, "a+")
        if WINDOWS:
            import msvcrt
            for _ in range(600):                       # wait up to a minute
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
        else:
            import fcntl
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def release(self):
        if self.f:
            try:
                if WINDOWS:
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f, fcntl.LOCK_UN)
            except OSError:
                pass
            self.f.close()
            self.f = None

    def __exit__(self, *exc):
        self.release()


def running_server():
    """The address of a RouSanGPT server that is already running, or None."""
    try:
        info = json.loads(SERVER_FILE.read_text())
        url = f"http://{HOST}:{int(info['port'])}"
        with _local.open(url + "/api/status", timeout=3) as r:
            if json.loads(r.read().decode()).get("app") == APP_NAME:
                return url
    except Exception:
        pass
    return None


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":            # like uvicorn: a port that is only closing counts as free
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def choose_port():
    """Keep the same port as last time when possible: the browser remembers settings
    (theme, last chat, microphone permission) per address."""
    wanted = []
    try:
        wanted.append(int(json.loads(SERVER_FILE.read_text())["port"]))
    except Exception:
        pass
    wanted += [DEFAULT_PORT, DEFAULT_PORT + 1, DEFAULT_PORT + 2]
    for port in wanted:
        if port_is_free(port):
            return port
    with socket.socket() as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


# ---------- The window ----------

def _firefox_profile():
    """A separate Firefox profile that looks like an app: no tabs, no address bar."""
    profile = DATA_DIR / "firefox-profile"
    (profile / "chrome").mkdir(parents=True, exist_ok=True)
    prefs = {
        "browser.shell.checkDefaultBrowser": False,
        "browser.startup.homepage_override.mstone": "ignore",
        "startup.homepage_welcome_url": "",
        "startup.homepage_welcome_url.additional": "",
        "browser.aboutwelcome.enabled": False,
        "trailhead.firstrun.didSeeAboutWelcome": True,
        "datareporting.policy.dataSubmissionEnabled": False,
        "datareporting.healthreport.uploadEnabled": False,
        "toolkit.telemetry.reportingpolicy.firstRun": False,
        "toolkit.legacyUserProfileCustomizations.stylesheets": True,
        "browser.tabs.warnOnClose": False,
        "browser.warnOnQuit": False,
        "browser.sessionstore.resume_from_crash": False,
        "browser.startup.page": 0,
        "browser.tabs.inTitlebar": 0,
        "browser.toolbars.bookmarks.visibility": "never",
        "browser.translations.automaticallyPopup": False,
        "extensions.pocket.enabled": False,
        # This profile only ever shows the local RouSanGPT page (web links open in the
        # normal browser), so the microphone can be allowed without a prompt.
        "permissions.default.microphone": 1,
    }
    lines = [f'user_pref("{k}", {json.dumps(v)});' for k, v in prefs.items()]
    (profile / "user.js").write_text("\n".join(lines) + "\n")
    (profile / "chrome" / "userChrome.css").write_text(
        "#TabsToolbar, #nav-bar, #PersonalToolbar, #sidebar-main, #sidebar-box "
        "{ visibility: collapse !important; }\n")
    return profile


def processes_using(marker):
    """Process ids whose command line contains `marker` (psutil, or /proc on Linux)."""
    found = []
    try:
        import psutil
        for p in psutil.process_iter(["pid", "cmdline"]):
            try:
                if marker in " ".join(p.info["cmdline"] or []):
                    found.append(p.info["pid"])
            except (psutil.Error, TypeError):
                pass
        return [pid for pid in found if pid != os.getpid()]
    except ImportError:
        pass
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            if marker in (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore"):
                found.append(int(entry.name))
        except OSError:
            pass
    return [pid for pid in found if pid != os.getpid()]


def open_window(url, kind=None):
    """Open the app window. Returns (kind, process) - process is None when we cannot
    follow the window (then the server relies on the page's heartbeat)."""
    w, h = WINDOW_SIZE
    if kind in (None, "chromium"):
        name, exe = find_browser("chromium")
        if exe:
            print(f"  (window: {name} app mode)", flush=True)
            proc = subprocess.Popen(
                [exe, f"--app={url}", f"--user-data-dir={DATA_DIR / 'browser-profile'}",
                 f"--class={APP_NAME}", f"--window-size={w},{h}", "--no-first-run",
                 "--no-default-browser-check"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return "chromium", (proc, str(DATA_DIR / "browser-profile"))
    if kind in (None, "firefox"):
        name, exe = find_browser("firefox")
        if exe:
            print(f"  (window: {name} with its own app profile)", flush=True)
            env = dict(os.environ, MOZ_APP_REMOTINGNAME=APP_NAME)
            window_class = [] if WINDOWS else ["--class", APP_NAME, "--name", APP_NAME]
            proc = subprocess.Popen(
                [exe, "--profile", str(_firefox_profile())] + window_class + ["--new-window", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                start_new_session=True)
            return "firefox", (proc, str(DATA_DIR / "firefox-profile"))
    if kind in (None, "webview"):
        import importlib.util
        if importlib.util.find_spec("webview") is not None:      # pywebview, optional
            print("  (window: pywebview)", flush=True)
            return "webview", None
    print("  (window: the default browser)", flush=True)
    import webbrowser
    webbrowser.open(url)
    return "default", None


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} desktop app")
    parser.add_argument("--data-dir", help="data folder (already applied above)")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webview", "default"])
    parser.add_argument("--console", action="store_true", help="print to the terminal, not the log")
    args = parser.parse_args()

    if not args.console:
        start_logging()
    ensure_dirs()

    lock = InstanceLock().__enter__()
    url = running_server()
    if url:                                     # already running: just show it
        lock.release()
        print(f"  (already running at {url})", flush=True)
        if not args.no_window:
            open_window(url, args.browser)
        return

    notify("Starting... the window opens in a few seconds.")
    port = choose_port()
    url = f"http://{HOST}:{port}"

    import uvicorn

    import server
    config = uvicorn.Config(server.app, host=HOST, port=port, log_level="warning")
    uv = uvicorn.Server(config)
    web_thread = threading.Thread(target=uv.run, daemon=True, name="uvicorn")
    web_thread.start()

    for _ in range(200):                        # wait until the server answers
        time.sleep(0.1)
        if not web_thread.is_alive():
            lock.release()
            print("  (the server could not start)", flush=True)
            notify("Could not start. See the log in " + str(LOG_FILE))
            sys.exit(1)
        try:
            with _local.open(url + "/api/status", timeout=2):
                break
        except Exception:
            pass

    SERVER_FILE.write_text(json.dumps({"port": port, "pid": os.getpid()}))
    lock.release()
    print(f"  (server running at {url})", flush=True)
    def warm_up():
        # load the search model while the window opens (questions wait for it)
        try:
            server.agent.warm_up()
        except Exception as e:
            print(f"  (warm-up failed: {e})", flush=True)
    threading.Thread(target=warm_up, daemon=True, name="warm-up").start()

    stopped = threading.Event()

    def on_shutdown():
        uv.should_exit = True
        stopped.set()

    server.lifecycle.enable(on_shutdown)

    kind, window = ("none", None) if args.no_window else open_window(url, args.browser)
    proc, marker = window if window else (None, None)

    if kind == "webview":
        import webview
        webview.create_window(APP_NAME, url, width=WINDOW_SIZE[0], height=WINDOW_SIZE[1])
        webview.start()                          # returns when the window is closed
        server.lifecycle.shutdown("the window was closed")
    elif proc is not None:
        opened = time.time()

        def follow_window():
            # Follow every process that uses the app's browser profile: browsers may
            # restart themselves (Firefox does with a new profile) or hand the window
            # to a copy that is already running.
            seen = False
            while True:
                alive = proc.poll() is None or bool(processes_using(marker))
                if alive:
                    seen = True
                elif seen or time.time() - opened > 20:
                    break
                time.sleep(1)
            if not seen:
                print("  (cannot follow the window; the page heartbeat decides)", flush=True)
                return
            server.lifecycle.shutdown("the window was closed")

        threading.Thread(target=follow_window, daemon=True).start()

    stopped.wait()
    if proc is not None and proc.poll() is None:
        proc.terminate()                         # Quit was chosen: close the window too
    web_thread.join(timeout=8)
    try:
        if json.loads(SERVER_FILE.read_text()).get("pid") == os.getpid():
            SERVER_FILE.unlink()
    except Exception:
        pass
    print(f"===== {APP_NAME} stopped {time.strftime('%H:%M:%S')} =====", flush=True)
    sys.stdout.flush()
    os._exit(0)                                  # do not wait for background jobs (videos)


if __name__ == "__main__":
    main()
