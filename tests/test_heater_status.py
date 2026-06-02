"""HOME-page heater on/off decode. Each HOME button arrives as a 0x24 frame
(data[0]=index, data[1]=state). Session 9 capture: Pool Heat = index 2, Spa Heat
= index 3, state 3 = enabled, state 0 = off. The reader commits these on HOME
page end and keeps the last value across a partial page."""

import unittest

from jandy.frames import DLE, STX, ETX
from jandy.iaq import IaqReader


def _frame(cmd, data):
    body = bytes([DLE, STX, 0x33, cmd]) + bytes(data)
    cksum = sum(body) & 0xFF
    return _Frame(body + bytes([cksum, DLE, ETX]))


class _Frame:
    def __init__(self, raw):
        self.raw = raw
        self.cmd = raw[3]
        self.data = raw[4:-3]


def _home(pool_state, spa_state):
    """A minimal HOME page: start, Pool Heat button (idx 2), Spa Heat button
    (idx 3), end. Button data layout: index, state, unknown, type, label..."""
    r = IaqReader()
    r.feed(_frame(0x23, [0x01]))  # page start, type HOME
    r.feed(_frame(0x24, [0x02, pool_state, 0x00, 0x0B] + list(b"Pool Heat")))
    r.feed(_frame(0x24, [0x03, spa_state, 0x00, 0x0B] + list(b"Spa Heat")))
    r.feed(_frame(0x28, [0x05]))  # page end
    return r


class TestHeaterStatusDecode(unittest.TestCase):
    def test_pool_on_spa_off(self):
        r = _home(pool_state=3, spa_state=0)
        self.assertTrue(r.has_pool_heat and r.pool_heat_enabled)
        self.assertTrue(r.has_spa_heat and not r.spa_heat_enabled)

    def test_both_on(self):
        r = _home(pool_state=3, spa_state=3)
        self.assertTrue(r.pool_heat_enabled and r.spa_heat_enabled)

    def test_both_off(self):
        r = _home(pool_state=0, spa_state=0)
        self.assertFalse(r.pool_heat_enabled or r.spa_heat_enabled)


class TestStickyWaterMode(unittest.TestCase):
    """Regression lock: water_mode must persist across a partial HOME page so
    spa-mode is never spuriously 'unknown' once seen."""

    def test_water_mode_persists_across_partial_page(self):
        r = IaqReader()
        # Full spa HOME page: value line idx 0 = "88", label idx 4 = "Spa Temp".
        r.feed(_frame(0x23, [0x01]))
        r.feed(_frame(0x25, [0x00] + list(b"88")))
        r.feed(_frame(0x25, [0x04] + list(b"Spa Temp")))
        r.feed(_frame(0x28, [0x05]))
        self.assertEqual(r.water_mode, 3)
        # A later partial HOME page with no temp label must NOT reset water_mode.
        r.feed(_frame(0x23, [0x01]))
        r.feed(_frame(0x24, [0x02, 0x00, 0x00, 0x05] + list(b"Pool Heat")))
        r.feed(_frame(0x28, [0x05]))
        self.assertEqual(r.water_mode, 3)


if __name__ == "__main__":
    unittest.main()
