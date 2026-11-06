# SPDX-License-Identifier: GPL-2.0-only
"""UI scale: the setting, the --scale flag and the Settings slider."""

import unittest

import support as S
from sbcommand import __main__ as M, pages, theme


class ScaleTest(S.AppTestCase):
    def tearDown(self):
        theme.SCALE = 100
        super().tearDown()

    def test_scale_sets_qt_factor_on_top_of_the_environment(self):
        env = {}
        M.set_scale(80, env)
        self.assertEqual(env["QT_SCALE_FACTOR"], "0.8")
        env = {"QT_SCALE_FACTOR": "2"}
        M.set_scale(85, env)
        self.assertEqual(env["QT_SCALE_FACTOR"], "1.7")
        env = {}
        M.set_scale(100, env)
        self.assertNotIn("QT_SCALE_FACTOR", env)    # 100% leaves Qt alone

    def test_relaunches_do_not_stack(self):
        env = {}
        M.set_scale(80, env)                        # first launch
        M.set_scale(80, env)                        # reopened copy inherits env
        self.assertEqual(env["QT_SCALE_FACTOR"], "0.8")
        M.set_scale(70, env)
        self.assertEqual(env["QT_SCALE_FACTOR"], "0.7")
        M.set_scale(100, env)                       # back to normal
        self.assertNotIn("QT_SCALE_FACTOR", env)
        env = {"QT_SCALE_FACTOR": "2"}              # user's own factor survives
        M.set_scale(50, env)
        M.set_scale(100, env)
        self.assertEqual(env["QT_SCALE_FACTOR"], "2")

    def test_scaled_ui_runs_through_xwayland_on_wayland(self):
        old = M.xcb_available
        M.xcb_available = lambda: True
        try:
            env = {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}
            M.set_scale(80, env)
            self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")
            M.set_scale(80, env)                    # relaunch keeps it
            self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")
            M.set_scale(100, env)                   # back to native Wayland
            self.assertNotIn("QT_QPA_PLATFORM", env)
            env = {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0", "QT_QPA_PLATFORM": "wayland"}
            M.set_scale(80, env)                    # the user's own choice wins
            self.assertEqual(env["QT_QPA_PLATFORM"], "wayland")
            env = {"WAYLAND_DISPLAY": "wayland-1"}  # no XWayland
            M.set_scale(80, env)
            self.assertNotIn("QT_QPA_PLATFORM", env)
            env = {"DISPLAY": ":0"}                 # an X11 session
            M.set_scale(80, env)
            self.assertNotIn("QT_QPA_PLATFORM", env)
        finally:
            M.xcb_available = old

    def test_scale_is_snapped_and_clamped(self):
        self.assertEqual(theme.clamp_scale(83), 85)
        self.assertEqual(theme.clamp_scale(10), 70)
        self.assertEqual(theme.clamp_scale(400), 150)
        self.assertEqual(theme.clamp_scale("junk"), 100)

    def test_relaunch_drops_a_one_off_scale(self):
        argv = ["-c", "code", "/here", "--scale", "80", "--palette", "helix", "--scale=90"]
        self.assertEqual(M.relaunch_args(argv), ["-c", "code", "/here", "--palette", "helix"])

    def test_slider_saves_and_asks_for_a_restart(self):
        pg = self.page(pages.SettingsPage)
        self.assertFalse(pg.scale_apply.isEnabled())
        asked = []
        self.ctx.restart_requested.connect(lambda: asked.append(True))
        pg.scale.setValue(77)
        self.assertEqual(pg.scale.value(), 75)
        self.assertEqual(pg.scale_lbl.text(), "75%")
        self.assertTrue(pg.scale_apply.isEnabled())
        pg.scale_apply.click()
        self.assertEqual(self.ctx.settings["ui_scale"], 75)
        self.assertEqual(asked, [True])


if __name__ == "__main__":
    unittest.main()
