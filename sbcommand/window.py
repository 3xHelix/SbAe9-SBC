# SPDX-License-Identifier: GPL-2.0-only
"""Main window: sidebar navigation, page stack and the bottom status bar."""

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from . import card as C
from . import config, icons, pages, pipewire, profiles
from . import theme as T
from .widgets import Throttle, VolumeRow, label


class Context(QObject):
    """Shared state handed to every page."""
    profile_changed = Signal()
    palette_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.settings = config.Settings()
        self.card = C.AE9(self)
        self.pw = pipewire.Watcher(self)
        self.tone = pipewire.TestTone(self)
        self.monitor = pipewire.MicMonitor(self)
        self.meter = pipewire.LevelMeter(self)


NAV = [
    ("SBX Profile", "home", pages.SbxPage),
    ("Equalizer", "equalizer", pages.EqPage),
    None,
    ("Playback", "playback", pages.PlaybackPage),
    ("Recording", "recording", pages.RecordingPage),
    ("Scout Mode", "scout", pages.ScoutPage),
    ("Mixer", "mixer", pages.MixerPage),
]
NAV_BOTTOM = [("Settings", "settings", pages.SettingsPage)]

def nav_qss():
    return f"""
QPushButton {{
    background: transparent; border: none; border-left: 3px solid transparent; border-radius: 0;
    text-align: left; padding: 11px 16px; font-size: 16px;
}}
QPushButton:hover {{ background: {T.rgba(T.OVERLAY, 0.06)}; }}
QPushButton:checked {{ color: {T.ACCENT_HI}; border-left: 3px solid {T.ACCENT}; background: {T.rgba(T.OVERLAY, 0.06)}; }}
"""


class OutputSwitch(QWidget):
    """Headphones / speakers pill in the bottom bar (Head Unit Output)."""

    def __init__(self, card, parent=None):
        super().__init__(parent)
        self.card = card
        self.setFixedSize(58, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Switch between speakers and the head unit's headphone jack")
        card.changed.connect(self._on_change)

    def _on_change(self, name):
        if name == C.OUTPUT:
            self.update()

    def mouseReleaseEvent(self, e):
        if self.card.present:
            self.card.set(C.OUTPUT, 0 if self.card.get(C.OUTPUT) == 1 else 1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hp = self.card.get(C.OUTPUT) == 1
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.PANEL))
        p.drawRoundedRect(self.rect(), 15, 15)
        p.setBrush(QColor(T.ACCENT))
        p.drawEllipse(2 if hp else 30, 2, 26, 26)
        icons.paint(p, "headphones", self.rect().adjusted(6, 7, -36, -7), T.ACCENT_TEXT if hp else T.MUTED)
        icons.paint(p, "speaker", self.rect().adjusted(35, 7, -7, -7), T.ACCENT_TEXT if not hp else T.MUTED)


