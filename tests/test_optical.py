# SPDX-License-Identifier: GPL-2.0-only
"""Optical (S/PDIF) and What U Hear: Playback → Digital, Recording → Other Input."""

import os
import unittest

import support as S
from sbcommand import card as C, pages, pipewire


class OpticalOutTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.OPTICAL_OUT, True)

    def digital(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(2)
        S.process(20)
        return pg

    def test_lives_on_the_digital_tab(self):
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(0)
        self.assertFalse(pg.optical_box.isVisible())
        pg.show_tab(2)
        self.assertTrue(pg.optical_box.isVisible())
        self.assertFalse(pg.optical_missing.isVisible())

    def test_older_driver_says_what_it_needs(self):
        self.mixer.remove(C.OPTICAL_OUT)
        pg = self.digital()
        self.assertFalse(pg.optical_box.isVisible())
        self.assertIn("v0.8.0", pg.optical_missing.text())
        self.assertTrue(pg.optical_missing.isVisible())

    def test_switch_drives_the_control(self):
        pg = self.digital()
        self.assertTrue(pg.optical.isChecked())
        pg.optical.setChecked(False)
        self.assertFalse(self.card(C.OPTICAL_OUT))
        self.mixer.external(C.OPTICAL_OUT, True)       # alsamixer, the driver
        S.process(20)
        pg.refresh()
        self.assertTrue(pg.optical.isChecked())

    def test_tells_you_when_it_is_silent(self):
        pg = self.digital()
        self.mixer.external(C.BIT_DEPTH, "24-bit")
        S.PW.stream = (192000, 2)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "On — same as the main output")
        self.assertEqual(pg.optical_quality.text(), "192 kHz · 24-bit · stereo")
        self.mixer.external(C.BIT_DEPTH, "32-bit")
        S.PW.stream = (384000, 2)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "On — silent right now")
        self.assertIn("32-bit, 384 kHz", pg.optical_note.text())
        S.PW.stream = (48000, 6)
        self.mixer.external(C.BIT_DEPTH, "24-bit")
        S.process(20)
        pg.refresh()
        self.assertIn("5.1 stream", pg.optical_note.text())
        self.mixer.external(C.OPTICAL_OUT, False)      # off: no warning
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.optical_lbl.text(), "Off")


