# SPDX-License-Identifier: GPL-2.0-only
"""Main window: sidebar navigation, page stack and the bottom status bar."""

import os
import time

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QStackedWidget,
                               QAbstractButton, QToolButton, QVBoxLayout, QWidget)

from sbae9kit import desktop, frame, glass

from . import card as C
from . import applier, config, encoder, icons, pages, pipewire, profiles
from .applier import Applier, Change
from . import theme as T
from .widgets import ApplyOverlay, Throttle, VolumeRow, label


CARD_MIN_MS = 2000


def card_pace(ms):
    """The least wait after a change that rebuilds the card's stream. Driver
    0.12.10 fixed the stale-RIRB reads behind the card wearing down under
    rapid switching (760 back-to-back reconfigs clean), so 2 s is plenty
    there; older drivers keep the longer wait. PipeWire / WirePlumber
    restarts (the input rates) keep theirs: those wait for the restart."""
    return min(ms, CARD_MIN_MS) if C.driver_at_least(0, 12, 10) else ms


class Context(QObject):
    """Shared state handed to every page."""
    profile_changed = Signal()
    palette_requested = Signal(str)
    restart_requested = Signal()
    restyle_requested = Signal()      # same window, new style sheet (glass opacity)

    def __init__(self):
        super().__init__()
        self.settings = config.Settings()
        C.select(self.settings["card"])     # two cards in the machine: the one picked last
        self.card = C.AE9(self)
        self.pw = pipewire.Watcher(self)
        self.tone = pipewire.TestTone(self)
        self.monitor = pipewire.MicMonitor(self)
        self.meter = pipewire.LevelMeter(self)
        # Keep PipeWire's rate inside what the card takes right now: Direct
        # Mode, the 5.1 profile and the driver's pcm_rates all change that.
        # stream changes go one at a time, each with a settle period
        self.applier = Applier(self.pw.refresh, self)
        self.applier.add_followup(self._recheck_rate)
        self._in_followup = False
        self.depth_pending = False
        self._rate_written = None   # (rate, quantum) the app last wrote
        self._dragons = False       # user picked experimental 96 kHz on 5.1
        self.card.changed.connect(self._on_card_rate)
        self.card.connection_changed.connect(self._on_card_rate)
        self.card.connection_changed.connect(lambda *_: self.pw.refresh())   # another card's nodes
        self.pw.updated.connect(self._on_pw_rate)
        # a card profile switch removes the AE-9's output and adds another:
        # PipeWire may then pick another card as default (HDMI, say)
        self._last_profile = None
        self._ae9_default_at = 0.0     # last seen as the default output
        self._keep_default_until = 0.0
        self._sink_before = None       # the AE-9 output before the switch
        self.pw.updated.connect(self._keep_default)

    def rate_set(self):
        """The rates the card plays right now (Direct Mode, 5.1, driver options)."""
        direct = C.direct_on(self.card)
        surround = self.pw.nodes.stream_layout() == "surround"
        return pipewire.playable_now(direct, surround)

    def rate_cap(self):
        return max(self.rate_set())

    def dragons_available(self):
        """5.1 at 96 kHz on drivers before 0.7.0: experimental, only when the
        driver's root-only surround_96k option reads 1 (Direct Mode, high rates
        on). Offered for an explicit pick only: never clamped to, restored or
        chosen automatically. From 0.7.0 it's a normal rate (see rate_cap)."""
        return (not C.surround_96k_stable() and self.rate_cap() == 48000 and self.pw.nodes.stream_layout() == "surround"
                and self.card.present and C.direct_on(self.card)
                and C.module_param("pcm_rates") != "0"
                and C.module_param("surround_96k") == "1")

    def active_rates(self):
        """The rates in force now: 48 and 96 kHz on 5.1 only while the user's
        own experimental pick is live, else rate_set()."""
        if self._dragons and not self.dragons_available():
            self._dragons = False
        return [48000, 96000] if self._dragons else self.rate_set()

    def active_cap(self):
        return max(self.active_rates())

    def apply_rate(self, user=False, startup=False):
        """Write PipeWire's rate for the app's own pick, capped to what the
        card takes. Like the profile sync, the app never fights changes made
        elsewhere (pw-metadata, other tools):

        - user: the user picked in the combo: always written.
        - startup: restore the saved pick, only if PipeWire forces nothing.
        - otherwise (Direct Mode / 5.1 / connection changed): re-cap only if
          PipeWire still holds exactly what the app last wrote.
        Automatic or nothing saved: PipeWire is left alone (except a user pick).
        """
        mode = self.settings["rate_mode"]
        if user:
            # 96 kHz on 5.1 only by an explicit pick, and only for this 5.1 run
            self._dragons = mode == 96000 and self.dragons_available()
        if not mode and not user:
            return
        eff = pipewire.effective_rate(mode or 0, self.active_rates())
        want = (eff, pipewire.quantum_for(eff, self.settings["quantum"] or 0))
        if not user:
            now = (pipewire.current_force_rate(), pipewire.current_quantum())
            if self._rate_written is None and now == want:
                self._rate_written = want   # already ours (e.g. from the last run)
                return
            if startup:
                if now != (0, 0):
                    return
            elif want == self._rate_written or now != self._rate_written:
                return
            if self.applier.busy and not self._in_followup:
                return   # re-checked when the current change has settled

        def run():
            pipewire.set_rate_mode(eff, pipewire.allowed_now(),
                                   self.settings["quantum"] or 0)
            self._rate_written = want

        def settled():
            live = pipewire.card_stream()
            return self._sink_ok() and (live is None or not eff or live[0] == eff)

        text = "Sample rate: automatic" if not eff else f"Sample rate: {eff / 1000:g} kHz"
        self.applier.submit(Change(
            "rate", text, run, card_pace(4000), settled,
            lambda: (pipewire.current_force_rate(), pipewire.current_quantum()) != want))

    def _recheck_rate(self):
        self._in_followup = True
        try:
            self.apply_rate()
        finally:
            self._in_followup = False

    # --- changes that rebuild the card's stream (paced by the applier) ---------
    def _sink_ok(self):
        sink = self.pw.nodes.sink
        return sink is None or sink.get("state") in ("running", "idle", "suspended")

    def set_direct(self, on):
        if bool(self.card.get(C.DIRECT)) == on and not self.applier.busy:
            return
        self.applier.submit(Change(
            "direct", "Direct Mode on" if on else "Direct Mode off",
            lambda: self.card.set(C.DIRECT, on), card_pace(5000),
            lambda: bool(self.card.get(C.DIRECT)) == on and self._sink_ok(),
            lambda: bool(self.card.get(C.DIRECT)) != on))

    def set_speaker_cfg(self, k):
        items = self.card.items(C.SPEAKER_CFG)
        name = items[k] if 0 <= k < len(items) else str(k)
        self.applier.submit(Change(
            "speakers", f"Speakers: {name}", lambda: self.card.set(C.SPEAKER_CFG, k), card_pace(4000),
            lambda: self.card.get(C.SPEAKER_CFG) == k and self._sink_ok(),
            lambda: self.card.get(C.SPEAKER_CFG) != k))

    def set_stream_layout(self, surround):
        """Switch the card profile to the stereo or 5.1 stream, if there's
        anything to switch. False when there isn't."""
        if not pipewire.layout_profile(self.pw.nodes, surround) and not self.applier.busy:
            return False
        want = "surround" if surround else "stereo"

        def run():
            n = self.pw.nodes
            target = pipewire.layout_profile(n, surround)
            if target:
                if self.tone.running:
                    self.tone.stop()
                self.switch_card_profile(n, target)

        def settled():
            n = self.pw.nodes
            live = pipewire.card_stream()
            chans = 6 if surround else 2
            return (n.stream_layout() == want and n.sink is not None and self._sink_ok()
                    and (live is None or live[1] == chans))

        self.applier.submit(Change("profile", "5.1 Stream" if surround else "Stereo Stream",
                                   run, card_pace(5000), settled,
                                   lambda: bool(pipewire.layout_profile(self.pw.nodes, surround))))
        return True

    def set_bit_depth(self, k):
        items = self.card.items(C.BIT_DEPTH)
        name = items[k] if 0 <= k < len(items) else str(k)

        def run():
            self.card.set(C.BIT_DEPTH, k)
            # the depth is taken when the card opens: reopen it now, unless an
            # app (an MPD playing native DSD) holds it: PipeWire can't reopen it
            self.depth_pending = (bool(pipewire.card_held_by_other())
                                  or not pipewire.reopen_sink(self.pw.nodes))

        self.applier.submit(Change("depth", f"Bit depth: {name}", run, card_pace(4000), self._sink_ok,
                                   lambda: self.card.get(C.BIT_DEPTH) != k))

    def set_mic_rate(self, rate):
        """Record the head unit mic at `rate` (None = PipeWire decides). Goes
        through a WirePlumber restart, which re-creates the card's nodes."""
        src = self.pw.nodes.source
        if not src:
            return

        def settled():
            n = self.pw.nodes
            return n.source is not None and self._sink_ok()

        text = f"Mic sample rate: {rate / 1000:g} kHz" if rate else "Mic sample rate: automatic"
        self.applier.submit(Change(
            "mic_rate", text, lambda: pipewire.set_mic_rate(src["name"], rate), 5000, settled,
            lambda: pipewire.mic_rate_setting() != rate))

    def set_input_rate(self, key, path, rate, title):
        """Record an extra input (What U Hear) at `rate`: its PipeWire config's
        audio.rate, then a PipeWire restart, which re-creates the nodes."""

        def settled():
            n = self.pw.nodes
            return getattr(n, key) is not None and self._sink_ok()

        self.applier.submit(Change(
            key + "_rate", f"{title} sample rate: {rate / 1000:g} kHz",
            lambda: pipewire.set_input_conf_rate(path, rate), 8000, settled,
            lambda: pipewire.input_conf_rate(path) != rate))

    def set_input_rule_rate(self, key, rate, title):
        """Record a card-profile input (What U Hear, driver 0.11.0+) at `rate`
        (None = follow PipeWire): a WirePlumber rule and restart."""

        def settled():
            n = self.pw.nodes
            return getattr(n, key) is not None and self._sink_ok()

        text = f"{title} sample rate: " + (f"{rate / 1000:g} kHz" if rate else "automatic")
        self.applier.submit(Change(
            key + "_rate", text, lambda: pipewire.set_input_rule_rate(key, rate), 5000, settled,
            lambda: pipewire.input_rule_rate(key) != rate))

    def set_capture_depth(self, k):
        items = self.card.items(C.CAP_BIT_DEPTH)
        name = items[k] if 0 <= k < len(items) else str(k)

        def run():
            self.card.set(C.CAP_BIT_DEPTH, k)
            pipewire.reopen_source(self.pw.nodes)   # taken when the capture opens

        self.applier.submit(Change("cap_depth", f"Mic bit depth: {name}", run, card_pace(4000), self._sink_ok,
                                   lambda: self.card.get(C.CAP_BIT_DEPTH) != k))

    def restore_rate(self):
        """Restore the saved pick at start, once the first PipeWire snapshot
        is in: before it, a 5.1 profile isn't known yet and the cap would be
        too high (6 ch above 48 kHz falls apart). With "Reload last rate on
        start" off the app only shows what PipeWire is running."""
        pipewire.update_allowed_rates(pipewire.allowed_now())
        if not self.settings["rate_mode"] or not self.settings["restore_rate_on_start"]:
            return
        if self.pw.nodes.device or self.pw.nodes.sink:
            self.apply_rate(startup=True)
        else:
            self.pw.updated.connect(self._restore_rate_once)

    def _restore_rate_once(self, *_):
        self.pw.updated.disconnect(self._restore_rate_once)
        self.apply_rate(startup=True)

    def _on_card_rate(self, name=None):
        if name in (None, True, False, C.DIRECT):
            self.apply_rate()

    def _on_pw_rate(self, *_):
        self.apply_rate()

    def switch_to_card(self, card_id):
        """Manage another of the machine's cards (the title bar's card menu)."""
        if card_id == C.card_id() and self.card.present:
            return
        self.settings["card"] = card_id
        self.card.switch_to(card_id)

    def switch_card_profile(self, nodes, name):
        """Switch the AE-9's card profile, pausing the optical encoder around
        it: the profile is built while nothing holds the optical output."""
        paused = encoder.pause()
        ok = pipewire.set_card_profile(nodes, name)
        if paused:
            QTimer.singleShot(int(3000 * applier.TIME_SCALE), encoder.resume)
        return ok

    def _keep_default(self, *_):
        """After the AE-9 changes card profile (5.1 / stereo stream, from here
        or elsewhere) while it was the default output, make its new output
        the default once it's there."""
        n = self.pw.nodes
        prof = n.card_profile()
        now = time.monotonic()
        if n.sink and n.sink_is_default and now >= self._keep_default_until:
            self._ae9_default_at = now
            self._sink_before = n.sink["name"]
        # "was default" a few seconds back: the switch can move the default
        # a snapshot before the new profile shows
        if (prof and self._last_profile and prof != self._last_profile
                and now - self._ae9_default_at < 6):
            self._keep_default_until = now + 10
        if prof:
            self._last_profile = prof
        if (now < self._keep_default_until and n.sink and n.default_sink
                and n.sink["name"] != self._sink_before):
            if n.sink_is_default:
                self._keep_default_until = 0.0
            elif n.sink["state"] in ("running", "idle", "suspended"):
                pipewire.set_default(n.sink["id"])
                self._keep_default_until = 0.0


