"""The iAqualink navigation allowlist is a safety gate: it must pass the global
page-movement keys and refuse every equipment and value keycode. 0x18 (Other
Devices) is deliberately excluded here because it is only safe from the HOME
page and is gated by the caller, not by this set."""

import unittest

from jandy.frames import is_iaq_nav_key


class TestIaqNavAllowlist(unittest.TestCase):
    def test_global_nav_keys_allowed(self):
        for key in (0x01, 0x02, 0x03, 0x05, 0x06, 0x20, 0x21):  # home/menu/onetouch/back/status/prev/next
            self.assertTrue(is_iaq_nav_key(key), f"0x{key:02X} should be a nav key")

    def test_other_devices_is_not_a_global_nav_key(self):
        # 0x18 is page-context-dependent; the caller gates it to the HOME page.
        self.assertFalse(is_iaq_nav_key(0x18))

    def test_equipment_and_value_keys_refused(self):
        # Home/devices equipment tiles and the digit/value space.
        for key in (0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x19, 0x1A, 0x1D, 0x1E, 0x1F, 0x30, 0x31):
            self.assertFalse(is_iaq_nav_key(key), f"0x{key:02X} must be refused")


if __name__ == "__main__":
    unittest.main()
