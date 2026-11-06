#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Installs Sound Blaster Command for the current user: a copy of the app in
# ~/.local/share/sbae9-sbc, the `sbae9-sbc` command, its icon and a menu
# entry. It's a copy, like SbAe9-AudioMon's: the menu app is always the build
# you last installed, never a half-edited working tree. Re-run after each
# tested change to update it.
set -e
HERE="$(dirname "$(readlink -f "$0")")"
APP="$HOME/.local/share/sbae9-sbc"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"
mkdir -p "$BIN" "$APPS"

# the app: launcher, package and icons, replacing the previous copy
rm -rf "$APP.new"
mkdir -p "$APP.new"
install -m 755 "$HERE/sbae9-sbc" "$APP.new/sbae9-sbc"
cp -r "$HERE/sbcommand" "$HERE/sbae9kit" "$HERE/appicon" "$APP.new/"
find "$APP.new" -name __pycache__ -prune -exec rm -rf {} +
git -C "$HERE" describe --always --dirty > "$APP.new/BUILD" 2>/dev/null || echo build > "$APP.new/BUILD"
rm -rf "$APP"
mv "$APP.new" "$APP"
ln -sf "$APP/sbae9-sbc" "$BIN/sbae9-sbc"

# app icon, one PNG per size (made by SbAe9-Kit's tools/make_icons.py)
for png in "$HERE"/appicon/sbae9-sbc-*.png; do
    size=$(basename "$png" .png); size=${size##*-}
    install -D -m 644 "$png" "$ICONS/${size}x${size}/apps/sbae9-sbc.png"
done
rm -f "$ICONS/scalable/apps/sbae9-sbc.svg"     # the old icon, so it doesn't win
touch "$ICONS"

cat > "$APPS/sbae9-sbc.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Sound Blaster Command
GenericName=AE-9 Control Panel
Comment=SBX effects, EQ, outputs and mixer for the Creative Sound Blaster AE-9
Exec=$BIN/sbae9-sbc
Icon=sbae9-sbc
Terminal=false
Categories=AudioVideo;Audio;Mixer;Settings;
Keywords=Creative;Sound Blaster;AE-9;SBX;Equalizer;
StartupWMClass=sbae9-sbc
DESK
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
echo "Installed $(cat "$APP/BUILD") to $APP."
echo "Launch 'Sound Blaster Command' from the menu or run: sbae9-sbc"
