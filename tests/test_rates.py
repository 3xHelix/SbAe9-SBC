# SPDX-License-Identifier: GPL-2.0-only
"""Sample rate: caps, quantum, hands off what others set, the drop-in file."""

import os
import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class RateBase(S.AppTestCase):
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



class RateTest(RateBase):
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
    def test_startup_reload_is_off_by_default(self):
        self.assertFalse(self.ctx.settings["restore_rate_on_start"])
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.restore_rate()
        self.settle()
        self.assertEqual(self.rate(), (0, 0))
        self.assertEqual([c for c in S.PW.calls if c[0] == "pw-metadata"], [])

    def test_startup_waits_for_pipewire_then_respects_5_1(self):
        S.PW.set_profile(S.SURROUND)
        self.ctx.settings["restore_rate_on_start"] = True
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.pw.nodes = pipewire.Nodes([])     # nothing known yet
        self.ctx.restore_rate()
        self.assertEqual(self.rate(), (0, 0))       # didn't guess
        self.snapshot()
        self.settle()
        self.assertEqual(self.rate(), (48000, 0))

    def test_startup_does_not_override_a_forced_rate(self):
        self.ctx.settings["restore_rate_on_start"] = True
        S.PW.settings["clock.force-rate"] = "192000"
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.restore_rate()
        self.settle()
        self.assertEqual(self.rate()[0], 192000)

    def test_startup_reload_can_be_switched_off(self):
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.settings["restore_rate_on_start"] = False
        self.ctx.restore_rate()
        self.settle()
        self.direct(False)                          # cap events don't write either
        self.direct(True)
        self.assertEqual([c for c in S.PW.calls if c[0] == "pw-metadata"], [])
        self.assertEqual(self.rate(), (0, 0))
        self.pick(192000)                           # a pick still works and is saved
        self.assertEqual(self.rate(), (192000, 1024))
        self.assertEqual(self.ctx.settings["rate_mode"], 192000)

    def test_settings_checkbox(self):
        pg = self.page(pages.SettingsPage)
        self.assertFalse(pg.restore_rate.isChecked())       # off until you want it
        self.assertFalse(pg.restore.isChecked())
        self.assertFalse(pg.autostart.isChecked())
        pg.restore_rate.setChecked(True)
        self.assertTrue(self.ctx.settings["restore_rate_on_start"])

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


class Driver070Test(RateBase):
    """Driver 0.7.0 fixed 5.1 at 96 kHz and turned it on by default."""

    def setUp(self):
        super().setUp()
        S.PARAMS.update({"version": "0.7.0", "surround_96k": "1"})

    def test_5_1_goes_to_96_like_any_rate(self):
        self.assertFalse(self.ctx.dragons_available())
        self.pick(384000)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (96000, 0))   # high pick clamps to 96, not 48
        self.layout(S.STEREO)
        self.assertEqual(self.rate(), (384000, 2048))

    def test_5_1_at_96_comes_back_at_start(self):
        S.PW.set_profile(S.SURROUND)
        self.snapshot()
        self.ctx.settings["restore_rate_on_start"] = True
        self.ctx.settings["rate_mode"] = 96000
        self.ctx.restore_rate()
        self.settle()
        self.assertEqual(self.rate(), (96000, 0))

    def test_surround_96k_off_keeps_5_1_at_48(self):
        S.PARAMS["surround_96k"] = "0"
        self.pick(96000)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (48000, 0))

    def test_dsp_mode_still_48(self):
        self.layout(S.SURROUND)
        self.pick(96000)
        self.direct(False)
        self.assertEqual(self.rate(), (48000, 0))

    def test_picker_shows_plain_96_on_5_1(self):
        pg = self.page(pages.PlaybackPage)
        self.layout(S.SURROUND)
        pg.refresh()
        q = pg.quality
        enabled = [q.itemText(k) for k in range(q.count()) if q.model().item(k).isEnabled()]
        self.assertEqual(enabled, ["Auto (48–96 kHz)", "48 kHz", "96 kHz"])
        self.assertIn("5.1 plays at 48/96 kHz", pg.rate_note.text())


