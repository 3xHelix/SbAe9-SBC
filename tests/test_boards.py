"""Which card the app runs on (sbae9kit's board detection): the AE-9 now, the
AE-7 later. On an AE-9, or with no card, everything reads as before."""
import unittest

import support as S
from sbae9kit import ae9
from sbae9kit import testing as kt
from sbcommand import card as C, encoder, pipewire, window


class DetectTest(S.AppTestCase):
    def test_ae9(self):
        S.sound_cards(kt.HDMI_CARD, kt.USB_CARD, kt.AE9_CARD)
        self.assertEqual(C.card_id(), "AE9")
        self.assertEqual(C.card_short(), "AE-9")
        self.assertEqual(C.card_hints(), ("AE9", "Sound Blaster AE-9", "AE-9"))
        self.assertEqual(C.board().index, 2)
        self.assertEqual(C.for_card("Sound Blaster AE-9"), "Sound Blaster AE-9")

    def test_ae7(self):
        S.sound_cards(kt.HDMI_CARD, kt.AE7_CARD)
        self.assertEqual(C.card_id(), "AE7")
        self.assertEqual(C.card_short(), "AE-7")
        self.assertEqual(C.card_hints(), ("AE7", "Sound Blaster AE-7", "AE-7"))
        self.assertEqual(C.for_card("Please connect a Sound Blaster AE-9."),
                         "Please connect a Sound Blaster AE-7.")
        self.assertTrue(C.board().model.provisional)
        self.assertEqual(encoder.optical_pcm(), "hw:AE7,4")

    def test_ae7_on_the_in_tree_driver_is_ignored(self):
        S.sound_cards(kt.HDMI_CARD, kt.AE7_INTREE)
        self.assertIsNone(C.board())
        self.assertEqual(C.card_id(), "AE9")          # as before detection
        self.assertEqual(C.card_short(), "AE-9")

    def test_no_card(self):
        S.sound_cards(kt.HDMI_CARD, kt.USB_CARD)
        self.assertIsNone(C.board())
        self.assertEqual(C.card_hints(), ("AE9", "Sound Blaster AE-9", "AE-9"))
        self.assertEqual(encoder.optical_pcm(), "hw:AE9,4")
        self.assertEqual(C.for_card(window.NO_CARD_TITLE), window.NO_CARD_TITLE)

    def test_two_cards_takes_the_first(self):
        S.sound_cards(kt.HDMI_CARD, kt.AE7_CARD, kt.AE9_CARD)
        self.assertEqual(C.card_id(), "AE7")
        self.assertEqual([c.id for c in ae9.find_cards()], ["AE7", "AE9"])

    def test_ae5_is_reserved(self):
        S.sound_cards(kt.AE5_CARD)
        self.assertIsNone(C.board())

    def test_redetect_after_a_reload(self):
        S.sound_cards(kt.HDMI_CARD)
        self.assertIsNone(C.board())
        kt.fake_sound_tree(S.SOUND_ROOT, (kt.HDMI_CARD, kt.AE9_CARD), point=False)
        self.assertIsNone(C.board())                    # cached until asked again
        self.assertEqual(C.redetect().id, "AE9")


class CardPathsTest(S.AppTestCase):
    """The /proc paths follow the detected card's id."""

    def test_proc_paths(self):
        S.sound_cards(kt.AE7_CARD)
        C.cards()                  # detect before open() is faked
        seen = []
        real = S.REAL_CARD_STREAM

        def fake_open(path, *a, **k):
            seen.append(path)
            raise OSError
        import builtins
        from unittest import mock
        with mock.patch.object(builtins, "open", fake_open):
            self.assertIsNone(real())
        self.assertTrue(seen and seen[0].startswith("/proc/asound/AE7/pcm0p/"), seen)

    def test_card_listed(self):
        S.sound_cards(kt.AE7_CARD)
        from unittest import mock
        with mock.patch("os.path.exists", lambda p: p == "/proc/asound/AE7") as _:
            self.assertTrue(C.card_listed())


class WindowTest(S.AppTestCase):
    def test_ae9_title_unchanged(self):
        w = self.window()
        self.assertEqual(w.windowTitle(), "Sound Blaster Command — AE-9")
        self.assertEqual(w.device_name.text(), "AE-9")

    def test_ae7_title(self):
        S.sound_cards(kt.AE7_CARD)
        w = self.window()
        self.assertEqual(w.windowTitle(), "Sound Blaster Command — AE-7")
        self.assertEqual(w.device_name.text(), "AE-7")


if __name__ == "__main__":
    unittest.main()