class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor(T.DIM)
        self.setFixedSize(16, 16)

    def set_color(self, c):
        self.color = QColor(c)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(2, 2, 12, 12)


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.card = ctx.card
        self.setWindowTitle("Sound Blaster Command — AE-9")
        self.setWindowIcon(QIcon(icons.pixmap("wave", T.ACCENT_HI, 64)))
        self.resize(1180, 760)
        self.setMinimumSize(1000, 660)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # title strip
        title = QFrame()
        title.setObjectName("titleBar")
        tl = QVBoxLayout(title)
        tl.setContentsMargins(18, 8, 18, 6)
        tl.setSpacing(0)
        tl.addWidget(label("Sound Blaster Command", "appTitle"))
        tl.addWidget(label("AE-9", "deviceName"))
        v.addWidget(title)

        self.missing = pages.Banner("Sound Blaster AE-9 not found. Is the snd-hda-codec-creative-ae9 "
                                    "driver loaded? Waiting for the card…", warn=True)
        self.missing.layout().setContentsMargins(16, 8, 16, 8)
        v.addWidget(self.missing)

        mid = QHBoxLayout()
        mid.setSpacing(0)
        v.addLayout(mid, 1)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        side.setStyleSheet(nav_qss().replace("QPushButton", "#sidebar QPushButton"))
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 10, 0, 12)
        sl.setSpacing(2)
        sl.addWidget(label("Sound Experience", "sideCaption"))
        sl.addSpacing(4)
        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        self.buttons = []

        def add(entry):
            name, ic, cls = entry
            page = cls(ctx)
            idx = self.stack.addWidget(page)
            b = QPushButton(name)
            b.setCheckable(True)
            b.setIcon(icons.icon(ic, T.TEXT, active=T.ACCENT_HI, size=22))
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.go(i))
            self.buttons.append(b)
            sl.addWidget(b)

        for entry in NAV:
            if entry is None:
                sl.addWidget(pages.hline())
            else:
                add(entry)
        sl.addStretch()
        sl.addWidget(pages.hline())
        for entry in NAV_BOTTOM:
            add(entry)
        mid.addWidget(side)
        mid.addWidget(self.stack, 1)

        # bottom bar
        bottom = QFrame()
        bottom.setObjectName("bottomBar")
        bottom.setFixedHeight(56)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(18, 0, 22, 0)
        bl.setSpacing(16)
        bl.addWidget(OutputSwitch(self.card))
        self.dot = StatusDot()
        bl.addWidget(self.dot)
        self.sbx_logo = label("SBX", "sbxLogo")
        bl.addWidget(self.sbx_logo)
        sep = QFrame()
        sep.setFixedSize(2, 26)
        sep.setStyleSheet(f"background:{T.TEXT};")
        self.sep = sep
        bl.addWidget(sep)
        self.profile_lbl = label("", "profileLabel")
        bl.addWidget(self.profile_lbl)
        bl.addStretch()
        self.mic = VolumeRow("mic", "mic-off", width=140, show_value=False)
        self.mic.setToolTip("Microphone level")
        self.mic.valueChanged.connect(Throttle(lambda val: self.card.set(C.MIC, round(val * 99)), 40))
        self.mic.muteToggled.connect(self._mic_mute)
        bl.addWidget(self.mic)
        vsep = QFrame()
        vsep.setFixedSize(2, 30)
        vsep.setStyleSheet(f"background:{T.TEXT};")
        bl.addWidget(vsep)
        self.vol = VolumeRow(width=190, show_value=False)
        self.vol.setToolTip("Volume (same as the head unit knob)")
        self.vol.valueChanged.connect(Throttle(
            lambda val: self.card.set(C.MASTER, C.master_pct_to_raw(val)), 30))
        self.vol.muteToggled.connect(lambda m: self.card.set(C.MASTER_SW, not m))
        bl.addWidget(self.vol)
        v.addWidget(bottom)

        self.card.changed.connect(self._on_card)
        self.card.info_changed.connect(self._on_card)
        self.card.connection_changed.connect(self._on_card)
        ctx.profile_changed.connect(self.refresh)
        ctx.pw.updated.connect(self._refresh_mic_mute)

        start = ctx.settings["page"]
        self.go(start if isinstance(start, int) and 0 <= start < self.stack.count() else 0)
        self.refresh()

    def go(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.buttons):
            b.setChecked(i == idx)
        self.ctx.settings["page"] = idx

    def _mic_mute(self, muted):
        n = self.ctx.pw.nodes
        if n.source:
            pipewire.set_mute(n.source["id"], muted)

    def _on_card(self, *_):
        self.refresh()

    def _refresh_mic_mute(self, *_):
        n = self.ctx.pw.nodes
        if n.source and self.card.present:
            _, muted = pipewire.get_volume(n.source["id"])
            self.mic.set_state(self.card.get(C.MIC, 0) / 99, muted)

    def refresh(self):
        present = self.card.present
        self.missing.setVisible(not present)
        self.stack.setEnabled(present)
        if not present:
            self.dot.set_color(T.DIM)
            self.profile_lbl.setText("No device")
            return
        direct = self.card.get(C.DIRECT, True)
        sbx = self.card.get(C.SBX, False)
        if direct:
            self.dot.set_color(T.DOT_IDLE)
            self.dot.setToolTip("Direct Mode: audio bypasses the DSP")
            self.profile_lbl.setText("Direct Mode")
        elif sbx:
            self.dot.set_color(T.OK)
            self.dot.setToolTip("SBX on: effects active")
            name = self.ctx.settings["active_profile"]
            prof = profiles.find(self.ctx.settings, name)
            mod = "" if profiles.matches(prof, self.card.snapshot()) else " *"
            scout = "  ·  Scout Mode" if self.card.get(C.SCOUT) else ""
            self.profile_lbl.setText(f"{name}{mod}{scout}")
        else:
            self.dot.set_color(T.WARN)
            self.dot.setToolTip("DSP path, SBX off")
            self.profile_lbl.setText("SBX off")
        raw = self.card.get(C.MASTER, 0)
        self.vol.set_state(C.master_raw_to_pct(raw), not self.card.get(C.MASTER_SW, True))
        self.vol.setToolTip(f"Volume {C.master_raw_to_db(raw):.1f} dB (same as the head unit knob)")
        self.mic.set_state(self.card.get(C.MIC, 0) / 99, self.mic.btn.isChecked())

    def closeEvent(self, e):
        self.ctx.tone.stop()
        self.ctx.monitor.stop()
        self.ctx.meter.stop()
        super().closeEvent(e)
