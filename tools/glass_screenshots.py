# SPDX-License-Identifier: GPL-2.0-only
"""Glass screenshots for the README (docs/glass-*.png), on a real KDE desktop.

    python3 tools/glass_screenshots.py BACKDROP.png [X,Y,W,H]

Shows BACKDROP full screen on one monitor (default 1920,0,1920,1080), puts
the app on top of it with Glass on, lets KDE frost it (through XWayland) and
takes the shot with spectacle: the window plus 100 px of backdrop all round.
Uses the test fakes, so the real card, PipeWire and settings aren't touched.
"""
import os, sys, subprocess
REAL_POPEN = subprocess.Popen
os.environ["QT_QPA_PLATFORM"] = "xcb"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, ROOT + "/tests")
import support as S
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel
from PIL import Image
from sbcommand import card as C, profiles, theme
from sbcommand.window import Context, MainWindow

if len(sys.argv) < 2:
    sys.exit(__doc__)
WALL = sys.argv[1]
MON = tuple(int(v) for v in sys.argv[2].split(",")) if len(sys.argv) > 2 else (1920, 0, 1920, 1080)
SP = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "sbae9-sbc-shots")
os.makedirs(SP, exist_ok=True)
WW, WH, PAD = 1180, 760, 100

S.reset(); theme.apply("helix"); theme.GLASS = True; theme.GLASS_OPACITY = 0.70
S.app.setStyle("Fusion"); S.app.setStyleSheet(theme.stylesheet())
# the README tool's setup: 5.1 in DSP mode, a current driver
S.PW.set_profile(S.SURROUND)
for p in S.PW.sink["info"]["params"]["Props"]:
    if "channelVolumes" in p:
        p["channelVolumes"] = [0.62 ** 3] * 6
S.PW.stream = (48000, 6)
S.PARAMS.update({"version": "0.9.1", "surround_96k": "1"})

# the wallpaper frame, full screen on the centre monitor, behind the app
wall = QLabel(); wall.setWindowFlag(Qt.FramelessWindowHint)
wall.setPixmap(QPixmap(WALL).scaled(MON[2], MON[3])); wall.setGeometry(*MON); wall.show(); S.process(600)

ctx = Context(); m = S.FakeMixer.last
for name, v in {C.DIRECT: False, C.SBX: True, C.OUTPUT: 0, C.MASTER: 214, C.MASTER_SW: True,
                C.SPEAKER_CFG: 4, C.BIT_DEPTH: 0, C.MIC: 80, "XLR Gain Capture Volume": 1, C.SCOUT: False,
                C.DAC_FILTER: 1}.items():
    m.values[name] = v
S.process(20)
x, y = MON[0] + (MON[2] - WW) // 2, MON[1] + (MON[3] - WH) // 2
w = MainWindow(ctx); w.resize(WW, WH); w.move(x, y); w.show(); S.process(800)
w.raise_(); w.activateWindow(); S.process(400)

subprocess.Popen = REAL_POPEN
for idx, prof, name, op in ((0, "Default", "glass-sbx", 0.70), (1, "Gaming", "glass-equalizer", 0.50)):
    theme.GLASS_OPACITY = op; S.app.setStyleSheet(theme.stylesheet()); w.update()
    ctx.card.apply(profiles.find(ctx.settings, prof)); ctx.settings.data["active_profile"] = prof
    w.go(idx); S.process(300); w.stack.currentWidget().refresh(); w.refresh(); S.process(600)
    full = f"{SP}/{name}-full.png"
    if os.path.exists(full):
        os.remove(full)
    p = REAL_POPEN(["spectacle", "-b", "-n", "-f", "-d", "0", "-o", full])
    for _ in range(80):
        S.process(100)
        if p.poll() is not None and os.path.exists(full):
            break
    S.process(300)
    g = w.frameGeometry()
    Image.open(full).crop((g.x() - PAD, g.y() - PAD, g.x() + g.width() + PAD, g.y() + g.height() + PAD)) \
        .save(f"{ROOT}/docs/{name}.png", optimize=True)
    print(name, g.x(), g.y(), g.width(), g.height())
w.close(); wall.close()
