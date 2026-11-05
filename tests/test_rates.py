# SPDX-License-Identifier: GPL-2.0-only
"""Sample rate: caps, quantum, hands off what others set, the drop-in file."""

import os
import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class RateTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.external(C.DIRECT, True)
        S.process(20)
        self.snapshot()
        S.PW.calls.clear()

    # helpers
    def pick(self, rate):
        self.ctx.settings["rate_mode"] = rate
        self.ctx.apply_rate(user=True)
        self.settle()

    def direct(self, on):
        self.mixer.external(C.DIRECT, on)    # head unit / driver / another tool
        S.process(20)
        self.settle()

    def layout(self, profile):
        S.PW.set_profile(profile)
        self.snapshot()
        self.settle()

    # caps
    def test_384_gets_the_big_quantum(self):
        self.pick(384000)
        self.assertEqual(self.rate(), (384000, 2048))
        self.pick(192000)
        self.assertEqual(self.rate(), (192000, 1024))
        self.pick(96000)
        self.assertEqual(self.rate(), (96000, 0))

    def test_dsp_mode_clamps_to_48_and_restores(self):
        self.pick(384000)
        self.direct(False)
        self.assertEqual(self.rate(), (48000, 0))
        self.direct(True)
        self.assertEqual(self.rate(), (384000, 2048))

    def test_5_1_clamps_to_48_and_restores(self):
        self.pick(96000)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (48000, 0))
        self.layout(S.STEREO)
        self.assertEqual(self.rate(), (96000, 0))

    def test_pcm_rates_0_means_48_only(self):
        S.PARAMS["pcm_rates"] = "0"
        self.pick(192000)
        self.assertEqual(self.rate(), (48000, 0))

    # hands off
    def test_nothing_picked_means_nothing_written(self):
        self.direct(False)
        self.direct(True)
        self.layout(S.SURROUND)
        self.assertEqual([c for c in S.PW.calls if c[0] == "pw-metadata"], [])

    def test_values_set_by_hand_are_left_alone(self):
        self.pick(384000)
        S.PW.settings.update({"clock.force-rate": "192000", "clock.force-quantum": "1024"})
        S.PW.calls.clear()
        self.direct(False)
        self.layout(S.SURROUND)
        self.direct(True)
        self.assertEqual(self.rate(), (192000, 1024))
        self.assertEqual([c for c in S.PW.calls if c[0] == "pw-metadata"], [])

    def test_allowed_rates_always_full_and_file_never_capped(self):
        self.pick(384000)
        self.direct(False)
        full = "[ 48000 96000 192000 384000 ]"
        self.assertEqual(S.PW.settings["clock.allowed-rates"], full)
        with open(pipewire.RATES_CONF) as f:
            conf = f.read()
        self.assertIn(f"default.clock.allowed-rates = {full}", conf)

    # start-up
    def test_startup_waits_for_pipewire_then_respects_5_1(self):
        S.PW.set_profile(S.SURROUND)
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.pw.nodes = pipewire.Nodes([])     # nothing known yet
        self.ctx.restore_rate()
        self.assertEqual(self.rate(), (0, 0))       # didn't guess
        self.snapshot()
        self.settle()
        self.assertEqual(self.rate(), (48000, 0))

    def test_startup_does_not_override_a_forced_rate(self):
        S.PW.settings["clock.force-rate"] = "192000"
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.restore_rate()
        self.settle()
        self.assertEqual(self.rate()[0], 192000)

    # experimental 5.1 at 96 kHz
    def test_dragons_only_by_explicit_pick(self):
        self.layout(S.SURROUND)
        self.assertFalse(self.ctx.dragons_available())
        S.PARAMS["surround_96k"] = "1"
        self.assertTrue(self.ctx.dragons_available())
        self.pick(384000)                           # a high pick clamps to 48, not 96
        self.assertEqual(self.rate(), (48000, 0))
        self.pick(96000)
        self.assertEqual(self.rate(), (96000, 0))
        self.snapshot()
        self.settle()
        self.assertEqual(self.rate(), (96000, 0))   # polls keep it
        S.PARAMS["surround_96k"] = "0"
        self.snapshot()
        self.settle()
        self.assertEqual(self.rate(), (48000, 0))
        S.PARAMS["surround_96k"] = "1"
        self.snapshot()
        self.settle()
        self.assertEqual(self.rate(), (48000, 0))   # never comes back by itself


class RatePickerUiTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.pg = self.page(pages.PlaybackPage)

    def enabled(self):
        q = self.pg.quality
        return [q.itemText(k) for k in range(q.count()) if q.model().item(k).isEnabled()]

    def test_dsp_mode_offers_48_only(self):
        self.mixer.external(C.DIRECT, False)
        S.process(20)
        self.pg.refresh()
        self.assertEqual(self.enabled(), ["Auto (48 kHz)", "48 kHz"])
        self.assertIn("DSP mode runs at 48 kHz", self.pg.rate_note.text())

    def test_5_1_offers_96_only_with_the_driver_option(self):
        self.mixer.external(C.DIRECT, True)
        S.PW.set_profile(S.SURROUND)
        self.snapshot()
        self.pg.refresh()
        self.assertEqual(self.enabled(), ["Auto (48 kHz)", "48 kHz"])
        S.PARAMS["surround_96k"] = "1"
        self.pg.refresh()
        self.assertIn("96 kHz (experimental: here be dragons)", self.enabled())

    def test_rate_set_elsewhere_is_shown_and_labelled(self):
        S.PW.settings["clock.force-rate"] = "192000"
        self.pg.refresh()
        self.assertEqual(self.pg.quality.currentText(), "192 kHz")
        self.assertIn("outside the app", self.pg.rate_note.text())

    def test_bit_depth_goes_through_the_card_and_reopens_the_sink(self):
        other = 1 - self.card(C.BIT_DEPTH)
        self.pg._depth(self.pg.depth.findData(other))
        self.settle()
        self.assertEqual(self.card(C.BIT_DEPTH), other)
        self.assertTrue(any(c[:2] == ("pactl", "suspend-sink") for c in S.PW.calls))

    def test_old_driver_shows_depth_greyed(self):
        self.mixer.remove(C.BIT_DEPTH)
        S.PARAMS["pcm_bits"] = "32"
        self.pg.refresh()
        self.assertFalse(self.pg.depth.isEnabled())
        self.assertEqual(self.pg.depth.currentText(), "32-bit")


if __name__ == "__main__":
    unittest.main()
