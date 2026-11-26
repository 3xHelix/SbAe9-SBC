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
    "encoder": "off",        # optical out service: "off", "fx" (effects loop), "ac3" or "dts"
    "encoder_last": "ac3",   # the encoder last picked, for Playback > Digital's choice
    "dsp_louder_seen": False,  # driver 0.12.11's "DSP mode is 6 dB louder" warning was shown
    "hp_plug_notice": True,  # Playback's "headphones plugged in, but it plays on Speakers" notice
    "card": None,            # the card managed with two in the machine: its ALSA id ("AE9"); None = the first
}
# (and "cards", written only once another card has a setting: per-card
# settings of cards other than the AE-9, by ALSA id: {"AE7": {"rate_mode": ...}})

# Kept per card: a rate or encoder picked for one card means nothing on another
# (the AE-7 plays no 176.4 kHz and has no optical out). The AE-9 ("AE9", the
# card every settings file before this was written for) keeps them where they
# always were, at the top level, so its file and behaviour don't change; any
# other card (an AE-7, a second AE-9 "AE9_1") gets its own entry in "cards",
# starting from the defaults.
PER_CARD = ("rate_mode", "quantum", "encoder", "encoder_last")
TOP_LEVEL_CARD = "AE9"


def _card_key():
    """The managed card's ALSA id (imported late: card.py pulls in Qt)."""
    from . import card
    return card.card_id()


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

    def _card_slot(self, key, make=False):
        """The managed card's own settings dict for a per-card key; None:
        the top level (the AE-9, or a key that isn't per card). An empty
        dict for a card with nothing stored yet (made with `make`)."""
        if key not in PER_CARD:
            return None
        cid = _card_key()
        if not cid or cid == TOP_LEVEL_CARD:
            return None
        cards = self.data.get("cards")
        if not isinstance(cards, dict):
            if not make:
                return {}
            cards = self.data["cards"] = {}
        slot = cards.get(cid)
        if not isinstance(slot, dict):
            if not make:
                return {}
            slot = cards[cid] = {}
        return slot

    def __getitem__(self, key):
        self._load()
        slot = self._card_slot(key)
        if slot is not None:
            return slot.get(key, DEFAULTS.get(key))
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self._load()
        slot = self._card_slot(key, make=True)
        if slot is not None:
            slot[key] = value
        else:
            self.data[key] = value
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
        self._mtime = self._stamp()
