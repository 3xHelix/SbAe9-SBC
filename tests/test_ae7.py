# SPDX-License-Identifier: GPL-2.0-only
"""The AE-7 (experimental): the card as driver kit 11 runs it.

Its controls are tests/fixtures/ae7_controls.json, written from the kit 11
driver's control list (ae7-k11): kit 11, PROVISIONAL, regenerate it from
driver 0.13.0. The AE-9's own tests stay as they are; these only cover the
AE-7's differences.
"""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support as S
from sbae9kit import testing as kt
from sbcommand import card as C, ctl, pages, pipewire, window


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


class AE9UnchangedTest(S.AppTestCase):
    """The helpers word and behave as before on the AE-9."""

    def test_missing_switch_is_direct_on_the_ae9(self):
        del self.mixer.controls[C.DIRECT]
        self.assertTrue(self.ctx.card.is_direct())
        self.assertFalse(C.no_direct(self.ctx.card))

    def test_texts(self):
        self.assertIn("ES9038", pages.dac_filter_tip())
        self.assertEqual(C.fixed_bits(), "24-bit")
        self.assertTrue(C.feature("speaker_setup", True))


if __name__ == "__main__":
    unittest.main()
