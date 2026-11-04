# SPDX-License-Identifier: GPL-2.0-only
"""The app's pages, one per sidebar entry."""

import subprocess

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QMenu, QMessageBox, QPushButton,
                               QRadioButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QTableWidget,
                               QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from . import __version__
from . import card as C
from . import icons, pipewire, profiles
from . import theme as T
from .widgets import (Dial, EffectControl, EqGraph, LevelBar, PaletteCard, ProfileCarousel, Segmented,
                      SpeakerDiagram, Throttle, ToggleSwitch, VolumeRow, label)


def tool(icon_name, tip, size=24):
    b = QToolButton()
    b.setIcon(icons.icon(icon_name, active=T.ACCENT, size=size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def info_button(text):
    b = tool("info", text, 18)
    b.clicked.connect(lambda: QMessageBox.information(b.window(), "About this setting", text))
    return b


def hline():
    f = QFrame()
    f.setObjectName("sideSep")
    return f


class Banner(QFrame):
    """Inline notice with an optional action button."""

    def __init__(self, text="", action=None, warn=False):
        super().__init__()
        self.setObjectName("warnBanner" if warn else "banner")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("info", T.DANGER if warn else T.ACCENT_HI, 18))
        lay.addWidget(ic)
        self.text = label(text, wrap=True)
        lay.addWidget(self.text, 1)
        self.button = None
        if action:
            self.button = QPushButton(action)
            self.button.setObjectName("accentButton")
            self.button.setCursor(Qt.PointingHandCursor)
            lay.addWidget(self.button)


class Page(QWidget):
    title = ""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.card = ctx.card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(26, 14, 26, 18)
        self.lay.setSpacing(12)
        self.card.changed.connect(self._changed)
        self.card.info_changed.connect(self._changed)
        self.card.connection_changed.connect(self._on_connection)

    # Slots for long-lived signals are methods (not lambdas) so Qt drops the
    # connection when the page is deleted, e.g. when the palette changes.
    def _on_connection(self, *_):
        self.refresh()

    def _on_pw(self, *_):
        if self.isVisible():
            self.refresh()

    def header(self, text, switch=None, extra=()):
        row = QHBoxLayout()
        row.setSpacing(14)
        if switch is not None:
            row.addWidget(switch)
        row.addWidget(label(text, "pageTitle"))
        for w in extra:
            row.addWidget(w) if isinstance(w, QWidget) else row.addLayout(w)
        row.addStretch()
        self.lay.addLayout(row)
        return row

    def _changed(self, name):
        if self.isVisible():
            self.refresh()
        else:
            self._dirty = True

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        pass


# =====================================================================================
class SbxPage(Page):
    title = "SBX Profile"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.sbx = ToggleSwitch()
        self.sbx.setToolTip("SBX on/off")
        self.sbx.toggled.connect(lambda on: self.card.set(C.SBX, on))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(360)
        self.combo.activated.connect(lambda i: self.pick(self.combo.itemText(i)))
        self.modified = label("", "muted")
        plus = tool("plus", "Save the current settings as a new profile", 28)
        plus.clicked.connect(self.save_as)
        dots = tool("dots", "More", 28)
        dots.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self)
        self.act_save = self.menu.addAction("Save", self.save)
        self.menu.addAction("Save as new…", self.save_as)
        self.act_revert = self.menu.addAction("Revert", self.revert)
        self.menu.addSeparator()
        self.act_rename = self.menu.addAction("Rename…", self.rename)
        self.act_delete = self.menu.addAction("Delete", self.delete)
        dots.setMenu(self.menu)
        self.header("SBX Profile", self.sbx, [self.combo, plus, dots, self.modified])

        self.banner = Banner("", "Turn Direct Mode off")
        self.banner.button.clicked.connect(lambda: self.card.set(C.DIRECT, False))
        self.lay.addWidget(self.banner)

        self.carousel = ProfileCarousel()
        self.carousel.picked.connect(self.pick)
        self.lay.addWidget(self.carousel)

        cap = QHBoxLayout()
        cap.addStretch()
        cap.addWidget(label("Acoustic Engine", "subTitle"))
        cap.addStretch()
        cap.addWidget(info_button(
            "Surround widens the sound stage beyond your speakers or headphones.\n"
            "Crystalizer restores detail lost to compression (cymbals, effects).\n"
            "Bass adds low-end weight.\n"
            "Smart Volume evens out loud and quiet passages: Night keeps peaks down, "
            "Loud lifts quiet sounds.\n"
            "Dialog+ brings voices forward.\n\n"
            "All of these run on the AE-9's own DSP. They are heard when Direct Mode "
            "is off and SBX is on."))
        self.lay.addLayout(cap)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.effects = {}
        for e in C.EFFECTS:
            ec = EffectControl(C.EFFECT_LABELS[e])
            ec.levelChanged.connect(Throttle(lambda v, e=e: self.card.set(C.fx_level(e), v), 60))
            ec.toggled.connect(lambda on, e=e: self.card.set(C.fx_switch(e), on))
            self.effects[e] = ec
            row.addStretch()
            row.addWidget(ec)
        row.addStretch()
        self.svmode = Segmented(["Night", "Normal", "Loud"])
        self.svmode.selected.connect(lambda m: self.card.set(C.SV_MODE, m))
        self.effects["Smart Volume"].layout().addWidget(self.svmode, 0, Qt.AlignHCenter)
        self.lay.addLayout(row)
        self.lay.addStretch()
        self._profiles_shown = None

    # --- profiles ----------------------------------------------------------------
    def _active(self):
        return profiles.find(self.ctx.settings, self.ctx.settings["active_profile"])

    def pick(self, name):
        prof = profiles.find(self.ctx.settings, name)
        if not prof:
            return
        self.card.apply(prof)
        self.ctx.settings["active_profile"] = name
        self.ctx.profile_changed.emit()
        self.refresh()

    def _ask_name(self, title, default=""):
        name, ok = QInputDialog.getText(self, title, "Profile name:", text=default)
        name = name.strip()
        if not ok or not name:
            return None
        if any(p["name"] == name and p.get("builtin") for p in profiles.BUILTIN):
            QMessageBox.warning(self, title, f"“{name}” is a built-in profile. Pick another name.")
            return None
        return name

    def save_as(self):
        name = self._ask_name("New profile", "New Profile 1")
        if name:
            profiles.save_user(self.ctx.settings, name, self.card.snapshot())
            self.ctx.settings["active_profile"] = name
            self.ctx.profile_changed.emit()
            self.refresh(force=True)

    def save(self):
        p = self._active()
        if p and not p.get("builtin"):
            profiles.save_user(self.ctx.settings, p["name"], self.card.snapshot(), p.get("art", "custom"))
            self.refresh(force=True)
        else:
            self.save_as()

    def revert(self):
        p = self._active()
        if p:
            self.pick(p["name"])

    def rename(self):
        p = self._active()
        if not p or p.get("builtin"):
            return
        new = self._ask_name("Rename profile", p["name"])
        if new and new != p["name"]:
            profiles.rename_user(self.ctx.settings, p["name"], new)
            self.ctx.settings["active_profile"] = new
            self.ctx.profile_changed.emit()
            self.refresh(force=True)

    def delete(self):
        p = self._active()
        if not p or p.get("builtin"):
            return
        if QMessageBox.question(self, "Delete profile", f"Delete “{p['name']}”?") == QMessageBox.Yes:
            profiles.delete_user(self.ctx.settings, p["name"])
            self.ctx.settings["active_profile"] = "Default"
            self.ctx.profile_changed.emit()
            self.refresh(force=True)

    # --- state -----------------------------------------------------------------
    def refresh(self, force=False):
        s = self.ctx.settings
        all_p = profiles.all_profiles(s)
        names = [p["name"] for p in all_p]
        active = s["active_profile"] if s["active_profile"] in names else "Default"
        if force or self._profiles_shown != names:
            self._profiles_shown = names
            self.combo.blockSignals(True)
            self.combo.clear()
            self.combo.addItems(names)
            self.combo.blockSignals(False)
            self.carousel.set_profiles(all_p, active)
        self.combo.setCurrentText(active)
        if self.carousel.current != active:
            self.carousel.set_current(active)
        prof = profiles.find(s, active)
        if not self.card.present:
            return
        snap = self.card.snapshot()
        dirty = not profiles.matches(prof, snap)
        self.modified.setText("● modified" if dirty else "")
        self.act_revert.setEnabled(dirty)
        user = bool(prof and not prof.get("builtin"))
        self.act_rename.setEnabled(user)
        self.act_delete.setEnabled(user)
        self.act_save.setEnabled(user and dirty)

        direct = self.card.get(C.DIRECT, True)
        sbx = bool(self.card.get(C.SBX, False))
        self.sbx.setCheckedSilently(sbx)
        self.sbx.setEnabled(not direct)
        if direct:
            self.banner.text.setText("Direct Mode is on: audio goes straight to the DAC and the SBX "
                                     "effects are bypassed. Changes here are kept for when it's off.")
            self.banner.button.show()
        elif not sbx:
            self.banner.text.setText("SBX is off. Switch it on (top left) to hear the effects.")
            self.banner.button.hide()
        self.banner.setVisible(direct or not sbx)
        for e, ec in self.effects.items():
            on, lvl = snap["fx"][e]
            ec.set_state(on, lvl)
        self.svmode.set_value(snap["sv_mode"])