class SeparateOpticalOutTest(S.AppTestCase):
    """Driver 0.12.0: optical out is also its own output (hw:AE9,4)."""

    def setUp(self):
        super().setUp()
        self.mixer.add_bool(C.OPTICAL_OUT, True)

    def digital(self):
        self.snapshot()
        pg = self.page(pages.PlaybackPage)
        pg.show_tab(2)
        S.process(20)
        return pg

    def test_hidden_on_older_drivers(self):
        pg = self.digital()
        self.assertFalse(pg.oo_box.isVisible())
        self.assertIn("same audio as the main output", pg.optical_quality_note.text())

    def test_sink_with_set_default(self):
        S.PW.add_optical_out()
        pg = self.digital()
        self.assertTrue(pg.oo_box.isVisible())
        self.assertEqual(pg.oo_name.text(), "AE-9 Optical Out")
        self.assertIn("mirrors the main output", pg.oo_note.text())
        S.PW.calls.clear()
        pg.oo_default.click()
        self.assertTrue(any(c[:2] == ("wpctl", "set-default") and c[2] == "993" for c in S.PW.calls))

    def test_device_without_sink_points_at_the_package(self):
        S.PLAYBACK_PCMS.add(4)
        pg = self.digital()
        self.assertTrue(pg.oo_box.isVisible())
        self.assertFalse(pg.oo_default.isVisible())
        self.assertIn("creative-ae9.conf", pg.oo_note.text())
        self.assertNotIn("ae9-optical-out.conf", pg.oo_note.text())

    def test_its_own_stream(self):
        S.PW.add_optical_out()
        S.PW.optical_stream = (96000, 2, "S32_LE")
        pg = self.digital()
        self.assertEqual(pg.optical_lbl.text(), "On — playing its own stream")
        self.assertEqual(pg.optical_quality.text(), "96 kHz · 24-bit · stereo (its own stream)")

    def test_passthrough_is_shown_and_can_be_cleared(self):
        S.PW.add_optical_out()
        self.mixer.add_iec958(status=b"\x04")
        pg = self.digital()
        self.assertTrue(pg.pt_row.isVisible())
        self.assertEqual(pg.pt_lbl.text(), "Off — PCM audio")
        self.assertFalse(pg.pt_clear.isVisible())
        self.mixer.external(C.OPTICAL_IEC958, b"\x06" + bytes(23))    # ae9-optical-passthrough
        S.process(20)
        pg.refresh()
        self.assertIn("Active", pg.pt_lbl.text())
        self.assertTrue(pg.pt_clear.isVisible())
        pg.pt_clear.click()
        self.assertEqual(self.mixer.get_iec958(C.OPTICAL_IEC958)[0], 0x04)
        self.assertEqual(pg.pt_lbl.text(), "Off — PCM audio")

    def test_mirror_switch_off_by_default(self):
        """Driver 0.12.1: optical plays only its own stream unless mirroring is on."""
        S.PW.add_optical_out()
        self.mixer.add_bool(C.OPTICAL_MIRROR, False)
        pg = self.digital()
        self.assertTrue(pg.plays_row.isVisible())
        self.assertEqual(pg.plays.currentData(), "own")
        self.assertEqual(pg.optical_lbl.text(), "On — waiting for AE-9 Optical Out")
        self.assertIn("stays quiet", pg.oo_note.text())
        self.assertIn("mirroring is off", pg.optical_quality_note.text())
        pg._pick_plays(pg.plays.findData("mirror"))
        self.assertIn((C.OPTICAL_MIRROR, True), self.mixer.writes)
        S.process(20)
        pg.refresh()
        self.assertEqual(pg.plays.currentData(), "mirror")
        self.assertNotIn("waiting", pg.optical_lbl.text())    # the mirror's own state now
        self.assertIn("mirrors the main output", pg.oo_note.text())

    def test_own_stream_says_where_it_goes_after(self):
        S.PW.add_optical_out()
        S.PW.optical_stream = (48000, 2, "S16_LE")
        self.mixer.add_bool(C.OPTICAL_MIRROR, False)
        pg = self.digital()
        self.assertIn("goes quiet", pg.optical_note.text())

    def test_no_mirror_switch_on_0_12_0(self):
        S.PW.add_optical_out()
        pg = self.digital()
        self.assertEqual(pg.plays.findData("mirror"), -1)
        self.assertIn("mirrors the main output while idle", pg.plays.itemText(0))
        self.assertIn("mirrors the main output", pg.oo_note.text())

    def test_no_passthrough_row_without_the_control(self):
        S.PW.add_optical_out()
        pg = self.digital()
        self.assertFalse(pg.pt_row.isVisible())


class OpticalOutSinkTest(S.AppTestCase):
    """Driver 0.12.0's separate optical output is its own sink, never the main one."""

    def test_main_sink_is_never_the_optical_one(self):
        S.PW.add_optical_out(first=True)
        n = pipewire.Nodes(S.PW.objects)
        self.assertNotIn("optical", n.sink["name"])
        self.assertEqual(n.optical_out["name"], "alsa_output.pci-0000_06_00.0.optical_out")
        self.assertEqual(n.optical_out_count, 1)

    def test_profile_sink_over_the_old_drop_in(self):
        S.PW.add_optical_out(first=True, name="alsa_output.ae9_optical", node_id=992)
        S.PW.add_optical_out(first=False)
        n = pipewire.Nodes(S.PW.objects)
        self.assertEqual(n.optical_out["name"], "alsa_output.pci-0000_06_00.0.optical_out")
        self.assertEqual(n.optical_out_count, 2)