NAV = [
    ("SBX Profile", "home", pages.SbxPage),
    ("Equalizer", "equalizer", pages.EqPage),
    None,
    ("Playback", "playback", pages.PlaybackPage),
    ("Recording", "recording", pages.RecordingPage),
    ("Scout Mode", "scout", pages.ScoutPage),
    ("Encoder", "encoder", pages.EncoderPage, "encoder"),
    ("Mixer", "mixer", pages.MixerPage),
]
NAV_BOTTOM = [("Settings", "settings", pages.SettingsPage)]
# A fourth item names the card-profile feature a page needs (C.feature): the
# AE-5 has no encoder (the AE-5 Plus does). Features the kit doesn't list yet
# count as there, so the AE-9 shows every page as before.


def page_offered(entry):
    return len(entry) < 4 or bool(C.feature(entry[3], True))

def nav_qss():
    return f"""
QPushButton {{
    background: transparent; border: none; border-left: 3px solid transparent; border-radius: 0;
    text-align: left; padding: 11px 16px; font-size: 16px;
}}
QPushButton:hover {{ background: {T.rgba(T.OVERLAY, 0.06)}; }}
QPushButton:checked {{ color: {T.ACCENT_HI}; border-left: 3px solid {T.ACCENT}; background: {T.rgba(T.OVERLAY, 0.06)}; }}
"""


