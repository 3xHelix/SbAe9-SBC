# SPDX-License-Identifier: GPL-2.0-only
"""Open the app on a fake Sound Blaster AE-7, to look at its pages.

    python3 tools/fake_ae7.py [palette] [--direct]

Uses the test fakes from tests/support.py and the AE-7's control list
(tests/fixtures/ae7_controls.json). No real card, PipeWire or settings are
touched: clicks change only the fake card, and settings go to a temp folder.
--direct adds the Direct Mode Switch (as driver 0.13.0 has with ae7=1).
"""
import os
import sys

# a real window, not the tests' offscreen one
if not os.environ.get("QT_QPA_PLATFORM"):
    os.environ["QT_QPA_PLATFORM"] = "wayland" if os.environ.get("WAYLAND_DISPLAY") else "xcb"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import support as S  # noqa: E402
from sbae9kit import testing as kt  # noqa: E402
from sbcommand import card as C, theme  # noqa: E402
from sbcommand.window import Context, MainWindow  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
palette = args[0] if args else "command"
S.reset()
S.sound_cards(kt.AE7_CARD)
S.use_controls("ae7_controls.json")
S.PARAMS.update({"version": "0.13.0"})
theme.apply(palette)
S.app.setStyle("Fusion")
S.app.setStyleSheet(theme.stylesheet())

ctx = Context()
if "--direct" in sys.argv:
    S.FakeMixer.last.add_bool(C.DIRECT, False)
    ctx.card.changed.emit(C.DIRECT)
w = MainWindow(ctx)
w.setWindowTitle("Sound Blaster Command (fake AE-7)")
w.resize(1180, 760)
w.show()
sys.exit(S.app.exec())