# =====================================================================================
class EqPage(Page):
    title = "Equalizer"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.sw = ToggleSwitch()
        self.sw.setToolTip("Equalizer on/off")
        self.sw.toggled.connect(lambda on: self.card.set(C.EQ_ON, on))
        self.header("Equalizer", self.sw, [info_button(
            "A 10-band graphic EQ on the AE-9's DSP, with Creative's 20 presets.\n\n"
            "Drag a point (or scroll over it) to change a band by 1 dB. Pre-gain, on the left, "
            "lowers the level going into the EQ so boosts don't clip.\n\n"
            "Save your own curves with +. The EQ is heard when Direct Mode is off and SBX is on.")])

        row = QHBoxLayout()
        row.setSpacing(10)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(320)
        self.combo.activated.connect(self._picked)
        plus = tool("plus", "Save this curve as a preset", 26)
        plus.clicked.connect(self.save_as)
        flat = tool("refresh", "Reset to flat", 24)
        flat.clicked.connect(lambda: self._apply_hw("Flat"))
        dots = tool("dots", "More", 26)
        dots.setPopupMode(QToolButton.InstantPopup)
        m = QMenu(self)
        self.act_rename = m.addAction("Rename", self.rename)
        self.act_delete = m.addAction("Delete", self.delete)
        dots.setMenu(m)
        row.addWidget(self.combo)
        row.addWidget(plus)
        row.addWidget(flat)
        row.addWidget(dots)
        row.addStretch()
        self.lay.addLayout(row)

        self.banner = Banner("")
        self.lay.addWidget(self.banner)

        self.graph = EqGraph(C.EQ_BAND_LABELS)
        self.graph.setMinimumHeight(300)
        self._band_set = Throttle(self._set_band, 40)
        self.graph.bandChanged.connect(self._band_set)
        self.lay.addWidget(self.graph, 1)
        self.lay.addWidget(label("Values are whole dB. Creative's presets use finer steps internally; "
                                 "editing a band rounds it.", "hint", wrap=True))
        self.user_name = None

    def _set_band(self, idx, db):
        self.card.set(C.EQ_CONTROLS[idx], int(db) + 12)
        if not self.card.get(C.EQ_ON):
            self.card.set(C.EQ_ON, True)

    def _apply_hw(self, name):
        self.card.set(C.EQ_PRESET, name, force=True)
        self.card.set(C.EQ_ON, True)
        self.refresh()

    def _picked(self, i):
        kind, name = self.combo.itemData(i) or (None, None)
        if kind == "hw":
            self._apply_hw(name)
        elif kind == "user":
            self.card.set_eq_db(self.ctx.settings["eq_presets"][name])
            self.card.set(C.EQ_ON, True)
            self.refresh()

    def save_as(self):
        name, ok = QInputDialog.getText(self, "Save EQ preset", "Preset name:", text="My EQ")
        name = name.strip()
        if ok and name:
            if name in profiles.HW_EQ_PRESETS:
                QMessageBox.warning(self, "Save EQ preset", "That name belongs to a built-in preset.")
                return
            presets = dict(self.ctx.settings["eq_presets"])
            presets[name] = self.card.eq_db()
            self.ctx.settings["eq_presets"] = presets
            self.refresh()

    def rename(self):
        if not self.user_name:
            return
        new, ok = QInputDialog.getText(self, "Rename EQ preset", "Preset name:", text=self.user_name)
        new = new.strip()
        if ok and new and new not in profiles.HW_EQ_PRESETS:
            presets = dict(self.ctx.settings["eq_presets"])
            presets[new] = presets.pop(self.user_name)
            self.ctx.settings["eq_presets"] = presets
            self.refresh()

    def delete(self):
        if not self.user_name:
            return
        presets = dict(self.ctx.settings["eq_presets"])
        presets.pop(self.user_name, None)
        self.ctx.settings["eq_presets"] = presets
        self.refresh()

    def refresh(self):
        if not self.card.present:
            return
        vals = self.card.eq_db()
        hw = self.card.get_item(C.EQ_PRESET)
        users = self.ctx.settings["eq_presets"]
        current = None
        if hw in profiles.HW_EQ_PRESETS and profiles.eq_equal(profiles.HW_EQ_PRESETS[hw], vals):
            current = ("hw", hw)
            vals = profiles.HW_EQ_PRESETS[hw]  # show the 0.1 dB curve
        else:
            for n, v in users.items():
                if profiles.eq_equal(v, vals):
                    current = ("user", n)
                    break
        self.user_name = current[1] if current and current[0] == "user" else None
        self.act_rename.setEnabled(bool(self.user_name))
        self.act_delete.setEnabled(bool(self.user_name))

        self.combo.blockSignals(True)
        self.combo.clear()
        for n in self.card.items(C.EQ_PRESET):
            self.combo.addItem(n, ("hw", n))
        if users:
            self.combo.insertSeparator(self.combo.count())
            for n in users:
                self.combo.addItem(icons.icon("star", T.ACCENT_HI, size=16), n, ("user", n))
        if current is None:
            self.combo.addItem("Custom (unsaved)", ("none", None))
            self.combo.setCurrentIndex(self.combo.count() - 1)
        else:
            for i in range(self.combo.count()):
                if self.combo.itemData(i) == current:
                    self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)

        on = bool(self.card.get(C.EQ_ON))
        self.sw.setCheckedSilently(on)
        self.graph.set_values(vals)
        audible = on and self.card.dsp_active
        self.graph.setActive(audible)
        if self.card.get(C.SCOUT):
            msg = "Scout Mode is on and is using the EQ. Turn it off to get your EQ back."
        elif self.card.get(C.DIRECT, True):
            msg = "Direct Mode is on, so the EQ is bypassed (Playback page)."
        elif not self.card.get(C.SBX):
            msg = "SBX is off, so the EQ is bypassed (SBX Profile page)."
        elif not on:
            msg = "The EQ is off. Moving a band switches it on."
        else:
            msg = ""
        self.banner.text.setText(msg)
        self.banner.setVisible(bool(msg))


