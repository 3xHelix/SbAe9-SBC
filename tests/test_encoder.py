# SPDX-License-Identifier: GPL-2.0-only
"""The optical encoder (AC-3 / DTS over optical): page, service control, pipeline."""

import os
import shutil
import unittest

import support as S
from sbcommand import card as C, encoder, pages, pipewire


class Base(S.AppTestCase):
    def setUp(self):
        super().setUp()
        os.makedirs(os.path.dirname(encoder.UNIT_PATH), exist_ok=True)
        open(encoder.UNIT_PATH, "w").close()
        self.addCleanup(lambda: os.path.exists(encoder.UNIT_PATH) and os.remove(encoder.UNIT_PATH))
        self._which = shutil.which
        encoder.shutil.which = lambda tool: "/usr/bin/" + tool
        self.addCleanup(setattr, encoder.shutil, "which", self._which)
        S.PW.add_optical_out()
        S.PW.add_input("alsa_input.pci-0000_06_00.0.what_u_hear", "AE-9 What U Hear", 2, 996,
                       False, True)

    def page(self):
        self.snapshot()
        return super().page(pages.EncoderPage)

    def systemctl(self):
        return [c[2] for c in S.ENCODER["calls"] if c[:2] == ("systemctl", "--user")]


class EncoderTest(Base):
    def test_off_by_default(self):
        pg = self.page()
        self.assertTrue(pg.radios["off"].isChecked())
        self.assertTrue(pg.radios["ac3"].isEnabled())
        self.assertTrue(pg.radios["dts"].isEnabled())
        self.assertIn("Off", pg.status.text())

    def test_ac3_enables_and_starts_the_service(self):
        pg = self.page()
        pg.group.button(1).click()
        self.assertEqual(self.window().ctx.settings["encoder"], "ac3")
        self.assertIn("enable", self.systemctl())
        self.assertIn("restart", self.systemctl())
        self.assertIn("On — AC-3 from What U Hear (stereo)", pg.status.text())
        self.assertIn("2.0", pg.why.text())          # stereo source for now
        pg.group.button(0).click()                    # No Encoder
        self.assertEqual(self.window().ctx.settings["encoder"], "off")
        self.assertIn("disable", self.systemctl())
        self.assertFalse(S.ENCODER["active"])

    def test_without_ffmpeg_dts_is_greyed(self):
        S.ENCODER["ffmpeg"] = {"ac3"}
        pg = self.page()
        self.assertTrue(pg.radios["ac3"].isEnabled())
        self.assertFalse(pg.radios["dts"].isEnabled())
        self.assertIn("no DTS encoder", pg.radios["dts"].toolTip())

    def test_needs_the_separate_optical_output(self):
        S.PW.objects[:] = [o for o in S.PW.objects
                           if "optical_out" not in str((o.get("info") or {}).get("props", {}).get("node.name"))]
        pg = self.page()
        self.assertFalse(pg.radios["ac3"].isEnabled())
        self.assertIn("0.12.0", pg.why.text())

    def test_needs_install_sh(self):
        os.remove(encoder.UNIT_PATH)
        ok, msg = encoder.set_mode("ac3")
        self.assertFalse(ok)
        self.assertIn("install.sh", msg)

    def test_pipeline_commands(self):
        rec, enc, out = encoder.commands("ac3", "alsa_input.x.what_u_hear", 6)
        self.assertEqual(rec[:4], ["pw-record", "--raw", "--target", "alsa_input.x.what_u_hear"])
        self.assertIn("5.1", enc)
        self.assertEqual(enc[enc.index("-c:a") + 1], "ac3")
        self.assertEqual(enc[enc.index("-b:a") + 1], "640k")
        self.assertEqual(enc[-3:], ["-f", "spdif", "-"])
        self.assertIn("hw:AE9,4", out)
        self.assertEqual(rec[rec.index("--channel-map") + 1], "FL,FR,FC,LFE,RL,RR")
        self.assertEqual(rec[rec.index("--format") + 1], "s32")
        self.assertEqual(enc[enc.index("-f") + 1], "s32le")  # raw samples from pw-record
        self.assertEqual(enc[enc.index("-ar") + 1], "48000")
        self.assertEqual(rec[-1], "-")
        rec, enc, out = encoder.commands("dts", "x", 2)
        self.assertNotIn("--channel-map", rec)
        self.assertIn("stereo", enc)
        self.assertEqual(enc[enc.index("-c:a") + 1], "dca")
        self.assertIn("experimental", enc)

    def test_pipewire_10_has_no_raw_option(self):
        S.TOOLS["raw"] = False                    # PipeWire 1.0-1.2: "-" is raw already
        rec, enc, _ = encoder.commands("ac3", "x", 2)
        self.assertNotIn("--raw", rec)
        self.assertEqual(enc[enc.index("-f") + 1], "s32le")


