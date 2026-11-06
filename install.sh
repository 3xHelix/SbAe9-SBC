#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Installs a menu entry and a `sbae9-sbc` command for the current user.
# The app runs from this folder; re-run after moving it.
set -e
HERE="$(dirname "$(readlink -f "$0")")"
ICONS=~/.local/share/icons/hicolor
mkdir -p ~/.local/bin ~/.local/share/applications
ln -sf "$HERE/sbae9-sbc" ~/.local/bin/sbae9-sbc
for png in "$HERE"/appicon/sbae9-sbc-*.png; do
    size=$(basename "$png" .png); size=${size##*-}
    mkdir -p "$ICONS/${size}x${size}/apps"
    cp "$png" "$ICONS/${size}x${size}/apps/sbae9-sbc.png"
done
rm -f "$ICONS/scalable/apps/sbae9-sbc.svg"     # the old icon, so it doesn't win
touch "$ICONS"
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
cat > ~/.local/share/applications/sbae9-sbc.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Sound Blaster Command
GenericName=AE-9 Control Panel
Comment=SBX effects, EQ, outputs and mixer for the Creative Sound Blaster AE-9
Exec=$HERE/sbae9-sbc
Icon=sbae9-sbc
Terminal=false
Categories=AudioVideo;Audio;Mixer;Settings;
Keywords=Creative;Sound Blaster;AE-9;SBX;Equalizer;
StartupWMClass=sbae9-sbc
DESK
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Installed. Launch 'Sound Blaster Command' from the menu or run: sbae9-sbc"
