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


DEFAULTS = {
    "active_profile": "Default",
    "profiles": [],          # user SBX profiles (built-ins live in profiles.py)
    "eq_presets": {},        # name -> [pre-gain, 10 bands] in dB
    "restore_on_start": False,  # the driver + alsa-state already keep settings
    "rate_mode": None,       # None = leave PipeWire alone, 0 = follow source, else Hz
    "page": 0,
    "palette": "command",    # see theme.PALETTES
}


class Settings:
    def __init__(self):
        self.path = os.path.join(config_dir(), "settings.json")
        self.data = copy.deepcopy(DEFAULTS)
        try:
            with open(self.path) as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, json.JSONDecodeError):
            pass

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