class Surround51Test(Base):
    """Driver 0.12.1: the 5.1 duplex profile's 6-channel What U Hear."""
    NAME_51 = "alsa_input.pci-0000_06_00.0.what_u_hear_51"

    def to_51(self):
        """What the 5.1 duplex profile has: only the 6-channel What U Hear."""
        S.PW.set_profile(S.SURROUND)
        for o in S.PW.objects:
            props = (o.get("info") or {}).get("props", {})
            if props.get("node.name") == "alsa_input.pci-0000_06_00.0.what_u_hear":
                props["node.name"] = self.NAME_51
                props["audio.channels"] = 6

    def test_stereo_profile_encodes_2_0(self):
        n = pipewire.Nodes()
        self.assertIsNone(n.what_u_hear_51)
        src, ch = encoder.source(n)
        self.assertEqual((src["name"], ch), ("alsa_input.pci-0000_06_00.0.what_u_hear", 2))
        self.assertEqual(encoder.surround_profile(n), S.SURROUND)

    def test_51_profile_encodes_5_1(self):
        self.to_51()
        n = pipewire.Nodes()
        self.assertEqual(n.what_u_hear_51["name"], self.NAME_51)
        self.assertEqual(n.what_u_hear["name"], self.NAME_51)     # Recording page still has it
        self.assertEqual(n.extra_count.get("what_u_hear", 0), 0)    # not a duplicate
        self.assertEqual(encoder.source(n), (n.what_u_hear_51, 6))
        self.assertIsNone(encoder.surround_profile(n))

    def test_51_next_to_stereo_is_not_a_duplicate(self):
        S.PW.add_input(self.NAME_51, "AE-9 What U Hear", 2, 995, False, True)
        n = pipewire.Nodes()
        self.assertEqual(n.what_u_hear["name"], "alsa_input.pci-0000_06_00.0.what_u_hear")
        self.assertEqual(n.extra_count["what_u_hear"], 1)
        self.assertEqual(encoder.source(n)[1], 6)

    def test_page_offers_the_switch_to_5_1(self):
        pg = self.page()
        self.assertFalse(pg.surround_row.isVisible())             # encoder off
        pg.group.button(1).click()
        self.assertTrue(pg.surround_row.isVisible())
        self.assertIn("2.0", pg.why.text())
        S.ENCODER["calls"].clear()
        pg.surround_btn.click()
        self.assertEqual(S.PW.profile(), S.SURROUND)
        # the encoder lets go of the optical output while the profile is built
        self.assertEqual(self.systemctl(), ["is-active", "stop"])
        self.assertFalse(S.ENCODER["active"])
        S.process(10)
        self.assertTrue(S.wait_until(lambda: S.ENCODER["active"], 2))
        self.to_51()
        self.snapshot()
        pg.refresh()
        self.assertFalse(pg.surround_row.isVisible())
        self.assertIn("(5.1)", pg.status.text())
        self.assertEqual(pg.why.text(), "")


