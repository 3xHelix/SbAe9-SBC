# SPDX-License-Identifier: GPL-2.0-only
"""The AE-7 (experimental): the card as driver kit 11 runs it.

Its controls are tests/fixtures/ae7_controls.json, written from the kit 11
driver's control list (ae7-k11): kit 11, PROVISIONAL, regenerate it from
driver 0.13.0. The AE-9's own tests stay as they are; these only cover the
AE-7's differences.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support as S
from sbae9kit import testing as kt
from sbcommand import card as C, config, ctl, pages, pipewire, window


class AE7Case(S.AppTestCase):
    direct_switch = False     # ae7=4 adds the Direct Mode Switch

    def setup_card(self):
        S.sound_cards(kt.AE7_CARD)
        S.use_controls("ae7_controls.json")
        S.PARAMS["pcm_dsd"] = "Y"     # the module has the option; the AE-7 still plays no DSD

    def setUp(self):
        super().setUp()
        if self.direct_switch:
            self.mixer.add_bool(C.DIRECT, False)
            self.ctx.card.changed.emit(C.DIRECT)
            S.process()

    def ctl(self, *args):
        with mock.patch.object(ctl.alsa, "Mixer", lambda idx: self.mixer), \
                mock.patch.object(ctl.Card, "close", lambda self: None):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = ctl.main(list(args))
        return code, json.loads(buf.getvalue())


class MasterTest(AE7Case):
    def test_scale(self):
        self.assertEqual(self.ctx.card.master_max(), 180)
        self.assertEqual(C.master_raw_to_db(180, 180), 0.0)
        self.assertEqual(C.master_raw_to_db(0, 180), -90.0)
        self.assertEqual(C.master_pct_to_raw(1.0, 180), 180)

    def test_window_volume(self):
        w = self.window()
        self.assertEqual(w.vol.toolTip(), "Volume -10.0 dB")

    def test_ae9_scale_unchanged(self):
        self.assertEqual(C.master_raw_to_db(254), 0.0)
        self.assertEqual(C.master_raw_to_db(0), -127.0)


class NoDirectSwitchTest(AE7Case):
    def test_dsp_mode(self):
        card = self.ctx.card
        self.assertFalse(card.has_direct())
        self.assertFalse(card.is_direct())
        self.assertTrue(C.no_direct(card))

    def test_effects_not_bypassed(self):
        self.mixer.external(C.SBX, True)
        S.process()
        self.assertTrue(self.ctx.card.dsp_active)

    def test_toggles_hidden(self):
        w = self.window()
        self.assertTrue(w.direct_switch.isHidden())
        pg = self.page(pages.PlaybackPage)
        self.assertFalse(pg.direct.isEnabled())
        self.assertIn("DSP only", pg.direct_lbl.text())
        self.assertTrue(pg.spk_cfg.isEnabled())

    def test_ctl(self):
        code, st = self.ctl("status")
        self.assertEqual((st["card"], st["card_name"]), ("AE-7", "Sound Blaster AE-7"))
        self.assertFalse(st["has_direct"])
        self.assertFalse(st["direct"])
        self.assertTrue(st["sbx_enabled"])
        code, res = self.ctl("direct", "1")
        self.assertFalse(res["ok"])
        self.assertIn("AE-7 has no Direct Mode Switch", res["error"])


class DirectSwitchTest(AE7Case):
    direct_switch = True

    def test_toggle_works(self):
        card = self.ctx.card
        self.assertTrue(card.has_direct())
        self.assertFalse(card.is_direct())
        w = self.window()
        self.assertFalse(w.direct_switch.isHidden())
        self.mixer.external(C.DIRECT, True)
        S.process()
        self.assertTrue(card.is_direct())
        code, st = self.ctl("status")
        self.assertTrue(st["has_direct"])
        self.assertTrue(st["direct"])
        code, res = self.ctl("direct", "0")
        self.assertTrue(res["ok"])
        self.assertFalse(self.mixer.values[C.DIRECT])


class HiddenTest(AE7Case):
    def test_no_dsd(self):
        self.assertFalse(C.has_native_dsd())
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        self.assertTrue(pg.dsd_box.isHidden())

    def test_no_encoder_page(self):
        enc = next(e for e in window.NAV if e and e[0] == "Encoder")
        self.assertFalse(window.page_offered(enc))

    def test_no_speaker_setup(self):
        pg = self.page(pages.PlaybackPage)
        self.assertTrue(pg.setup.box.isHidden())
        self.assertIn("AE-7 has no speaker setup", pg.setup.missing.text())
        self.assertNotIn("newer", pg.setup.missing.text())

    def test_no_head_unit_or_optical(self):
        self.assertFalse(C.has_head_unit())
        self.assertIsNone(C.optical_out_max())

    def test_no_louder_warning(self):
        S.PARAMS["version"] = "0.13.0"
        self.assertFalse(C.dsp_full_level())

    def test_crystalvoice_without_mic_monitor(self):
        """Kit 11 / 0.13.0: the AE-9's CrystalVoice controls, no mic monitor."""
        card = self.ctx.card
        self.assertTrue(card.has(C.VC))
        self.assertEqual(len(card.items(C.VC_MORPH)), 18)
        self.assertEqual(len(card.items(C.VC_MICEQ)), 12)
        self.assertFalse(card.has(C.MIC_MONITOR))
        self.assertEqual(card.control(C.MIC_GAIN).max, 2)     # 0 / +10 / +20 dB
        self.assertEqual(card.items(C.SPEAKER_CFG), ["2.0", "2.1", "4.0", "4.1", "5.1"])

    def test_shared_sbx_and_input_controls(self):
        """0.13.0: Headphone Profile (tested on a real AE-7), Headphone
        Virtualization and Capture Bit Depth, as on the AE-9."""
        card = self.ctx.card
        self.assertEqual(len(card.items(C.HP_PROFILE)), 37)
        self.assertFalse(C.untested(C.HP_PROFILE))
        self.assertTrue(card.has(C.HP_VIRT))
        self.assertEqual(card.items(C.CAP_BIT_DEPTH), ["24-bit", "32-bit"])
        pg = self.page(pages.PlaybackPage)
        self.assertFalse(pg.hp_prof_row.isHidden())
        self.assertNotIn("haven't been tested", pg.hp_prof_note.text())
        self.assertFalse(pg.virt_row.isHidden())
        self.assertTrue(pg.line_virt.isHidden())

    def test_virtualization_locked_on(self):
        """0.13.0-rc2: the AE-7 keeps Headphone Virtualization on (as Windows)."""
        self.mixer.external(C.HP_VIRT, False)      # an off write that snapped back, say
        S.process()
        pg = self.page(pages.PlaybackPage)
        self.assertTrue(C.locked_on(C.HP_VIRT))
        self.assertTrue(pg.hp_virt.isChecked())
        self.assertFalse(pg.hp_virt.isEnabled())
        self.assertIn("On the AE-7 this stays on.", pg.virt_note.text())
        self.assertIn("turn SBX Surround off or use Direct Mode", pg.hp_virt.toolTip())

    def test_dac_filter_text(self):
        self.assertNotIn("ES9038", pages.dac_filter_tip())
        self.assertIn("Minimum Phase", pages.dac_filter_tip())

    def test_bit_depth_32_fixed(self):
        self.assertEqual(C.fixed_bits(), "32-bit")
        pg = self.page(pages.PlaybackPage)
        self.assertEqual(pg.depth.currentText(), "32-bit")
        self.assertFalse(pg.depth.isEnabled())
        code, st = self.ctl("status")
        self.assertEqual(st["depth_fixed"], "32-bit")