class Driver094Test(RateBase):
    """Driver 0.9.4: 44.1/88.2 kHz in stereo (pcm_rates=2), 5.1 up to 192 kHz
    (surround_192k), and Direct Mode restarts a playing stream itself."""

    def setUp(self):
        super().setUp()
        S.PARAMS.update({"version": "0.9.4", "pcm_rates": "2", "surround_96k": "1",
                         "surround_192k": "1", "dac_441": "Y", "dsp_96k": "N"})

    def enabled(self, pg):
        q = pg.quality
        return [q.itemText(k) for k in range(q.count()) if q.model().item(k).isEnabled()]

    def test_44_1_and_88_2_play_in_stereo(self):
        for r in (44100, 88200):
            self.pick(r)
            self.assertEqual(self.rate(), (r, 0))

    def test_allowed_rates_list_the_cd_rates(self):
        self.pick(44100)
        full = "[ 44100 48000 88200 96000 192000 384000 ]"
        self.assertEqual(S.PW.settings["clock.allowed-rates"], full)
        with open(pipewire.RATES_CONF) as f:
            self.assertIn(f"allowed-rates = {full}", f.read())

    def test_start_updates_an_old_drop_in(self):
        old = "[ 48000 96000 192000 384000 ]"
        pipewire.set_rate_mode(0, pipewire.RATES)             # written by an older version
        self.assertEqual(S.PW.settings["clock.allowed-rates"], old)
        self.ctx.restore_rate()
        full = "[ 44100 48000 88200 96000 192000 384000 ]"
        self.assertEqual(S.PW.settings["clock.allowed-rates"], full)
        with open(pipewire.RATES_CONF) as f:
            self.assertIn(full, f.read())

    def test_start_leaves_rates_set_elsewhere(self):
        pipewire.set_rate_mode(0, pipewire.RATES)
        S.PW.settings["clock.allowed-rates"] = "[ 48000 ]"     # another tool
        self.ctx.restore_rate()
        self.assertEqual(S.PW.settings["clock.allowed-rates"], "[ 48000 ]")

    def test_start_without_a_drop_in_writes_nothing(self):
        self.ctx.restore_rate()
        self.assertFalse(os.path.exists(pipewire.RATES_CONF))

    def test_5_1_goes_to_192_and_moves_cd_rates_up(self):
        self.pick(192000)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (192000, 1024))
        self.pick(88200)                            # stereo only: 96 kHz on 5.1
        self.assertEqual(self.rate(), (96000, 0))
        self.pick(44100)
        self.assertEqual(self.rate(), (48000, 0))
        self.pick(384000)
        self.assertEqual(self.rate(), (192000, 1024))
        self.layout(S.STEREO)
        self.assertEqual(self.rate(), (384000, 2048))

    def test_surround_192k_off_keeps_5_1_at_96(self):
        S.PARAMS["surround_192k"] = "0"
        self.pick(192000)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (96000, 0))

    def test_dsp_mode_still_48(self):
        self.pick(44100)
        self.direct(False)
        self.assertEqual(self.rate(), (48000, 0))
        self.direct(True)
        self.assertEqual(self.rate(), (44100, 0))

    def test_dsp_96k_lets_dsp_mode_play_96(self):
        S.PARAMS["dsp_96k"] = "Y"
        for pick, dsp in ((96000, 96000), (44100, 48000), (88200, 96000),
                          (192000, 96000), (384000, 96000), (48000, 48000)):
            self.direct(True)
            self.pick(pick)
            self.direct(False)
            self.assertEqual(self.rate()[0], dsp, pick)
            self.direct(True)
            self.assertEqual(self.rate()[0], pick, pick)     # back with Direct Mode on

    def test_dsp_96k_on_5_1_too(self):
        S.PARAMS["dsp_96k"] = "Y"
        self.layout(S.SURROUND)
        self.pick(192000)
        self.direct(False)
        self.assertEqual(self.rate(), (96000, 0))

    def test_dsp_mode_picker_with_dsp_96k(self):
        S.PARAMS["dsp_96k"] = "Y"
        pg = self.page(pages.PlaybackPage)
        self.direct(False)
        pg.refresh()
        self.assertEqual(self.enabled(pg), ["Auto (48–96 kHz)", "48 kHz", "96 kHz"])
        self.assertIn("DSP mode runs at 48 or 96 kHz", pg.rate_note.text())
        S.PARAMS["dsp_96k"] = "N"
        pg.refresh()
        self.assertEqual(self.enabled(pg), ["Auto (48 kHz)", "48 kHz"])

    def test_picker_lists_cd_rates_and_greys_them_on_5_1(self):
        pg = self.page(pages.PlaybackPage)
        pg.refresh()
        self.assertEqual(self.enabled(pg), ["Auto (44.1–384 kHz)", "44.1 kHz", "48 kHz", "88.2 kHz",
                                            "96 kHz", "192 kHz", "384 kHz"])
        self.layout(S.SURROUND)
        pg.refresh()
        self.assertEqual(self.enabled(pg), ["Auto (48–192 kHz)", "48 kHz", "96 kHz", "192 kHz"])
        self.assertIn("5.1 plays at 48/96/192 kHz; 44.1/88.2/384 kHz are stereo only.",
                      pg.rate_note.text())

    def test_pcm_rates_1_hides_cd_rates(self):
        S.PARAMS["pcm_rates"] = "1"
        pg = self.page(pages.PlaybackPage)
        pg.refresh()
        self.assertNotIn("44.1 kHz", [pg.quality.itemText(k) for k in range(pg.quality.count())])

    def test_no_pause_and_play_hint(self):
        self.assertTrue(C.restarts_stream_on_direct())
        self.assertNotIn("pause and play", pages.DIRECT_TIP)
        del S.PARAMS["surround_192k"]
        self.assertFalse(C.restarts_stream_on_direct())


