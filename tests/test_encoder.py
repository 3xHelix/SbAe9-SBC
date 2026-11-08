# SPDX-License-Identifier: GPL-2.0-only
"""The optical encoder (AC-3 / DTS over optical): page, service control, pipeline."""

import os
import shutil
import unittest

import support as S
from sbcommand import encoder, pages


class EncoderTest(S.AppTestCase):
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
        self.assertEqual(rec[-1], "-")
        rec, enc, out = encoder.commands("dts", "x", 2)
        self.assertNotIn("--channel-map", rec)
        self.assertEqual(enc[enc.index("-c:a") + 1], "dca")
        self.assertIn("experimental", enc)


if __name__ == "__main__":
    unittest.main()
