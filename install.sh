#!/usr/bin/env bash
# One-click installer for Discord Quest Runner (Linux).
#   Install:    curl -fsSL https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.sh | bash
#   Uninstall:  curl -fsSL .../install.sh | bash -s -- --uninstall      (or run ./install.sh --uninstall)
set -euo pipefail

RAW="https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/discord-quest-runner"
BIN="$HOME/.local/bin/discord-quest-runner"
DESKTOP="$DATA_HOME/applications/discord-quest-runner.desktop"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/discord-quest-runner"

if [ "${1:-}" = "--uninstall" ]; then
  pkill -f "$APP_DIR/quest_runner.py" 2>/dev/null || true
  rm -rf "$APP_DIR" "$BIN" "$DESKTOP" "$CACHE"
  echo "Uninstalled."
  exit 0
fi

command -v python3 >/dev/null || { echo "python3 is required."; exit 1; }
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "tkinter is missing. Install it first:"
  echo "  Arch/CachyOS: sudo pacman -S tk"
  echo "  Debian/Ubuntu: sudo apt install python3-tk"
  echo "  Fedora:        sudo dnf install python3-tkinter"
  exit 1
fi

mkdir -p "$APP_DIR" "$(dirname "$BIN")" "$(dirname "$DESKTOP")"

# Use the local copy when run from a checkout, otherwise download.
SRC="$(dirname "${BASH_SOURCE[0]:-}")"
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$SRC/quest_runner.py" ]; then
  cp "$SRC/quest_runner.py" "$APP_DIR/quest_runner.py"
else
  curl -fsSL "$RAW/quest_runner.py" -o "$APP_DIR/quest_runner.py"
fi
chmod +x "$APP_DIR/quest_runner.py"

printf '#!/bin/sh\nexec python3 "%s/quest_runner.py" "$@"\n' "$APP_DIR" > "$BIN"
chmod +x "$BIN"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Discord Quest Runner
Comment=Pick games and complete Discord quests
Exec=$BIN
Icon=applications-games
Terminal=false
Categories=Utility;Game;
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

echo "Installed. Launch 'Discord Quest Runner' from your app menu, or run: discord-quest-runner"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "(add ~/.local/bin to PATH to use the command)";; esac
