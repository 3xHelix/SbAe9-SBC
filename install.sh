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
Actions=ToggleDirect;ToggleOutput;ToggleSbx;

[Desktop Action ToggleDirect]
Name=Toggle Direct Mode / DSP
Exec=$BIN/sbae9-sbc ctl direct toggle --notify

[Desktop Action ToggleOutput]
Name=Toggle Speakers / Headphones
Exec=$BIN/sbae9-sbc ctl output toggle --notify

[Desktop Action ToggleSbx]
Name=Toggle SBX
Exec=$BIN/sbae9-sbc ctl sbx toggle --notify
DESK
update-desktop-database "$APPS" 2>/dev/null || true

# KDE global shortcuts: the actions above, no keys by default (System
# Settings > Keyboard > Shortcuts > Sound Blaster Command)
if command -v kpackagetool6 >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/share/kglobalaccel"
    ln -sf "$APPS/sbae9-sbc.desktop" "$HOME/.local/share/kglobalaccel/sbae9-sbc.desktop"
    # tell the running shortcut service now (it reads the folder at login)
    if command -v gdbus >/dev/null 2>&1; then
        for a in "_launch|Sound Blaster Command" "ToggleDirect|Toggle Direct Mode / DSP" \
                 "ToggleOutput|Toggle Speakers / Headphones" "ToggleSbx|Toggle SBX"; do
            gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
                --method org.kde.KGlobalAccel.doRegister \
                "['sbae9-sbc.desktop', '${a%%|*}', 'Sound Blaster Command', '${a#*|}']" \
                >/dev/null 2>&1 || true
        done
    fi
fi

# the GNOME Shell extension ("Sound Blaster AE-9" in the top bar), if GNOME is here
GNOME=""
UUID="sbae9-sbc@3xhelix.github.io"
if command -v gnome-shell >/dev/null 2>&1; then
    EXT="$HOME/.local/share/gnome-shell/extensions/$UUID"
    rm -rf "$EXT"
    mkdir -p "$EXT"
    cp -r "$HERE/gnome-extension/$UUID"/. "$EXT/"
    rm -f "$EXT/schemas/gschemas.compiled"
    glib-compile-schemas "$EXT/schemas"         # its settings (rates, quanta, shortcuts)
    GNOME=1
fi

# the KDE Plasma panel widget ("Sound Blaster AE-9"), if Plasma 6 is here
WIDGET=""
if command -v kpackagetool6 >/dev/null 2>&1; then
    if kpackagetool6 -t Plasma/Applet --upgrade "$HERE/plasmoid" >/dev/null 2>&1 ||
       kpackagetool6 -t Plasma/Applet --install "$HERE/plasmoid" >/dev/null 2>&1; then
        WIDGET=1
    fi
fi
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
echo "Installed $(cat "$APP/BUILD") to $APP."
echo "Launch 'Sound Blaster Command' from the menu or run: sbae9-sbc"
[ -n "$GNOME" ] && echo "GNOME extension: turn on 'Sound Blaster AE-9' in the Extensions app" \
    "(after a first install or an update, log out and back in) or run: gnome-extensions enable $UUID"
[ -n "$WIDGET" ] && echo "Panel widget: right-click the panel > Add Widgets > 'Sound Blaster AE-9'" \
    "(after an update, it reloads at the next login or: plasmashell --replace &)"
true
