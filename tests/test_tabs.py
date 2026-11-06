# SPDX-License-Identifier: GPL-2.0-only
"""Page tabs (Playback, Recording, Settings) and the start-at-login switch."""

import os
import unittest

import support as S
from sbcommand import config, pages


class TabsTest(S.AppTestCase):
    def test_tab_names(self):
        for cls, names in ((pages.PlaybackPage, ["Speakers/Headphones", "Digital"]),
                           (pages.RecordingPage, ["Microphone", "Other Input"]),
                           (pages.SettingsPage, ["Application", "Device"])):
            pg = self.page(cls)
            self.assertEqual([b.text() for b in pg.tab_bar.buttons], names)

    def test_clicking_a_tab_switches_and_is_remembered(self):
        pg = self.page(pages.SettingsPage)
        self.assertEqual(pg.tab_stack.currentIndex(), 0)
        self.assertTrue(pg.scale.isVisible())
        pg.tab_bar.buttons[1].click()
        S.process(20)
        self.assertTrue(pg.table.isVisible())
        self.assertFalse(pg.scale.isVisible())
        again = self.page(pages.SettingsPage)        # e.g. after a palette switch
        self.assertEqual(again.tab_stack.currentIndex(), 1)
        self.assertEqual(again.tab_bar.current(), 1)
        self.assertEqual(self.page(pages.PlaybackPage).tab_stack.currentIndex(), 0)


class AutostartTest(S.AppTestCase):
    def test_switch_writes_and_removes_the_autostart_entry(self):
        path = config.autostart_path()
        self.assertTrue(path.startswith(os.environ["XDG_CONFIG_HOME"]))   # never the real one
        pg = self.page(pages.SettingsPage)
        self.assertFalse(pg.autostart.isChecked())
        pg.autostart.setChecked(True)
        with open(path) as f:
            entry = f.read()
        self.assertIn("Exec=", entry)
        self.assertTrue(entry.split("Exec=")[1].split("\n")[0].endswith("sbae9-sbc"))
        self.assertTrue(self.page(pages.SettingsPage).autostart.isChecked())
        pg.autostart.setChecked(False)
        self.assertFalse(os.path.exists(path))


class DesktopTest(S.AppTestCase):
    def test_window_is_named_after_the_app_for_docks(self):
        from sbcommand import __main__ as M
        self.assertEqual(M.qt_argv(["-platform", "xcb"]), ["sbae9-sbc", "-platform", "xcb"])

    def test_alsamixer_opens_in_the_first_terminal_installed(self):
        import shutil
        old = shutil.which
        try:
            shutil.which = lambda name: "/usr/bin/" + name if name in ("ptyxis", "xterm") else None
            self.assertEqual(pages.alsamixer_command(0), ["ptyxis", "--", "alsamixer", "-c", "0"])
            shutil.which = lambda name: None
            self.assertIsNone(pages.alsamixer_command(0))
        finally:
            shutil.which = old


if __name__ == "__main__":
    unittest.main()
