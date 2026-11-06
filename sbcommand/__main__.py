# SPDX-License-Identifier: GPL-2.0-only
"""Entry point: python3 -m sbcommand"""

import argparse
import os
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

from sbae9kit import desktop

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
# UI scale, the XWayland choice, the window's X11 name and relaunching are
# shared with SbAe9-AudioMon (sbae9kit.desktop). XWayland is used for a UI
# scale other than 100% (Qt on Wayland misplaces popups then) and for Glass
# (KDE only blurs behind X11 windows); a QT_QPA_PLATFORM you set wins.
BASE_ENV = desktop.env_prefix(config.APP_ID) + "_BASE_SCALE_FACTOR"
QPA_MARK = desktop.env_prefix(config.APP_ID) + "_SET_QPA"
xcb_available = desktop.xcb_available


def set_scale(pct, env=os.environ, glass=False):
    """Draw everything at pct percent, and pick XWayland if that or Glass
    needs it. Must run before QApplication exists."""
    theme.SCALE = desktop.set_scale(config.APP_ID, pct, env)
    use_xwayland(theme.SCALE != 100 or glass, env)


def use_xwayland(wanted, env=os.environ):
    return desktop.use_xwayland(config.APP_ID, wanted, env, xcb_ok=xcb_available())


def qt_argv(qt_args):
    """Qt's argv, named after the app so docks match the window (WM_CLASS)."""
    return desktop.qt_argv(config.APP_ID, qt_args)


RELAUNCH_DROP = ("--scale",)      # one-off options a reopened window doesn't repeat


def relaunch_args(argv):
    return desktop.relaunch_args(argv, RELAUNCH_DROP)


def main():
    args, qt_args = parse_args(sys.argv)
    saved = config.Settings()
    theme.GLASS = bool(saved["glass"])
    theme.GLASS_OPACITY = theme.clamp_glass(saved["glass_opacity"]) / 100
    set_scale(args.scale if args.scale else saved["ui_scale"], glass=theme.GLASS)
    app = QApplication(qt_argv(qt_args))
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
        """Reopen the app (new UI scale, Glass on/off): start a fresh copy, then quit."""
        if desktop.relaunch(RELAUNCH_DROP):
            win.close()
            app.quit()

    ctx.restart_requested.connect(restart)

    def restyle():
        app.setStyleSheet(theme.stylesheet())
        win.update()
        for wdg in win.findChildren(QWidget):
            wdg.update()

    ctx.restyle_requested.connect(restyle)

    # let Ctrl+C in a terminal close the app
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