class OpticalPlaysTest(Base):
    """Playback > Digital's "Optical out plays": own / mirror / effects / encoder."""

    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.OPTICAL_OUT, True)
        self.mixer.add_bool(C.OPTICAL_MIRROR, False)

    def digital(self):
        self.snapshot()
        pg = super(Base, self).page(pages.PlaybackPage)
        pg.show_tab(2)
        S.process(20)
        pg.refresh()
        return pg

    def pick(self, pg, key):
        pg._pick_plays(pg.plays.findData(key))
        S.process(20)
        pg.refresh()

    def test_choices(self):
        pg = self.digital()
        self.assertEqual([pg.plays.itemData(k) for k in range(pg.plays.count())],
                         ["own", "mirror", "fx", "enc"])
        self.assertEqual(pg.plays.currentData(), "own")
        self.assertEqual(pg.plays.itemText(3), "Encoder: AC-3")

    def test_effects_turns_the_mirror_off_and_starts_the_loop(self):
        self.mixer.external(C.OPTICAL_MIRROR, True)
        pg = self.digital()
        self.assertEqual(pg.plays.currentData(), "mirror")
        self.pick(pg, "fx")
        self.assertFalse(self.mixer.values[C.OPTICAL_MIRROR])
        self.assertEqual(self.window().ctx.settings["encoder"], "fx")
        self.assertIn("restart", self.systemctl())
        self.assertEqual(pg.plays.currentData(), "fx")
        self.assertIn("echo", pg.plays_note.text())
        # the Encoder page says so, and its "No Encoder" leaves the loop alone
        ep = super(Base, self).page(pages.EncoderPage)
        self.assertIn("with effects", ep.status.text())
        S.ENCODER["calls"].clear()
        ep.group.button(0).click()
        self.assertEqual(self.systemctl(), [])
        self.assertEqual(self.window().ctx.settings["encoder"], "fx")

    def test_mirror_stops_the_service(self):
        pg = self.digital()
        self.pick(pg, "fx")
        self.pick(pg, "mirror")
        self.assertTrue(self.mixer.values[C.OPTICAL_MIRROR])
        self.assertEqual(self.window().ctx.settings["encoder"], "off")
        self.assertFalse(S.ENCODER["active"])
        self.assertEqual(pg.plays.currentData(), "mirror")

    def test_encoder_choice_uses_the_last_encoder(self):
        self.window().ctx.settings["encoder_last"] = "dts"
        pg = self.digital()
        self.assertEqual(pg.plays.itemText(3), "Encoder: DTS")
        self.pick(pg, "enc")
        self.assertEqual(self.window().ctx.settings["encoder"], "dts")
        self.pick(pg, "own")
        self.assertEqual(self.window().ctx.settings["encoder"], "off")
        self.assertFalse(self.mixer.values[C.OPTICAL_MIRROR])

    def test_no_effects_without_what_u_hear(self):
        S.PW.objects[:] = [o for o in S.PW.objects
                           if "what_u_hear" not in str((o.get("info") or {}).get("props", {}).get("node.name"))]
        pg = self.digital()
        self.assertEqual(pg.plays.findData("fx"), -1)


class EffectsLoopTest(Base):
    def test_both_streams_never_fall_back(self):
        cmd = encoder.fx_command("alsa_input.x.what_u_hear", 2, "alsa_output.x.optical_out")
        cap = cmd[cmd.index("--capture-props") + 1]
        play = cmd[cmd.index("--playback-props") + 1]
        for props in (cap, play):
            self.assertIn("node.dont-fallback=true", props)
            self.assertIn("node.linger=true", props)
            self.assertNotIn("'", props)                  # SPA JSON: double quotes only
        self.assertIn('target.object="alsa_input.x.what_u_hear"', cap)
        self.assertIn('target.object="alsa_output.x.optical_out"', play)
        self.assertIn("stream.dont-remix=true", cap)

    def test_wireplumber_04_also_never_reconnects(self):
        cmd = encoder.fx_command("a", 2, "o")
        self.assertNotIn("dont-reconnect", " ".join(cmd))   # 0.5 honours dont-fallback
        S.TOOLS["wp"] = (0, 4)
        cmd = encoder.fx_command("a", 2, "o")
        for props in (cmd[cmd.index("--capture-props") + 1], cmd[cmd.index("--playback-props") + 1]):
            self.assertIn("node.dont-reconnect=true", props)
            self.assertIn("node.dont-fallback=true", props)

    def test_51_source_is_downmixed(self):
        cap = encoder.fx_command("alsa_input.x.what_u_hear_51", 6, "o")[4]
        self.assertNotIn("dont-remix", cap)               # PipeWire mixes 6 -> 2
        self.assertIn("audio.position=[ FL FR ]", cap)

    def test_runs_only_while_the_main_output_plays(self):
        main = next(o for o in S.PW.objects
                    if (o.get("info") or {}).get("props", {}).get("media.class") == "Audio/Sink"
                    and "optical" not in o["info"]["props"]["node.name"])

        def wanted(state):
            main["info"]["state"] = state
            return encoder.fx_wanted(pipewire.Nodes())
        self.assertEqual(wanted("running"), ("alsa_input.pci-0000_06_00.0.what_u_hear", 2,
                                             "alsa_output.pci-0000_06_00.0.optical_out"))
        self.assertIs(wanted("idle"), False)              # between tracks: keep it
        self.assertIsNone(wanted("suspended"))            # stopped: profiles can load

    def test_needs_the_optical_sink_itself(self):
        S.PW.objects[:] = [o for o in S.PW.objects
                           if "optical_out" not in str((o.get("info") or {}).get("props", {}).get("node.name"))]
        self.assertIn("Optical Out", encoder.missing(encoder.FX))


if __name__ == "__main__":
    unittest.main()
