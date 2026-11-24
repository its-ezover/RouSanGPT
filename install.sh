#!/usr/bin/env bash
# Install (or update) RouSanGPT as a desktop app for this user. No sudo needed.
#
#   ./install.sh                              install or update
#   ./install.sh --import-data <folder>       also copy chats, course database and media
#                                             from an existing RouSanGPT folder
#
# Running it again updates the app and keeps your data.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ROOT="$DATA_HOME/RouSanGPT"
APP="$ROOT/app"
VENV="$ROOT/venv"
DATA="$ROOT/data"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/rousangpt"
DESKTOP_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$DESKTOP_DIR/rousangpt.desktop"
ICON_DIR="$DATA_HOME/icons/hicolor"

IMPORT_FROM=""
while [ $# -gt 0 ]; do
    case "$1" in
        --import-data) IMPORT_FROM="${2:-}"; shift 2 || { echo "--import-data needs a folder"; exit 1; } ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
    esac
done

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; }
MISSING=()

# install commands: name  arch  debian  fedora
hint() {
    echo "      Arch:          sudo pacman -S $2"
    echo "      Debian/Ubuntu: sudo apt install $3"
    echo "      Fedora:        sudo dnf install $4"
}

bold "RouSanGPT installer"
echo "  app:  $APP"
echo "  data: $DATA"
echo

# ---------- 1. System programs ----------
bold "Checking the programs RouSanGPT uses"

PYTHON=""
for p in python3 python; do
    if command -v "$p" >/dev/null && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        PYTHON="$(command -v "$p")"; break
    fi
done
if [ -z "$PYTHON" ]; then
    fail "Python 3.10 or newer is required."
    hint python python python3 python3 python3
    exit 1
fi
ok "Python $("$PYTHON" -c 'import platform; print(platform.python_version())') ($PYTHON)"
if ! "$PYTHON" -c 'import venv, ensurepip' 2>/dev/null; then
    fail "Python's venv module is missing."
    hint venv python python3-venv python3
    exit 1
fi

if command -v ffmpeg >/dev/null; then ok "FFmpeg (videos, animations, voice input)"
else fail "FFmpeg is missing: videos, animations and voice input will not work."; hint ffmpeg ffmpeg ffmpeg ffmpeg; MISSING+=("ffmpeg"); fi

if command -v dot >/dev/null; then ok "Graphviz (network diagrams)"
else fail "Graphviz is missing: topology diagrams will not work."; hint graphviz graphviz graphviz graphviz; MISSING+=("graphviz"); fi

if command -v soffice >/dev/null || command -v libreoffice >/dev/null; then ok "LibreOffice (old .ppt files)"
elif command -v catppt >/dev/null; then ok "catppt (old .ppt files, text only)"
else warn "Optional: LibreOffice or catdoc, only needed to add old .ppt files."; hint "libreoffice-fresh (or catdoc)" "libreoffice-impress (or catdoc)" "libreoffice-impress (or catdoc)"; fi

BROWSER=""
for b in chromium chromium-browser google-chrome-stable google-chrome brave brave-browser microsoft-edge-stable vivaldi-stable; do
    if command -v "$b" >/dev/null; then BROWSER="$b"; break; fi
done
if [ -n "$BROWSER" ]; then ok "App window: $BROWSER (app mode)"
elif command -v firefox >/dev/null; then ok "App window: Firefox (own profile, no tabs)"; warn "Optional: a Chromium-based browser gives the most app-like window."; hint chromium chromium chromium-browser chromium
else warn "No Chromium-based browser or Firefox found: the app opens in your default browser."; hint chromium chromium chromium-browser chromium; fi

if command -v ollama >/dev/null; then ok "Ollama (local model, optional)"
else warn "Optional: Ollama, for answers without the internet. See https://ollama.com/download"; echo "      Arch:          sudo pacman -S ollama"; fi
echo

# ---------- 2. Is the app running? ----------
running_port() {
    [ -f "$DATA/server.json" ] || return 1
    local port
    port="$("$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1]))['port'])" "$DATA/server.json" 2>/dev/null)" || return 1
    curl -s -m 2 "http://127.0.0.1:$port/api/status" 2>/dev/null | grep -q RouSanGPT && echo "$port"
}
if port="$(running_port)"; then
    bold "RouSanGPT is running. Closing it so it can be updated..."
    curl -s -m 5 -X POST "http://127.0.0.1:$port/api/quit" >/dev/null || true
    for _ in $(seq 30); do running_port >/dev/null || break; sleep 1; done
    if running_port >/dev/null; then fail "Please close the RouSanGPT window and run the installer again."; exit 1; fi
fi

