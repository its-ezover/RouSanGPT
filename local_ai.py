"""Managing the local AI (Ollama): status, starting it, choosing and downloading models."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import binaries
from app_paths import LOG_DIR

OLLAMA_URL = "http://127.0.0.1:11434"
INSTALL_URL = "https://ollama.com/download"

# Models that work well with the tutor's tools, smallest first.
MODEL_CHOICES = [
    {"name": "qwen2.5:1.5b", "size_gb": 1.0, "min_ram_gb": 4, "about": "very small and fast, basic answers"},
    {"name": "qwen2.5:3b", "size_gb": 1.9, "min_ram_gb": 8, "about": "small, good for most laptops"},
    {"name": "llama3.2:3b", "size_gb": 2.0, "min_ram_gb": 8, "about": "small alternative from Meta"},
    {"name": "qwen2.5:7b", "size_gb": 4.7, "min_ram_gb": 14, "about": "better answers, needs about 8 GB free"},
    {"name": "qwen2.5:14b", "size_gb": 9.0, "min_ram_gb": 24, "about": "best answers, needs a strong computer"},
]

_started = None          # the "ollama serve" process RouSanGPT started, if any


def _get(path, timeout=1.5):
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def server_version():
    try:
        return _get("/api/version").get("version")
    except Exception:
        return None


def ram_gb():
    """Total memory in GB (None if unknown)."""
    try:
        if sys.platform.startswith("linux"):
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024 / 1024, 1)
        if sys.platform.startswith("win"):
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.ullTotalPhys / 1024 ** 3, 1)
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            return round(int(out.stdout.strip()) / 1024 ** 3, 1)
    except Exception:
        pass
    return None


def recommended_model(ram=None):
    ram = ram if ram is not None else ram_gb()
    if ram is None:
        return "qwen2.5:3b"
    best = MODEL_CHOICES[0]["name"]
    for m in MODEL_CHOICES:
        if ram >= m["min_ram_gb"] and m["name"].startswith("qwen"):
            best = m["name"]
    return best


def _system_service_active():
    """Is Ollama running as a systemd system service (for example Arch's ollama package)?"""
    if not sys.platform.startswith("linux"):
        return False
    try:
        out = subprocess.run(["systemctl", "is-active", "ollama"], capture_output=True,
                             text=True, timeout=3)
        return out.stdout.strip() == "active"
    except Exception:
        return False


def who_runs_it():
    """Which Ollama is answering, and where its models are stored."""
    if server_version() is None:
        return None, ""
    if _started is not None and _started.poll() is None:
        return "app", os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")
    if sys.platform.startswith("win"):
        return "windows-app", os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")
    if _system_service_active():
        place = "/var/lib/ollama" if Path("/var/lib/ollama").exists() else "/usr/share/ollama/.ollama"
        return "system", place
    return "other", os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")


def installed_models():
    try:
        return [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1024 ** 3, 1)}
                for m in _get("/api/tags", timeout=3).get("models", [])]
    except Exception:
        return []


def has_model(models, wanted):
    names = [m["name"] if isinstance(m, dict) else m for m in models]
    return any(n == wanted or n == wanted + ":latest" or n.split(":")[0] == wanted for n in names)


def status(current_model):
    program = binaries.find_tool("ollama")
    version = server_version()
    runner, models_dir = who_runs_it()
    models = installed_models() if version else []
    ram = ram_gb()
    return {
        "installed": program is not None,
        "program": program or "",
        "running": version is not None,
        "version": version or "",
        "runner": runner or "",
        "models_dir": models_dir,
        "models": models,
        "current": current_model,
        "current_ready": has_model(models, current_model),
        "ram_gb": ram,
        "recommended": recommended_model(ram),
        "choices": MODEL_CHOICES,
        "install_url": INSTALL_URL,
    }


def start():
    """Start "ollama serve" only if nothing answers on localhost:11434."""
    global _started
    if server_version() is not None:
        return "Ollama is already running."
    program = binaries.require_tool("ollama")
    log = open(LOG_DIR / "ollama.log", "ab")
    kwargs = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x08000000          # no console window
    else:
        kwargs["start_new_session"] = True
    _started = subprocess.Popen([program, "serve"], **kwargs)
    import time
    for _ in range(40):
        time.sleep(0.25)
        if server_version() is not None:
            return "Ollama started."
        if _started.poll() is not None:
            break
    raise RuntimeError("Ollama did not start. See logs/ollama.log in the data folder.")


def stop_if_started_by_us():
    global _started
    if _started is not None and _started.poll() is None:
        _started.terminate()
        try:
            _started.wait(5)
        except Exception:
            _started.kill()
    _started = None


def pull(model, progress):
    """Download a model, calling progress(text) as it goes."""
    import ollama
    last = -1
    for part in ollama.pull(model, stream=True):
        total = getattr(part, "total", None) or 0
        done = getattr(part, "completed", None) or 0
        state = getattr(part, "status", "") or ""
        if total:
            pct = int(done * 100 / total)
            if pct != last:
                last = pct
                progress(f"{state}: {pct}% ({done / 1024 ** 3:.1f} of {total / 1024 ** 3:.1f} GB)", pct)
        else:
            progress(state, None)
