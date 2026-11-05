# SPDX-License-Identifier: GPL-2.0-only
""""Applying changes…": one stream change at a time, each settling first."""

import time
import unittest

import support as S
from sbcommand import applier, card as C, pages
from sbcommand.applier import Applier, Change


class ApplierUnitTest(unittest.TestCase):
    def setUp(self):
        S.reset()
        self.log = []
        self.a = Applier(lambda: None)
        self.a.step.connect(lambda t, n, tot: self.log.append(("step", t)))
        self.a.busy_changed.connect(lambda b: self.log.append(("busy", b)))

    def change(self, key, label=None, **kw):
        return Change(key, label or key, lambda: self.log.append(("run", label or key)), **kw)

    def finish(self):
        self.assertTrue(S.wait_until(lambda: not self.a.busy))

    def test_one_at_a_time_with_the_wait_in_between(self):
        t0 = time.monotonic()
        self.a.submit(self.change("a", min_ms=3000))
        self.a.submit(self.change("b", min_ms=3000))
        self.assertEqual([e for e in self.log if e[0] == "run"], [("run", "a")])
        self.finish()
        self.assertEqual([e for e in self.log if e[0] == "run"], [("run", "a"), ("run", "b")])
        self.assertGreaterEqual(time.monotonic() - t0, 2 * 3000 * applier.TIME_SCALE / 1000)
        self.assertEqual(self.log[0], ("busy", True))
        self.assertEqual(self.log[-1], ("busy", False))

    def test_latest_pick_per_setting_wins(self):
        self.a.submit(self.change("x"))
        self.a.submit(self.change("rate", "48"))
        self.a.submit(self.change("rate", "96"))
        self.finish()
        self.assertEqual([e[1] for e in self.log if e[0] == "run"], ["x", "96"])

    def test_change_no_longer_needed_is_skipped(self):
        self.a.submit(self.change("x"))
        self.a.submit(self.change("y", needed=lambda: False))
        self.finish()
        self.assertEqual([e[1] for e in self.log if e[0] == "run"], ["x"])

    def test_follow_ups_run_in_the_same_round(self):
        fired = []

        def follow():
            if not fired:
                fired.append(1)
                self.a.submit(self.change("clamp"))

        self.a.add_followup(follow)
        self.a.submit(self.change("profile"))
        self.finish()
        self.assertEqual([e for e in self.log if e[0] == "busy"], [("busy", True), ("busy", False)])
        self.assertEqual([e[1] for e in self.log if e[0] == "run"], ["profile", "clamp"])

    def test_waits_for_settled_but_gives_up_at_the_cap(self):
        t0 = time.monotonic()
        self.a.submit(self.change("stuck", min_ms=100, settled=lambda: False))
        self.finish()
        self.assertGreaterEqual(time.monotonic() - t0, applier.MAX_MS * applier.TIME_SCALE / 1000)


class OverlayTest(S.AppTestCase):
    def test_overlay_covers_the_window_while_applying(self):
        w = self.window()
        self.ctx.set_direct(False)
        S.process(5)
        self.assertTrue(w.applying.isVisible())
        self.assertEqual(w.applying.geometry(), w.centralWidget().rect())
        self.settle()
        self.assertFalse(w.applying.isVisible())

    def test_speakers_profile_and_rate_clamp_in_one_round(self):
        self.ctx.settings["rate_mode"] = 384000
        self.ctx.apply_rate(user=True)
        self.settle()
        steps, busy = [], []
        self.ctx.applier.step.connect(lambda t, n, tot: steps.append(t))
        self.ctx.applier.busy_changed.connect(busy.append)
        pg = self.page(pages.PlaybackPage)
        self.mixer.external(C.DIRECT, False)
        S.process(10)
        self.settle()
        steps.clear()
        busy.clear()
        self.mixer.external(C.DIRECT, True)
        S.process(10)
        self.settle()
        steps.clear()
        busy.clear()
        pg._speaker_cfg(pg.spk_cfg.findData(4))      # 5.1 speakers
        self.settle()
        self.assertEqual(steps, ["Speakers: 5.1", "5.1 stream", "Sample rate: 48 kHz"])
        self.assertEqual(busy, [True, False])

    def test_direct_mode_pick_that_changes_nothing_is_free(self):
        self.mixer.external(C.DIRECT, True)
        S.process(10)
        self.ctx.set_direct(True)
        self.assertFalse(self.ctx.applier.busy)


if __name__ == "__main__":
    unittest.main()
