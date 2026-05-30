"""Frame layer: streaming DLE/STX/ETX extraction, de-stuffing, checksum.

This is the part that ports verbatim to ESP-IDF C, so it gets the most
thorough coverage against the real captured frames plus the stuffing edges.
"""

import unittest

from jandy.frames import FrameExtractor
from tests import fixtures as fx


class TestFrameExtraction(unittest.TestCase):
    def setUp(self):
        self.ex = FrameExtractor()

    def test_extracts_single_simple_frame(self):
        frames = self.ex.feed(fx.POLL_PUMP)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].raw, fx.POLL_PUMP)

    def test_decodes_frame_fields(self):
        frame = self.ex.feed(fx.DISPLAY_AIR_LABEL)[0]
        self.assertEqual(frame.dest, 0x33)
        self.assertEqual(frame.cmd, 0x25)
        self.assertEqual(frame.data, fx.h("05 41 69 72 20 54 65 6D 70 00"))
        self.assertEqual(frame.checksum, 0x41)

    def test_all_captured_frames_validate(self):
        for raw in fx.ALL_CAPTURED:
            frames = FrameExtractor().feed(raw)
            self.assertEqual(len(frames), 1, f"want one frame from {raw.hex()}")
            self.assertTrue(frames[0].checksum_valid(), f"bad checksum {raw.hex()}")

    def test_skips_leading_zero_byte(self):
        frames = self.ex.feed(b"\x00" + fx.POLL_PUMP)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].raw, fx.POLL_PUMP)

    def test_extracts_two_back_to_back_frames(self):
        frames = self.ex.feed(fx.POLL_PUMP + fx.POLL_58)
        self.assertEqual([f.raw for f in frames], [fx.POLL_PUMP, fx.POLL_58])

    def test_reassembles_frame_split_across_feeds(self):
        self.assertEqual(self.ex.feed(fx.POLL_PUMP[:3]), [])
        frames = self.ex.feed(fx.POLL_PUMP[3:])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].raw, fx.POLL_PUMP)

    def test_unstuffs_dle_in_data(self):
        frame = self.ex.feed(fx.WIRE_STUFFED_DATA)[0]
        self.assertEqual(frame.raw, fx.LOGICAL_STUFFED_DATA)
        self.assertTrue(frame.checksum_valid())

    def test_unstuffs_dle_checksum_byte(self):
        frame = self.ex.feed(fx.WIRE_STUFFED_CKSUM)[0]
        self.assertEqual(frame.raw, fx.LOGICAL_STUFFED_CKSUM)
        self.assertEqual(frame.checksum, 0x10)
        self.assertTrue(frame.checksum_valid())

    def test_resyncs_on_new_stx_midframe(self):
        # 10 02 99 starts a frame, then a fresh 10 02 restarts it cleanly
        noisy = fx.h("10 02 99") + fx.POLL_PUMP
        frames = self.ex.feed(noisy)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].raw, fx.POLL_PUMP)

    def test_flags_corrupted_checksum(self):
        bad = bytearray(fx.POLL_PUMP)
        bad[4] ^= 0xFF  # mangle the checksum byte (index 4 in this 7-byte frame)
        frame = FrameExtractor().feed(bytes(bad))[0]
        self.assertFalse(frame.checksum_valid())


if __name__ == "__main__":
    unittest.main()
