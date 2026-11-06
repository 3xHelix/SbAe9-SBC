# SPDX-License-Identifier: GPL-2.0-only
"""The app's own title bar: no desktop frame, minimize / close, edge grips."""

import unittest

from PySide6.QtCore import Qt

import support as S
from sbcommand import pages


class FrameTest(S.AppTestCase):
    def test_frameless_by_default_with_buttons_and_grips(self):
        w = self.window()
        w.resize(1100, 700)
        S.process(20)
        self.assertTrue(w.frameless())
        self.assertTrue(all(b.isVisible() for b in w.win_buttons))
        self.assertEqual(len(w.grips), 8)
        self.assertTrue(all(g.isVisible() for g in w.grips))
        for g in w.grips:                            # every grip hugs the window's edge
            r = g.geometry()
            self.assertTrue(r.left() == 0 or r.top() == 0 or r.right() == 1099 or r.bottom() == 699, r)

    def test_settings_switch_brings_the_desktop_frame_back(self):
        pg = self.page(pages.SettingsPage)
        w = pg.window()
        pg.frameless.setChecked(False)
        S.process(20)
        self.assertFalse(w.frameless())
        self.assertFalse(self.ctx.settings["frameless"])
        self.assertFalse(any(b.isVisible() for b in w.win_buttons))
        self.assertFalse(any(g.isVisible() for g in w.grips))
        pg.frameless.setChecked(True)
        S.process(20)
        self.assertTrue(w.frameless())

    def test_minimize_and_close_buttons(self):
        w = self.window()
        minimize, close = w.win_buttons
        self.assertEqual(close.objectName(), "winClose")
        minimize.click()
        S.process(20)
        self.assertTrue(w.windowState() & Qt.WindowMinimized)


class AppIconTest(S.AppTestCase):
    def test_window_uses_the_png_icon_in_every_size(self):
        from sbcommand import window
        ic = window.app_icon()
        sizes = sorted(sz.width() for sz in ic.availableSizes())
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256, 512])
        self.assertFalse(self.window().windowIcon().isNull())

    def test_falls_back_to_the_wave_without_pngs(self):
        from sbcommand import window
        old = window.APPICON_DIR
        window.APPICON_DIR = "/nonexistent"
        try:
            self.assertFalse(window.app_icon().isNull())
        finally:
            window.APPICON_DIR = old


if __name__ == "__main__":
    unittest.main()
