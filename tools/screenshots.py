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
from sbcommand import card as C, profiles, theme
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

ctx = Context()
m = S.FakeMixer.last
for name, v in {C.DIRECT: False, C.SBX: True, C.OUTPUT: 0, C.MASTER: 214, C.MASTER_SW: True,
                C.SPEAKER_CFG: 4, C.BIT_DEPTH: 0, C.MIC: 80, C.XLR_GAIN: 1, C.SCOUT: False,
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
    w.go(idx)
    S.process(150)
    page = w.stack.currentWidget()
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
for idx, name in ((1, "equalizer"), (2, "playback"), (3, "recording"), (5, "mixer")):
    shot(idx, name)
print("saved to", out)