class RatesTest(AE7Case):
    """Kit 11: DSP mode 48 kHz only (stereo and 5.1); Direct Mode stereo at
    44.1-384 kHz, no 176.4; mic 44.1 / 48 / 96; What U Hear 44.1 / 48."""

    def test_offered(self):
        self.assertEqual(pipewire.offered_rates(), [44100, 48000, 88200, 96000, 192000, 384000])
        self.assertEqual(pipewire.allowed_now(), pipewire.offered_rates())
        self.assertFalse(C.plays_176k4())

    def test_dsp_mode(self):
        self.assertEqual(self.ctx.rate_set(), [48000])
        self.assertFalse(C.dsp_96k())
        self.assertEqual(C.surround_max(), 48000)
        self.assertEqual(pipewire.playable_now(False, True), [48000])

    def test_direct_mode(self):
        self.assertEqual(pipewire.playable_now(True, False), [44100, 48000, 88200, 96000, 192000, 384000])
        self.assertEqual(pipewire.playable_now(True, True), [48000])     # 5.1: DSP mode only

    def test_inputs(self):
        self.assertEqual(pages.input_rates(), (44100, 48000))
        self.assertFalse(C.wuh_96k())
        self.assertEqual(C.board_rates("mic_rates"), (44100, 48000, 96000))

    def test_ctl(self):
        code, st = self.ctl("status")
        self.assertEqual(st["rates"], [44100, 48000, 88200, 96000, 192000, 384000])
        self.assertEqual(st["playable"], [48000])

    def test_ae9_unchanged(self):
        S.sound_cards(kt.AE9_CARD)
        self.assertIsNone(C.board_rates("direct_rates"))
        self.assertEqual(pipewire.offered_rates(), pipewire.RATES)


