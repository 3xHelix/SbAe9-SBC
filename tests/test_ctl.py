# SPDX-License-Identifier: GPL-2.0-only
"""`sbae9-sbc ctl`, the panel widget's command line: status and changes."""

import errno
import io
import json
import unittest
from unittest import mock
from contextlib import redirect_stdout

import support as S
from sbcommand import card as C, config, ctl, pipewire


class CtlTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        # ctl opens the card itself: hand it this test's fake (kept open)
        p1 = mock.patch.object(ctl.alsa, "Mixer", lambda idx: self.mixer)
        p2 = mock.patch.object(ctl.Card, "close", lambda self: None)
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)

    def ctl(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ctl.main(list(args))
        return code, json.loads(buf.getvalue())

    def test_status(self):
        S.PARAMS.update({"pcm_rates": "2", "dac_441": "1", "dsp_96k": "Y", "pcm_176k4": "Y"})
        self.mixer.external(C.DIRECT, False)
        S.PW.stream = (48000, 2)
        code, st = self.ctl("status")
        self.assertEqual(code, 0)
        self.assertTrue(st["present"])
        self.assertFalse(st["direct"])
        self.assertEqual(st["playable"], [48000, 96000])
        self.assertEqual(st["rates"], pipewire.ALL_RATES)
        self.assertEqual(st["live"], {"rate": 48000, "channels": 2})
        self.assertIsNone(st["phantom"])

    def test_direct_recaps_the_saved_rate(self):
        S.PARAMS.update({"version": "0.9.4", "surround_96k": "1", "dsp_96k": "Y"})
        self.mixer.external(C.DIRECT, True)
        self.ctl("rate", "192000")
        self.assertEqual(self.rate(), (192000, 1024))
        self.assertEqual(config.Settings()["rate_mode"], 192000)
        code, out = self.ctl("direct", "0")
        self.assertTrue(out["ok"])
        self.assertFalse(self.card(C.DIRECT))
        self.assertEqual(self.rate(), (96000, 0))       # DSP mode tops out at 96
        self.ctl("direct", "1")
        self.assertEqual(self.rate(), (192000, 1024))   # the pick comes back

    def test_quantum_never_below_what_the_rate_needs(self):
        self.mixer.external(C.DIRECT, True)
        self.ctl("rate", "384000")
        self.ctl("quantum", "256")
        self.assertEqual(self.rate(), (384000, 2048))
        self.ctl("rate", "48000")
        self.assertEqual(self.rate(), (48000, 256))
        self.assertTrue(self.ctl("quantum", "144")[1]["ok"])     # any value in range
        self.assertEqual(self.rate(), (48000, 144))
        code, out = self.ctl("quantum", "4")
        self.assertFalse(out["ok"])

    def test_preset_sets_rate_and_quantum_at_once(self):
        self.mixer.external(C.DIRECT, True)
        self.assertTrue(self.ctl("preset", "96000", "96")[1]["ok"])
        self.assertEqual(self.rate(), (96000, 96))
        s = config.Settings()
        self.assertEqual((s["rate_mode"], s["quantum"]), (96000, 96))
        self.assertTrue(self.ctl("preset", "192000", "0")[1]["ok"])
        self.assertEqual(self.rate(), (192000, 1024))

    def test_the_app_uses_the_quantum_pick(self):
        self.ctx.settings["quantum"] = 512
        self.ctx.settings["rate_mode"] = 96000
        self.mixer.external(C.DIRECT, True)
        self.ctx.apply_rate(user=True)
        self.settle()
        self.assertEqual(self.rate(), (96000, 512))

    def test_sbx_needs_dsp_mode_first(self):
        self.mixer.external(C.DIRECT, True)
        self.mixer.external(C.SBX, False)
        code, out = self.ctl("sbx", "1")
        self.assertFalse(out["ok"])
        self.assertIn("Direct Mode off", out["error"])
        self.assertFalse(self.card(C.SBX))
        code, st = self.ctl("status")
        self.assertFalse(st["sbx_enabled"])
        self.ctl("direct", "0")
        code, st = self.ctl("status")
        self.assertTrue(st["sbx_enabled"])
        self.assertTrue(self.ctl("sbx", "1")[1]["ok"])
        self.assertTrue(self.card(C.SBX))

    def test_toggles(self):
        self.mixer.external(C.DIRECT, True)
        self.mixer.external(C.OUTPUT, 0)
        self.ctl("direct", "toggle")
        self.assertFalse(self.card(C.DIRECT))
        self.mixer.external(C.SBX, False)
        self.ctl("sbx", "toggle")
        self.assertTrue(self.card(C.SBX))
        self.ctl("output", "toggle")
        self.assertEqual(self.card(C.OUTPUT), 1)
        self.ctl("output", "toggle")
        self.assertEqual(self.card(C.OUTPUT), 0)
        self.ctl("direct", "toggle")
        self.assertTrue(self.card(C.DIRECT))
        code, out = self.ctl("sbx", "toggle")          # two stages: not in Direct Mode
        self.assertFalse(out["ok"])

    def test_notify_says_how_it_left_things(self):
        said = []
        with mock.patch.object(ctl, "notify", lambda text, error=False: said.append((text, error))):
            self.mixer.external(C.DIRECT, True)
            self.ctl("direct", "toggle", "--notify")
            self.ctl("sbx", "toggle", "--notify")
            self.ctl("direct", "toggle", "--notify")
            self.ctl("sbx", "toggle", "--notify")
        self.assertEqual(said[0], ("DSP on (Direct Mode off)", False))
        self.assertEqual(said[1][0], "SBX on" if self.card(C.SBX) else "SBX off")
        self.assertEqual(said[2], ("Direct Mode on", False))
        self.assertTrue(said[3][1])                       # SBX refused in Direct Mode
        self.assertIn("Direct Mode off", said[3][0])

    def test_sbx_and_depth(self):
        self.mixer.external(C.DIRECT, False)
        self.ctl("sbx", "1")
        self.assertTrue(self.card(C.SBX))
        if self.mixer.has(C.BIT_DEPTH):
            self.ctl("depth", "1")
            self.assertEqual(self.card(C.BIT_DEPTH), 1)
            self.assertTrue(any(c[:2] == ("pactl", "suspend-sink") for c in S.PW.calls))

    def test_phantom(self):
        self.mixer.add_bool(C.HU_PHANTOM, False)
        code, st = self.ctl("status")
        self.assertEqual(st["phantom"], {"on": False, "writable": True})
        self.ctl("phantom", "1")
        self.assertTrue(self.card(C.HU_PHANTOM))
        self.ctl("phantom", "0")
        self.assertFalse(self.card(C.HU_PHANTOM))

    def test_phantom_busy_says_why(self):
        self.mixer.add_bool(C.HU_PHANTOM, False)
        orig = self.mixer.set

        def busy(name, value):
            if name == C.HU_PHANTOM:
                raise OSError(errno.EBUSY, "busy")
            orig(name, value)
        self.mixer.set = busy
        try:
            code, out = self.ctl("phantom", "1")
        finally:
            self.mixer.set = orig
        self.assertFalse(out["ok"])
        self.assertIn("card just started", out["error"])

    def test_settings_written_elsewhere_are_read_back(self):
        a, b = config.Settings(), config.Settings()
        a["quantum"] = 128
        self.assertEqual(b["quantum"], 128)
        b["palette"] = "helix"
        self.assertEqual(a["quantum"], 128)
        self.assertEqual(config.Settings()["quantum"], 128)


if __name__ == "__main__":
    unittest.main()
