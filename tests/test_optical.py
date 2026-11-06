# SPDX-License-Identifier: GPL-2.0-only
"""Optical (S/PDIF) and What U Hear: Playback → Digital, Recording → Other Input."""

import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class OpticalOutTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.OPTICAL_OUT, True)

    def digital(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(1)
        S.process(20)
        return pg

    def test_lives_on_the_digital_tab(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        self.assertFalse(pg.optical_box.isVisible())
        pg.show_tab(1)
        self.assertTrue(pg.optical_box.isVisible())
        self.assertFalse(pg.optical_missing.isVisible())

    def test_older_driver_says_what_it_needs(self):
        self.mixer.remove(C.OPTICAL_OUT)
        pg = self.digital()
        self.assertFalse(pg.optical_box.isVisible())
        self.assertIn("v0.8.0", pg.optical_missing.text())
        self.assertTrue(pg.optical_missing.isVisible())

    def test_switch_drives_the_control(self):
        pg = self.digital()
        self.assertTrue(pg.optical.isChecked())
        pg.optical.setChecked(False)
        self.assertFalse(self.card(C.OPTICAL_OUT))
        self.mixer.external(C.OPTICAL_OUT, True)       # alsamixer, the driver
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.optical.isChecked())

    def test_tells_you_when_it_is_silent(self):
        pg = self.digital()
        self.mixer.external(C.BIT_DEPTH, "24-bit")
        S.PW.stream = (192000, 2)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "On — same as the main output")
        self.assertEqual(pg.optical_quality.text(), "192 kHz · 24-bit · stereo")
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


class OtherInputTest(S.AppTestCase):
    def other(self):
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(1)
        S.process(20)
        return pg, {sec.key: sec for sec in pg.inputs}

    def test_never_taken_for_the_mic(self):
        S.PW.add_optical_in(first=True, alsa_props=True)
        S.PW.add_what_u_hear(first=True, alsa_props=True)
        n = pipewire.Nodes(S.PW.objects)
        self.assertEqual(n.optical_in["name"], "alsa_input.ae9_optical")
        self.assertEqual(n.what_u_hear["name"], "alsa_input.ae9_what_u_hear")
        self.assertNotIn(n.source["name"], ("alsa_input.ae9_optical", "alsa_input.ae9_what_u_hear"))

    def test_both_listed_with_set_default(self):
        S.PW.add_optical_in()
        S.PW.add_what_u_hear()
        pg, secs = self.other()
        for key, name, node_id in (("optical_in", "AE-9 Optical In", "999"),
                                   ("what_u_hear", "AE-9 What U Hear", "998")):
            sec = secs[key]
            self.assertTrue(sec.isVisible(), key)
            self.assertEqual(sec.name.text(), name)
            S.PW.calls.clear()
            sec.set_default.click()
            self.assertTrue(any(c[:2] == ("wpctl", "set-default") and c[2] == node_id
                                for c in S.PW.calls), key)
        self.assertFalse(pg.other_none.isVisible())

    def test_setup_hint_when_pipewire_lacks_it(self):
        S.PCMS.update({1, 2})
        pg, secs = self.other()
        self.assertIn("ae9-optical-in.conf", secs["optical_in"].note.text())
        self.assertIn("ae9-what-u-hear.conf", secs["what_u_hear"].note.text())
        self.assertFalse(secs["what_u_hear"].set_default.isVisible())

    def test_nothing_on_an_older_driver(self):
        pg, secs = self.other()
        self.assertFalse(any(s.isVisible() for s in secs.values()))
        self.assertTrue(pg.other_none.isVisible())


if __name__ == "__main__":
    unittest.main()