class DirectRatesTest(AE7Case):
    direct_switch = True

    def test_rate_set_follows_the_switch(self):
        self.assertEqual(self.ctx.rate_set(), [48000])
        self.mixer.external(C.DIRECT, True)
        S.process()
        self.assertEqual(max(self.ctx.rate_set()), 384000)
        self.assertNotIn(176400, self.ctx.rate_set())


class HeadphoneGainTest(AE7Case):
    def test_picker(self):
        pg = self.page(pages.PlaybackPage)
        self.assertFalse(pg.hp_gain.isHidden())
        self.assertEqual([pg.hp_gain.itemText(k) for k in range(pg.hp_gain.count())],
                         ["Low (16 - 31 ohm)", "Normal (32 - 149 ohm)", "High (150 - 600 ohm)"])
        self.assertEqual(pg.hp_gain.currentIndex(), 1)
        pg.hp_gain.activated.emit(2)
        self.assertEqual(self.mixer.values[C.HP_GAIN], 2)

    def test_labels_fall_back_to_the_items(self):
        self.assertEqual(C.hp_gain_labels(["Low", "High"]), ["Low", "High"])

    def test_hidden_without_the_control(self):
        del self.mixer.controls[C.HP_GAIN]
        pg = self.page(pages.PlaybackPage)
        self.assertTrue(pg.hp_gain.isHidden())

    def test_hidden_on_the_ae9(self):
        S.sound_cards(kt.AE9_CARD)
        S.MIXER_SPEC[0] = None
        self.ctx.card.switch_to("AE9")
        S.process()
        pg = self.page(pages.PlaybackPage)
        self.assertTrue(pg.hp_gain.isHidden())


class PlugTest(AE7Case):
    def test_headphone_jack(self):
        pg = self.page(pages.PlaybackPage)
        self.assertEqual(pg.hp_sub.text(), "Headphone jack: nothing plugged in")
        self.assertTrue(pg.hp_hint.isHidden())
        self.mixer.external(C.CARD_PHONES, True)
        S.process()
        pg.refresh()
        self.assertEqual(pg.hp_sub.text(), "Headphone jack: plugged in")
        self.assertFalse(pg.hp_hint.isHidden())
        self.assertNotIn("head unit", pg.hp_hint.text.text())

    def test_mic_jack(self):
        pg = self.page(pages.RecordingPage)
        pg.refresh()
        self.assertEqual(pg.mic_jack.text(), "Line-in / Mic-in jack: nothing plugged in")
        self.mixer.external(C.CARD_MIC, True)
        S.process()
        pg.refresh()
        self.assertEqual(pg.mic_jack.text(), "Line-in / Mic-in jack: plugged in")

    def test_without_plug_controls(self):
        for n in (C.CARD_PHONES, C.CARD_MIC):
            del self.mixer.controls[n]
        pg = self.page(pages.PlaybackPage)
        self.assertEqual(pg.hp_sub.text(), pages.hp_where())