# ---------- 3. Copy the program ----------
bold "Installing the program"
mkdir -p "$ROOT" "$DATA"
NEW_APP="$ROOT/app.new"
rm -rf "$NEW_APP"
mkdir -p "$NEW_APP"
for f in "$SRC"/*.py; do
    case "$(basename "$f")" in test_api.py|hello.py|voice_samples.py) continue ;; esac
    cp "$f" "$NEW_APP/"
done
cp -r "$SRC/web" "$SRC/icons" "$NEW_APP/"
cp "$SRC/requirements.txt" "$SRC/README.md" "$SRC/uninstall.sh" "$NEW_APP/"
[ -d "$SRC/bin" ] && cp -r "$SRC/bin" "$NEW_APP/"
rm -rf "$APP"
mv "$NEW_APP" "$APP"
ok "Program copied (your .env, chats and course files are not part of the program)"

# ---------- 4. Python packages ----------
bold "Installing the Python packages (the first time this takes a few minutes)"
if [ -x "$VENV/bin/python" ] && ! "$VENV/bin/python" -c 'import sys' 2>/dev/null; then
    rm -rf "$VENV"            # broken venv (for example after a Python upgrade)
fi
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
if ! "$VENV/bin/python" -m pip install --quiet --upgrade -r "$APP/requirements.txt"; then
    fail "Installing the Python packages failed (see above). Check the internet connection and run ./install.sh again."
    exit 1
fi
ok "Python packages installed"

# ---------- 5. Import existing data ----------
if [ -n "$IMPORT_FROM" ]; then
    bold "Importing data from $IMPORT_FROM"
    IMPORT_FROM="$(cd "$IMPORT_FROM" && pwd)" || { fail "Folder not found"; exit 1; }
    stamp="$(date +%Y%m%d-%H%M%S)"
    for item in course_db chats.db formula_tools.json materials videos animations diagrams quizzes; do
        [ -e "$IMPORT_FROM/$item" ] || continue
        if [ -e "$DATA/$item" ] && [ -n "$(ls -A "$DATA/$item" 2>/dev/null)" ]; then
            mv "$DATA/$item" "$DATA/$item.before-import-$stamp"
            warn "$item already existed; kept the old copy as $item.before-import-$stamp"
        else
            rm -rf "${DATA:?}/$item"
        fi
        cp -a "$IMPORT_FROM/$item" "$DATA/$item"
        ok "Imported $item"
    done
    if [ -t 0 ] && [ -f "$IMPORT_FROM/.env" ] && grep -q '^GEMINI_API_KEY=.' "$IMPORT_FROM/.env" \
       && ! grep -q '"gemini_api_key": *"..' "$DATA/settings.json" 2>/dev/null; then
        read -r -p "  Use the Gemini API key from $IMPORT_FROM/.env in the app? [y/N] " answer
        if [[ "$answer" =~ ^[Yy] ]]; then
            APP_DIR="$APP" "$VENV/bin/python" - "$IMPORT_FROM/.env" "$DATA" <<'PY'
import sys, os
sys.path.insert(0, os.environ.get("APP_DIR", ""))
from dotenv import dotenv_values
key = (dotenv_values(sys.argv[1]).get("GEMINI_API_KEY") or "").strip()
os.environ["ROUSANGPT_DATA_DIR"] = sys.argv[2]
import settings
settings.save({"gemini_api_key": key})
print("  \033[32m✓\033[0m API key saved in the app's settings (only on this computer)")
PY
        fi
    fi
fi

# ---------- 6. Launcher, menu entry, icon ----------
bold "Adding RouSanGPT to the app menu"
mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
cat > "$LAUNCHER" <<EOF
#!/bin/sh
# RouSanGPT desktop app (made by install.sh)
export ROUSANGPT_DATA_DIR="$DATA"
exec "$VENV/bin/python" "$APP/launcher.py" "\$@"
EOF
chmod +x "$LAUNCHER"

for size in 48 64 128 256 512; do
    mkdir -p "$ICON_DIR/${size}x${size}/apps"
    cp "$APP/icons/rousangpt-$size.png" "$ICON_DIR/${size}x${size}/apps/rousangpt.png"
done

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=RouSanGPT
GenericName=Computer Networks Tutor
Comment=AI tutor for Computer Networks: explanations, quizzes, diagrams and videos
Exec="$LAUNCHER"
Icon=rousangpt
Terminal=false
Categories=Education;
Keywords=networks;tutor;AI;TCP;subnetting;
StartupNotify=true
StartupWMClass=RouSanGPT
EOF
chmod +x "$DESKTOP_FILE"

command -v update-desktop-database >/dev/null && update-desktop-database -q "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$ICON_DIR" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
command -v kbuildsycoca5 >/dev/null && kbuildsycoca5 >/dev/null 2>&1 || true
ok "Menu entry: $DESKTOP_FILE"
ok "Command:    $LAUNCHER"

# ---------- Summary ----------
echo
bold "RouSanGPT is installed."
echo "  Open it from your app menu (Education > RouSanGPT)."
case ":$PATH:" in
    *":$BIN_DIR:"*) echo "  Or run: rousangpt" ;;
    *) echo "  Or run: $LAUNCHER   (add $BIN_DIR to your PATH to type just 'rousangpt')" ;;
esac
echo "  Your data is in: $DATA"
if [ ${#MISSING[@]} -gt 0 ]; then
    echo
    warn "Still missing: ${MISSING[*]} (see the install commands above). The rest of the app works."
fi
