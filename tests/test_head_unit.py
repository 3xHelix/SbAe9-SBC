# SPDX-License-Identifier: GPL-2.0-only
"""Head unit plugs: the 3.5 mm auto switch and the plugged indicators."""

import unittest

import support as S
from sbcommand import card as C, pages


class HeadUnitTest(S.AppTestCase):
    def add_all(self, auto=False, phones=False, line_in=False):
        self.mixer.add_bool(C.HU_AUTO, auto)
        self.mixer.add_bool(C.HU_PHONES, phones)
        self.mixer.add_bool(C.HU_LINE_IN, line_in)

    def playback(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def test_hidden_on_older_drivers(self):
        pg = self.playback()
        self.assertFalse(pg.hp_auto_row.isVisible())
        self.assertEqual(pg.hp_sub.text(), "Head unit headphone jack")
        rec = self.page(pages.RecordingPage)
        self.assertFalse(rec.line_in.isVisible())

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
        self.add_all(phones=False, line_in=True)
        pg = self.playback()
        self.assertIn("nothing in the 3.5 mm jack", pg.hp_sub.text())
        self.mixer.external(C.HU_PHONES, True)
        S.process(20)
        pg.refresh()
        self.assertIn("3.5 mm plugged in", pg.hp_sub.text())
        rec = self.page(pages.RecordingPage)
        rec.show_tab(0)
        rec.refresh()
        self.assertEqual(rec.line_in.text(), "Head unit 3.5 mm line-in: plugged in")

    def test_auto_switch_moves_the_output_selector(self):
        self.add_all(auto=True)
        pg = self.playback()
        self.mixer.external(C.OUTPUT, 1)            # the driver switched on a plug
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.r_hp.isChecked())


if __name__ == "__main__":
    unittest.main()
