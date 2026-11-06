# SPDX-License-Identifier: GPL-2.0-only
"""Recording → Microphone: the mic / line-in's sample rate and bit depth."""

import os
import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class MicRateTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.answer = True       # the "audio will drop" question
        self._old = pages.RecordingPage.confirm_wireplumber_restart
        pages.RecordingPage.confirm_wireplumber_restart = lambda pg: self.answer

    def tearDown(self):
        pages.RecordingPage.confirm_wireplumber_restart = self._old
        super().tearDown()

    def mic(self, top=96000):
        S.PW.set_mic_range(top)
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def enabled(self, pg):
        c = pg.mic_rate
        return [c.itemText(k) for k in range(c.count()) if c.model().item(k).isEnabled()]

    def test_offers_what_the_driver_records(self):
        pg = self.mic(96000)
        self.assertEqual(self.enabled(pg), ["Automatic", "48 kHz", "96 kHz"])
        self.assertEqual(pg.mic_rate.currentText(), "Automatic")
        self.assertEqual(pg.mic_depth.currentText(), "24-bit")
        self.assertFalse(pg.mic_depth.isEnabled())

    def test_older_driver_is_48_only(self):
        pg = self.mic(48000)
        self.assertEqual(self.enabled(pg), ["Automatic", "48 kHz"])
        self.assertIn("0.9.1", pg.mic_now.text())

    def test_picking_96_writes_the_rule_and_restarts_wireplumber(self):
        pg = self.mic(96000)
        pg._mic_rate(pg.mic_rate.findData(96000))
        self.settle()
        with open(pipewire.MIC_CONF) as f:
            conf = f.read()
        self.assertIn('node.name = "alsa_input.pci-0000_06_00.0.analog-stereo"', conf)
        self.assertIn("audio.rate = 96000", conf)
        self.assertIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)
        self.assertEqual(pipewire.mic_rate_setting(), 96000)
        pg.refresh()
        self.assertEqual(pg.mic_rate.currentText(), "96 kHz")

    def test_automatic_removes_the_rule(self):
        pg = self.mic(96000)
        pg._mic_rate(pg.mic_rate.findData(96000))
        self.settle()
        S.PW.calls.clear()
        pg._mic_rate(0)
        self.settle()
        self.assertFalse(os.path.exists(pipewire.MIC_CONF))
        self.assertIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)

    def test_same_pick_does_nothing(self):
        pg = self.mic(96000)
        pg._mic_rate(0)
        self.settle()
        self.assertNotIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)

    def test_saying_no_changes_nothing(self):
        self.answer = False
        pg = self.mic(96000)
        pg._mic_rate(pg.mic_rate.findData(96000))
        self.settle()
        self.assertFalse(os.path.exists(pipewire.MIC_CONF))
        self.assertNotIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)
        self.assertEqual(pg.mic_rate.currentText(), "Automatic")

    def test_depth_is_a_real_choice_with_the_driver_control(self):
        self.mixer.add_enum(C.CAP_BIT_DEPTH, ["24-bit", "32-bit"])
        pg = self.mic(96000)
        d = pg.mic_depth
        self.assertTrue(d.isEnabled())
        self.assertEqual([d.itemText(k) for k in range(d.count())], ["24-bit", "32-bit (as Windows)"])
        pg._mic_depth(1)
        self.settle()
        self.assertEqual(self.card(C.CAP_BIT_DEPTH), 1)
        self.assertTrue(any(c[:2] == ("pactl", "suspend-source") for c in S.PW.calls))
        self.assertNotIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)

    def test_shows_what_it_records_now(self):
        S.PW.capture = (96000, 2)
        pg = self.mic(96000)
        self.assertEqual(pg.mic_now.text(), "Recording now: 96 kHz · 24-bit · stereo")


if __name__ == "__main__":
    unittest.main()
