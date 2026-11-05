# SPDX-License-Identifier: GPL-2.0-only
"""Speaker Config <-> PipeWire card profile (stereo / 5.1 stream)."""

import unittest

import support as S
from sbcommand import card as C, pages, pipewire


def profile_writes():
    return [c for c in S.PW.calls if c[0] == "pw-cli" and c[3] == "Profile"]


class LayoutProfileTest(S.AppTestCase):
    def nodes(self):
        return pipewire.Nodes(__import__("json").loads(S.PW.run("pw-dump")))

    def test_keeps_the_input_when_switching(self):
        self.assertEqual(pipewire.layout_profile(self.nodes(), True), S.SURROUND)
        S.PW.set_profile(S.SURROUND)
        self.assertEqual(pipewire.layout_profile(self.nodes(), False), S.STEREO)

    def test_output_only_profile_stays_output_only(self):
        S.PW.set_profile("output:analog-stereo")
        self.assertEqual(pipewire.layout_profile(self.nodes(), True), "output:analog-surround-51")

    def test_nothing_to_do(self):
        self.assertIsNone(pipewire.layout_profile(self.nodes(), False))   # already stereo
        S.PW.set_profile("pro-audio")
        self.assertIsNone(pipewire.layout_profile(self.nodes(), True))    # user's own choice

    def test_without_the_profile_set_there_is_no_switch(self):
        dev = S.PW.device["info"]["params"]
        dev["EnumProfile"] = [p for p in dev["EnumProfile"] if "surround" not in p["name"]]
        n = self.nodes()
        self.assertFalse(n.can_switch_layout())
        self.assertIsNone(pipewire.layout_profile(n, True))


class PlaybackSyncTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.pg = self.page(pages.PlaybackPage)
        self.mixer.external(C.DIRECT, False)
        self.settle()
        S.PW.calls.clear()
        self.mixer.writes.clear()

    def pick_speakers(self, name):
        k = self.ctx.card.items(C.SPEAKER_CFG).index(name)
        self.pg._speaker_cfg(self.pg.spk_cfg.findData(k))
        self.settle()
        self.pg.refresh()

    def test_5_1_speakers_switch_to_the_5_1_stream(self):
        self.pick_speakers("5.1")
        self.assertEqual(self.ctx.card.get_item(C.SPEAKER_CFG), "5.1")
        self.assertEqual(S.PW.profile(), S.SURROUND)
        self.assertEqual(self.pg.stream.currentText(), "5.1 stream")

    def test_4_0_needs_the_6_channel_stream_too(self):
        self.pick_speakers("4.0")
        self.assertEqual(S.PW.profile(), S.SURROUND)

    def test_back_to_2_1_goes_stereo(self):
        self.pick_speakers("5.1")
        self.pick_speakers("2.1")
        self.assertEqual(S.PW.profile(), S.STEREO)
        self.assertEqual(self.pg.stream.currentText(), "Stereo stream")

    def test_driver_changing_speaker_config_does_not_switch_the_profile(self):
        self.mixer.external(C.SPEAKER_CFG, "5.1")   # the driver follows the stream itself
        S.process(30)
        self.snapshot()
        self.assertEqual(profile_writes(), [])
        self.assertEqual(S.PW.profile(), S.STEREO)

    def test_profile_changed_in_kde_shows_up(self):
        S.PW.set_profile(S.SURROUND)
        self.snapshot()
        self.pg.refresh()
        self.assertEqual(self.pg.stream.currentText(), "5.1 stream")

    def test_stream_switch_works_in_direct_mode(self):
        self.mixer.external(C.DIRECT, True)
        S.process(20)
        self.pg.refresh()
        self.assertFalse(self.pg.spk_cfg.isEnabled())
        self.assertTrue(self.pg.stream.isEnabled())
        self.pg._switch_stream(True)
        self.settle()
        self.assertEqual(S.PW.profile(), S.SURROUND)

    def test_selector_hidden_without_the_profile_set(self):
        dev = S.PW.device["info"]["params"]
        dev["EnumProfile"] = [p for p in dev["EnumProfile"] if "surround" not in p["name"]]
        self.snapshot()
        self.pg.refresh()
        self.assertFalse(self.pg.stream.isVisibleTo(self.pg))
        self.pick_speakers("5.1")
        self.assertEqual(profile_writes(), [])


if __name__ == "__main__":
    unittest.main()
