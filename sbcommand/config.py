# SPDX-License-Identifier: GPL-2.0-only
"""App settings and user profiles, stored as JSON in ~/.config/sbae9-sbc/."""

import copy
import json
import os

APP_ID = "sbae9-sbc"


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, APP_ID)
    os.makedirs(d, exist_ok=True)
    return d


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    d = os.path.join(base, APP_ID)
    os.makedirs(d, exist_ok=True)
    return d


def autostart_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "autostart", APP_ID + ".desktop")


def autostart_enabled():
    return os.path.exists(autostart_path())


def set_autostart(on):
    """Start the app at login (an XDG autostart entry), or stop doing so."""
    path = autostart_path()
    if not on:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    launcher = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), APP_ID)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Sound Blaster Command\n"
                "Comment=AE-9 control panel\n"
                f"Exec={launcher}\n"
                f"Icon={APP_ID}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n")


DEFAULTS = {
    "active_profile": "Default",
    "profiles": [],          # user SBX profiles (built-ins live in profiles.py)
    "eq_presets": {},        # name -> [pre-gain, 10 bands] in dB
    "restore_on_start": False,  # the driver + alsa-state already keep settings
    "restore_rate_on_start": False, # on: bring back the last rate you picked at start
    "rate_mode": None,       # None = leave PipeWire alone, 0 = follow source, else Hz
    "page": 0,
    "tabs": {},              # page title -> last tab shown
    "palette": "command",    # see theme.PALETTES
    "frameless": True,       # the app's own title bar instead of the desktop's frame
    "ui_scale": 100,         # percent, see theme.SCALES
    "glass": False,          # see-through backgrounds on any palette
    "phantom_confirm": "popup",  # turning phantom power on: "popup" warning or "two_click"
    "quantum": 0,            # PipeWire quantum picked (0 = PipeWire decides); high rates raise it
    "glass_opacity": 70,     # percent, see theme.GLASS_RANGE
    "encoder": "off",        # optical encoder: "off", "ac3" or "dts" (see encoder.py)
}


class Settings:
    """settings.json. The panel widget (sbae9-sbc ctl) writes it too, so a
    change on disk is read back before the next read or write."""

    def __init__(self):
        self.path = os.path.join(config_dir(), "settings.json")
        self.data = copy.deepcopy(DEFAULTS)
        self._mtime = None
        self._load()

    def _stamp(self):
        try:
            st = os.stat(self.path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def _load(self):
        stamp = self._stamp()
        if stamp == self._mtime:
            return
        self._mtime = stamp
        try:
            with open(self.path) as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, json.JSONDecodeError):
            pass

    def __getitem__(self, key):
        self._load()
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self._load()
        self.data[key] = value
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
        self._mtime = self._stamp()
