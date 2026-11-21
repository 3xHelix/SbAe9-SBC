"""Two of our cards in one machine: the title bar's card menu picks the one to
manage. And the card profile: texts worded for a card without the AE-9's head
unit, the optical out's top rate, pages a card doesn't have."""
import unittest
from unittest import mock

import support as S
from sbae9kit import testing as kt
from sbcommand import card as C, pages, pipewire, window


def two_cards():
    S.sound_cards(kt.HDMI_CARD, kt.AE7_CARD, kt.AE9_CARD)


class PickTest(S.AppTestCase):
    def test_first_card_without_a_pick(self):
        two_cards()
        self.assertEqual([c.id for c in C.cards()], ["AE7", "AE9"])
        self.assertEqual(C.card_id(), "AE7")

    def test_pick_by_id(self):
        two_cards()
        C.select("AE9")
        self.assertEqual(C.card_id(), "AE9")
        self.assertEqual(C.card_short(), "AE-9")
        self.assertEqual(C.card_hints()[0], "AE9")

    def test_pick_gone_falls_back_to_the_first(self):
        S.sound_cards(kt.HDMI_CARD, kt.AE9_CARD)
        C.select("AE7")
        self.assertEqual(C.card_id(), "AE9")

    def test_pick_survives_a_redetect(self):
        two_cards()
        C.select("AE9")
        self.assertEqual(C.redetect().id, "AE9")

    def test_twins_get_card_numbers(self):
        S.sound_cards(kt.HDMI_CARD, kt.AE9_CARD, ("AE9_1",) + kt.AE9_CARD[1:])
        found = C.cards()
        self.assertEqual([C.card_label(c, found) for c in found], ["AE-9 (card 1)", "AE-9 (card 2)"])
        self.assertEqual(C.card_label(found[0], found[:1]), "AE-9")

    def test_saved_pick_at_start(self):
        two_cards()
        self.ctx.settings["card"] = "AE9"
        from sbcommand.window import Context
        ctx = Context()
        try:
            self.assertEqual(C.card_id(), "AE9")
        finally:
            ctx.pw._timer.stop()
            ctx.applier._poll.stop()
            ctx.deleteLater()

    def test_nodes_of_the_picked_card_only(self):
        two_cards()
        ae7 = {"alsa.driver_name": "snd_hda_codec_creative_ae9", "api.alsa.path": "hw:1,0"}
        ae9_ = {"alsa.driver_name": "snd_hda_codec_creative_ae9", "api.alsa.path": "hw:2,0"}
        C.select("AE9")
        self.assertTrue(pipewire._is_ae9(ae9_))
        self.assertFalse(pipewire._is_ae9(ae7))
        C.select("AE7")
        self.assertTrue(pipewire._is_ae9(ae7))
        self.assertFalse(pipewire._is_ae9(ae9_))

    def test_one_card_takes_any_of_ours(self):
        """As before the pick: one card, no stricter matching."""
        node = {"alsa.driver_name": "snd_hda_codec_creative_ae9", "api.alsa.path": "hw:7,0"}
        self.assertTrue(pipewire._is_ae9(node))


