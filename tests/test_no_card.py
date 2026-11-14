# SPDX-License-Identifier: GPL-2.0-only
"""The window while the AE-9 is missing: a "no card" screen, as Windows' SBC."""

import errno

import support
from support import AppTestCase, process

from sbcommand import card as C
from sbcommand import window


class NoCardTest(AppTestCase):
    def lose_card(self):
        self.ctx.card._lost()
        self.ctx.card._retry.stop()     # the fake card would come straight back
        process()

    def test_with_the_card_the_pages_show(self):
        w = self.window()
        self.assertIs(w.body.currentWidget(), w.stack)
        self.assertFalse(w.devices_btn.isVisible())
        self.assertFalse(w.no_card_bar.isVisible())
        self.assertTrue(w.bottom_bar.isVisible())
        self.assertTrue(all(b.isVisible() for b in w.buttons))

    def test_without_the_card_only_my_devices_and_settings(self):
        w = self.window()
        w.go(3)
        self.lose_card()
        self.assertIs(w.body.currentWidget(), w.no_card)
        self.assertTrue(w.devices_btn.isVisible() and w.devices_btn.isChecked())
        shown = [b.text() for b in w.buttons if b.isVisible()]
        self.assertEqual(shown, ["Settings"])
        self.assertFalse(w.bottom_bar.isVisible())
        self.assertTrue(w.no_card_bar.isVisible())
        self.assertEqual(w.no_card_bar.text(), window.NO_CARD)

    def test_settings_opens_without_the_card_and_the_page_is_kept(self):
        w = self.window()
        w.go(3)
        self.lose_card()
        settings = len(w.buttons) - 1
        w.buttons[settings].click()
        self.assertIs(w.body.currentWidget(), w.stack)
        self.assertEqual(w.stack.currentIndex(), settings)
        self.assertTrue(w.stack.isEnabled())
        w.devices_btn.click()
        self.assertIs(w.body.currentWidget(), w.no_card)
        self.assertEqual(self.ctx.settings["page"], 3)

    def test_no_driver_says_so(self):
        support.DRIVER["loaded"] = False
        w = self.window()
        self.lose_card()
        self.assertIn("isn't loaded", w.no_card_bar.text())

    def test_card_back_restores_the_page(self):
        w = self.window()
        w.go(3)
        self.lose_card()
        self.ctx.card._try_open()
        process()
        self.assertIs(w.body.currentWidget(), w.stack)
        self.assertEqual(w.stack.currentIndex(), 3)
        self.assertTrue(w.buttons[3].isChecked())
        self.assertTrue(w.bottom_bar.isVisible())
        self.assertFalse(w.no_card_bar.isVisible())


def enodev(*_):
    raise OSError(errno.ENODEV, "No such device")


class NotAnsweringTest(AppTestCase):
    """Driver 0.12.8: the card stays on the bus but stops answering; every
    control write fails with ENODEV until the driver is reloaded."""

    def test_enodev_shows_the_no_card_screen_with_how_to_fix(self):
        w = self.window()
        self.mixer.set = enodev
        self.assertFalse(self.ctx.card.set(C.SBX, True))
        process()
        self.assertFalse(self.ctx.card.answering)
        self.assertIs(w.body.currentWidget(), w.no_card)
        self.assertEqual(w.no_card.title.text(), window.NOT_ANSWERING_TITLE)
        self.assertIn("sudo modprobe -r snd-hda-codec-creative-ae9", w.no_card_bar.text())
        self.assertFalse(w.bottom_bar.isVisible())

    def test_write_returns_enodev(self):
        self.mixer.set = enodev
        self.assertEqual(self.ctx.card.write(C.SBX, True), errno.ENODEV)
        self.assertFalse(self.ctx.card.answering)

    def test_other_errors_dont_count(self):
        def ebusy(*_):
            raise OSError(errno.EBUSY, "busy")
        self.mixer.set = ebusy
        self.ctx.card.set(C.SBX, True)
        self.assertTrue(self.ctx.card.answering)

    def test_driver_reload_brings_the_pages_back(self):
        w = self.window()
        w.go(3)
        self.mixer.set = enodev
        self.ctx.card.set(C.SBX, True)
        process()
        self.ctx.card._lost()           # modprobe -r
        self.ctx.card._try_open()       # modprobe
        process()
        self.assertTrue(self.ctx.card.answering)
        self.assertIs(w.body.currentWidget(), w.stack)
        self.assertEqual(w.stack.currentIndex(), 3)

    def test_ctl_says_how_to_fix(self):
        from sbcommand import ctl
        self.assertIn("modprobe", ctl.ERRORS[errno.ENODEV])


class DspWaitsFor48kTest(AppTestCase):
    """Direct Mode off during a 44.1 kHz stream: the driver keeps it direct
    and starts DSP mode with the next 48 kHz stream."""

    def setUp(self):
        super().setUp()
        self.mixer.values[C.DIRECT] = 0

    def test_note_while_a_44k1_stream_plays(self):
        support.PW.stream = (44100, 2)
        w = self.window()
        w.refresh()
        self.assertTrue(w.dsp_wait.isVisible())
        self.assertIn("44.1 kHz", w.dsp_wait.text.text())
        self.assertIn("clock.force-rate 48000", w.dsp_wait.text.text())

    def test_no_note_at_48k_nothing_playing_or_direct(self):
        w = self.window()
        for stream, direct in (((48000, 2), 0), (None, 0), ((44100, 2), 1)):
            support.PW.stream = stream
            self.mixer.values[C.DIRECT] = direct
            w.refresh()
            self.assertFalse(w.dsp_wait.isVisible(), (stream, direct))

    def test_96k_is_fine_with_dsp_96k(self):
        support.PARAMS["dsp_96k"] = "Y"
        support.PW.stream = (96000, 2)
        self.assertIsNone(C.dsp_waiting_rate(self.ctx.card, support.PW.stream))
        support.PARAMS["dsp_96k"] = "N"
        self.assertEqual(C.dsp_waiting_rate(self.ctx.card, support.PW.stream), 96000)

    def test_use_48k_picks_48k(self):
        support.PW.stream = (44100, 2)
        w = self.window()
        w.refresh()
        w.dsp_wait.button.click()
        self.settle()
        self.assertEqual(self.ctx.settings["rate_mode"], 48000)
        self.assertIn(("pw-metadata", "-n", "settings", "0", "clock.force-rate", "48000"),
                      [tuple(c) for c in support.PW.calls])


if __name__ == "__main__":
    import unittest
    unittest.main()
