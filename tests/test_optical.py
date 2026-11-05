# SPDX-License-Identifier: GPL-2.0-only
"""Optical (S/PDIF): the out switch, when it's silent, and the optical input."""

import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class OpticalOutTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.OPTICAL_OUT, True)

    def test_hidden_on_drivers_without_it(self):
        self.mixer.remove(C.OPTICAL_OUT)
        pg = self.page(pages.PlaybackPage)
        self.assertFalse(pg.optical_box.isVisible())

    def test_switch_drives_the_control(self):
        pg = self.page(pages.PlaybackPage)
        self.assertTrue(pg.optical_box.isVisible())
        self.assertTrue(pg.optical.isChecked())
        pg.optical.setChecked(False)
        self.assertFalse(self.card(C.OPTICAL_OUT))
        self.mixer.external(C.OPTICAL_OUT, True)       # alsamixer, the driver
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.optical.isChecked())

    def test_tells_you_when_it_is_silent(self):
        pg = self.page(pages.PlaybackPage)
        self.mixer.external(C.BIT_DEPTH, "24-bit")
        S.PW.stream = (192000, 2)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "On — same as the main output")
        self.mixer.external(C.BIT_DEPTH, "32-bit")
        S.PW.stream = (384000, 2)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "On — silent right now")
        self.assertIn("32-bit, 384 kHz", pg.optical_note.text())
        S.PW.stream = (48000, 6)
        self.mixer.external(C.BIT_DEPTH, "24-bit")
        S.process(20)
        pg.refresh()
        self.assertIn("5.1 stream", pg.optical_note.text())
        self.mixer.external(C.OPTICAL_OUT, False)      # off: no warning
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "Off")


class OpticalInTest(S.AppTestCase):
    def test_never_taken_for_the_mic(self):
        S.PW.add_optical_in(first=True, alsa_props=True)
        n = pipewire.Nodes(S.PW.objects)
        self.assertEqual(n.optical_in["name"], "alsa_input.ae9_optical")
        self.assertNotEqual(n.source["name"], "alsa_input.ae9_optical")

    def test_listed_on_the_recording_page(self):
        S.PW.add_optical_in()
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        self.assertTrue(pg.optical_box.isVisible())
        self.assertEqual(pg.optical_name.text(), "AE-9 Optical In")
        pg.optical_default.click()
        self.assertTrue(any(c[:2] == ("wpctl", "set-default") and c[2] == "999" for c in S.PW.calls))

    def test_setup_hint_when_pipewire_lacks_it(self):
        self.mixer.add_bool(C.OPTICAL_OUT, True)
        pg = self.page(pages.RecordingPage)
        self.assertTrue(pg.optical_box.isVisible())
        self.assertIn("ae9-optical-in.conf", pg.optical_note.text())
        self.assertFalse(pg.optical_default.isVisible())

    def test_hidden_without_optical(self):
        pg = self.page(pages.RecordingPage)
        self.assertFalse(pg.optical_box.isVisible())


if __name__ == "__main__":
    unittest.main()
