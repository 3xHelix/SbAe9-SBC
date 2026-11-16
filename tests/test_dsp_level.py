# SPDX-License-Identifier: GPL-2.0-only
"""Driver 0.12.11: DSP mode plays at Direct Mode's level (it was 6 dB low),
so the first switch to DSP mode warns to lower the volume first."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

import support as S
from sbcommand import card as C, ctl, pages


class DspLouderTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.asked = []
        self.answer = pages.QMessageBox.Yes
        p = mock.patch.object(pages.QMessageBox, "question",
                              lambda *a, **k: self.asked.append(a[2]) or self.answer)
        p.start()
        self.addCleanup(p.stop)
        self.mixer.external(C.DIRECT, True)
        S.process()

    def playback(self):
        return self.page(pages.PlaybackPage)

    def test_old_driver_never_asks(self):
        S.PARAMS["version"] = "0.12.10"
        pg = self.playback()
        pg.direct.setChecked(False)
        S.process(100)
        self.assertEqual(self.asked, [])
        self.assertFalse(self.mixer.get(C.DIRECT))

    def test_asks_once_before_switching(self):
        S.PARAMS["version"] = "0.12.11"
        pg = self.playback()
        pg.direct.setChecked(False)
        S.process(100)
        self.assertEqual(len(self.asked), 1)
        self.assertIn("6 dB louder", self.asked[0])
        self.assertIn("lower the volume", self.asked[0])
        self.assertFalse(self.mixer.get(C.DIRECT))
        self.assertTrue(self.ctx.settings["dsp_louder_seen"])
        # back to Direct and off again: not asked again
        self.ctx.set_direct(True)
        S.process(100)
        pg.refresh()
        pg.direct.setChecked(False)
        S.process(100)
        self.assertEqual(len(self.asked), 1)

    def test_no_keeps_direct_mode(self):
        S.PARAMS["version"] = "0.12.11"
        self.answer = pages.QMessageBox.No
        pg = self.playback()
        pg.direct.setChecked(False)
        S.process(100)
        self.assertEqual(len(self.asked), 1)
        self.assertTrue(self.mixer.get(C.DIRECT))
        self.assertTrue(pg.direct.isChecked())
        self.assertFalse(self.ctx.settings["dsp_louder_seen"])

    def test_turning_direct_on_never_asks(self):
        S.PARAMS["version"] = "0.12.11"
        self.mixer.external(C.DIRECT, False)
        S.process()
        self.assertTrue(pages.set_direct_checked(None, self.ctx, True))
        self.assertEqual(self.asked, [])

    def test_tip_says_same_level(self):
        S.PARAMS["version"] = "0.12.11"
        self.assertTrue(C.dsp_full_level())
        S.PARAMS["version"] = "0.12.10"
        self.assertFalse(C.dsp_full_level())


class DspLouderShortcutTest(S.AppTestCase):
    """The keyboard shortcut can't ask first: its notification says it once."""

    def setUp(self):
        super().setUp()
        for p in (mock.patch.object(ctl.alsa, "Mixer", lambda idx: self.mixer),
                  mock.patch.object(ctl.Card, "close", lambda self: None)):
            p.start()
            self.addCleanup(p.stop)

    def toggle(self):
        with redirect_stdout(io.StringIO()):
            ctl.main(["direct", "toggle", "--notify"])

    def test_once(self):
        S.PARAMS["version"] = "0.12.11"
        said = []
        with mock.patch.object(ctl, "notify", lambda text, error=False: said.append(text)):
            self.mixer.external(C.DIRECT, True)
            self.toggle()
            self.toggle()
            self.toggle()
        self.assertIn("6 dB louder", said[0])
        self.assertEqual(said[1], "Direct Mode on")
        self.assertEqual(said[2], "DSP on (Direct Mode off)")

    def test_old_driver(self):
        S.PARAMS["version"] = "0.12.10"
        said = []
        with mock.patch.object(ctl, "notify", lambda text, error=False: said.append(text)):
            self.mixer.external(C.DIRECT, True)
            self.toggle()
        self.assertEqual(said, ["DSP on (Direct Mode off)"])


if __name__ == "__main__":
    unittest.main()