class Driver097Test(RateBase):
    """Driver 0.9.7: 176.4 kHz in stereo, with its pcm_176k4 option."""

    def setUp(self):
        super().setUp()
        S.PARAMS.update({"version": "0.9.7", "pcm_rates": "2", "surround_96k": "1",
                         "surround_192k": "1", "dac_441": "Y", "dsp_96k": "Y",
                         "pcm_176k4": "Y", "src_reclock": "Y"})

    def offered(self, pg):
        q = pg.quality
        return [q.itemText(k) for k in range(q.count()) if q.model().item(k).isEnabled()]

    def test_176_4_plays_in_stereo_with_the_big_buffer(self):
        self.pick(176400)
        self.assertEqual(self.rate(), (176400, 1024))
        self.assertEqual(S.PW.settings["clock.allowed-rates"],
                         "[ 44100 48000 88200 96000 176400 192000 384000 ]")

    def test_5_1_moves_it_to_192_and_dsp_mode_to_96(self):
        self.pick(176400)
        self.layout(S.SURROUND)
        self.assertEqual(self.rate(), (192000, 1024))
        self.layout(S.STEREO)
        self.direct(False)
        self.assertEqual(self.rate(), (96000, 0))
        self.direct(True)
        self.assertEqual(self.rate(), (176400, 1024))

    def test_dsp_mode_without_dsp_96k_goes_to_48(self):
        S.PARAMS["dsp_96k"] = "N"
        self.pick(176400)
        self.direct(False)
        self.assertEqual(self.rate(), (48000, 0))

    def test_picker_lists_it_and_greys_it_on_5_1(self):
        pg = self.page(pages.PlaybackPage)
        pg.refresh()
        self.assertIn("176.4 kHz", self.offered(pg))
        self.layout(S.SURROUND)
        pg.refresh()
        self.assertNotIn("176.4 kHz", self.offered(pg))
        self.assertIn("44.1/88.2/176.4/384 kHz are stereo only", pg.rate_note.text())

    def test_not_offered_without_pcm_176k4(self):
        for value in ("N", None):
            if value:
                S.PARAMS["pcm_176k4"] = value
            else:
                S.PARAMS.pop("pcm_176k4", None)
            pg = self.page(pages.PlaybackPage)
            pg.refresh()
            items = [pg.quality.itemText(k) for k in range(pg.quality.count())]
            self.assertNotIn("176.4 kHz", items)
            self.pick(44100)
            self.assertNotIn("176400", S.PW.settings["clock.allowed-rates"])

    def test_device_tab_lists_the_new_options(self):
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        text = pg.info.text()
        self.assertIn("pcm_176k4=Y", text)
        self.assertIn("src_reclock=Y", text)
        self.assertIn("44.1/48/88.2/96/176.4/192/384 kHz", text)


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
