"""Native DSD64 (driver 0.12.14's pcm_dsd option): seeing a DSD stream, the
Settings → Device switch, and Direct Mode off while DSD plays."""
import unittest
from unittest import mock

import support as S
from sbcommand import card as C, pages, pipewire
from PySide6.QtWidgets import QMessageBox

HW_DSD = """access: RW_INTERLEAVED
format: DSD_U32_BE
subformat: STD
channels: 2
rate: 88200 (88200/1)
period_size: 5440
buffer_size: 21760
"""
HW_PCM = HW_DSD.replace("DSD_U32_BE", "S32_LE")
STATUS = """state: RUNNING
owner_pid   : 4242
trigger_time: 24001.379662929
"""
DSD = {"format": "DSD_U32_BE", "rate": 88200, "channels": 2, "bit_clock": 2822400,
       "name": "DSD64", "pid": 4242, "app": "mpd"}


class ParseTest(unittest.TestCase):
    def test_dsd64(self):
        d = pipewire.parse_dsd(HW_DSD, STATUS)
        self.assertEqual(d, {k: v for k, v in DSD.items() if k != "app"})

    def test_pcm_at_88k2_is_not_dsd(self):
        self.assertIsNone(pipewire.parse_dsd(HW_PCM, STATUS))

    def test_closed(self):
        self.assertIsNone(pipewire.parse_dsd("closed\n", ""))
        self.assertIsNone(pipewire.parse_dsd("", ""))

    def test_no_owner(self):
        self.assertIsNone(pipewire.parse_dsd(HW_DSD, "")["pid"])

    def test_text(self):
        self.assertEqual(pages.dsd_text(DSD), "DSD64 (native) · 2.8224 MHz · stereo · via mpd")
        self.assertEqual(pages.dsd_text(dict(DSD, app="")), "DSD64 (native) · 2.8224 MHz · stereo")


class ProcessNameTest(unittest.TestCase):
    def test_a_thread_names_its_process(self):
        """owner_pid is the opening thread (MPD's "output:AE-9 ..."): name the process."""
        import os
        import threading
        tid, done = [], threading.Event()
        t = threading.Thread(target=lambda: (tid.append(threading.get_native_id()), done.wait(5)),
                             name="output:AE-9 x")
        t.start()
        while not tid:
            pass
        try:
            self.assertEqual(pipewire.process_name(tid[0]), pipewire.process_name(os.getpid()))
        finally:
            done.set()
            t.join()

    def test_gone(self):
        self.assertEqual(pipewire.process_name(2 ** 22 + 1), "")
        self.assertEqual(pipewire.process_name(None), "")


class RealCardStreamTest(unittest.TestCase):
    """The unpatched card_stream: a DSD stream's "88200" isn't a PCM rate."""

    def run_with(self, hw):
        real = S.REAL_CARD_STREAM
        with mock.patch.object(pipewire, "_proc_pcm", lambda c, n, p="pcm0p": hw if n == "hw_params" else STATUS):
            return real()

    def test_dsd_is_no_pcm_stream(self):
        self.assertIsNone(self.run_with(HW_DSD))

    def test_pcm_still_reads(self):
        self.assertEqual(self.run_with(HW_PCM), (88200, 2))


class ScriptTest(unittest.TestCase):
    def test_on_writes_sysfs_and_conf(self):
        s = C.native_dsd_script(True)
        self.assertIn("echo 1 > /sys/module/snd_hda_codec_creative_ae9/parameters/pcm_dsd", s)
        self.assertIn("options snd-hda-codec-creative-ae9 pcm_dsd=1", s)
        self.assertIn("> /etc/modprobe.d/ae9-dsd.conf", s)

    def test_off_writes_conf_with_0(self):
        """Off must survive a reboot on 0.12.15, whose default is on: write
        pcm_dsd=0 rather than removing the file."""
        s = C.native_dsd_script(False)
        self.assertIn("echo 0 > /sys/module/snd_hda_codec_creative_ae9/parameters/pcm_dsd", s)
        self.assertIn("options snd-hda-codec-creative-ae9 pcm_dsd=0", s)
        self.assertIn("> /etc/modprobe.d/ae9-dsd.conf", s)
        self.assertNotIn("rm ", s)



class DsdUiTest(S.AppTestCase):
    def test_running_now_shows_dsd(self):
        S.PW.dsd = DSD
        pg = self.page(pages.PlaybackPage)
        pg.refresh()
        self.assertEqual(pg.now_playing.text(), "Running now: DSD64 (native) · 2.8224 MHz · stereo · via mpd")
        self.assertNotIn("88.2 kHz", pg.now_playing.text())

    def test_running_now_pcm_unchanged(self):
        S.PW.stream = (88200, 2)
        pg = self.page(pages.PlaybackPage)
        pg.refresh()
        self.assertIn("Running now: 88.2 kHz", pg.now_playing.text())

    def test_switch_hidden_without_the_option(self):
        S.PARAMS.pop("pcm_dsd", None)
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        self.assertTrue(pg.dsd_box.isHidden())

    def test_switch_shows_the_driver_state(self):
        S.PARAMS.update({"version": "0.12.14", "pcm_dsd": "N"})
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        self.assertFalse(pg.dsd_box.isHidden())
        self.assertFalse(pg.dsd.isChecked())
        S.PARAMS["pcm_dsd"] = "Y"
        pg.refresh()
        self.assertTrue(pg.dsd.isChecked())

    def test_switch_turns_it_on(self):
        S.PARAMS.update({"version": "0.12.14", "pcm_dsd": "N"})
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        calls = []

        def fake_set(on):
            calls.append(on)
            S.PARAMS["pcm_dsd"] = "Y" if on else "N"
            return True
        with mock.patch.object(C, "set_native_dsd", fake_set):
            pg.dsd.setChecked(True)
        self.assertEqual(calls, [True])
        self.assertTrue(pg.dsd.isChecked())

    def test_cancelled_password_puts_it_back(self):
        S.PARAMS.update({"version": "0.12.14", "pcm_dsd": "N"})
        pg = self.page(pages.SettingsPage)
        pg.refresh()
        with mock.patch.object(C, "set_native_dsd", lambda on: False):
            pg.dsd.setChecked(True)
        self.assertFalse(pg.dsd.isChecked())

    def test_direct_off_warns_while_dsd_plays(self):
        S.PW.dsd = DSD
        self.ctx.settings["dsp_louder_seen"] = True
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No) as q, \
                mock.patch.object(self.ctx, "set_direct") as sd:
            self.assertFalse(pages.set_direct_checked(None, self.ctx, False))
        self.assertIn("Direct Mode off stops it", q.call_args[0][2])
        self.assertIn("(mpd)", q.call_args[0][2])
        sd.assert_not_called()
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
                mock.patch.object(self.ctx, "set_direct") as sd:
            self.assertTrue(pages.set_direct_checked(None, self.ctx, False))
        sd.assert_called_once_with(False)

    def test_direct_off_no_dsd_no_warning(self):
        self.ctx.settings["dsp_louder_seen"] = True
        with mock.patch.object(QMessageBox, "question") as q, \
                mock.patch.object(self.ctx, "set_direct") as sd:
            self.assertTrue(pages.set_direct_checked(None, self.ctx, False))
        q.assert_not_called()
        sd.assert_called_once_with(False)

    def test_dsp_waiting_rate_ignores_dsd(self):
        S.PW.dsd = DSD             # card_stream is None while DSD plays
        self.assertIsNone(C.dsp_waiting_rate(self.ctx.card, pipewire.card_stream()))


if __name__ == "__main__":
    unittest.main()
