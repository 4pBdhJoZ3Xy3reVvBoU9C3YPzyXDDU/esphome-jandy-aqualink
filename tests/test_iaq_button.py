"""Parse iAqualink 0x24 button frames into (index, state, type, segments).
Fixtures are real button frames from the AqualinkD reference capture
(source/iaqtouch.h), covering the home and devices page shapes."""

import unittest

from jandy.frames import FrameExtractor
from jandy.iaq import parse_iaq_button
from tests import fixtures as fx


def one(wire):
    frames = FrameExtractor().feed(fx.h(wire))
    assert len(frames) == 1
    return frames[0]


class TestParseIaqButton(unittest.TestCase):
    def test_home_filter_pump_two_word_label(self):
        b = parse_iaq_button(one("10 02 33 24 00 00 00 08 46 69 6C 74 65 72 00 50 75 6D 70 00 79 10 03"))
        self.assertEqual(b.index, 0)
        self.assertEqual(b.state, 0x00)
        self.assertEqual(b.type, 0x08)
        self.assertEqual(b.segments, ["Filter", "Pump"])

    def test_devices_filter_pump_on(self):
        b = parse_iaq_button(
            one("10 02 33 24 00 01 00 01 46 69 6C 74 65 72 20 50 75 6D 70 00 4F 4E 20 00 50 10 03")
        )
        self.assertEqual(b.index, 0)
        self.assertEqual(b.state, 0x01)
        self.assertEqual(b.segments, ["Filter Pump", "ON "])

    def test_devices_vsp1_spd_adj(self):
        b = parse_iaq_button(
            one("10 02 33 24 02 00 00 01 56 53 50 31 20 53 70 64 00 41 44 4A 00 AC 10 03")
        )
        self.assertEqual(b.index, 2)
        self.assertEqual(b.segments, ["VSP1 Spd", "ADJ"])

    def test_non_button_frame_returns_none(self):
        self.assertIsNone(parse_iaq_button(one("10 02 33 30 75 10 03")))  # a poll


if __name__ == "__main__":
    unittest.main()
