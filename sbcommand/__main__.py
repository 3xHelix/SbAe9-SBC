# SPDX-License-Identifier: GPL-2.0-only
"""Entry point: python3 -m sbcommand"""

import argparse
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from . import __version__, pipewire, profiles, theme
from .window import Context, MainWindow


def parse_args(argv):
    names = ", ".join(f"{k} ({v['label']})" for k, v in theme.PALETTES.items())
    ap = argparse.ArgumentParser(
        prog="sbae9-sbc", description="Sound Blaster Command for Linux: AE-9 control panel.")
    ap.add_argument("--palette", type=str.lower, choices=list(theme.PALETTES), metavar="NAME",
                    help=f"colour palette for this launch, without changing the saved one: {names}")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Qt's own options (e.g. -platform, -style) pass through untouched.
    return ap.parse_known_args(argv[1:])


def main():
    args, qt_args = parse_args(sys.argv)
    app = QApplication(sys.argv[:1] + qt_args)
    app.setApplicationName("Sound Blaster Command")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("sbae9-sbc")
    app.setDesktopFileName("sbae9-sbc")
    app.setStyle("Fusion")

    ctx = Context()
    s = ctx.settings
    theme.apply(args.palette or s["palette"])
    app.setStyleSheet(theme.stylesheet())
    if s["restore_on_start"] and ctx.card.present:
        prof = profiles.find(s, s["active_profile"])
        if prof:
            ctx.card.apply(prof)
    ctx.restore_rate()   # the saved pick, after a PipeWire restart

    win = MainWindow(ctx)
    win.show()

    def switch_palette(name):
        """Restyle by rebuilding the window; the card, PipeWire helpers and
        settings live in ctx and carry over (mic monitor keeps running)."""
        nonlocal win
        s["palette"] = name
        theme.apply(name)
        app.setStyleSheet(theme.stylesheet())
        old, win = win, MainWindow(ctx)
        win.setGeometry(old.geometry())
        win.showMaximized() if old.isMaximized() else win.show()
        old.hide()
        old.deleteLater()

    ctx.palette_requested.connect(switch_palette)

    # let Ctrl+C in a terminal close the app
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
