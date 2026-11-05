# SPDX-License-Identifier: GPL-2.0-only
"""EQ preset list, per-channel volume, the speaker test, small UI rules."""

import os
import tempfile
import unittest

import support as S
from sbcommand import card as C, pages, pipewire, profiles, theme


class EqPresetTest(S.AppTestCase):
    def listing(self, pg):
        out = []
        for i in range(pg.combo.count()):
            kind = (pg.combo.itemData(i) or (None,))[0]
            text = pg.combo.itemText(i)
            out.append("--" if not text and kind is None else f"[{text}]" if kind == "heading" else text)
        return out

    def test_new_driver_order_with_games_heading(self):
        pg = self.page(pages.EqPage)
        got = self.listing(pg)
        self.assertEqual(got[:16], S.NEW_EQ_ORDER[:16])
        self.assertEqual(got[16:22], ["--", "[Games]", "Project CARS", "Racing", "Rocket League", "RPG"])
        heading = pg.combo.model().item(got.index("[Games]"))
        self.assertFalse(heading.isEnabled())

    def test_old_driver_order_shown_as_is(self):
        self.mixer.set_items(C.EQ_PRESET, S.OLD_EQ_ORDER)
        pg = self.page(pages.EqPage)
        got = self.listing(pg)
        self.assertEqual(got[:20], S.OLD_EQ_ORDER)
        self.assertNotIn("[Games]", got)

    def test_picking_a_preset_sets_it_by_name(self):
        pg = self.page(pages.EqPage)
        pg._picked(pg.combo.findText("Rock"))
        self.assertEqual(self.ctx.card.get_item(C.EQ_PRESET), "Rock")
        self.assertTrue(self.card(C.EQ_ON))

    def test_app_preset_table_matches_the_driver(self):
        self.assertEqual(list(profiles.HW_EQ_PRESETS), S.NEW_EQ_ORDER)
        self.assertTrue(all(len(v) == 11 for v in profiles.HW_EQ_PRESETS.values()))


class MixerChannelTest(S.AppTestCase):
    def test_stereo_rows_and_route_write(self):
        pg = self.page(pages.MixerPage)
        self.assertEqual(pg.chan_map, ["FL", "FR"])
        pg.chan_sliders[1].setValue(14)
        S.process(100)
        route = [c for c in S.PW.calls if c[0] == "pw-cli" and c[3] == "Route"]
        self.assertTrue(route, "volume should go on the card's output route")
        self.assertIn("index: 1, device: 1", route[-1][4])
        left, right = S.PW.channel_volumes()
        self.assertAlmostEqual(right, 0.14 ** 3, places=5)

    def test_link_moves_all_channels(self):
        pg = self.page(pages.MixerPage)
        pg.link.setChecked(True)
        pg.chan_sliders[0].setValue(40)
        self.assertEqual([s.value() for s in pg.chan_sliders], [40, 40])

    def test_six_rows_on_5_1(self):
        S.PW.set_profile(S.SURROUND)
        pg = self.page(pages.MixerPage)
        self.snapshot()
        pg.refresh()
        self.assertEqual(pg.chan_map, ["FL", "FR", "FC", "LFE", "RL", "RR"])

    def test_pactl_fallback_without_a_route(self):
        S.PW.device["info"]["params"]["Route"] = []
        self.snapshot()
        pipewire.set_channel_volumes(self.ctx.pw.nodes, [0.1, 0.2])
        self.assertTrue(any(c[:2] == ("pactl", "set-sink-volume") for c in S.PW.calls))


class SpeakerTestTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.voices = tempfile.mkdtemp()
        self._old_dir = pipewire.VOICE_DIR
        pipewire.VOICE_DIR = self.voices
        for f in pipewire.VOICE_FILES.values():
            open(os.path.join(self.voices, f), "wb").close()

    def tearDown(self):
        pipewire.VOICE_DIR = self._old_dir
        super().tearDown()

    def test_voice_on_one_channel_position(self):
        self.ctx.tone.start("sink", ["center"], surround=True)
        prog, args = S.PW.processes[-1]
        self.assertEqual(prog, "pw-play")
        self.assertEqual(args[:4], ["--target", "sink", "--channels", "1"])
        self.assertEqual(args[4:6], ["--channel-map", "FC"])
        self.assertTrue(args[-1].endswith("Front_Center.wav"))
        self.ctx.tone.stop()

    def test_tone_fallback_without_alsa_utils(self):
        pipewire.VOICE_DIR = "/nonexistent"
        self.ctx.tone.start("sink", ["rear-left"], surround=True)
        args = S.PW.processes[-1][1]
        self.assertIn("--channels", args)
        self.assertEqual(args[args.index("--channels") + 1], "6")
        self.ctx.tone.stop()

    def test_channels_follow_the_layout(self):
        pg = self.page(pages.PlaybackPage)
        self.mixer.external(C.DIRECT, False)
        self.assertEqual(pg.test_channels(), ["left", "right"])   # stereo stream
        S.PW.set_profile(S.SURROUND)
        self.mixer.external(C.SPEAKER_CFG, "4.0")
        self.snapshot()
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.test_channels(), ["left", "right", "rear-right", "rear-left"])
        self.mixer.external(C.SPEAKER_CFG, "5.1")
        S.process(20)
        pg.refresh()
        self.assertEqual(len(pg.test_channels()), 6)


class UiRulesTest(S.AppTestCase):
    def test_warning_red_is_the_same_in_every_palette(self):
        reds = set()
        for name in theme.PALETTES:
            theme.apply(name)
            reds.add(theme.DANGER)
        theme.apply("command")
        self.assertEqual(len(reds), 1)

    def test_bottom_bar_says_off_not_sbx_off(self):
        w = self.window()
        self.mixer.external(C.DIRECT, False)
        self.mixer.external(C.SBX, False)
        S.process(20)
        w.refresh()
        self.assertEqual(w.profile_lbl.text(), "Off")


if __name__ == "__main__":
    unittest.main()