class PillSwitch(QWidget):
    """Two-way pill in the bottom bar: an icon each side, the knob on the
    one in use. `right()` says which; `toggle()` switches."""

    def __init__(self, card, control, left_icon, right_icon, tip, parent=None):
        super().__init__(parent)
        self.card, self.control = card, control
        self.icons = (left_icon, right_icon)
        self.setFixedSize(58, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        card.changed.connect(self._on_change)

    def _on_change(self, name):
        if name == self.control:
            self.update()

    def right(self):
        return False

    def toggle(self):
        pass

    def mouseReleaseEvent(self, e):
        if self.card.present and self.rect().contains(e.position().toPoint()):
            self.toggle()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        right = self.right()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.PANEL))
        p.drawRoundedRect(self.rect(), 15, 15)
        p.setBrush(QColor(T.ACCENT))
        p.drawEllipse(30 if right else 2, 2, 26, 26)
        icons.paint(p, self.icons[0], self.rect().adjusted(6, 7, -36, -7), T.MUTED if right else T.ACCENT_TEXT)
        icons.paint(p, self.icons[1], self.rect().adjusted(35, 7, -7, -7), T.ACCENT_TEXT if right else T.MUTED)


def output_tip():
    """The headphones / speakers switch's tooltip, for the managed card."""
    speakers = "the card's RCA out" if C.has_head_unit() else "the card's speaker outputs"
    return f"Switch between speakers ({speakers}) and headphones ({C.phones_jacks()})"


