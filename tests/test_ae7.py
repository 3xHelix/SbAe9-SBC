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
from sbcommand import card as C, ctl, pages, window


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
