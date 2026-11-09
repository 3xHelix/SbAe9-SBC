# SPDX-License-Identifier: GPL-2.0-only
"""Driver 0.12.2: Voice Clarity, the card's mic monitor, headphone virtualization."""

import unittest

import support as S
from sbcommand import card as C, pages

MICEQ = ["Off", "Preset 1 - Reduce Bass, harshness, improve clarity", "Preset 10 - Improve clarity"]
MORPHS = ["Neutral", "Male", "Female", "Kid", "Elderly", "Deep Voice", "From Up North", "Unstable",
          "Emo", "Elf", "Dwarf", "Demon", "Infiltrator", "Brute", "Orc", "Marine", "Chipmunk", "Robot"]


class VoiceClarityTest(S.AppTestCase):
    def add(self):
        for name in (C.VC, C.VC_AEC, C.VC_NR, C.VC_SVM):
            self.mixer.add_bool(name, False)
        self.mixer.add_enum(C.VC_MICEQ, MICEQ, 0)
        self.mixer.add_enum(C.VC_MORPH, MORPHS, 0)

    def tab(self):
        pg = self.page(pages.RecordingPage)
        pg.show_tab(1)
        pg.refresh()
        return pg

    def test_needs_the_driver(self):
        pg = self.tab()
        self.assertTrue(pg.vc.missing.isVisible())
        self.assertFalse(pg.vc.master.isVisible())

    def test_effects_wait_for_the_master(self):
        self.add()
        pg = self.tab()
        self.assertFalse(pg.vc.fx[C.VC_AEC][0].isEnabled())
        self.assertFalse(pg.vc.miceq.isEnabled())
        self.assertIn("Off", pg.vc.note.text())
        pg.vc.master.setChecked(True)
        self.assertIn((C.VC, True), self.mixer.writes)
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.vc.fx[C.VC_AEC][0].isEnabled())
        self.assertIn("nothing picked yet", pg.vc.note.text())
        pg.vc.fx[C.VC_NR][0].setChecked(True)
        self.assertIn((C.VC_NR, True), self.mixer.writes)
        S.process(20)
        pg.refresh()
        self.assertIn("48 kHz", pg.vc.note.text())

    def test_mic_eq_and_morph_from_the_drivers_names(self):
        self.add()
        self.mixer.external(C.VC, True)
        pg = self.tab()
        self.assertEqual([pg.vc.miceq.itemText(k) for k in range(pg.vc.miceq.count())], MICEQ)
        self.assertEqual([b.text() for b in pg.vc.morphs.buttons()], MORPHS)
        pg.vc.miceq.activated.emit(2)
        self.assertIn((C.VC_MICEQ, 2), self.mixer.writes)
        pg.vc.morphs.button(17).click()                   # Robot
        self.assertIn((C.VC_MORPH, 17), self.mixer.writes)

    def test_voice_test_records_then_plays(self):
        self.add()
        self.mixer.external(C.VC, True)
        pg = self.tab()
        S.PW.processes.clear()
        pg.vc.test.click()
        self.assertEqual(S.PW.processes[-1][0], "pw-record")
        self.assertFalse(pg.vc.test.isEnabled())
        pg.vc._play_back()
        self.assertEqual(S.PW.processes[-1][0], "pw-play")


class CardMonitorTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.MIC_MONITOR, False)

    def test_dsp_mode_uses_the_cards_monitor(self):
        self.mixer.external(C.DIRECT, False)
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        self.assertEqual(pg.listen_title.text(), "Monitor")
        S.PW.processes.clear()
        pg.listen.setChecked(True)
        self.assertIn((C.MIC_MONITOR, True), self.mixer.writes)
        self.assertEqual(S.PW.processes, [])              # no PipeWire loop, no warm-up
        self.assertFalse(self.ctx.monitor.running)

    def test_first_use_since_boot_plays_silence(self):
        self.mixer.external(C.DIRECT, False)
        S.DSP_PATH["ready"] = False
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        S.PW.processes.clear()
        pg.listen.setChecked(True)
        prog, args = S.PW.processes[-1]
        self.assertEqual(prog, "pw-play")
        self.assertIn(S.PW.sink["info"]["props"]["node.name"], args)

    def test_direct_mode_falls_back_to_listen(self):
        self.mixer.external(C.DIRECT, True)
        pg = self.page(pages.RecordingPage)
        pg.show_tab(0)
        pg.refresh()
        self.assertEqual(pg.listen_title.text(), "Listen")
        self.assertIn("Direct Mode", pg.listen_lbl.text())
        pg.listen.setChecked(True)
        self.assertNotIn((C.MIC_MONITOR, True), self.mixer.writes)
        self.assertTrue(self.ctx.monitor.running)


class VirtualizationTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.HP_VIRT, True)
        self.mixer.add_bool(C.LINE_VIRT, False)
        self._q = pages.QMessageBox.question
        self.addCleanup(setattr, pages.QMessageBox, "question", self._q)

    def playback(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        pg.refresh()
        return pg

    def test_greyed_in_direct_mode(self):
        self.mixer.external(C.DIRECT, True)
        pg = self.playback()
        self.assertTrue(pg.virt_row.isVisible())
        self.assertFalse(pg.hp_virt.isEnabled())
        self.assertIn("Direct Mode off only", pg.virt_note.text())

    def test_switches(self):
        self.mixer.external(C.DIRECT, False)
        self.mixer.external(C.OUTPUT, 1)
        pg = self.playback()
        self.assertTrue(pg.hp_virt.isChecked())
        pg.hp_virt.setChecked(False)
        self.assertIn((C.HP_VIRT, False), self.mixer.writes)

    def test_line_out_asks_first(self):
        self.mixer.external(C.DIRECT, False)
        self.mixer.external(C.OUTPUT, 1)
        pg = self.playback()
        pages.QMessageBox.question = lambda *a, **k: pages.QMessageBox.No
        pg.line_virt.setChecked(True)
        self.assertNotIn((C.LINE_VIRT, True), self.mixer.writes)
        self.assertFalse(pg.line_virt.isChecked())
        pages.QMessageBox.question = lambda *a, **k: pages.QMessageBox.Yes
        pg.line_virt.setChecked(True)
        self.assertIn((C.LINE_VIRT, True), self.mixer.writes)
        S.process(20)
        pg.refresh()
        self.assertIn("line out", pg.virt_note.text())
        self.assertEqual(pg.hp_sub.text(), "On Line Out")


if __name__ == "__main__":
    unittest.main()
