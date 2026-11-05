# SPDX-License-Identifier: GPL-2.0-only
"""Entry point: python3 -m sbcommand"""

import argparse
import os
import signal
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication

from . import __version__, config, pipewire, profiles, theme
from .window import Context, MainWindow


def parse_args(argv):
    names = ", ".join(f"{k} ({v['label']})" for k, v in theme.PALETTES.items())
    ap = argparse.ArgumentParser(
        prog="sbae9-sbc", description="Sound Blaster Command for Linux: AE-9 control panel.")
    ap.add_argument("--palette", type=str.lower, choices=list(theme.PALETTES), metavar="NAME",
                    help=f"colour palette for this launch, without changing the saved one: {names}")
    ap.add_argument("--scale", type=int, metavar="PCT",
                    help=f"UI scale in percent for this launch ({theme.SCALES[0]}-{theme.SCALES[1]}), "
                         "without changing the saved one")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Qt's own options (e.g. -platform, -style) pass through untouched.
    return ap.parse_known_args(argv[1:])


# QT_SCALE_FACTOR as the user's environment had it, before this app changed
# it. Kept in the environment so a relaunched copy (which inherits our
# QT_SCALE_FACTOR) still scales from the original, not from ours.
BASE_ENV = "SBAE9_SBC_BASE_SCALE_FACTOR"


def set_scale(pct, env=os.environ):
    """Ask Qt to draw everything at pct percent (on top of any factor the
    user's environment set). Must run before QApplication exists."""
    theme.SCALE = theme.clamp_scale(pct)
    base = env.setdefault(BASE_ENV, env.get("QT_SCALE_FACTOR", ""))
    try:
        factor = float(base or 1) * theme.SCALE / 100
    except ValueError:
        factor = theme.SCALE / 100
    if factor == 1 and not base:
        env.pop("QT_SCALE_FACTOR", None)
    else:
        env["QT_SCALE_FACTOR"] = f"{factor:g}"


def relaunch_args(argv):
    """The command line this launch was started with, minus a one-off
    --scale, so the reopened window uses the saved scale."""
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
        elif a == "--scale":
            skip = True
        elif not a.startswith("--scale="):
            out.append(a)
    return out


def main():
    args, qt_args = parse_args(sys.argv)
    set_scale(args.scale if args.scale else config.Settings()["ui_scale"])
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

    def restart():
        """Reopen the app (for a new UI scale): start a fresh copy, then quit."""
        if QProcess.startDetached(sys.executable, relaunch_args(sys.orig_argv[1:])):
            win.close()
            app.quit()

    ctx.restart_requested.connect(restart)

    # let Ctrl+C in a terminal close the app
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
