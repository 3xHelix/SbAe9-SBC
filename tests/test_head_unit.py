# SPDX-License-Identifier: GPL-2.0-only
"""Head unit plugs: the 3.5 mm auto switch and the plugged indicators."""

import unittest

import support as S
from sbcommand import card as C, pages


class HeadUnitTest(S.AppTestCase):
    def add_all(self, auto=False, phones=False, mic=False):
        self.mixer.add_bool(C.HU_AUTO, auto)
        self.mixer.add_bool(C.HU_PHONES, phones)
        self.mixer.add_bool(C.HU_MIC, mic)

    def playback(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def test_hidden_on_older_drivers(self):
        pg = self.playback()
        self.assertFalse(pg.hp_auto_row.isVisible())
        self.assertEqual(pg.hp_sub.text(), "Head unit")
        rec = self.page(pages.RecordingPage)
        self.assertFalse(rec.mic_jack.isVisible())

    def test_auto_switch_off_by_default_and_drives_the_control(self):
        self.add_all()
        pg = self.playback()
        self.assertTrue(pg.hp_auto_row.isVisible())
        self.assertFalse(pg.hp_auto.isChecked())
        pg.hp_auto.setChecked(True)
        self.assertTrue(self.card(C.HU_AUTO))
        self.mixer.external(C.HU_AUTO, False)       # alsamixer, module option
        S.process(20)
        pg.refresh()
        self.assertFalse(pg.hp_auto.isChecked())

    def test_plugged_indicators_follow_the_jacks(self):
        self.add_all(phones=False, mic=True)
        pg = self.playback()
        self.assertEqual(pg.hp_sub.text(), "Unplugged")
        self.mixer.external(C.HU_PHONES, True)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.hp_sub.text(), "Plugged In")
        rec = self.page(pages.RecordingPage)
        rec.show_tab(0)
        rec.refresh()
        self.assertEqual(rec.mic_jack.text(), "3.5 mm mic: plugged in")

    def test_auto_switch_moves_the_output_selector(self):
        self.add_all(auto=True)
        pg = self.playback()
        self.mixer.external(C.OUTPUT, 1)            # the driver switched on a plug
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.r_hp.isChecked())

    def test_older_test_builds_names_still_work(self):
        self.mixer.add_bool("Head Unit Phones Plugged", True)       # before the rename
        self.mixer.add_bool("Head Unit Line In Plugged", True)
        pg = self.playback()
        self.assertTrue(self.ctx.card.has(C.HU_PHONES))
        self.assertEqual(pg.hp_sub.text(), "Plugged In")
        rec = self.page(pages.RecordingPage)
        rec.show_tab(0)
        rec.refresh()
        self.assertEqual(rec.mic_jack.text(), "3.5 mm mic: plugged in")

    def test_details_moved_to_hover(self):
        self.add_all(phones=True)
        pg = self.playback()
        self.assertIn('1/4"', pg.hp_sub.toolTip())
        self.assertIn("3.5 mm", pg.hp_sub.toolTip())
        self.mixer.external(C.SPEAKER_CFG, "5.1")
        self.mixer.external(C.DIRECT, False)
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.spk_sub.text().startswith("5.1 Surround"))
        self.assertNotIn("RCA", pg.spk_sub.text())
        self.assertIn("3.5 mm C/Sub out", pg.spk_sub.toolTip())

    def test_mic_name_is_short(self):
        self.assertEqual(pages.mic_name({"description": "CA0132 Sound Core3D [Sound Blaster AE-7/AE-9] "
                                                        "(Sound Blaster AE-9) Analog Stereo"}),
                         "AE-9 Head Unit Mic / Aux")
        self.assertEqual(pages.mic_name({"description": "AE-9 Head Unit Mic / Aux"}), "AE-9 Head Unit Mic / Aux")
        self.assertEqual(pages.mic_name({"description": "AE-9 Studio Mic"}), "AE-9 Studio Mic")


class MicGainTest(S.AppTestCase):
    def test_released_drivers_xlr_gain_name_still_works(self):
        pg = self.page(pages.RecordingPage)          # the 0.6.8 snapshot: "XLR Gain Capture Volume"
        pg.show_tab(0)
        pg.xlr.selected.emit("2")
        self.assertEqual(self.mixer.writes[-1], ("XLR Gain Capture Volume", 2))

    def test_new_mic_gain_name_is_used_when_the_driver_has_it(self):
        self.mixer.remove("XLR Gain Capture Volume")
        self.mixer.add_enum(C.MIC_GAIN, ["0", "1", "2"], 1)
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        self.assertEqual(self.ctx.card.get(C.MIC_GAIN), 1)
        pg.xlr.selected.emit("0")
        self.assertEqual(self.mixer.writes[-1], (C.MIC_GAIN, 0))


if __name__ == "__main__":
    unittest.main()