# =====================================================================================
class PlaybackPage(Page):
    title = "Playback"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.header("Playback")
        tabs = QHBoxLayout()
        tabs.addWidget(label("Speakers/Headphones", "tabActive"))
        tabs.addStretch()
        self.lay.addLayout(tabs)

        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(10)

        dev = QHBoxLayout()
        dcol = QVBoxLayout()
        dcol.setSpacing(0)
        dcol.addWidget(label("Playback device:", "sectionTitle"))
        self.dev_name = label("—", "sectionTitle")
        dcol.addWidget(self.dev_name)
        dev.addLayout(dcol)
        dev.addStretch()
        self.set_default = QPushButton("Set Default")
        self.set_default.setMinimumWidth(150)
        self.set_default.clicked.connect(self._make_default)
        self.default_ok = QLabel()
        dev.addWidget(self.set_default)
        dev.addWidget(self.default_ok)
        left.addLayout(dev)

        left.addWidget(label("Output", "sectionTitle"))
        self.group = QButtonGroup(self)
        self.r_spk = QRadioButton()
        self.r_hp = QRadioButton()
        self.group.addButton(self.r_spk, 0)
        self.group.addButton(self.r_hp, 1)
        self.group.idClicked.connect(lambda i: self.card.set(C.OUTPUT, i))

        def out_row(radio, icon_name, title):
            w = QWidget()
            g = QGridLayout(w)
            g.setContentsMargins(0, 4, 0, 4)
            g.setHorizontalSpacing(12)
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon_name, T.TEXT, 22))
            g.addWidget(radio, 0, 0)
            g.addWidget(ic, 0, 1)
            t = label(title)
            t.setStyleSheet("font-size:15px;")
            g.addWidget(t, 0, 2)
            sub = label("", "muted")
            g.addWidget(sub, 1, 2, 1, 2)
            g.setColumnStretch(3, 1)
            return w, g, sub

        w, g, self.spk_sub = out_row(self.r_spk, "speaker", "Speakers")
        self.spk_cfg = QComboBox()
        self.spk_cfg.setToolTip("Speaker setup the DSP mixes for (used when Direct Mode is off)")
        self.spk_cfg.activated.connect(lambda i: self.card.set(C.SPEAKER_CFG, self.spk_cfg.itemData(i)))
        g.addWidget(self.spk_cfg, 0, 4)
        left.addWidget(w)
        w, g, self.hp_sub = out_row(self.r_hp, "headphones", "Headphones")
        left.addWidget(w)
        self.hp_sub.setText("Head unit headphone jack")

        left.addSpacing(6)
        dm = QHBoxLayout()
        dm.addWidget(label("Direct Mode", "sectionTitle"))
        dm.addWidget(info_button(
            "Direct Mode sends audio straight to the ESS DAC at the stream's own sample rate "
            "(up to 384 kHz), bypassing the DSP. SBX effects and the EQ are not heard.\n\n"
            "With Direct Mode off, audio goes through the Sound Core3D DSP at 96 kHz, so "
            "SBX, the EQ and Scout Mode work.\n\n"
            "Switching Direct Mode on during playback goes silent until the stream restarts "
            "(pause and play), same as on Windows."))
        dm.addStretch()
        left.addLayout(dm)
        dmr = QHBoxLayout()
        self.direct = ToggleSwitch()
        self.direct.toggled.connect(lambda on: self.card.set(C.DIRECT, on))
        self.direct_lbl = label("", "bigValue")
        dmr.addWidget(self.direct)
        dmr.addWidget(self.direct_lbl)
        dmr.addStretch()
        left.addLayout(dmr)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.diagram = SpeakerDiagram()
        right.addWidget(self.diagram, 0, Qt.AlignHCenter)
        self.test = QPushButton("Test")
        self.test.setFixedWidth(120)
        self.test.clicked.connect(self._test)
        right.addWidget(self.test, 0, Qt.AlignHCenter)
        self.test_hint = label("Plays a tone left, then right", "muted")
        right.addWidget(self.test_hint, 0, Qt.AlignHCenter)
        ctx.tone.step.connect(self._tone_step)

        grid.addLayout(left, 0, 0)
        grid.addLayout(right, 0, 1)

        # Filters / quality
        fl = QVBoxLayout()
        fh = QHBoxLayout()
        fh.addWidget(label("Filters", "sectionTitle"))
        fh.addStretch()
        fh.addWidget(info_button(
            "The ES9038 DAC's digital filter. Fast roll-off is flatter up to 20 kHz; "
            "slow roll-off rings less. Default keeps the filter Windows starts with."))
        fl.addLayout(fh)
        self.filter = QComboBox()
        self.filter.activated.connect(lambda i: self.card.set(C.DAC_FILTER, self.filter.itemData(i)))
        fl.addWidget(self.filter)
        ql = QVBoxLayout()
        qh = QHBoxLayout()
        qh.addWidget(label("Audio Quality", "sectionTitle"))
        qh.addStretch()
        qh.addWidget(info_button(
            "The sample rate PipeWire runs the card at. Automatic follows what's playing "
            "(48/96/192/384 kHz). A fixed rate resamples everything to it.\n\n"
            "44.1 kHz isn't supported by the driver yet, so that music gets resampled.\n"
            "With Direct Mode off the DSP itself runs at 96 kHz.\n\n"
            "This sets PipeWire's global clock (written to "
            "~/.config/pipewire/pipewire.conf.d/90-sbae9-sbc-rates.conf)."))
        ql.addLayout(qh)
        self.quality = QComboBox()
        self.quality.activated.connect(self._quality)
        ql.addWidget(self.quality)
        self.now_playing = label("", "muted")
        ql.addWidget(self.now_playing)
        fl.addWidget(label("", "muted"))
        grid.addLayout(fl, 1, 0, Qt.AlignTop)
        grid.addLayout(ql, 1, 1, Qt.AlignTop)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        self.lay.addLayout(grid)
        self.lay.addStretch()
        self._quality_built = None
        ctx.pw.updated.connect(self._on_pw)

    def _make_default(self):
        n = self.ctx.pw.nodes
        if n.sink:
            pipewire.set_default(n.sink["id"])
            self.ctx.pw.refresh()

    def _test(self):
        if self.ctx.tone.running:
            self.ctx.tone.stop()
            return
        n = self.ctx.pw.nodes
        self.ctx.tone.start(n.sink["name"] if n.sink else None)

    def _tone_step(self, ch):
        self.diagram.set_state(playing=ch)
        self.test.setText("Stop" if ch else "Test")

    def _quality(self, i):
        mode = self.quality.itemData(i)
        pipewire.set_rate_mode(mode)
        self.ctx.settings["rate_mode"] = mode
        QTimer.singleShot(300, self.ctx.pw.refresh)

    def refresh(self):
        n = self.ctx.pw.nodes
        self.dev_name.setText("Sound Blaster AE-9" if n.sink else "AE-9 not found in PipeWire")
        self.set_default.setEnabled(bool(n.sink) and not n.sink_is_default)
        self.set_default.setText("Default device" if n.sink_is_default else "Set Default")
        self.default_ok.setPixmap(icons.pixmap("check", T.ACCENT_HI if n.sink_is_default else T.DIM, 22))
        fmt = n.sink_format()
        if fmt and fmt[0]:
            self.now_playing.setText(f"Running now: {fmt[0] / 1000:g} kHz, {fmt[1]}")
        else:
            self.now_playing.setText("Idle")

        bits = C.module_param("pcm_bits") or "24"
        rates_param = C.module_param("pcm_rates") or "0"
        modes = [0] + pipewire.RATES if rates_param != "0" else [48000]
        if self._quality_built != (bits, tuple(modes)):
            self._quality_built = (bits, tuple(modes))
            self.quality.clear()
            for m in modes:
                text = (f"{bits} bit, automatic (48–384 kHz)" if m == 0 else f"{bits} bit, {m / 1000:g} kHz")
                self.quality.addItem(text, m)
        cur = pipewire.current_rate_mode()
        i = self.quality.findData(cur)
        self.quality.setCurrentIndex(i if i >= 0 else 0)

        if not self.card.present:
            return
        out = self.card.get(C.OUTPUT, 0)
        (self.r_hp if out == 1 else self.r_spk).setChecked(True)
        cfg = self.card.get_item(C.SPEAKER_CFG) or "2.1"
        if self.spk_cfg.count() != len(self.card.items(C.SPEAKER_CFG)):
            self.spk_cfg.clear()
            for k, it in enumerate(self.card.items(C.SPEAKER_CFG)):
                self.spk_cfg.addItem(f"{it} Speakers", k)
        self.spk_cfg.setCurrentIndex(self.card.get(C.SPEAKER_CFG, 0) or 0)
        direct = bool(self.card.get(C.DIRECT, True))
        self.spk_cfg.setEnabled(not direct)
        self.spk_sub.setText(f"{cfg} {'Stereo' if cfg == '2.0' else 'Stereo + Sub'} · RCA outputs")
        self.diagram.set_state(mode="headphones" if out == 1 else "speakers", config=cfg)
        self.direct.setCheckedSilently(direct)
        self.direct_lbl.setText("On — DSP bypassed" if direct else "Off — SBX / EQ active")
        names = {"Default": "Default (Windows startup filter)", "Fast": "Fast Roll Off",
                 "Slow": "Slow Roll Off"}
        if self.filter.count() != len(self.card.items(C.DAC_FILTER)):
            self.filter.clear()
            for k, it in enumerate(self.card.items(C.DAC_FILTER)):
                self.filter.addItem(names.get(it, it), k)
        self.filter.setCurrentIndex(self.card.get(C.DAC_FILTER, 0) or 0)


