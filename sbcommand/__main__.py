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
    app.setStyleSheet(theme.stylesheet())

    ctx = Context()
    s = ctx.settings
    if s["restore_on_start"] and ctx.card.present:
        prof = profiles.find(s, s["active_profile"])
        if prof:
            ctx.card.apply(prof)
    if s["rate_mode"] is not None and pipewire.current_rate_mode() != s["rate_mode"]:
        pipewire.set_rate_mode(s["rate_mode"])

    win = MainWindow(ctx)
    win.show()

    # let Ctrl+C in a terminal close the app
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
