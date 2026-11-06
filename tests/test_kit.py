# SPDX-License-Identifier: GPL-2.0-only
"""The shared kit (sbae9kit) is exactly the copy SbAe9-Kit shipped.

Change the kit in ~/Projects/SbAe9-Kit and copy it here with its
tools/sync_kit.py, never by editing sbae9kit/ in this repo.
"""

import unittest

import support  # noqa: F401  (puts the app on the path)
import sbae9kit
from sbae9kit import vendor


class KitTest(unittest.TestCase):
    def test_vendored_kit_is_unchanged(self):
        self.assertEqual(vendor.verify(), [])

    def test_manifest_matches_the_kit_version(self):
        self.assertEqual(vendor.read_manifest()["kit"], sbae9kit.KIT_VERSION)


if __name__ == "__main__":
    unittest.main()
