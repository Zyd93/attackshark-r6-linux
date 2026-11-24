#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
RULE_DST="/etc/udev/rules.d/60-attackshark-r6.rules"
REMOVE_UDEV=false

if [ "${1:-}" = "--remove-udev" ]; then
    REMOVE_UDEV=true
fi

rm -f "$BIN_DIR/attackshark-r6" "$BIN_DIR/attackshark-r6-cli"
rm -f "$APPS_DIR/attackshark-r6.desktop"
rm -f "$ICON_BASE/256x256/apps/attackshark-r6.png"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

if [ "$REMOVE_UDEV" = true ] && [ -f "$RULE_DST" ]; then
    echo "Removing $RULE_DST (requires root)..."
    if [ "$(id -u)" -eq 0 ]; then
        rm -f "$RULE_DST"
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=hidraw --subsystem-match=usb
        udevadm settle
    elif command -v sudo >/dev/null 2>&1; then
        sudo rm -f "$RULE_DST"
        sudo udevadm control --reload-rules
        sudo udevadm trigger --subsystem-match=hidraw --subsystem-match=usb
        sudo udevadm settle
    elif command -v pkexec >/dev/null 2>&1; then
        pkexec sh -c "rm -f '$RULE_DST' && udevadm control --reload-rules && udevadm trigger --subsystem-match=hidraw --subsystem-match=usb && udevadm settle"
    else
        echo "Please run as root: rm -f $RULE_DST && udevadm control --reload-rules && udevadm trigger"
    fi
elif [ -f "$RULE_DST" ]; then
    echo "Note: $RULE_DST was preserved. Run './uninstall.sh --remove-udev' or:"
    echo "  sudo rm -f $RULE_DST && sudo udevadm control --reload-rules && sudo udevadm trigger"
fi

echo "Uninstalled ATTACK SHARK R6 launchers and desktop entry."
echo "Note: ~/.config/attackshark-r6 was preserved (remove manually if desired)."
