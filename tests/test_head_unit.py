# SPDX-License-Identifier: GPL-2.0-only
"""Head unit plugs: the 3.5 mm auto switch and the plugged indicators."""

import unittest

import support as S
from sbcommand import card as C, pages
from sbcommand import theme as T


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
        self.assertFalse(rec.phantom.isVisible())

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

    def test_output_name_is_short(self):
        long = "CA0132 Sound Core3D [Sound Blaster AE-7/AE-9] (Sound Blaster AE-9) Analog Stereo"
        self.assertEqual(pages.output_name({"description": long}), "Sound Blaster AE-9")
        self.assertEqual(pages.output_name({"description": "AE-9 Analog Out"}), "AE-9 Analog Out")


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


class PhantomPowerTest(S.AppTestCase):
    def rec(self, on=False, writable=True):
        self.mixer.add_bool(C.HU_PHANTOM, on, writable=writable)
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def phantom_writes(self):
        return [w for w in self.mixer.writes if w[0] == C.HU_PHANTOM]

    def answer(self, yes):
        asked = []
        old = pages.confirm_phantom
        pages.confirm_phantom = lambda parent: asked.append(1) or yes
        self.addCleanup(setattr, pages, "confirm_phantom", old)
        return asked

    def test_hidden_without_the_control(self):
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        self.assertFalse(pg.phantom.isVisible())
        self.assertFalse(pg.phantom_btn.isVisible())

    def test_read_only_driver_shows_state_without_a_button(self):
        pg = self.rec(writable=False)
        self.assertTrue(pg.phantom.isVisible())
        self.assertFalse(pg.phantom_btn.isVisible())
        self.assertEqual(pg.phantom.text(), "Off — switched by the head unit's button")
        self.mixer.external(C.HU_PHANTOM, True)     # the button on the head unit
        S.process(20)
        self.assertTrue(pg.phantom.text().startswith("On"))

    def test_warning_first_cancel_writes_nothing(self):
        pg = self.rec()
        self.assertTrue(pg.phantom_btn.isVisible())
        asked = self.answer(False)
        pg.phantom_btn.click()
        self.assertEqual(asked, [1])
        self.assertEqual(self.phantom_writes(), [])

    def test_warning_then_turn_on_lights_red_and_one_click_off(self):
        pg = self.rec()
        self.answer(True)
        pg.phantom_btn.click()
        self.assertEqual(self.phantom_writes(), [(C.HU_PHANTOM, True)])
        S.process(20)                                # the change event
        self.assertIn("On", pg.phantom.text())
        self.assertIn(T.DANGER, pg.phantom_btn.styleSheet())
        asked = self.answer(True)
        pg.phantom_btn.click()                       # off: no question
        self.assertEqual(asked, [])
        self.assertEqual(self.phantom_writes()[-1], (C.HU_PHANTOM, False))
        S.process(20)
        self.assertEqual(pg.phantom.text(), "Off")
        self.assertNotIn(T.DANGER, pg.phantom_btn.styleSheet())

    def test_two_click_mode_arms_then_turns_on_without_a_popup(self):
        self.ctx.settings["phantom_confirm"] = "two_click"
        pg = self.rec()
        asked = self.answer(True)
        pg.phantom_btn.click()
        self.assertEqual(self.phantom_writes(), [])
        self.assertEqual(pg.phantom_btn.text(), "Click again to turn on")
        pg.phantom_btn.click()
        self.assertEqual(self.phantom_writes(), [(C.HU_PHANTOM, True)])
        self.assertEqual(asked, [])
        S.process(20)
        self.assertEqual(pg.phantom_btn.text(), "Phantom Power 48V")

    def test_two_click_arm_times_out(self):
        self.ctx.settings["phantom_confirm"] = "two_click"
        old = pages.PHANTOM_ARM_MS
        pg = self.rec()
        pg._arm_timer.setInterval(50)
        pg.phantom_btn.click()
        S.process(150)
        self.assertEqual(pg.phantom_btn.text(), "Phantom Power 48V")
        pg.phantom_btn.click()                       # armed again, not on
        self.assertEqual(self.phantom_writes(), [])
        pages.PHANTOM_ARM_MS = old

    def test_ebusy_and_eagain_say_why(self):
        import errno
        from sbae9kit.mixer import AlsaError
        pg = self.rec()
        self.answer(True)
        for err, text in ((errno.EBUSY, "can't be switched on yet"), (errno.EAGAIN, "hasn't reported")):
            def fail(name, value, err=err):
                raise AlsaError(err, "write")
            self.mixer.set = fail
            pg.phantom_btn.click()
            self.assertIn(text, pg.phantom_note.text())
            self.assertTrue(pg.phantom_note.isVisible())
            self.assertEqual(pg.phantom.text(), "Off")

    def test_never_turned_on_at_start(self):
        self.mixer.add_bool(C.HU_PHANTOM, False)
        self.ctx.settings["restore_on_start"] = True
        self.window()
        S.process(50)
        self.assertEqual(self.phantom_writes(), [])
        self.assertNotIn("phantom", " ".join(k for k in self.ctx.settings.data if k != "phantom_confirm"))

    def test_device_table_cannot_switch_it(self):
        self.mixer.add_bool(C.HU_PHANTOM, False)
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        self.assertFalse(pg._editors[C.HU_PHANTOM].isEnabled())
        self.assertFalse(pg.phantom_box.isHidden())
        self.assertEqual(pg.phantom_mode.currentData(), "popup")


if __name__ == "__main__":
    unittest.main()
