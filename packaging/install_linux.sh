#!/usr/bin/env bash
# Insomnia Launcher — Linux install script.
#
# Installs the one-file binary built by PyInstaller and its desktop entry so the
# launcher shows up in the application menu and can be started normally.
#
# Usage:
#   ./packaging/build_linux.sh          # first, produces dist/InsomniaLauncher
#   ./packaging/install_linux.sh        # copy binary + .desktop to user dirs
#
# The installer never touches any game data: your library, filters, Steam API
# key and settings live in ~/.local/share/insomnia-launcher and are preserved.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BINARY="$ROOT/dist/InsomniaLauncher"
ICON="$ROOT/ui/assets/icon.png"

if [ ! -x "$BINARY" ]; then
    echo "error: $BINARY not found — run ./packaging/build_linux.sh first" >&2
    exit 1
fi
if [ ! -f "$ICON" ]; then
    echo "error: icon not found: $ICON" >&2
    exit 1
fi

# Per-user install (no sudo needed) is the default.
INSTALL_MODE="${1:-user}"   # "user" or "system"
case "$INSTALL_MODE" in
    user)
        BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
        APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
        ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
        ;;
    system)
        BIN_DIR="/usr/local/bin"
        APP_DIR="/usr/share/applications"
        ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
        ;;
    *)
        echo "error: unknown mode '$INSTALL_MODE' (use 'user' or 'system')" >&2
        exit 1
        ;;
esac

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

echo "Installing binary to $BIN_DIR/insomnia-launcher ..."
install -m 755 "$BINARY" "$BIN_DIR/insomnia-launcher"

echo "Installing icon to $ICON_DIR/insomnia-launcher.png ..."
install -m 644 "$ICON" "$ICON_DIR/insomnia-launcher.png"

DESKTOP_FILE="$APP_DIR/insomnia-launcher.desktop"
echo "Installing desktop entry: $DESKTOP_FILE"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Insomnia Launcher
Comment=Unify and launch all your game libraries
Exec=$BIN_DIR/insomnia-launcher
Icon=insomnia-launcher
Terminal=false
Categories=Game;Utility;
StartupNotify=true
EOF

# Make sure the menu picks it up (ignored gracefully if unavailable).
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Done. Insomnia Launcher is installed."
echo "  Launcher : $BIN_DIR/insomnia-launcher"
echo "  Menu     : $DESKTOP_FILE"
echo
echo "Your library, filters and Steam API key (at ~/.local/share/insomnia-launcher)"
echo "are untouched by upgrades — just re-run this installer after a new build."