class OtherInputTest(S.AppTestCase):
    def other(self):
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(pg.OTHER_TAB)
        S.process(20)
        return pg, {sec.key: sec for sec in pg.inputs}

    def test_never_taken_for_the_mic(self):
        S.PW.add_optical_in(first=True, alsa_props=True)
        S.PW.add_what_u_hear(first=True, alsa_props=True)
        n = pipewire.Nodes(S.PW.objects)
        self.assertEqual(n.optical_in["name"], "alsa_input.ae9_optical")
        self.assertEqual(n.what_u_hear["name"], "alsa_input.ae9_what_u_hear")
        self.assertNotIn(n.source["name"], ("alsa_input.ae9_optical", "alsa_input.ae9_what_u_hear"))

    def test_both_listed_with_set_default(self):
        S.PW.add_optical_in()
        S.PW.add_what_u_hear()
        pg, secs = self.other()
        for key, name, node_id in (("optical_in", "AE-9 Optical In", "999"),
                                   ("what_u_hear", "AE-9 What U Hear", "998")):
            sec = secs[key]
            self.assertTrue(sec.isVisible(), key)
            self.assertEqual(sec.name.text(), name)
            S.PW.calls.clear()
            sec.set_default.click()
            self.assertTrue(any(c[:2] == ("wpctl", "set-default") and c[2] == node_id
                                for c in S.PW.calls), key)
        self.assertFalse(pg.other_none.isVisible())

    def test_setup_hint_when_pipewire_lacks_it(self):
        S.PCMS.update({1, 2})
        pg, secs = self.other()
        self.assertIn("ae9-optical-in.conf", secs["optical_in"].note.text())
        self.assertIn("ae9-what-u-hear.conf", secs["what_u_hear"].note.text())
        self.assertFalse(secs["what_u_hear"].set_default.isVisible())

    def test_rear_rca_listed_with_set_default(self):
        S.PW.add_rear_rca(alsa_props=True)
        n = pipewire.Nodes(S.PW.objects)
        self.assertEqual(n.rear_rca["name"], "alsa_input.ae9_rear_rca")
        self.assertNotEqual(n.source["name"], "alsa_input.ae9_rear_rca")   # never taken for the mic
        pg, secs = self.other()
        sec = secs["rear_rca"]
        self.assertTrue(sec.isVisible())
        self.assertEqual(sec.name.text(), "AE-9 Rear RCA In")
        S.PW.calls.clear()
        sec.set_default.click()
        self.assertTrue(any(c[:2] == ("wpctl", "set-default") and c[2] == "997" for c in S.PW.calls))

    def _metered(self):
        """The source of the last level-meter start."""
        recs = [args for prog, args in S.PW.processes if prog == "pw-record"]
        return recs[-1][recs[-1].index("--target") + 1] if recs else None

    def test_rear_rca_meter_follows_the_tab(self):
        S.PW.add_rear_rca()
        pg, secs = self.other()
        sec = secs["rear_rca"]
        self.assertTrue(sec.meter_row.isVisible())
        self.assertEqual(self._metered(), "alsa_input.ae9_rear_rca")
        pg.ctx.meter.levels.emit(-40.0, -46.0)
        self.assertEqual(sec.peak.text(), "-40 dBFS")
        self.assertEqual(sec.meter_l.db, -40.0)
        pg.show_tab(0)                        # back to the mic
        S.process(20)
        self.assertNotEqual(self._metered(), "alsa_input.ae9_rear_rca")
        self.assertEqual(sec.peak.text(), "—")   # the old meter falls silent
        pg.ctx.meter.levels.emit(-12.0, -12.0)
        self.assertEqual(pg.peak.text(), "-12 dBFS")
        self.assertEqual(sec.peak.text(), "—")

    def test_no_meter_without_the_node(self):
        S.PCMS.update({3})
        pg, secs = self.other()
        self.assertFalse(secs["rear_rca"].meter_row.isVisible())
        self.assertFalse(secs["optical_in"].meter_row.isVisible())
        self.assertIsNone(pg._meter_target)

    def test_card_profile_sources_on_0_11(self):
        """Driver 0.11.0's card profile makes What U Hear and rear RCA sources itself."""
        S.PARAMS["version"] = "0.11.0"
        S.PW.add_input("alsa_input.pci-0000_06_00.0.what_u_hear", "AE-9 What U Hear", 2, 996,
                       False, True)
        S.PW.add_input("alsa_input.pci-0000_06_00.0.rear_rca", "AE-9 Rear RCA In", 3, 995,
                       False, True)
        pg, secs = self.other()
        self.assertEqual(secs["rear_rca"].node["name"], "alsa_input.pci-0000_06_00.0.rear_rca")
        self.assertTrue(secs["rear_rca"].meter_row.isVisible())
        self.assertNotIn("twice", secs["rear_rca"].note.text())
        wuh = secs["what_u_hear"]
        self.assertTrue(wuh.isVisible())
        self.assertTrue(wuh.rate_row.isVisible())      # a WirePlumber rule sets it
        self.assertTrue(wuh.rule_mode)
        self.assertEqual(wuh.rate.currentText(), "Automatic")

    def test_twice_with_a_leftover_config(self):
        S.PARAMS["version"] = "0.11.0"
        S.PW.add_rear_rca(alsa_props=True)
        S.PW.add_input("alsa_input.pci-0000_06_00.0.rear_rca", "AE-9 Rear RCA In", 3, 995,
                       False, True)
        pg, secs = self.other()
        sec = secs["rear_rca"]
        self.assertEqual(sec.node["name"], "alsa_input.pci-0000_06_00.0.rear_rca")
        self.assertIn("twice", sec.note.text())
        self.assertIn("ae9-rear-rca-in.conf", sec.note.text())

    def test_profile_seen_on_an_old_version_string(self):
        """A dev build still says 0.10.1: its card-profile sources tell."""
        S.PARAMS["version"] = "0.10.1"
        S.PW.add_input("alsa_input.pci-0000_06_00.0.what_u_hear", "AE-9 What U Hear", 2, 996,
                       False, True)
        S.PCMS.update({3})
        pg, secs = self.other()
        self.assertTrue(secs["what_u_hear"].rule_mode)
        self.assertIn("creative-ae9.conf", secs["rear_rca"].note.text())

    def test_setup_hint_on_0_11_points_at_the_package(self):
        S.PARAMS["version"] = "0.11.0"
        S.PCMS.update({1, 3})
        pg, secs = self.other()
        self.assertIn("creative-ae9.conf", secs["rear_rca"].note.text())
        self.assertNotIn("ae9-rear-rca-in.conf", secs["rear_rca"].note.text())
        self.assertIn("creative-ae9.conf", secs["optical_in"].note.text())   # in the profile too

    def test_optical_twice_with_the_old_config(self):
        S.PARAMS["version"] = "0.11.0"
        S.PW.add_optical_in(alsa_props=True)
        S.PW.add_input("alsa_input.pci-0000_06_00.0.optical_in", "AE-9 Optical In", 1, 994,
                       False, True)
        pg, secs = self.other()
        sec = secs["optical_in"]
        self.assertEqual(sec.node["name"], "alsa_input.pci-0000_06_00.0.optical_in")
        self.assertIn("twice", sec.note.text())
        self.assertIn("ae9-optical-in.conf", sec.note.text())

    def test_rear_rca_setup_hint(self):
        S.PCMS.update({3})
        pg, secs = self.other()
        self.assertTrue(secs["rear_rca"].isVisible())
        self.assertIn("ae9-rear-rca-in.conf", secs["rear_rca"].note.text())
        self.assertFalse(secs["optical_in"].isVisible())

    def test_nothing_on_an_older_driver(self):
        pg, secs = self.other()
        self.assertFalse(any(s.isVisible() for s in secs.values()))
        self.assertTrue(pg.other_none.isVisible())


