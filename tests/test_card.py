# SPDX-License-Identifier: GPL-2.0-only
"""The card layer: controls by name, profiles, conversions, events."""

import unittest

import support as S
from sbcommand import card as C, profiles


class CardTest(S.AppTestCase):
    def test_enum_set_by_name_stores_index(self):
        self.ctx.card.set(C.SPEAKER_CFG, "5.1")
        self.assertEqual(self.card(C.SPEAKER_CFG), 4)
        self.assertEqual(self.ctx.card.get_item(C.SPEAKER_CFG), "5.1")

    def test_same_value_is_not_rewritten_unless_forced(self):
        self.ctx.card.set(C.EQ_PRESET, "Flat")
        self.mixer.writes.clear()
        self.ctx.card.set(C.EQ_PRESET, "Flat")
        self.assertEqual(self.mixer.writes, [])
        self.ctx.card.set(C.EQ_PRESET, "Flat", force=True)
        self.assertEqual(self.mixer.writes, [(C.EQ_PRESET, NEW_INDEX["Flat"])])

    def test_master_volume_conversions_round_trip(self):
        for raw in (1, 60, 178, 254):
            self.assertEqual(C.master_pct_to_raw(C.master_raw_to_pct(raw)), raw)
        self.assertEqual(C.master_raw_to_db(254), 0)
        self.assertEqual(C.master_raw_to_db(188), -33)

    def test_profile_applies_eq_preset_by_name_in_either_driver_order(self):
        prof = profiles.find({"profiles": []}, "Movie")
        for order in (S.NEW_EQ_ORDER, S.OLD_EQ_ORDER):
            with self.subTest(order=order[0]):
                self.mixer.set_items(C.EQ_PRESET, order)
                self.ctx.card.apply(prof)
                self.assertEqual(self.ctx.card.get_item(C.EQ_PRESET), prof["eq_preset"])

    def test_snapshot_matches_applied_profile(self):
        prof = profiles.find({"profiles": []}, "Gaming")
        self.ctx.card.apply(prof)
        self.assertTrue(profiles.matches(prof, self.ctx.card.snapshot()))

    def test_outside_change_reaches_the_app(self):
        seen = []
        self.ctx.card.changed.connect(seen.append)
        self.mixer.external(C.MASTER, 120)   # head-unit knob
        S.process(20)
        self.assertIn(C.MASTER, seen)
        self.assertEqual(self.ctx.card.get(C.MASTER), 120)


NEW_INDEX = {n: i for i, n in enumerate(S.NEW_EQ_ORDER)}

if __name__ == "__main__":
    unittest.main()
