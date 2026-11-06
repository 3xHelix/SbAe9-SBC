# SPDX-License-Identifier: GPL-2.0-only
"""Entry point: python3 -m sbcommand"""

import argparse
import os
import signal
import sys

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QWidget

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


def set_scale(pct, env=os.environ, glass=False):
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
    use_xwayland(theme.SCALE != 100 or glass, env)


# Qt on Wayland puts popups (dropdown lists, menus) in the wrong place when
# QT_SCALE_FACTOR isn't 1. Through XWayland they line up, so a scaled UI runs
# there. Glass runs there too: KDE only blurs behind X11 windows for apps
# without KDE's own libraries. Otherwise the app stays native Wayland. A
# QT_QPA_PLATFORM the user set is left alone.
QPA_MARK = "SBAE9_SBC_SET_QPA"


def xcb_available():
    from PySide6.QtCore import QLibraryInfo
    plugins = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    return os.path.exists(os.path.join(plugins, "platforms", "libqxcb.so"))


def use_xwayland(scaled, env=os.environ):
    if env.pop(QPA_MARK, None):              # set by us on an earlier launch
        env.pop("QT_QPA_PLATFORM", None)
    wayland = env.get("WAYLAND_DISPLAY") or env.get("XDG_SESSION_TYPE") == "wayland"
    if (scaled and wayland and env.get("DISPLAY") and "QT_QPA_PLATFORM" not in env
            and xcb_available()):
        env["QT_QPA_PLATFORM"] = "xcb"
        env[QPA_MARK] = "1"


def qt_argv(qt_args):
    """Qt's argv. Its first entry names the window to X11 (WM_CLASS), which
    is how docks match a window to its menu entry when the app runs through
    XWayland; the launcher's own argv[0] is "-c", so use the app's id."""
    return [config.APP_ID] + list(qt_args)


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
        """Reopen the app (for a new UI scale): start a fresh copy, then quit."""
        if QProcess.startDetached(sys.executable, relaunch_args(sys.orig_argv[1:])):
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
