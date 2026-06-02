"""The DEVICES-page toggle allowlist is a safety gate: it passes only the three
intended circuit keycodes (Spa Light 0x19, Extra Aux 0x1d, Sprinklers 0x1e) and
refuses every other DEVICES keycode, including the heaters and Spa Mode."""

import unittest

from jandy.frames import is_device_toggle_allowed


class TestDeviceToggleAllowlist(unittest.TestCase):
    def test_intended_toggles_allowed(self):
        for key in (0x19, 0x1D, 0x1E):  # spa light, extra aux, sprinklers
            self.assertTrue(is_device_toggle_allowed(key), f"0x{key:02X} should be allowed")

    def test_other_devices_keycodes_refused(self):
        # VSP adjust 0x13, Pool Heat 0x14, Spa Heat 0x15, High Speed 0x1a, Spa Mode
        # 0x1f, plus nav/value bytes: none may toggle through this path.
        for key in (0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x1A, 0x1F, 0x01, 0x06, 0x18, 0x30, 0x31):
            self.assertFalse(is_device_toggle_allowed(key), f"0x{key:02X} must be refused")


if __name__ == "__main__":
    unittest.main()