WUH_CONF = """# AE-9 What U Hear (copy of the driver's config)
# 48 or 96 kHz (driver 0.9.5+; set audio.rate = 96000 below for 96 kHz).
context.objects = [
    { factory = adapter
        args = {
            factory.name     = api.alsa.pcm.source
            node.name        = "alsa_input.ae9_what_u_hear"
            api.alsa.path    = "hw:AE9,2"
            audio.rate       = 48000
            audio.channels   = 2
        }
    }
]
"""


class WhatUHearRateTest(S.AppTestCase):
    def setUp(self):
        super().setUp()
        os.makedirs(pipewire.PW_CONF_DIR, exist_ok=True)
        self.path = os.path.join(pipewire.PW_CONF_DIR, "ae9-what-u-hear.conf")
        with open(self.path, "w") as f:
            f.write(WUH_CONF)
        self.addCleanup(os.remove, self.path)
        S.PARAMS["wuh_96k"] = "Y"
        S.PW.add_what_u_hear()
        self.answer = True
        old = pages.confirm_pipewire_restart
        pages.confirm_pipewire_restart = lambda parent, what: self.answer
        self.addCleanup(setattr, pages, "confirm_pipewire_restart", old)

    def section(self):
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(pg.OTHER_TAB)
        S.process(20)
        return {sec.key: sec for sec in pg.inputs}["what_u_hear"]

    def pick(self, sec, rate):
        sec._pick_rate(sec.rate.findData(rate))
        self.settle()

    def test_finds_the_config_and_shows_its_rate(self):
        sec = self.section()
        self.assertTrue(sec.rate_row.isVisible())
        self.assertEqual(sec.conf_path, self.path)
        self.assertEqual(sec.rate.currentData(), 48000)
        self.assertTrue(sec.rate.isEnabled())

    def test_96_rewrites_audio_rate_only_and_restarts_pipewire(self):
        sec = self.section()
        S.PW.calls.clear()
        self.pick(sec, 96000)
        with open(self.path) as f:
            text = f.read()
        self.assertIn("audio.rate       = 96000", text)
        self.assertIn("set audio.rate = 96000 below", text)      # the comment is left alone
        self.assertEqual(text.replace("= 96000\n", "= 48000\n", 1), WUH_CONF)
        self.assertIn(("systemctl", "--user", "restart", "pipewire"), S.PW.calls)

    def test_cancel_changes_nothing(self):
        self.answer = False
        sec = self.section()
        S.PW.calls.clear()
        self.pick(sec, 96000)
        self.assertEqual(pipewire.input_conf_rate(self.path), 48000)
        self.assertNotIn(("systemctl", "--user", "restart", "pipewire"), S.PW.calls)
        self.assertEqual(sec.rate.currentData(), 48000)

    def test_older_driver_offers_48_only(self):
        del S.PARAMS["wuh_96k"]
        sec = self.section()
        self.assertFalse(sec.rate.isEnabled())
        self.assertFalse(sec.rate.model().item(sec.rate.findData(96000)).isEnabled())

    def test_config_elsewhere_greys_it_out(self):
        os.remove(self.path)
        self.addCleanup(open(self.path, "w").close)               # for the cleanup's remove
        sec = self.section()
        self.assertTrue(sec.rate_row.isVisible())
        self.assertFalse(sec.rate.isEnabled())
        self.assertIn("ae9-what-u-hear.conf", sec.rate.toolTip())

    def test_optical_in_has_no_rate_row(self):
        S.PW.add_optical_in()
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(pg.OTHER_TAB)
        S.process(20)
        self.assertFalse({s.key: s for s in pg.inputs}["optical_in"].rate_row.isVisible())