class OutputSwitch(PillSwitch):
    """Headphones / speakers (Head Unit Output)."""

    def __init__(self, card, parent=None):
        super().__init__(card, C.OUTPUT, "headphones", "speaker", output_tip(), parent)

    def right(self):
        return self.card.get(C.OUTPUT) != 1

    def toggle(self):
        self.card.set(C.OUTPUT, 0 if self.card.get(C.OUTPUT) == 1 else 1)


class DirectSwitch(PillSwitch):
    """Direct Mode / DSP, through the app's Direct Mode change (as the
    Playback page's switch)."""

    def __init__(self, ctx, parent=None):
        super().__init__(ctx.card, C.DIRECT, "direct", "chip",
                         "Switch between the DSP (SBX, EQ, speaker setup) and Direct Mode "
                         "(straight to the DAC, up to 384 kHz)", parent)
        self.ctx = ctx

    def right(self):
        # Direct on the left, DSP on the right: the order you switch things
        # on (DSP, then SBX), as in the panel widgets
        return not C.direct_on(self.card)

    def toggle(self):
        pages.set_direct_checked(self, self.ctx, self.right())


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


APPICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "appicon")


def app_icon():
    """The app icon (appicon/sbae9-sbc-<size>.png, every size), or the wave
    symbol if the PNGs are missing."""
    return desktop.app_icon(APPICON_DIR, config.APP_ID,
                            fallback=QIcon(icons.pixmap("wave", T.ACCENT_HI, 64)))


def blur_behind(win):
    """KDE's frost behind the glass window (shared with SbAe9-AudioMon)."""
    return glass.blur_behind(win)


# the frameless window's title bar and edge grips (shared with SbAe9-AudioMon)
TitleBar, EdgeGrip = frame.TitleBar, frame.EdgeGrip