class PerCardSettingsTest(S.AppTestCase):
    """Rate, quantum and encoder picks are kept per card; the AE-9's stay at
    the settings file's top level, as before."""

    def test_ae9_at_the_top_level(self):
        self.ctx.settings["rate_mode"] = 96000
        with open(self.ctx.settings.path) as f:
            data = json.load(f)
        self.assertEqual(data["rate_mode"], 96000)
        self.assertNotIn("cards", data)

    def test_each_card_its_own(self):
        two = (kt.HDMI_CARD, kt.AE7_CARD, kt.AE9_CARD)
        S.sound_cards(*two)
        st = self.ctx.settings
        C.select("AE9")
        st["rate_mode"] = 176400
        st["quantum"] = 1024
        C.select("AE7")
        self.assertIsNone(st["rate_mode"])           # the AE-7 starts from the defaults
        self.assertEqual(st["quantum"], 0)
        st["rate_mode"] = 44100
        self.assertEqual(st["rate_mode"], 44100)
        C.select("AE9")
        self.assertEqual((st["rate_mode"], st["quantum"]), (176400, 1024))
        with open(st.path) as f:
            data = json.load(f)
        self.assertEqual(data["rate_mode"], 176400)
        self.assertEqual(data["cards"], {"AE7": {"rate_mode": 44100}})

    def test_other_settings_shared(self):
        S.sound_cards(kt.AE7_CARD)
        self.ctx.settings["palette"] = "x"
        with open(self.ctx.settings.path) as f:
            self.assertEqual(json.load(f)["palette"], "x")

    def test_old_file_kept(self):
        """A settings file from before: the AE-9 reads it unchanged."""
        with open(self.ctx.settings.path, "w") as f:
            json.dump({"rate_mode": 48000, "encoder": "ac3"}, f)
        st = config.Settings()
        self.assertEqual((st["rate_mode"], st["encoder"]), (48000, "ac3"))


class CardModelTest(S.AppTestCase):
    """Driver 0.13.0's "Card Model" control names the card; the ALSA id,
    names and PCI subsystem stay the fallback."""

    def test_names_the_card(self):
        # a card whose id and names don't say (a renamed id): the control does
        odd = ("Mine", "Creative card", "Creative card at 0xfc004000 irq 45",
               (0x1102, 0x9999), "snd-hda-codec-creative-ae9", ("0p", "0c"))
        S.sound_cards(kt.HDMI_CARD, odd)
        self.assertEqual(C.cards(), [])
        S.sound_cards(kt.HDMI_CARD, odd)
        S.CARD_MODELS[1] = "Sound Blaster AE-7"
        self.assertEqual([(c.id, c.short, c.source) for c in C.cards()], [("Mine", "AE-7", "card_model")])

    def test_wins_over_the_id(self):
        S.CARD_MODELS[2] = "Sound Blaster AE-9"
        C._found.clear()
        self.assertEqual(C.cards()[0].source, "card_model")
        self.assertEqual(C.card_short(), "AE-9")

    def test_without_it_as_before(self):
        self.assertEqual(C.cards()[0].source, "card_id")

    def test_read(self):
        m = S.FakeMixer()
        m.add_enum(C.CARD_MODEL, ["Sound Blaster AE-7"])
        with mock.patch.object(C.alsa, "Mixer", lambda idx: m):
            self.assertEqual(S.REAL_READ_CARD_MODEL(2), "Sound Blaster AE-7")
        m2 = S.FakeMixer()
        with mock.patch.object(C.alsa, "Mixer", lambda idx: m2):
            self.assertIsNone(S.REAL_READ_CARD_MODEL(2))

        def gone(idx):
            raise OSError(19, "no card")
        with mock.patch.object(C.alsa, "Mixer", gone):
            self.assertIsNone(S.REAL_READ_CARD_MODEL(2))


