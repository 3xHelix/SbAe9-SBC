# SPDX-License-Identifier: GPL-2.0-only
"""Glass: see-through backgrounds on any palette."""

import unittest

import support as S
from sbcommand import __main__ as M, pages, theme


class GlassTest(S.AppTestCase):
    def tearDown(self):
        theme.GLASS, theme.GLASS_OPACITY = False, 0.70
        theme.apply("command")
        super().tearDown()

    def test_backgrounds_go_see_through_on_every_palette(self):
        for name in theme.PALETTES:
            theme.apply(name)
            theme.GLASS = False
            solid = theme.stylesheet()
            self.assertNotIn("rgba(", theme.surface(theme.TITLE_BG))
            theme.GLASS = True
            glass = theme.stylesheet()
            self.assertIn(theme.rgba(theme.TITLE_BG, 0.7), glass, name)
            self.assertIn("background: transparent", glass.split("#titleBar")[0])
            self.assertNotEqual(solid, glass)
            self.assertAlmostEqual(theme.surface_q(theme.GRAPH_BG).alphaF(), 0.7, places=3)

    def test_controls_stay_solid(self):
        theme.apply("helix")
        theme.GLASS = True
        qss = theme.stylesheet()
        self.assertIn(f"background: {theme.PANEL}; border: none; padding: 7px 18px", qss)

    def test_window_is_translucent_only_with_glass(self):
        w = self.window()
        self.assertFalse(w.testAttribute(S.Qt.WA_TranslucentBackground))
        theme.GLASS = True
        w2 = self.window()
        self.assertTrue(w2.testAttribute(S.Qt.WA_TranslucentBackground))

    def test_switch_saves_and_reopens(self):
        pg = self.page(pages.SettingsPage)
        self.assertFalse(pg.glass.isChecked())
        self.assertFalse(pg.glass_opacity.isEnabled())
        asked = []
        self.ctx.restart_requested.connect(lambda: asked.append(True))
        pg.glass.setChecked(True)
        self.assertTrue(self.ctx.settings["glass"])
        self.assertEqual(asked, [True])

    def test_opacity_applies_live_and_is_saved(self):
        theme.GLASS = True
        pg = self.page(pages.SettingsPage)
        restyled = []
        self.ctx.restyle_requested.connect(lambda: restyled.append(True))
        pg.glass_opacity.setValue(52)               # snaps to 5s
        self.assertEqual(pg.glass_opacity.value(), 50)
        self.assertEqual(self.ctx.settings["glass_opacity"], 50)
        self.assertEqual(theme.GLASS_OPACITY, 0.5)
        self.assertTrue(restyled)
        self.assertEqual(pg.glass_lbl.text(), "50%")

    def test_opacity_range_is_95_to_30(self):
        theme.GLASS = True
        pg = self.page(pages.SettingsPage)
        self.assertEqual((pg.glass_opacity.minimum(), pg.glass_opacity.maximum()), (30, 95))
        pg.glass_opacity.setValue(30)
        self.assertEqual(theme.GLASS_OPACITY, 0.3)
        self.assertEqual(pg.glass_lbl.text(), "30%")
        self.assertEqual(theme.clamp_glass(5), 30)
        self.assertEqual(theme.clamp_glass(100), 95)

    def test_glass_runs_through_xwayland_for_the_blur(self):
        old = M.xcb_available
        M.xcb_available = lambda: True
        try:
            env = {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}
            M.set_scale(100, env, glass=True)
            self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")
            M.set_scale(100, env, glass=False)      # glass off: native again
            self.assertNotIn("QT_QPA_PLATFORM", env)
        finally:
            M.xcb_available = old
            theme.SCALE = 100


if __name__ == "__main__":
    unittest.main()