NO_CARD_TITLE = "Please connect a Sound Blaster AE-9."
NO_CARD = "Your audio device cannot be detected. Please check your connection."
NO_CARD_SUB = "The window fills in as soon as the card appears."
NOT_ANSWERING_TITLE = "The Sound Blaster AE-9 stopped answering."
NOT_ANSWERING_SUB = ("Changes no longer reach it. Reload the driver with these commands in a "
                     "terminal (the window has already let go of the card), or power the PC "
                     "off and on. The window fills in again once the card is back.")
RELOAD_TOOL_SUB = ("Changes no longer reach it. Run this in a terminal. It reloads the driver: "
                   "stops PipeWire and the AE-9 services, reloads, starts them again. If it says "
                   "the card didn't start, power the PC off (PSU switch) for 15-30 s. The window "
                   "fills in again once the card is back.")
NOT_ANSWERING_BAR = "The sound card stopped answering. Reload the driver, or power the PC off and on."
RELOADING_TITLE = "Reloading the AE-9 driver…"
RELOADING_SUB = ("ae9-reload is reloading the driver. Sound Blaster Command has let go of the "
                 "card and fills the window in again once it's back.")
RELOADING_BAR = "Reloading the driver…"
# An AE-7 the driver doesn't run yet (0.13.0: experimental, opt-in)
AE7_OFF_TITLE = "Sound Blaster AE-7 found: its experimental support is off."
AE7_OFF_SUB = ("The AE-7 is still on the kernel's own driver. Run this in a terminal and reboot "
               "to try the experimental support (see the driver's docs/AE7.md):")
AE7_UNBOUND_SUB = ("Enabling the AE-7's experimental support isn't finished: the driver "
                   "left it alone. This command says what's missing:")
AE7_OFF_BAR = "Sound Blaster AE-7 found: experimental support is off (sudo ae9-ae7-enable)."
NO_DRIVER = ("The AE-9 driver (snd-hda-codec-creative-ae9) isn't loaded. "
             "Install or load it, and the card shows up here.")


def no_card_reason(card):
    """The bottom strip's text while the card is missing or not answering."""
    if card.reloading:
        return RELOADING_BAR
    if not card.answering:
        return NOT_ANSWERING_BAR
    if C.ae7_waiting():
        return AE7_OFF_BAR
    return NO_CARD if C.driver_loaded() else C.for_card(NO_DRIVER)


