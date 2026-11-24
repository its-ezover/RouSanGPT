"""Where RouSanGPT keeps its code and its data.

CODE_DIR: the program files (read-only when installed).
DATA_DIR: everything the app writes (database, chats, settings, media, logs).

In dev mode (python server.py / python chat.py in the repo) both are the repo folder,
so nothing changes. The installed app sets ROUSANGPT_DATA_DIR to a separate folder.
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    CODE_DIR = Path(sys._MEIPASS)                     # packaged (PyInstaller) build
else:
    CODE_DIR = Path(__file__).resolve().parent

# The modules must stay importable after agent.py changes the working folder to DATA_DIR
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

_custom = os.environ.get("ROUSANGPT_DATA_DIR", "").strip()
DATA_DIR = Path(_custom).expanduser().resolve() if _custom else CODE_DIR

# True when running as the installed app (data kept apart from the code)
INSTALLED = DATA_DIR != CODE_DIR

DATA_FOLDERS = ("course_db", "materials", "videos", "animations", "diagrams", "quizzes", "logs")
LOG_DIR = DATA_DIR / "logs"
SETTINGS_FILE = DATA_DIR / "settings.json"
CHATS_DB = DATA_DIR / "chats.db"
FORMULA_TOOLS_FILE = DATA_DIR / "formula_tools.json"


def ensure_dirs():
    """Create the data folders that are missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in DATA_FOLDERS:
        (DATA_DIR / name).mkdir(exist_ok=True)


ensure_dirs()