class MenuTest(S.AppTestCase):
    def test_no_arrow_with_one_card(self):
        w = self.window()
        self.assertTrue(w.card_name.arrow.isHidden())
        self.assertEqual(w.card_name.name.text(), "AE-9")

    def test_arrow_and_menu_with_two(self):
        two_cards()
        w = self.window()
        self.assertFalse(w.card_name.arrow.isHidden())
        acts = w.card_name.build_menu().actions()
        self.assertEqual([a.text() for a in acts], ["AE-7", "AE-9"])
        self.assertEqual([a.isChecked() for a in acts], [True, False])
        self.assertIn("AE-9 at 0xfbf04000", acts[1].toolTip())

    def test_picking_switches_the_card(self):
        two_cards()
        w = self.window()
        self.assertEqual(w.windowTitle(), "Sound Blaster Command — AE-7")
        w.card_name.build_menu().actions()[1].trigger()
        S.process()
        self.assertEqual(self.ctx.settings["card"], "AE9")
        self.assertEqual(C.card_id(), "AE9")
        self.assertTrue(self.ctx.card.present)
        self.assertEqual(w.card_name.name.text(), "AE-9")
        self.assertEqual(w.windowTitle(), "Sound Blaster Command — AE-9")
        self.assertEqual([a.isChecked() for a in w.card_name.build_menu().actions()], [False, True])

    def test_switch_rewords_the_window(self):
        two_cards()
        w = self.window()
        texts = lambda: " ".join(x.text() for x in w.findChildren(window.QLabel))  # noqa: E731
        frameless = next(c for c in w.findChildren(window.QAbstractButton)
                         if "title bar" in c.text())
        self.assertIn("drag the AE-7 header", frameless.text())
        self.ctx.switch_to_card("AE9")
        S.process()
        self.assertIn("drag the AE-9 header", frameless.text())
        self.assertNotIn("AE-7", texts())

    def test_same_card_is_a_no_op(self):
        w = self.window()
        with mock.patch.object(self.ctx.card, "switch_to") as sw:
            self.ctx.switch_to_card("AE9")
        sw.assert_not_called()
        del w


class ProfileTest(S.AppTestCase):
    def test_ae9_wording_unchanged(self):
        self.assertTrue(C.has_head_unit())
        self.assertEqual(C.volume_tip(), "Volume (same as the head unit knob)")
        self.assertEqual(window.output_tip(),
                         "Switch between speakers (the card's RCA out) and headphones "
                         "(the head unit's headphone jacks)")
        self.assertEqual(pages.hp_where(), "Head unit")
        self.assertEqual(pages.headphones_tip(), pages.HEADPHONES_TIP)
        self.assertEqual(pages.optical_top_khz(), "192")
        self.assertEqual(pages.mic_name(None), "AE-9 Head Unit Mic / Aux")

    def test_no_card_words_as_the_ae9(self):
        S.sound_cards(kt.HDMI_CARD)
        self.assertTrue(C.has_head_unit())
        self.assertEqual(C.model().key, "ae9")

    def test_ae7_wording(self):
        S.sound_cards(kt.AE7_CARD)
        self.assertFalse(C.has_head_unit())
        self.assertEqual(C.volume_tip(-10), "Volume -10.0 dB")
        self.assertNotIn("head unit", window.output_tip())
        self.assertEqual(pages.hp_where(), "Headphone jack")
        self.assertNotIn("head unit", pages.headphones_tip())
        self.assertEqual(pages.optical_top_khz(), "96")
        self.assertEqual(pages.mic_name(None), "AE-7 Mic In")
        self.assertEqual(pages.output_name(None), "Sound Blaster AE-7")

    def test_ae7_window(self):
        S.sound_cards(kt.AE7_CARD)
        w = self.window()
        self.assertEqual(w.vol.toolTip()[:6], "Volume")
        self.assertNotIn("head unit", w.vol.toolTip())
        self.assertNotIn("head unit", w.output_switch.toolTip())

    def test_page_needs_a_feature(self):
        enc = next(e for e in window.NAV if e and e[0] == "Encoder")
        self.assertTrue(window.page_offered(enc))          # the kit doesn't list it: there
        with mock.patch.object(C, "feature", lambda name, default=None: False):
            self.assertFalse(window.page_offered(enc))
            w = self.window()
            i = [e for e in window.NAV if e].index(enc)
            self.assertTrue(w.buttons[i].isHidden())
            self.assertFalse(w.buttons[0].isHidden())

    def test_info_text_follows_the_card(self):
        S.sound_cards(kt.AE7_CARD)
        b = pages.info_button(lambda: f"Boost for {pages.mic_boost_where()} on the AE-9.")
        self.assertEqual(b.toolTip(), "Boost for the card's mic jack on the AE-7.")


if __name__ == "__main__":
    unittest.main()
