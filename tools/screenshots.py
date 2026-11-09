# SPDX-License-Identifier: GPL-2.0-only
"""Render the README screenshots into docs/ (2x, HiDPI).

    python3 tools/screenshots.py [palette] [out-dir]

Uses the test fakes from tests/support.py: a 5.1 setup in DSP mode with the
Default and Gaming profiles. No real card, PipeWire or settings are touched.
"""
import os
import sys

os.environ["QT_SCALE_FACTOR"] = "2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import support as S
from sbcommand import card as C, pages, profiles, theme
from sbcommand.window import Context, MainWindow

palette = sys.argv[1] if len(sys.argv) > 1 else "helix"
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "docs")
S.reset()
theme.apply(palette)
S.app.setStyle("Fusion")
S.app.setStyleSheet(theme.stylesheet())

# a 5.1 setup in DSP mode, playing 48 kHz 5.1
S.PW.set_profile(S.SURROUND)
for p in S.PW.sink["info"]["params"]["Props"]:
    if "channelVolumes" in p:
        p["channelVolumes"] = [0.62 ** 3] * 6
S.PW.stream = (48000, 6)
# a current driver (v0.12.2): 96 kHz recording, its names, optical in and out,
# What U Hear, the rear RCA input, custom headphone slots
S.PARAMS.update({"version": "0.12.2", "surround_96k": "1", "dsp_96k": "Y", "wuh_96k": "Y",
                 "hp_custom": "DT990=Beyerdynamic DT 990 Pro;;;"})
S.PW.set_mic_range(96000)
S.PW.source["info"]["props"]["node.description"] = "AE-9 Head Unit Mic / Aux"
S.PW.capture = (48000, 2)
S.PW.add_optical_in()
S.PW.add_what_u_hear()
S.PW.add_rear_rca()
S.PW.add_optical_out(first=False)

ctx = Context()
m = S.FakeMixer.last
m.add_bool(C.OPTICAL_OUT, True)
m.add_enum(C.CAP_BIT_DEPTH, ["24-bit", "32-bit"])
m.add_bool(C.OPTICAL_MIRROR, False)
m.add_bool(C.HP_VIRT, True)
m.add_bool(C.LINE_VIRT, False)
m.add_bool(C.MIC_MONITOR, False)
for name in (C.VC, C.VC_AEC, C.VC_NR, C.VC_SVM):
    m.add_bool(name, False)
m.add_enum(C.VC_MICEQ, ["Off", "Preset 1 - Reduce Bass, harshness, improve clarity",
                        "Preset DM-1 - Improve vocal and clarity"])
m.add_enum(C.VC_MORPH, ["Neutral", "Male", "Female", "Kid", "Elderly", "Deep Voice", "From Up North",
                        "Unstable", "Emo", "Elf", "Dwarf", "Demon", "Infiltrator", "Brute", "Orc",
                        "Marine", "Chipmunk", "Robot"])
m.add_enum(C.HP_PROFILE, ["Off"] + list(C.HP_KEYS) +
           ["Beyerdynamic DT 990 Pro", "Custom 2", "Custom 3", "Custom 4"], 0)
hp = os.path.join(C.HP_DIRS[0], "creative-ae9", "hp")
os.makedirs(hp, exist_ok=True)
for key in list(C.HP_KEYS.values()) + ["DT990"]:
    open(os.path.join(hp, key + ".bin"), "wb").close()
for name, v in {C.DIRECT: False, C.SBX: True, C.OUTPUT: 0, C.MASTER: 214, C.MASTER_SW: True,
                C.SPEAKER_CFG: 4, C.BIT_DEPTH: 0, C.MIC: 80, "XLR Gain Capture Volume": 1, C.SCOUT: False,
                C.DAC_FILTER: 1}.items():
    m.values[name] = v
ctx.settings.data["palette"] = palette
S.process(20)

def use(profile_name):
    ctx.card.apply(profiles.find(ctx.settings, profile_name))
    ctx.settings.data["active_profile"] = profile_name
    S.process(20)

w = MainWindow(ctx)
w.resize(1180, 760)
w.show()
ctx.pw.refresh()
S.process(50)

def shot(idx, name):
    if isinstance(idx, type):           # a page class: its place in the side bar
        idx = next(i for i in range(w.stack.count()) if isinstance(w.stack.widget(i), idx))
    w.go(idx)
    S.process(150)
    page = w.stack.currentWidget()
    if hasattr(page, "tab_bar"):
        page.show_tab(0, save=False)
    if hasattr(page, "refresh"):
        page.refresh()
    w.refresh()
    S.process(150)
    img = w.grab()
    img.save(os.path.join(out, name + ".png"))
    print(name, img.width(), img.height(), "dpr", img.devicePixelRatio())

use("Default")
shot(0, "screenshot")
use("Gaming")
for idx, name in ((pages.EqPage, "equalizer"), (pages.PlaybackPage, "playback"),
                  (pages.RecordingPage, "recording"), (pages.MixerPage, "mixer")):
    shot(idx, name)
print("saved to", out)
