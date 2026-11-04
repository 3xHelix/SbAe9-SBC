"""SBX profiles: a full set of effect and EQ settings, applied in one go.

"Default" is what the driver (and Windows) start with. Gaming, Movie and
Music are starting points in the spirit of the Creative app's stock
profiles; users can save their own on top.
"""

import copy

from . import card as C

FLAT = [0] * 11


def _p(name, art, author, fx, sv_mode="Normal", eq_on=False, eq_preset="Flat", eq=None):
    return {"name": name, "art": art, "author": author, "builtin": True,
            "fx": {k: list(v) for k, v in fx.items()}, "sv_mode": sv_mode,
            "eq_on": eq_on, "eq_preset": eq_preset, "eq": list(eq or FLAT)}


# Driver's preset tables (0.1 dB -> dB), used to label/draw presets exactly.
HW_EQ_PRESETS = {
    "Flat": FLAT,
    "Rock": [0, 0, 0, 2, 1, 0, 3, 1, -1, 3, 3],
    "Concert": [0, 0, 0, 0, 0, 0, 0, 0, -1, 3, -5],
    "Night": [0, 0, 0, 0, 0, 0, 0, 0, -1, 3, -5],
    "Acoustic": [0, 0, 0, 2, 0, 0, 2.5, 2, 2, 2, 3],
    "Classical": [0, 0, 0, 1.5, 2, 1, 3, 1, 0, 3, 3],
    "Country": [0, 0, 0, 0, 0, 2, 2.5, 2.5, 2, 3, 3],
    "Dance": [0, 0, 0, 1, 1.5, 0.5, 1.5, 2, 1, 2.5, 2.5],
    "Hip Hop": [0, 0, 0, 2, 2.5, 1.5, 2.5, 0, -2.5, -1, -1.5],
    "Jazz": [0, 0, 0, 0, 2.5, 2.5, 3, 1, 1, 3, 3],
    "Pop": [-1, 1.7, 2.6, 2.1, 2.7, 0.7, 3.4, 1.2, 5.6, 6, 5.2],
    "R&B": [0, 0, 0, 0, -1.5, 2.5, 1.5, 2, 0, 2, 1],
    "Vocal": [0, 0, 0, -1.5, -0.5, 3, 3, 3, 0, 0, 1],
    "Gaming": [0, 0, 0, 3, -2, 0, 3, 0, 0, 3, 2],
    "Cinema": [0, 0, 0, 0, 0, 2, 3, 0, 0, 1, 1],
    "Project CARS": FLAT, "Racing": FLAT, "Rocket League": FLAT, "RPG": FLAT,
    "Stadium": [0, 3.9, 5.7, 4.3, 3, 3.6, 3.5, 3.3, 4, 6, 6.8],
}

BUILTIN = [
    _p("Default", "default", "The Sound Blaster Team",
       {"Surround": (True, 67), "Crystalizer": (True, 65), "Bass": (False, 50),
        "Smart Volume": (True, 74), "Dialog Plus": (False, 50)}),
    _p("Gaming", "gaming", "The Sound Blaster Team",
       {"Surround": (True, 60), "Crystalizer": (True, 50), "Bass": (True, 30),
        "Smart Volume": (True, 50), "Dialog Plus": (False, 50)},
       eq_on=True, eq_preset="Gaming", eq=HW_EQ_PRESETS["Gaming"]),
    _p("Movie", "movie", "The Sound Blaster Team",
       {"Surround": (True, 70), "Crystalizer": (True, 40), "Bass": (True, 55),
        "Smart Volume": (True, 40), "Dialog Plus": (True, 60)},
       eq_on=True, eq_preset="Cinema", eq=HW_EQ_PRESETS["Cinema"]),
    _p("Music", "music", "The Sound Blaster Team",
       {"Surround": (True, 30), "Crystalizer": (True, 55), "Bass": (True, 45),
        "Smart Volume": (False, 50), "Dialog Plus": (False, 50)}),
    _p("Night", "night", "The Sound Blaster Team",
       {"Surround": (True, 40), "Crystalizer": (False, 50), "Bass": (False, 50),
        "Smart Volume": (True, 80), "Dialog Plus": (True, 50)}, sv_mode="Night"),
]


def all_profiles(settings):
    return [copy.deepcopy(p) for p in BUILTIN] + [copy.deepcopy(p) for p in settings["profiles"]]


def find(settings, name):
    for p in all_profiles(settings):
        if p["name"] == name:
            return p
    return None


def eq_equal(a, b):
    """Band lists equal within the driver's whole-dB read-back."""
    return len(a) == len(b) and all(abs(x - y) <= 0.55 for x, y in zip(a, b))


def matches(profile, snap):
    """True when the card's current settings equal the profile."""
    if not profile:
        return False
    for e in C.EFFECTS:
        want = profile["fx"].get(e)
        have = snap["fx"].get(e)
        if want and have and (bool(want[0]) != have[0] or int(want[1]) != have[1]):
            return False
    if profile.get("sv_mode") != snap.get("sv_mode"):
        return False
    if bool(profile.get("eq_on")) != snap.get("eq_on"):
        return False
    if not eq_equal(profile["eq"], snap["eq"]):
        return False
    return True


def save_user(settings, name, snap, art="custom"):
    users = [p for p in settings["profiles"] if p["name"] != name]
    p = {"name": name, "art": art, "author": "Personal", "builtin": False}
    p.update(copy.deepcopy(snap))
    users.append(p)
    settings["profiles"] = users
    return p


def delete_user(settings, name):
    settings["profiles"] = [p for p in settings["profiles"] if p["name"] != name]


def rename_user(settings, old, new):
    users = settings["profiles"]
    for p in users:
        if p["name"] == old:
            p["name"] = new
    settings["profiles"] = users
