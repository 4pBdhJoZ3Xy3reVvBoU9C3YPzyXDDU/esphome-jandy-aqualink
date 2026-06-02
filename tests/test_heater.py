"""Heater on/off is the highest-stakes control. is_heater_key allowlists ONLY the
two HOME-page heater keycodes; heater_enable_allowed is the full gate: a heater key
is honored only on the HOME page (0x13 is the VSP-adjust on DEVICES and 0x14 is Pool
Heat on DEVICES), and Spa Heat (0x14) only while the panel is in spa mode (water_mode
3), because spa heat must never be enabled outside spa mode."""

import unittest

from jandy.frames import (
    is_heater_key,
    heater_enable_allowed,
    KEY_IAQ_HOME_POOL_HEAT,
    KEY_IAQ_HOME_SPA_HEAT,
    IAQ_PAGE_HOME,
    IAQ_PAGE_DEVICES,
)

WATER_MODE_POOL = 2
WATER_MODE_SPA = 3


class TestIsHeaterKey(unittest.TestCase):
    def test_only_the_two_home_heater_keys(self):
        self.assertTrue(is_heater_key(KEY_IAQ_HOME_POOL_HEAT))  # 0x13
        self.assertTrue(is_heater_key(KEY_IAQ_HOME_SPA_HEAT))   # 0x14

    def test_rejects_everything_else(self):
        for k in (0x11, 0x12, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1D, 0x1E, 0x01, 0x06):
            self.assertFalse(is_heater_key(k), f"0x{k:02X} must not be a heater key")


class TestHeaterEnableAllowed(unittest.TestCase):
    def test_pool_heat_allowed_on_home_any_mode(self):
        self.assertTrue(heater_enable_allowed(KEY_IAQ_HOME_POOL_HEAT, IAQ_PAGE_HOME, WATER_MODE_POOL))
        self.assertTrue(heater_enable_allowed(KEY_IAQ_HOME_POOL_HEAT, IAQ_PAGE_HOME, WATER_MODE_SPA))

    def test_spa_heat_allowed_on_home_only_in_spa_mode(self):
        self.assertTrue(heater_enable_allowed(KEY_IAQ_HOME_SPA_HEAT, IAQ_PAGE_HOME, WATER_MODE_SPA))
        self.assertFalse(heater_enable_allowed(KEY_IAQ_HOME_SPA_HEAT, IAQ_PAGE_HOME, WATER_MODE_POOL))

    def test_no_heater_off_home(self):
        # 0x13 on DEVICES = VSP-adjust, 0x14 on DEVICES = Pool Heat: never honor off HOME.
        self.assertFalse(heater_enable_allowed(KEY_IAQ_HOME_POOL_HEAT, IAQ_PAGE_DEVICES, WATER_MODE_POOL))
        self.assertFalse(heater_enable_allowed(KEY_IAQ_HOME_SPA_HEAT, IAQ_PAGE_DEVICES, WATER_MODE_SPA))

    def test_non_heater_key_refused_even_on_home(self):
        self.assertFalse(heater_enable_allowed(0x11, IAQ_PAGE_HOME, WATER_MODE_SPA))
        self.assertFalse(heater_enable_allowed(0x1D, IAQ_PAGE_HOME, WATER_MODE_SPA))


if __name__ == "__main__":
    unittest.main()