# =====================================================================================
class RecordingPage(Page):
    title = "Recording"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.header("Recording")
        dev = QHBoxLayout()
        dcol = QVBoxLayout()
        dcol.setSpacing(0)
        dcol.addWidget(label("Recording device:", "sectionTitle"))
        self.dev_name = label("—", "sectionTitle")
        dcol.addWidget(self.dev_name)
        dev.addLayout(dcol)
        dev.addStretch()
        self.set_default = QPushButton("Set Default")
        self.set_default.setMinimumWidth(150)
        self.set_default.clicked.connect(self._make_default)
        self.default_ok = QLabel()
        dev.addWidget(self.set_default)
        dev.addWidget(self.default_ok)
        self.lay.addLayout(dev)

        g = QGridLayout()
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(14)
        g.addWidget(label("Microphone (XLR / head unit)", "subTitle"), 0, 0, 1, 3)
        g.addWidget(label("Level"), 1, 0)
        self.mic = VolumeRow("mic", "mic-off")
        self.mic.valueChanged.connect(Throttle(lambda v: self.card.set(C.MIC, round(v * 99)), 40))
        self.mic.muteToggled.connect(self._mute)
        g.addWidget(self.mic, 1, 1, 1, 2)
        g.addWidget(label("Input"), 2, 0)
        meters = QVBoxLayout()
        meters.setSpacing(5)
        self.meter_l, self.meter_r = LevelBar(), LevelBar()
        meters.addWidget(self.meter_l)
        meters.addWidget(self.meter_r)
        g.addLayout(meters, 2, 1)
        self.peak = label("", "muted")
        self.peak.setMinimumWidth(66)
        g.addWidget(self.peak, 2, 2)
        g.addWidget(label("XLR Gain"), 3, 0)
        self.xlr = Segmented(["0", "1", "2"], labels={"0": "0 dB", "1": "+10 dB", "2": "+20 dB"})
        self.xlr.selected.connect(lambda v: self.card.set(C.XLR_GAIN, int(v)))
        xr = QHBoxLayout()
        xr.addWidget(self.xlr)
        xr.addWidget(info_button("Microphone preamp boost on the XLR input. Use +20 dB for quiet "
                                 "dynamic mics, 0 dB for loud sources or condensers."))
        xr.addStretch()
        g.addLayout(xr, 3, 1)
        g.addWidget(label("Listen"), 4, 0)
        lr = QHBoxLayout()
        self.listen = ToggleSwitch()
        self.listen.toggled.connect(self._listen)
        lr.addWidget(self.listen)
        lr.addWidget(label("Hear the microphone through the default output "
                           "(use headphones to avoid feedback)", "muted"))
        lr.addStretch()
        g.addLayout(lr, 4, 1, 1, 2)
        g.setColumnStretch(1, 1)
        self.lay.addLayout(g)
        self.lay.addSpacing(8)
        self.lay.addWidget(label(
            "Phantom power (48V) is the button on the head unit's front panel. "
            "The driver records at 48 kHz, 2 channels.", "hint", wrap=True))
        self.lay.addStretch()
        ctx.meter.levels.connect(self._levels)
        ctx.monitor.state.connect(self.listen.setCheckedSilently)
        ctx.pw.updated.connect(self._on_pw)

    def _make_default(self):
        n = self.ctx.pw.nodes
        if n.source:
            pipewire.set_default(n.source["id"])
            self.ctx.pw.refresh()

    def _mute(self, muted):
        n = self.ctx.pw.nodes
        if n.source:
            pipewire.set_mute(n.source["id"], muted)

    def _listen(self, on):
        n = self.ctx.pw.nodes
        if on and n.source:
            self.ctx.monitor.start(n.source["name"])
        else:
            self.ctx.monitor.stop()

    def _levels(self, l, r):
        self.meter_l.set_db(l)
        self.meter_r.set_db(r)
        top = max(l, r)
        self.peak.setText(f"{top:.0f} dBFS" if top > -89 else "—")

    def showEvent(self, e):
        super().showEvent(e)
        n = self.ctx.pw.nodes
        if n.source:
            self.ctx.meter.start(n.source["name"])

    def hideEvent(self, e):
        super().hideEvent(e)
        self.ctx.meter.stop()

    def refresh(self):
        n = self.ctx.pw.nodes
        self.dev_name.setText("Sound Blaster AE-9 (XLR mic)" if n.source else "AE-9 input not found in PipeWire")
        self.set_default.setEnabled(bool(n.source) and not n.source_is_default)
        self.set_default.setText("Default device" if n.source_is_default else "Set Default")
        self.default_ok.setPixmap(icons.pixmap("check", T.ACCENT_HI if n.source_is_default else T.DIM, 22))
        if n.source and not self.ctx.meter._proc and self.isVisible():
            self.ctx.meter.start(n.source["name"])
        muted = False
        if n.source:
            _, muted = pipewire.get_volume(n.source["id"])
        if not self.card.present:
            return
        raw = self.card.get(C.MIC, 0)
        self.mic.set_state(raw / 99, muted, "muted" if raw == 0 else f"{C.mic_raw_to_db(raw):+d} dB")
        self.xlr.set_value(str(self.card.get(C.XLR_GAIN, 1)))


