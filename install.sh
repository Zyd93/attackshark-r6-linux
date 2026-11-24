#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULE_SRC="$SCRIPT_DIR/60-attackshark-r6.rules"
RULE_DST="/etc/udev/rules.d/60-attackshark-r6.rules"
OLD_RULE="/etc/udev/rules.d/99-attackshark-r6.rules"
APPS_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

chmod +x "$SCRIPT_DIR/attackshark-r6" "$SCRIPT_DIR/attackshark-r6-cli" "$SCRIPT_DIR/uninstall.sh" 2>/dev/null || \
    chmod +x "$SCRIPT_DIR/attackshark-r6" "$SCRIPT_DIR/attackshark-r6-cli"

echo "Installing user launchers into ~/.local/bin and ~/.local/share/applications..."
mkdir -p "$HOME/.local/bin" "$APPS_DIR" "$ICON_BASE/256x256/apps"
ln -sf "$SCRIPT_DIR/attackshark-r6" "$HOME/.local/bin/attackshark-r6"
ln -sf "$SCRIPT_DIR/attackshark-r6-cli" "$HOME/.local/bin/attackshark-r6-cli"

if [ -f "$SCRIPT_DIR/assets/icon.png" ]; then
    cp "$SCRIPT_DIR/assets/icon.png" "$ICON_BASE/256x256/apps/attackshark-r6.png"
fi

cat > "$APPS_DIR/attackshark-r6.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ATTACK SHARK R6
Comment=Configure ATTACK SHARK R6 Mouse (DPI, Polling Rate, Buttons, Macros)
Exec=$HOME/.local/bin/attackshark-r6
Icon=attackshark-r6
Terminal=false
Categories=Utility;HardwareSettings;Settings;
StartupWMClass=attackshark-r6
EOF

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo "Installing udev rule to $RULE_DST (requires root)..."
if [ "$(id -u)" -eq 0 ]; then
    rm -f "$OLD_RULE"
    install -m 0644 "$RULE_SRC" "$RULE_DST"
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=hidraw --subsystem-match=usb
    udevadm settle
elif command -v sudo >/dev/null 2>&1; then
    sudo rm -f "$OLD_RULE"
    sudo install -m 0644 "$RULE_SRC" "$RULE_DST"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw --subsystem-match=usb
    sudo udevadm settle
elif command -v pkexec >/dev/null 2>&1; then
    pkexec sh -c "rm -f '$OLD_RULE' && install -m 0644 '$RULE_SRC' '$RULE_DST' && udevadm control --reload-rules && udevadm trigger --subsystem-match=hidraw --subsystem-match=usb && udevadm settle"
else
    echo "Please copy $RULE_SRC to $RULE_DST as root and reload udev."
    exit 1
fi

echo "Done! Launch with 'attackshark-r6' or 'attackshark-r6-cli status'."
