# SPDX-License-Identifier: GPL-2.0-only
"""Entry point: python3 -m sbcommand"""

import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from . import __version__, pipewire, profiles, theme
from .window import Context, MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sound Blaster Command")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("sbae9-sbc")
    app.setDesktopFileName("sbae9-sbc")
    app.setStyle("Fusion")

    ctx = Context()
    s = ctx.settings
    theme.apply(s["palette"])
    app.setStyleSheet(theme.stylesheet())
    if s["restore_on_start"] and ctx.card.present:
        prof = profiles.find(s, s["active_profile"])
        if prof:
            ctx.card.apply(prof)
    if s["rate_mode"] is not None and pipewire.current_rate_mode() != s["rate_mode"]:
        pipewire.set_rate_mode(s["rate_mode"])

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
