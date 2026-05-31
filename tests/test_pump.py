"""Decode live pump RPM and watts from the iAqualink STATUS page text.

Frames are built from the exact lines captured during the 2026-05-31 survey: the
STATUS2 page (type 0x2A) carried "Filter Pump", "Intelliflo VS 1",
"    RPM: 2750", "  Watts: 1263". The decoder finds the "RPM:" and "Watts:" lines
and parses the trailing integer, mirroring AqualinkD passDeviceStatusPage."""

import unittest

from jandy.frames import FrameExtractor
from jandy.iaq import IaqReader

STATUS2 = 0x2A


def _frame(cmd, payload):
    body = bytes([0x10, 0x02, 0x33, cmd]) + bytes(payload)
    return body + bytes([sum(body) & 0xFF, 0x10, 0x03])


def _msg(idx, text):
    return _frame(0x25, bytes([idx]) + text.encode("ascii") + b"\x00")


def _start(page):
    return _frame(0x23, bytes([page]))


def _end():
    return _frame(0x28, bytes([0x00]))


def feed(reader, *frames):
    for w in frames:
        for f in FrameExtractor().feed(w):
            reader.feed(f)


class TestPumpStatus(unittest.TestCase):
    def test_reads_rpm_and_watts_from_status2(self):
        r = IaqReader()
        feed(
            r,
            _start(STATUS2),
            _msg(0, "Filter Pump"),
            _msg(2, "Intelliflo VS 1"),
            _msg(3, "    RPM: 2750"),
            _msg(4, "  Watts: 1263"),
            _end(),
        )
        self.assertTrue(r.has_pump_rpm)
        self.assertEqual(r.pump_rpm, 2750)
        self.assertTrue(r.has_pump_watts)
        self.assertEqual(r.pump_watts, 1263)

    def test_no_pump_data_until_page_end(self):
        r = IaqReader()
        feed(r, _start(STATUS2), _msg(3, "    RPM: 2750"))
        self.assertFalse(r.has_pump_rpm)

    def test_home_page_does_not_set_pump(self):
        r = IaqReader()
        feed(r, _start(0x01), _msg(3, "    RPM: 2750"), _end())
        self.assertFalse(r.has_pump_rpm)

    def test_rpm_updates_on_new_read(self):
        r = IaqReader()
        feed(r, _start(STATUS2), _msg(3, "    RPM: 2750"), _end())
        feed(r, _start(STATUS2), _msg(3, "    RPM: 1800"), _end())
        self.assertEqual(r.pump_rpm, 1800)


if __name__ == "__main__":
    unittest.main()