if __name__ == "__main__":
    unittest.main()


class WhatUHearRuleRateTest(S.AppTestCase):
    """Driver 0.11.0: What U Hear is the card profile's source; a WirePlumber
    rule pins its rate."""

    def setUp(self):
        super().setUp()
        S.PARAMS.update({"version": "0.11.0", "wuh_96k": "Y"})
        S.PW.add_input("alsa_input.pci-0000_06_00.0.what_u_hear", "AE-9 What U Hear", 2, 996,
                       False, True)
        self.path = pipewire.INPUT_RULES["what_u_hear"][0]
        self.addCleanup(lambda: os.path.exists(self.path) and os.remove(self.path))
        self.answer = True
        old = pages.confirm_wireplumber_restart
        pages.confirm_wireplumber_restart = lambda parent, what: self.answer
        self.addCleanup(setattr, pages, "confirm_wireplumber_restart", old)

    def section(self):
        self.snapshot()
        pg = self.page(pages.RecordingPage)
        pg.show_tab(pg.OTHER_TAB)
        S.process(20)
        return {sec.key: sec for sec in pg.inputs}["what_u_hear"]

    def test_96_writes_the_rule_and_restarts_wireplumber(self):
        sec = self.section()
        S.PW.calls.clear()
        sec._pick_rate(sec.rate.findData(96000))
        self.settle()
        with open(self.path) as f:
            text = f.read()
        self.assertIn('node.name = "~alsa_input.pci-.*[.]what_u_hear(_51)?$"', text)
        self.assertIn("audio.rate = 96000", text)
        self.assertEqual(pipewire.input_rule_rate("what_u_hear"), 96000)
        self.assertIn(("systemctl", "--user", "restart", "wireplumber"), S.PW.calls)
        sec._pick_rate(sec.rate.findData(None))       # Automatic removes it
        self.settle()
        self.assertFalse(os.path.exists(self.path))

    def test_cancel_changes_nothing(self):
        self.answer = False
        sec = self.section()
        sec._pick_rate(sec.rate.findData(48000))
        self.settle()
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(sec.rate.currentText(), "Automatic")

    def test_copied_config_source_keeps_the_config_picker(self):
        S.PW.objects[:] = [o for o in S.PW.objects
                           if "what_u_hear" not in str((o.get("info") or {}).get("props", {}).get("node.name", ""))]
        S.PW.add_what_u_hear()
        sec = self.section()
        self.assertFalse(sec.rule_mode)
        self.assertEqual(sec.rate.findData(None), -1)
