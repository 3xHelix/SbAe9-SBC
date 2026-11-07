# SPDX-License-Identifier: GPL-2.0-only
"""Playback → Speaker Setup: bass redirect and per-speaker level and distance."""

import unittest

import support as S
from sbcommand import card as C, pages
from sbae9kit import mixer as alsa


class SpeakerSetupTest(S.AppTestCase):
    def add_controls(self, old_gain=False):
        """The driver's speaker-setup controls (raw values are Hz, dB and cm)."""
        m = self.mixer

        def add_int(name, lo, hi, value):
            m._add(name, value, type=alsa.TYPE_INTEGER, min=lo, max=hi, items=[])
        m.add_bool(C.BASS_REDIRECT, False)
        add_int(C.BASS_XOVER, 50, 200, 80)
        if old_gain:                    # driver 0.10.0
            add_int(C.BASS_SUB_GAIN_OLD, -12, 12, 0)
        else:
            m.add_bool(C.BASS_SUB_BOOST, False)
        for ch in C.SPEAKER_CHANNELS:
            add_int(C.speaker_level(ch), -12, 12, 0)
            add_int(C.speaker_distance(ch), 0, 500, 0)

    def setup_tab(self, direct=False, cfg="2.1"):
        self.mixer.external(C.DIRECT, direct)
        self.mixer.external(C.SPEAKER_CFG, cfg)
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(1)
        S.process(20)
        pg.refresh()
        return pg.setup

    def test_older_driver_says_it_needs_a_newer_one(self):
        st = self.setup_tab()
        self.assertTrue(st.missing.isVisible())
        self.assertFalse(st.box.isVisible())

    def test_greyed_in_direct_mode_with_a_way_out(self):
        self.add_controls()
        st = self.setup_tab(direct=True)
        self.assertTrue(st.direct_banner.isVisible())
        self.assertFalse(st.box.isEnabled())
        st.direct_banner.button.click()
        self.settle()
        self.assertFalse(self.card(C.DIRECT))
        st.refresh()
        self.assertFalse(st.direct_banner.isVisible())
        self.assertTrue(st.box.isEnabled())

    def test_greyed_when_the_driver_marks_it_inactive(self):
        self.add_controls()
        st = self.setup_tab()
        self.assertTrue(st.box.isEnabled())
        self.mixer.set_inactive(C.BASS_REDIRECT)
        S.process(20)
        st.refresh()
        self.assertFalse(st.box.isEnabled())

    def test_bass_redirect_switch_and_speaker_type(self):
        self.add_controls()
        st = self.setup_tab()
        self.assertFalse(st.redirect_grid.isEnabled())
        st.redirect.setChecked(True)
        self.assertTrue(self.card(C.BASS_REDIRECT))
        st.refresh()
        self.assertTrue(st.redirect_grid.isEnabled())
        self.assertEqual(st.spk_type.currentText(), "Tower (80 Hz)")
        st._pick_type(st.spk_type.findData(120))
        self.assertEqual(self.card(C.BASS_XOVER), 120)
        self.assertEqual(st.xover.value(), 12)
        st.xover.setValue(15)                       # 150 Hz: neither type
        S.process(100)
        self.assertEqual(self.card(C.BASS_XOVER), 150)
        self.assertEqual(st.spk_type.currentText(), "Custom")
        st.sub_boost.setChecked(True)
        self.assertTrue(self.card(C.BASS_SUB_BOOST))

    def test_sub_boost_on_driver_0_10_0s_int_control(self):
        self.add_controls(old_gain=True)
        self.mixer.external(C.BASS_REDIRECT, True)
        st = self.setup_tab()
        self.assertTrue(st.sub_boost.isVisible())
        self.assertFalse(st.sub_boost.isChecked())
        st.sub_boost.setChecked(True)
        self.assertEqual(self.card(C.BASS_SUB_GAIN_OLD), C.SUB_BOOST_OLD_ON)
        st.sub_boost.setChecked(False)
        self.assertEqual(self.card(C.BASS_SUB_GAIN_OLD), 0)
        self.mixer.external(C.BASS_SUB_GAIN_OLD, -3)    # set as dB before: any non-zero is on
        S.process(20)
        st.refresh()
        self.assertTrue(st.sub_boost.isChecked())

    def test_no_sub_warns_that_redirect_thins_the_sound(self):
        self.add_controls()
        st = self.setup_tab(cfg="2.0")
        self.assertIn("thin", st.redirect_note.text())
        st = self.setup_tab(cfg="2.1")
        self.assertFalse(st.redirect_note.isVisible())

    def test_level_and_distance_write_the_card(self):
        self.add_controls()
        st = self.setup_tab()
        name, lvl, lvl_val, dist, delay = st.rows["Front L"]
        lvl.setValue(3)
        S.process(100)
        self.assertEqual(self.card(C.speaker_level("Front L")), 3)
        self.assertEqual(lvl_val.text(), "+3 dB")
        dist.setValue(100)
        self.assertEqual(self.card(C.speaker_distance("Front L")), 100)
        self.assertEqual(delay.text(), "2.94 ms")

    def test_changes_from_elsewhere_show_without_writing_back(self):
        self.add_controls()
        st = self.setup_tab()
        self.mixer.writes.clear()
        self.mixer.external(C.speaker_level("Sub"), -6)
        self.mixer.external(C.speaker_distance("Sub"), 250)
        self.mixer.external(C.BASS_XOVER, 120)
        S.process(20)
        st.refresh()
        self.assertEqual(st.rows["Sub"][1].value(), -6)
        self.assertEqual(st.rows["Sub"][3].value(), 250)
        self.assertEqual(st.spk_type.currentText(), "Desktop (120 Hz)")
        self.assertEqual(self.mixer.writes, [])

    def test_only_the_speaker_configs_speakers_are_editable(self):
        self.add_controls()
        st = self.setup_tab(cfg="2.1")
        self.assertTrue(st.rows["Sub"][1].isEnabled())
        self.assertFalse(st.rows["Center"][1].isEnabled())
        self.assertFalse(st.rows["Rear L"][3].isEnabled())
        self.assertTrue(st.layout_note.isVisible())

    def test_reset(self):
        self.add_controls()
        self.mixer.external(C.speaker_level("Front R"), 5)
        self.mixer.external(C.speaker_distance("Front R"), 40)
        st = self.setup_tab()
        st.reset.click()
        self.assertEqual(self.card(C.speaker_level("Front R")), 0)
        self.assertEqual(self.card(C.speaker_distance("Front R")), 0)
        self.assertEqual(st.rows["Front R"][3].value(), 0)


if __name__ == "__main__":
    unittest.main()