# =====================================================================================
class ScoutPage(Page):
    title = "Scout Mode"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.header("Scout Mode")
        box = QFrame()
        box.setObjectName("card")
        bl = QHBoxLayout(box)
        bl.setContentsMargins(24, 24, 24, 24)
        bl.setSpacing(28)
        art = QLabel()
        art.setPixmap(icons.pixmap("scout", T.ACCENT_HI, 120))
        bl.addWidget(art, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(12)
        top = QHBoxLayout()
        self.sw = ToggleSwitch(size=(52, 26))
        self.sw.toggled.connect(lambda on: self.card.set(C.SCOUT, on))
        top.addWidget(self.sw)
        self.state = label("", "pageTitle")
        top.addWidget(self.state)
        top.addStretch()
        col.addLayout(top)
        col.addWidget(label(
            "Hear your enemies before they hear you. Scout Mode brings out footsteps, reloads and "
            "distant movement in games.", wrap=True))
        col.addWidget(label(
            "While it's on, the card switches Smart Volume on at 90 and uses Creative's Scout EQ "
            "curve. Your own Smart Volume and EQ settings come back when you switch it off.",
            "muted", wrap=True))
        col.addStretch()
        bl.addLayout(col, 1)
        self.lay.addWidget(box)
        self.banner = Banner("", "Enable DSP effects")
        self.banner.button.clicked.connect(self._enable)
        self.lay.addWidget(self.banner)
        self.lay.addStretch()

    def _enable(self):
        self.card.set(C.DIRECT, False)
        self.card.set(C.SBX, True)

    def refresh(self):
        if not self.card.present:
            return
        on = bool(self.card.get(C.SCOUT))
        self.sw.setCheckedSilently(on)
        self.state.setText("On" if on else "Off")
        self.banner.text.setText("Scout Mode works through the DSP: it needs Direct Mode off and SBX on.")
        self.banner.setVisible(not self.card.dsp_active)


# =====================================================================================
class MixerPage(Page):
    title = "Mixer"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.header("Mixer")
        g = QGridLayout()
        g.setHorizontalSpacing(22)
        g.setVerticalSpacing(14)
        r = 0
        g.addWidget(label("Playback", "sectionTitle"), r, 0)
        r += 1
        self.out_name = label("Speakers")
        g.addWidget(self.out_name, r, 0)
        self.master = VolumeRow()
        self.master.valueChanged.connect(Throttle(
            lambda v: self.card.set(C.MASTER, C.master_pct_to_raw(v)), 30))
        self.master.muteToggled.connect(lambda m: self.card.set(C.MASTER_SW, not m))
        g.addWidget(self.master, r, 1)
        r += 1
        g.addWidget(label("Balance"), r, 0)
        bal = QHBoxLayout()
        bal.addWidget(label("L", "muted"))
        self.balance = QSlider(Qt.Horizontal)
        self.balance.setRange(-100, 100)
        self.balance.setStyleSheet(f"QSlider::sub-page:horizontal{{background:{T.TRACK};}}")
        self.balance.valueChanged.connect(Throttle(self._balance, 60))
        self.balance.setToolTip("Double-click the label to centre")
        bal.addWidget(self.balance, 1)
        bal.addWidget(label("R", "muted"))
        bal.addSpacing(10)
        self.bal_val = label("", "muted")
        self.bal_val.setMinimumWidth(66)
        bal.addWidget(self.bal_val)
        center = QPushButton("Centre")
        center.clicked.connect(lambda: self.balance.setValue(0))
        bal.addWidget(center)
        g.addLayout(bal, r, 1)
        r += 1
        g.addWidget(label("", "muted"), r, 0)
        r += 1
        g.addWidget(label("Recording", "sectionTitle"), r, 0)
        r += 1
        g.addWidget(label("Microphone"), r, 0)
        self.mic = VolumeRow("mic", "mic-off")
        self.mic.valueChanged.connect(Throttle(lambda v: self.card.set(C.MIC, round(v * 99)), 40))
        self.mic.muteToggled.connect(self._mic_mute)
        g.addWidget(self.mic, r, 1)
        r += 1
        g.addWidget(label("XLR Gain"), r, 0)
        self.xlr = Segmented(["0", "1", "2"], labels={"0": "0 dB", "1": "+10 dB", "2": "+20 dB"})
        self.xlr.selected.connect(lambda v: self.card.set(C.XLR_GAIN, int(v)))
        xr = QHBoxLayout()
        xr.addWidget(self.xlr)
        xr.addStretch()
        g.addLayout(xr, r, 1)
        g.setColumnStretch(1, 1)
        g.setColumnMinimumWidth(0, 130)
        box = QWidget()
        box.setMaximumWidth(760)
        box.setLayout(g)
        self.lay.addWidget(box)
        self.lay.addWidget(label(
            "Speakers and headphones each keep their own volume on the card. "
            "Balance is applied by PipeWire.", "hint", wrap=True))
        self.lay.addStretch()
        ctx.pw.updated.connect(self._on_pw)

    def _balance(self, v):
        n = self.ctx.pw.nodes
        cv = n.sink_channel_volumes()
        if n.sink and cv:
            pipewire.set_balance(n.sink["id"], v / 100, cv)
            self.bal_val.setText("centre" if v == 0 else f"{'L' if v < 0 else 'R'} {abs(v)}%")

    def _mic_mute(self, muted):
        n = self.ctx.pw.nodes
        if n.source:
            pipewire.set_mute(n.source["id"], muted)

    def refresh(self):
        n = self.ctx.pw.nodes
        if not self.balance.isSliderDown():
            b = int(round(pipewire.balance_of(n.sink_channel_volumes()) * 100))
            self.balance.blockSignals(True)
            self.balance.setValue(b)
            self.balance.blockSignals(False)
            self.bal_val.setText("centre" if b == 0 else f"{'L' if b < 0 else 'R'} {abs(b)}%")
        if not self.card.present:
            return
        self.out_name.setText("Headphones" if self.card.get(C.OUTPUT) == 1 else "Speakers")
        raw = self.card.get(C.MASTER, 0)
        muted = not self.card.get(C.MASTER_SW, True)
        self.master.set_state(C.master_raw_to_pct(raw), muted,
                              f"{C.master_raw_to_db(raw):.1f} dB" if raw else "−∞ dB")
        mraw = self.card.get(C.MIC, 0)
        mm = pipewire.get_volume(n.source["id"])[1] if n.source else False
        self.mic.set_state(mraw / 99, mm, "muted" if mraw == 0 else f"{C.mic_raw_to_db(mraw):+d} dB")
        self.xlr.set_value(str(self.card.get(C.XLR_GAIN, 1)))


# =====================================================================================
class SettingsPage(Page):
    title = "Settings"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.header("Settings")
        self.lay.addWidget(label("Device", "sectionTitle"))
        self.info = label("", "muted", wrap=True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lay.addWidget(self.info)

        self.rates_banner = Banner("High sample rates (96–384 kHz) are off in the driver "
                                   "(pcm_rates=0). Turn them on until the next reboot?",
                                   "Enable (asks for password)")
        self.rates_banner.button.clicked.connect(self._enable_rates)
        self.lay.addWidget(self.rates_banner)

        self.lay.addWidget(label("Appearance", "sectionTitle"))
        pal = QHBoxLayout()
        pal.setSpacing(12)
        self.palettes = {}
        for key in T.PALETTES:
            pc = PaletteCard(key)
            pc.set_selected(key == T.CURRENT)
            pc.clicked.connect(self._pick_palette)
            self.palettes[key] = pc
            pal.addWidget(pc)
        pal.addStretch()
        self.lay.addLayout(pal)

        self.lay.addWidget(label("App", "sectionTitle"))
        self.restore = QCheckBox("Re-apply the active SBX profile when the app starts")
        self.restore.setToolTip("Usually not needed: the driver and alsa-state keep the card's "
                                "settings across reboots.")
        self.restore.setChecked(bool(ctx.settings["restore_on_start"]))
        self.restore.toggled.connect(lambda on: ctx.settings.__setitem__("restore_on_start", on))
        self.lay.addWidget(self.restore)
        row = QHBoxLayout()
        reset = QPushButton("Reset SBX and EQ to defaults")
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        mixer = QPushButton("Open alsamixer")
        mixer.clicked.connect(self._alsamixer)
        row.addWidget(mixer)
        row.addStretch()
        self.lay.addLayout(row)

        self.lay.addWidget(label("All hardware controls", "sectionTitle"))
        self.lay.addWidget(label("Every ALSA control the driver exposes, including ones that are greyed out "
                                 "(inactive) in the current mode. Changes apply right away.", "hint", wrap=True))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Control", "Value", "State"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(420)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setColumnWidth(1, 200)
        self.lay.addWidget(self.table, 1)
        self._editors = {}

    def _pick_palette(self, key):
        if key != T.CURRENT:
            self.ctx.palette_requested.emit(key)

    def _enable_rates(self):
        path = f"{C.MODULE_PARAMS}/pcm_rates"
        try:
            subprocess.run(["pkexec", "sh", "-c", f"echo 1 > {path}"], timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.refresh()

    def _alsamixer(self):
        for term in (["konsole", "-e"], ["gnome-terminal", "--"], ["xterm", "-e"]):
            try:
                subprocess.Popen(term + ["alsamixer", "-c", str(self.card.card_index)])
                return
            except OSError:
                continue

    def _reset(self):
        if QMessageBox.question(self, "Reset", "Reset all SBX effects and the EQ to the driver defaults?") \
                != QMessageBox.Yes:
            return
        self.card.set(C.SCOUT, False)
        self.card.apply(profiles.BUILTIN[0])
        self.card.set(C.EQ_ON, False)
        self.ctx.settings["active_profile"] = "Default"
        self.ctx.profile_changed.emit()

    def _editor(self, c):
        if c.type == 1:
            w = QCheckBox()
            w.toggled.connect(lambda on, n=c.name: self.card.set(n, on))
        elif c.type == 3:
            w = QComboBox()
            w.addItems(c.items)
            w.activated.connect(lambda i, n=c.name: self.card.set(n, i))
        else:
            w = QSpinBox()
            w.setRange(c.min, c.max)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, n=c.name: self.card.set(n, v))
        return w

    def refresh(self):
        mod = C.module_version() or "not loaded"
        rates = C.module_param("pcm_rates")
        bits = C.module_param("pcm_bits")
        n = self.ctx.pw.nodes
        lines = [
            f"<b>{self.card.longname or 'Sound Blaster AE-9 not found'}</b>",
            f"ALSA card {self.card.card_index} · driver snd-hda-codec-creative-ae9 {mod}",
            f"Playback rates: {'48 kHz only' if rates == '0' else '48/96/192/384 kHz' if rates == '1' else '+ 44.1/88.2 kHz (experimental)' if rates == '2' else '?'}"
            f" · sample bits: {bits or '?'}",
            f"PipeWire sink: {n.sink['name'] if n.sink else '—'}",
            f"PipeWire source: {n.source['name'] if n.source else '—'}",
            f"Sound Blaster Command for Linux {__version__}",
        ]
        self.info.setText("<br>".join(lines))
        self.rates_banner.setVisible(rates == "0")
        ctrls = self.card.all_controls()
        if self.table.rowCount() != len(ctrls):
            self.table.setRowCount(len(ctrls))
            self._editors = {}
            for i, c in enumerate(ctrls):
                self.table.setItem(i, 0, QTableWidgetItem(c.name))
                ed = self._editor(c)
                self._editors[c.name] = ed
                self.table.setCellWidget(i, 1, ed)
                self.table.setItem(i, 2, QTableWidgetItem())
        for i, c in enumerate(ctrls):
            ed = self._editors.get(c.name)
            v = self.card.get(c.name)
            if ed is None or v is None:
                continue
            ed.blockSignals(True)
            if isinstance(ed, QCheckBox):
                ed.setChecked(bool(v))
            elif isinstance(ed, QComboBox):
                ed.setCurrentIndex(v)
            else:
                ed.setValue(v)
            ed.blockSignals(False)
            st = self.table.item(i, 2)
            st.setText("inactive" if c.inactive else "active")
            st.setForeground(QColor(T.DIM if c.inactive else T.TEXT))
