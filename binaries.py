"""Finding and using the other programs RouSanGPT needs (ffmpeg, Graphviz, LibreOffice...)."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from app_paths import CODE_DIR

WINDOWS = sys.platform.startswith("win")
MAC = sys.platform == "darwin"

# How to install each program, shown when it is missing
INSTALL_HINTS = {
    "ffmpeg": "Arch: sudo pacman -S ffmpeg | Debian/Ubuntu: sudo apt install ffmpeg | "
              "Fedora: sudo dnf install ffmpeg",
    "dot": "Arch: sudo pacman -S graphviz | Debian/Ubuntu: sudo apt install graphviz | "
           "Fedora: sudo dnf install graphviz",
    "soffice": "Arch: sudo pacman -S libreoffice-fresh | Debian/Ubuntu: sudo apt install "
               "libreoffice-impress | Fedora: sudo dnf install libreoffice-impress",
    "catppt": "Arch: sudo pacman -S catdoc | Debian/Ubuntu: sudo apt install catdoc | "
              "Fedora: sudo dnf install catdoc",
    "ollama": "see https://ollama.com/download (Arch: sudo pacman -S ollama)",
}

NICE_NAMES = {"ffmpeg": "FFmpeg", "dot": "Graphviz", "soffice": "LibreOffice",
              "catppt": "catdoc (catppt)", "ollama": "Ollama"}

# Usual install folders on Windows (used by the Windows build later)
_WINDOWS_PLACES = {
    "dot": [r"C:\Program Files\Graphviz\bin"],
    "soffice": [r"C:\Program Files\LibreOffice\program"],
    "ffmpeg": [r"C:\ffmpeg\bin"],
    "ollama": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama")],
}


class ToolMissing(RuntimeError):
    """A program RouSanGPT needs is not installed."""

    def __init__(self, name):
        self.name = name
        hint = INSTALL_HINTS.get(name, "")
        super().__init__(f"{NICE_NAMES.get(name, name)} is not installed on this computer."
                         + (f" Install it ({hint})." if hint else ""))


def find_tool(name):
    """Full path of a program: first CODE_DIR/bin, then PATH, then the usual places.
    Returns None when it cannot be found."""
    exe = name + ".exe" if WINDOWS else name
    bundled = CODE_DIR / "bin" / exe
    if bundled.is_file():
        return str(bundled)
    found = shutil.which(name)
    if found:
        return found
    if WINDOWS:
        for folder in _WINDOWS_PLACES.get(name, []):
            candidate = Path(folder) / exe
            if candidate.is_file():
                return str(candidate)
    return None


def require_tool(name):
    """Like find_tool, but raises a clear ToolMissing error when it is missing."""
    path = find_tool(name)
    if path is None:
        raise ToolMissing(name)
    return path


def run_ffmpeg(args, timeout=None):
    """Run ffmpeg quietly. Raises RuntimeError with ffmpeg's message on failure."""
    result = subprocess.run([require_tool("ffmpeg"), "-y", "-loglevel", "error"] + list(args),
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + result.stderr[-300:])
    return result


def media_seconds(path, default=10.0):
    """Length of an audio or video file in seconds, read from ffmpeg's output
    (so ffprobe is not needed)."""
    try:
        result = subprocess.run([require_tool("ffmpeg"), "-hide_banner", "-i", str(path)],
                                capture_output=True, text=True, timeout=30)
    except (ToolMissing, subprocess.TimeoutExpired):
        return default
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not m:
        return default
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def open_file(path_or_url):
    """Open a file or web address with the computer's default program."""
    target = str(path_or_url)
    try:
        if WINDOWS:
            os.startfile(target)                      # noqa: S606 (Windows only)
        elif MAC:
            subprocess.Popen(["open", target],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", target],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, AttributeError):
        pass