class NoCardPage(QWidget):
    """What the window shows while the AE-9 is missing (as Windows' SBC)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("content")
        lay = QVBoxLayout(self)
        lay.addStretch()
        self.title = label(C.for_card(NO_CARD_TITLE), "noCardTitle", wrap=True)
        self.title.setMinimumWidth(1)
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)
        self.sub = label(NO_CARD_SUB, "muted", wrap=True)
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.sub)

        # not answering: how to reload the driver
        self.steps_box = QWidget()
        sb = QVBoxLayout(self.steps_box)
        sb.setContentsMargins(40, 12, 40, 0)
        self.steps = QLabel(C.RELOAD_STEPS)
        self.steps.setObjectName("reloadSteps")
        self.steps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.steps.setWordWrap(True)
        sb.addWidget(self.steps)
        row = QHBoxLayout()
        row.addStretch()
        self.copy_btn = QPushButton("Copy commands")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.steps.text()))
        row.addWidget(self.copy_btn)
        self.retry_btn = QPushButton("Try again")
        self.retry_btn.setObjectName("accentButton")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.setToolTip("Open the card again now (e.g. after reloading the driver some other way)")
        row.addWidget(self.retry_btn)
        row.addStretch()
        sb.addLayout(row)
        lay.addWidget(self.steps_box)
        self.steps_box.hide()
        lay.addStretch()

    def show_state(self, answering, reloading=False):
        if reloading:
            self.title.setText(C.for_card(RELOADING_TITLE))
            self.sub.setText(RELOADING_SUB)
            self.steps_box.hide()
            return
        ae7 = C.ae7_waiting() if answering else None
        if ae7:
            self.title.setText(AE7_OFF_TITLE)
            self.sub.setText(AE7_OFF_SUB if ae7 == "kernel" else AE7_UNBOUND_SUB)
            self.steps.setText(C.AE7_ENABLE if ae7 == "kernel" else C.AE7_STATUS)
            self.copy_btn.setText("Copy command")
            self.steps_box.setVisible(True)
            return
        self.title.setText(C.for_card(NO_CARD_TITLE if answering else NOT_ANSWERING_TITLE))
        tool = None if answering else C.reload_tool()
        self.sub.setText(C.for_card(NO_CARD_SUB if answering else RELOAD_TOOL_SUB if tool
                                    else NOT_ANSWERING_SUB))
        # ae9-reload (driver 0.12.9+) when it's there; the commands by hand before it
        self.steps.setText(C.RELOAD_TOOL if tool else C.RELOAD_STEPS)
        self.copy_btn.setText("Copy command" if tool else "Copy commands")
        self.steps_box.setVisible(not answering)


class CardName(QWidget):
    """The title bar's card name ("AE-9"). With two of our cards in the machine
    it gets a drop-down arrow: a menu of the cards, to pick the one to manage."""
    picked = Signal(str)       # the ALSA id of the card picked in the menu

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        self.name = label(C.card_short(), "deviceName")
        h.addWidget(self.name)
        self.arrow = QToolButton()
        self.arrow.setObjectName("cardMenu")
        self.arrow.setIcon(icons.icon("chevron-down", T.ACCENT, active=T.ACCENT_HI, size=16))
        self.arrow.setIconSize(QSize(16, 16))
        self.arrow.setFixedSize(24, 24)
        self.arrow.setAutoRaise(True)
        self.arrow.setCursor(Qt.PointingHandCursor)
        self.arrow.setFocusPolicy(Qt.NoFocus)
        self.arrow.setToolTip("Pick the card to manage")
        self.arrow.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self.arrow.clicked.connect(self.show_menu)
        h.addWidget(self.arrow)
        h.addStretch()
        self.menu = QMenu(self)
        self.update_cards()

    def many(self):
        return len(C.cards()) > 1

    def update_cards(self):
        """The name of the managed card, and the arrow only with two or more."""
        self.name.setText(C.card_short())
        many = self.many()
        self.arrow.setVisible(many)
        self.name.setCursor(Qt.PointingHandCursor if many else Qt.ArrowCursor)
        b = C.board()
        self.name.setToolTip((b.longname or b.name) if b and many else "")

    def build_menu(self):
        """One checkable entry per card; the managed one checked."""
        self.menu.clear()
        found, now = C.cards(), C.board()
        for c in found:
            a = self.menu.addAction(C.card_label(c, found))
            a.setCheckable(True)
            a.setChecked(bool(now) and c.id == now.id)
            a.setToolTip(c.longname or c.name)
            a.triggered.connect(lambda _=False, cid=c.id: self.picked.emit(cid))
        self.menu.setToolTipsVisible(True)
        return self.menu

    def show_menu(self):
        if not self.many():
            return
        self.build_menu().popup(self.mapToGlobal(self.name.geometry().bottomLeft()))

    def mousePressEvent(self, e):
        if self.many() and e.button() == Qt.LeftButton:
            self.show_menu()
            e.accept()
        else:
            super().mousePressEvent(e)


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.card = ctx.card
        self.setWindowTitle(C.for_card("Sound Blaster Command — AE-9"))
        self.setWindowIcon(app_icon())
        self.resize(1180, 760)
        self.setMinimumSize(1000, 660)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # title strip
        title = self.title_bar = TitleBar()
        th = QHBoxLayout(title)
        th.setContentsMargins(18, 8, 10, 6)
        th.setSpacing(4)
        tl = QVBoxLayout()
        tl.setSpacing(0)
        tl.addWidget(label("Sound Blaster Command", "appTitle"))
        self.card_name = CardName()
        self.card_name.picked.connect(ctx.switch_to_card)
        self.device_name = self.card_name.name
        tl.addWidget(self.card_name)
        th.addLayout(tl)
        th.addStretch()
        self.win_buttons = []
        for name, tip, slot in (("minimize", "Minimize", self.showMinimized), ("close", "Close", self.close)):
            b = QToolButton()
            b.setObjectName("winClose" if name == "close" else "winButton")
            b.setIcon(icons.icon(name, T.MUTED, active=T.TEXT, size=18))
            b.setIconSize(QSize(18, 18))
            b.setFixedSize(34, 28)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(slot)
            th.addWidget(b, 0, Qt.AlignTop)
            self.win_buttons.append(b)
        v.addWidget(title)

        # Direct Mode off, but the stream plays on direct until a 48 kHz one
        self.dsp_wait = pages.Banner("", action="Use 48 kHz")
        self.dsp_wait.layout().setContentsMargins(16, 8, 16, 8)
        self.dsp_wait.button.setToolTip("Sets Playback's sample rate to 48 kHz")
        self.dsp_wait.button.clicked.connect(self._use_48k)
        v.addWidget(self.dsp_wait)

        mid = QHBoxLayout()
        mid.setSpacing(0)
        v.addLayout(mid, 1)

        side = self.sidebar = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        side.setStyleSheet(nav_qss().replace("QPushButton", "#sidebar QPushButton"))
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 10, 0, 12)
        sl.setSpacing(2)
        self.side_caption = label("Sound Experience", "sideCaption")
        sl.addWidget(self.side_caption)
        sl.addSpacing(4)
        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        self.buttons = []
        self.nav_seps = []

        # no card: "My Devices" stands in for the pages, which need the card
        self.devices_btn = QPushButton("My Devices")
        self.devices_btn.setCheckable(True)
        self.devices_btn.setIcon(icons.icon("speaker", T.TEXT, active=T.ACCENT_HI, size=22))
        self.devices_btn.setIconSize(QSize(22, 22))
        self.devices_btn.setCursor(Qt.PointingHandCursor)
        self.devices_btn.clicked.connect(self._show_no_card)
        sl.addWidget(self.devices_btn)

        self.nav_entries = []

        def add(entry):
            name, ic, cls = entry[:3]
            self.nav_entries.append(entry)
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
                self.nav_seps.append(pages.hline())
                sl.addWidget(self.nav_seps[-1])
            else:
                add(entry)
        self.n_card_pages = len(self.buttons)
        sl.addStretch()
        sl.addWidget(pages.hline())
        for entry in NAV_BOTTOM:
            add(entry)
        mid.addWidget(side)
        self.no_card = NoCardPage()
        self.no_card.retry_btn.clicked.connect(self.card.retry)
        self.body = QStackedWidget()
        self.body.addWidget(self.stack)
        self.body.addWidget(self.no_card)
        mid.addWidget(self.body, 1)

        # bottom bar
        bottom = self.bottom_bar = QFrame()
        bottom.setObjectName("bottomBar")
        bottom.setFixedHeight(56)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(18, 0, 22, 0)
        bl.setSpacing(16)
        self.output_switch = OutputSwitch(self.card)
        bl.addWidget(self.output_switch)
        self.direct_switch = DirectSwitch(self.ctx)
        bl.addWidget(self.direct_switch)
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
        self.vol.setToolTip(C.volume_tip())
        self.vol.valueChanged.connect(Throttle(
            lambda val: self.card.set(C.MASTER, C.master_pct_to_raw(val, self.card.master_max())), 30))
        self.vol.muteToggled.connect(lambda m: self.card.set(C.MASTER_SW, not m))
        bl.addWidget(self.vol)
        v.addWidget(bottom)
        self.no_card_bar = label("", "noCardBar", wrap=True)
        self.no_card_bar.setAlignment(Qt.AlignCenter)
        self.no_card_bar.setMinimumHeight(56)
        v.addWidget(self.no_card_bar)

        self.card.changed.connect(self._on_card)
        self.card.info_changed.connect(self._on_card)
        self.card.connection_changed.connect(self._on_card)
        self.card.answering_changed.connect(self._on_card)
        self.card.reloading_changed.connect(self._on_card)
        ctx.profile_changed.connect(self.refresh)
        ctx.pw.updated.connect(self._refresh_mic_mute)
        ctx.pw.updated.connect(self._refresh_dsp_wait)

        start = ctx.settings["page"]
        self.go(start if isinstance(start, int) and 0 <= start < self.stack.count() else 0)
        self._shown_short = C.AE9_SHORT      # every text is written for the AE-9
        self._retext()
        self.refresh()

        # "Applying changes…" while a stream change settles
        self.applying = ApplyOverlay(root)
        ctx.applier.busy_changed.connect(self.applying.set_busy)
        ctx.applier.step.connect(self.applying.set_step)
        if ctx.applier.busy:
            self.applying.set_busy(True)

        if T.GLASS:
            # see-through backgrounds; must be set before the window is created
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.grips = [EdgeGrip(edges, self) for edges in EdgeGrip.CURSORS]
        self.set_frameless(bool(ctx.settings["frameless"]))

    # own title bar vs. the desktop's frame
    def frameless(self):
        return bool(self.windowFlags() & Qt.FramelessWindowHint)

    def set_frameless(self, on):
        shown, state = self.isVisible(), self.windowState()
        self.setWindowFlag(Qt.FramelessWindowHint, on)   # hides the window if it was shown
        for b in self.win_buttons:
            b.setVisible(on)
        self._place_grips()
        if shown:
            self.setWindowState(state)
            self.show()

    def _place_grips(self):
        on = self.frameless() and not (self.isMaximized() or self.isFullScreen())
        for g in self.grips:
            g.setVisible(on)
            if on:
                g.place(self.width(), self.height())

    def showEvent(self, e):
        super().showEvent(e)
        if T.GLASS:
            blur_behind(self)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_grips()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            self._place_grips()

    def go(self, idx):
        self.body.setCurrentWidget(self.stack)
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.buttons):
            b.setChecked(i == idx)
        self.devices_btn.setChecked(False)
        if self.card.present:      # without the card only Settings opens; keep the saved page
            self.ctx.settings["page"] = idx

    def _show_no_card(self):
        self.body.setCurrentWidget(self.no_card)
        for b in self.buttons:
            b.setChecked(False)
        self.devices_btn.setChecked(True)

    def _show_card(self, present):
        """Swap between the card's pages and the "no card" screen."""
        if present == getattr(self, "_shown_present", None):
            return
        self._shown_present = present
        for w in self.nav_seps + [self.side_caption]:
            w.setVisible(present)
        for b, entry in zip(self.buttons[:self.n_card_pages], self.nav_entries):
            b.setVisible(present and page_offered(entry))
        self.devices_btn.setVisible(not present)
        self.bottom_bar.setVisible(present)
        self.no_card_bar.setVisible(not present)
        if present:
            start = self.ctx.settings["page"]
            ok = isinstance(start, int) and 0 <= start < self.stack.count()
            if ok and start < self.n_card_pages and not page_offered(self.nav_entries[start]):
                ok = False             # a page this card doesn't have (Encoder on an AE-5)
            self.go(start if ok else 0)
        else:
            self._show_no_card()

    def _mic_mute(self, muted):
        n = self.ctx.pw.nodes
        if n.source:
            pipewire.set_mute(n.source["id"], muted)

    def _on_card(self, *_):
        self.card_name.update_cards()
        self.output_switch.setToolTip(output_tip())
        self._retext()
        self.setWindowTitle(C.for_card("Sound Blaster Command — AE-9"))
        self.refresh()

    def _retext(self):
        """Word every label, button and tooltip for the managed card: they're
        written for the AE-9 ("AE-9 Optical Out"), so on an AE-7, or after
        picking the other card in the title bar, swap the name. Texts that
        refresh themselves already go through C.for_card."""
        old, new = self._shown_short, C.card_short()
        if old == new:
            return
        self._shown_short = new
        for w in self.findChildren(QWidget):
            tip = w.toolTip()
            if old in tip:
                w.setToolTip(tip.replace(old, new))
            if isinstance(w, (QLabel, QAbstractButton)):
                t = w.text()
                if old in t:
                    w.setText(t.replace(old, new))
        # pages that word texts by the card's profile (head unit or not)
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            if hasattr(page, "card_switched"):
                page.card_switched()
        self._show_card_force()

    def _show_card_force(self):
        """Re-run the page list (a card switch can offer other pages)."""
        self._shown_present = None
        self._show_card(self.card.present and self.card.answering)

    def _refresh_dsp_wait(self, *_):
        rate = self.card.answering and C.dsp_waiting_rate(self.card, pipewire.card_stream())
        if rate:
            self.dsp_wait.text.setText(
                f"DSP mode and the effects start with the next 48 kHz stream: the one playing now "
                f"is {rate / 1000:g} kHz, so it stays direct. Set the sample rate to 48 kHz "
                f"(or: pw-metadata -n settings 0 clock.force-rate 48000).")
        self.dsp_wait.setVisible(bool(rate))

    def _use_48k(self):
        self.ctx.settings["rate_mode"] = 48000
        self.ctx.apply_rate(user=True)

    def _refresh_mic_mute(self, *_):
        n = self.ctx.pw.nodes
        if n.source and self.card.present:
            _, muted = pipewire.get_volume(n.source["id"])
            self.mic.set_state(self.card.get(C.MIC, 0) / 99, muted)

    def refresh(self):
        # a card that stopped answering (driver 0.12.8) is as good as missing
        present = self.card.present and self.card.answering
        self._show_card(present)
        self._refresh_dsp_wait()
        if not present:
            self.no_card.show_state(self.card.answering, self.card.reloading)
            self.no_card_bar.setText(no_card_reason(self.card))
            self.dot.set_color(T.DIM)
            self.profile_lbl.setText("No device")
            return
        direct = C.direct_on(self.card)
        self.direct_switch.setVisible(not C.no_direct(self.card))
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
            self.profile_lbl.setText("Off")
        raw = self.card.get(C.MASTER, 0)
        top = self.card.master_max()
        self.vol.set_state(C.master_raw_to_pct(raw, top), not self.card.get(C.MASTER_SW, True))
        self.vol.setToolTip(C.volume_tip(C.master_raw_to_db(raw, top)))
        self.mic.set_state(self.card.get(C.MIC, 0) / 99, self.mic.btn.isChecked())

    def closeEvent(self, e):
        self.ctx.tone.stop()
        self.ctx.monitor.stop()
        self.ctx.meter.stop()
        super().closeEvent(e)