def fake_pci(name, ids, driver=None):
    devices = os.path.join(C.ae9.boards.ROOT, "sys", "bus", "pci", "devices")
    d = os.path.join(devices, name)
    os.makedirs(d, exist_ok=True)
    for f, v in zip(("vendor", "device", "subsystem_vendor", "subsystem_device"), ids):
        with open(os.path.join(d, f), "w") as fh:
            fh.write(f"0x{v:04x}\n")
    if driver:
        target = os.path.join(devices, "..", "drivers", driver)
        os.makedirs(target, exist_ok=True)
        os.symlink(target, os.path.join(d, "driver"))


class AE7OffTest(S.AppTestCase):
    """An AE-7 the driver doesn't run (0.13.0: opt-in with ae9-ae7-enable)."""

    def setup_card(self):
        S.sound_cards(kt.HDMI_CARD)
        fake_pci("0000:0a:00.0", (0x1002, 0xab28, 0x1002, 0xab28), "snd_hda_intel")

    def test_none(self):
        self.assertIsNone(C.ae9.ae7_waiting())

    def test_on_the_kernel_driver(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI, "snd_hda_intel")
        self.assertEqual(C.ae9.ae7_waiting(), "kernel")
        w = self.window()
        w.no_card.show_state(True)
        self.assertIn("AE-7 found", w.no_card.title.text())
        self.assertEqual(w.no_card.steps.text(), "sudo ae9-ae7-enable")
        self.assertFalse(w.no_card.steps_box.isHidden())
        self.assertIn("ae9-ae7-enable", window.no_card_reason(self.ctx.card))

    def test_refused(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI)
        self.assertEqual(C.ae9.ae7_waiting(), "unbound")
        w = self.window()
        w.no_card.show_state(True)
        self.assertEqual(w.no_card.steps.text(), "ae9-ae7-enable --status")
        self.assertIn("isn't finished", w.no_card.sub.text())
        self.assertNotIn("parked", window.no_card_reason(self.ctx.card))

    def park(self, which):
        path = os.path.join(C.ae9.boards.ROOT, C.ae9.AE7_PARK_FILES[which])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()

    def test_parked(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI)
        self.park(0)
        self.assertEqual(C.ae9.ae7_waiting(), "parked")
        w = self.window()
        w.no_card.show_state(True)
        self.assertEqual(w.no_card.title.text(), window.AE7_OFF_TITLE)
        self.assertIn(C.ae9.AE7_WAITING["parked"][0], w.no_card.sub.text())
        self.assertEqual(w.no_card.steps.text(), "sudo ae9-ae7-enable")
        self.assertIn("parked", window.no_card_reason(self.ctx.card))

    def test_parked_by_the_modprobe_file_alone(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI)
        self.park(1)
        self.assertEqual(C.ae9.ae7_waiting(), "parked")

    def test_park_files_with_the_kernel_driver(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI, "snd_hda_intel")
        self.park(0)
        self.assertEqual(C.ae9.ae7_waiting(), "kernel")
        self.assertNotIn("parked", window.no_card_reason(self.ctx.card))

    def test_ours(self):
        fake_pci("0000:05:00.0", C.ae9.boards.AE7_PCI, "snd-hda-codec-creative-ae9")
        self.assertIsNone(C.ae9.ae7_waiting())

    def test_ae9_screen_unchanged(self):
        w = self.window()
        w.no_card.show_state(True)
        self.assertEqual(w.no_card.title.text(), window.NO_CARD_TITLE)
        self.assertTrue(w.no_card.steps_box.isHidden())


class AE9UnchangedTest(S.AppTestCase):
    """The helpers word and behave as before on the AE-9."""

    def test_missing_switch_is_direct_on_the_ae9(self):
        del self.mixer.controls[C.DIRECT]
        self.assertTrue(self.ctx.card.is_direct())
        self.assertFalse(C.no_direct(self.ctx.card))

    def test_texts(self):
        self.assertFalse(C.untested(C.HP_PROFILE))
        self.assertFalse(C.locked_on(C.HP_VIRT))
        self.assertIn("ES9038", pages.dac_filter_tip())
        self.assertEqual(C.fixed_bits(), "24-bit")
        self.assertTrue(C.feature("speaker_setup", True))


if __name__ == "__main__":
    unittest.main()
