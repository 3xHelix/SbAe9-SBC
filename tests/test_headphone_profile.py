# SPDX-License-Identifier: GPL-2.0-only
"""Playback → Headphones: the Headphone Profile picker (Creative's EQ curves)."""

import os
import unittest

import support as S
from sbcommand import card as C, pages

MODELS = ["Off", "AKG M220", "Apple Earphone", "audio-technica ATH-M50", "Sound BlasterX P5"]


class HeadphoneProfileTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.external(C.DIRECT, False)
        self.mixer.external(C.OUTPUT, 1)

    def add(self, value=0, curves=True):
        self.mixer.add_enum(C.HP_PROFILE, MODELS, value)
        if curves:
            d = os.path.join(C.HP_DIRS[0], "creative-ae9", "hp")
            os.makedirs(d, exist_ok=True)
            for f in ("AKGM220.bin", "ATHM50.bin"):
                open(os.path.join(d, f), "wb").close()

    def playback(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def test_hidden_on_older_drivers(self):
        self.assertFalse(self.playback().hp_prof_row.isVisible())

    def test_lists_the_drivers_models_and_sets_one(self):
        self.add()
        pg = self.playback()
        self.assertTrue(pg.hp_prof_row.isVisible())
        self.assertEqual([pg.hp_prof.itemText(k) for k in range(pg.hp_prof.count())], MODELS)
        self.assertTrue(pg.hp_prof.isEnabled())
        pg.hp_prof.activated.emit(3)
        self.assertEqual(self.card(C.HP_PROFILE), 3)
        self.assertFalse(pg.hp_prof_note.isVisible())

    def test_follows_changes_from_elsewhere(self):
        self.add()
        pg = self.playback()
        self.mixer.external(C.HP_PROFILE, 1)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.hp_prof.currentText(), "AKG M220")

    def test_greyed_without_curves_and_says_how_to_get_them(self):
        self.add(curves=False)
        pg = self.playback()
        self.assertFalse(pg.hp_prof.isEnabled())
        self.assertIn("ae9-get-firmware", pg.hp_prof_note.text())

    def test_greyed_in_direct_mode(self):
        self.add()
        self.mixer.external(C.DIRECT, True)
        pg = self.playback()
        self.assertFalse(pg.hp_prof.isEnabled())
        self.assertIn("Direct Mode off", pg.hp_prof_note.text())

    def test_says_when_it_rests(self):
        self.add(value=3)
        self.mixer.external(C.OUTPUT, 0)
        pg = self.playback()
        self.assertIn("Headphones", pg.hp_prof_note.text())
        self.mixer.external(C.OUTPUT, 1)
        S.PW.stream = (96000, 2)
        S.process(20)
        pg.refresh()
        self.assertIn("48 kHz", pg.hp_prof_note.text())
        S.PW.stream = (48000, 2)
        pg.refresh()
        self.assertFalse(pg.hp_prof_note.isVisible())


    def test_renamed_items_show_live(self):
        """Driver 0.12.2's custom slots: renaming one (hp_custom) sends an INFO
        event, and the picker shows the new name without a restart."""
        self.add()
        pg = self.playback()
        named = MODELS + ["Beyerdynamic DT 990 Pro", "Custom 2"]
        self.mixer.set_items(C.HP_PROFILE, named)
        self.mixer._event(self.mixer.controls[C.HP_PROFILE].numid, S.alsa.EVENT_MASK_INFO)
        S.process(50)       # the card's event watcher; no manual refresh
        self.assertEqual([pg.hp_prof.itemText(k) for k in range(pg.hp_prof.count())], named)


    def test_says_the_encoder_holds_profiles_back(self):
        self.add(value=1)
        S.ENCODER["active"] = True
        self.ctx.settings["encoder"] = "ac3"
        pg = self.playback()
        self.assertIn("switch the encoder off", pg.hp_prof_note.text())
        self.ctx.settings["encoder"] = "fx"       # the effects loop stops by itself
        pg.refresh()
        self.assertNotIn("encoder", pg.hp_prof_note.text())


if __name__ == "__main__":
    unittest.main()
