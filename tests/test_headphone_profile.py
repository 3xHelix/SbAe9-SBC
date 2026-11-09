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
            for m in MODELS[1:]:
                open(os.path.join(d, C.HP_KEYS[m] + ".bin"), "wb").close()

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


    def full_list(self, slots="DT990=Beyerdynamic DT 990 Pro;;;"):
        """Driver 0.12.2: Off + Creative's 32 + 4 custom slots."""
        items = ["Off"] + list(C.HP_KEYS) + ["Beyerdynamic DT 990 Pro", "Custom 2", "Custom 3", "Custom 4"]
        S.PARAMS["hp_custom"] = slots
        self.mixer.add_enum(C.HP_PROFILE, items, 0)
        d = os.path.join(C.HP_DIRS[0], "creative-ae9", "hp")
        os.makedirs(d, exist_ok=True)
        for key in list(C.HP_KEYS.values()) + ["DT990"]:
            if key != "HD280Pro":                 # one of Creative's files missing
                open(os.path.join(d, key + ".bin"), "wb").close()
        return items

    def test_empty_custom_slots_hidden_missing_files_greyed(self):
        items = self.full_list()
        pg = self.playback()
        texts = [pg.hp_prof.itemText(k) for k in range(pg.hp_prof.count())]
        self.assertIn("Beyerdynamic DT 990 Pro", texts)
        self.assertNotIn("Custom 2", texts)                       # empty: hidden
        self.assertIn("SENNHEISER HD 280 Pro (file missing)", texts)
        row = pg.hp_prof.findText("SENNHEISER HD 280 Pro (file missing)")
        self.assertFalse(pg.hp_prof.model().item(row).isEnabled())
        # the rows map to the control's own numbers
        pg._pick_hp_profile(pg.hp_prof.findText("Beyerdynamic DT 990 Pro"))
        self.assertEqual(self.card(C.HP_PROFILE), items.index("Beyerdynamic DT 990 Pro"))

    def test_empty_slot_with_its_file_is_shown(self):
        self.full_list()
        open(os.path.join(C.HP_DIRS[0], "creative-ae9", "hp", "custom3.bin"), "wb").close()
        pg = self.playback()
        self.assertGreaterEqual(pg.hp_prof.findText("Custom 3"), 0)

    def test_a_picked_missing_profile_says_so(self):
        items = self.full_list()
        self.mixer.external(C.HP_PROFILE, items.index("SENNHEISER HD 280 Pro"))
        pg = self.playback()
        self.assertEqual(pg.hp_prof.currentText(), "SENNHEISER HD 280 Pro (file missing)")
        self.assertIn("file is missing", pg.hp_prof_note.text())

    def test_reload_after_install_picks_off_then_it_again(self):
        items = self.full_list()
        k = items.index("Beyerdynamic DT 990 Pro")
        self.mixer.external(C.HP_PROFILE, k)
        pg = self.playback()
        self.mixer.writes.clear()
        pg._reload_hp_slot("Beyerdynamic DT 990 Pro")
        self.assertEqual(self.mixer.writes, [(C.HP_PROFILE, 0)])
        S.wait_until(lambda: len(self.mixer.writes) > 1, 3)
        self.assertEqual(self.mixer.writes[-1], (C.HP_PROFILE, k))


if __name__ == "__main__":
    unittest.main()
