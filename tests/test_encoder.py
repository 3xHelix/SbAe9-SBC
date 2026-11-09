# SPDX-License-Identifier: GPL-2.0-only
"""The optical encoder (AC-3 / DTS over optical): page, service control, pipeline."""

import os
import shutil
import unittest

import support as S
from sbcommand import encoder, pages, pipewire


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
        self.assertEqual(rec[:3], ["pw-record", "--target", "alsa_input.x.what_u_hear"])
        self.assertIn("5.1", enc)
        self.assertEqual(enc[enc.index("-c:a") + 1], "ac3")
        self.assertEqual(enc[enc.index("-b:a") + 1], "640k")
        self.assertEqual(enc[-3:], ["-f", "spdif", "-"])
        self.assertIn("hw:AE9,4", out)
        self.assertEqual(rec[rec.index("--channel-map") + 1], "FL,FR,FC,LFE,RL,RR")
        self.assertEqual(rec[rec.index("--format") + 1], "s32")
        self.assertEqual(enc[enc.index("-f") + 1], "au")     # pw-record's pipe output
        self.assertEqual(rec[-1], "-")
        rec, enc, out = encoder.commands("dts", "x", 2)
        self.assertNotIn("--channel-map", rec)
        self.assertIn("stereo", enc)
        self.assertEqual(enc[enc.index("-c:a") + 1], "dca")
        self.assertIn("experimental", enc)


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


if __name__ == "__main__":
    unittest.main()
