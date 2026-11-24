#!/usr/bin/env bash
# Remove the RouSanGPT desktop app for this user.
#
#   ./uninstall.sh            remove the app, keep your data (chats, course files, settings)
#   ./uninstall.sh --purge    also delete your data (asks first)
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ROOT="$DATA_HOME/RouSanGPT"
DATA="$ROOT/data"
PURGE=0
case "${1:-}" in
    --purge) PURGE=1 ;;
    "") ;;
    -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 1 ;;
esac

# Close the app if it is running
if [ -f "$DATA/server.json" ]; then
    port="$(sed -n 's/.*"port": *\([0-9]*\).*/\1/p' "$DATA/server.json")"
    if [ -n "$port" ] && curl -s -m 2 "http://127.0.0.1:$port/api/status" 2>/dev/null | grep -q RouSanGPT; then
        echo "Closing RouSanGPT..."
        curl -s -m 5 -X POST "http://127.0.0.1:$port/api/quit" >/dev/null || true
        sleep 3
    fi
fi

rm -f "$HOME/.local/bin/rousangpt"
rm -f "$DATA_HOME/applications/rousangpt.desktop"
for d in "$DATA_HOME"/icons/hicolor/*/apps; do rm -f "$d/rousangpt.png"; done
rm -rf "$ROOT/app" "$ROOT/app.new" "$ROOT/venv"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA_HOME/applications" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$DATA_HOME/icons/hicolor" 2>/dev/null || true
echo "RouSanGPT was removed from this computer."

if [ "$PURGE" = 1 ]; then
    if [ -d "$DATA" ]; then
        read -r -p "Also DELETE your data in $DATA (chats, course files, settings, API key)? [y/N] " answer
        if [[ "$answer" =~ ^[Yy] ]]; then
            rm -rf "$ROOT"
            echo "Your data was deleted."
        else
            echo "Your data was kept in $DATA"
        fi
    fi
elif [ -d "$DATA" ]; then
    echo "Your data was kept in $DATA (use --purge to delete it)."
fi
