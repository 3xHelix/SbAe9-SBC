# SPDX-License-Identifier: GPL-2.0-only
"""PipeWire 1.0 / WirePlumber 0.4 (Ubuntu 24.04, Mint 22)."""

import subprocess
import unittest

import support as S
from sbcommand import pipewire


class OldPipeWireTest(S.AppTestCase):
    def meter_args(self):
        S.PW.processes.clear()
        m = pipewire.LevelMeter()
        m.start("alsa_input.x")
        m.stop()
        return next(a for p, a in S.PW.processes if p == "pw-record")

    def test_meter_asks_for_raw_only_where_it_exists(self):
        self.assertIn("--raw", self.meter_args())
        S.TOOLS["raw"] = False
        self.assertNotIn("--raw", self.meter_args())


class VersionProbeTest(unittest.TestCase):
    """The real probes, on canned tool output."""
    def setUp(self):
        old = subprocess.run
        self.addCleanup(setattr, subprocess, "run", old)
        pipewire._TOOL_HELP.clear()
        pipewire._WP.clear()
        self.addCleanup(pipewire._TOOL_HELP.clear)
        self.addCleanup(pipewire._WP.clear)

    def fake(self, help_text, wp_text):
        class R:
            def __init__(self, out):
                self.stdout, self.stderr, self.returncode = out, "", 0
        subprocess.run = lambda args, **k: R(help_text if args[0] == "pw-record" else wp_text)

    def test_pipewire_10_and_wireplumber_04(self):
        has_option, wp_version = S.REAL_PROBES
        self.fake("  -r, --remote   Remote daemon name\n", "wireplumber\nCompiled with libwireplumber 0.4.17\n")
        self.assertFalse(has_option("pw-record", "--raw"))
        self.assertEqual(wp_version(), (0, 4))

    def test_current_versions(self):
        has_option, wp_version = S.REAL_PROBES
        self.fake("  -a, --raw   RAW mode\n", "Compiled with libwireplumber 0.5.19\n")
        self.assertTrue(has_option("pw-record", "--raw"))
        self.assertEqual(wp_version(), (0, 5))


if __name__ == "__main__":
    unittest.main()
