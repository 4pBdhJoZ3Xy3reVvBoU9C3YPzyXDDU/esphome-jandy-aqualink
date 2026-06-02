"""Heater setpoint value frame. The format is AqualinkD's num2iaqtRSset, used for
BOTH pump RPM and heater setpoint. The captured "Set Temp (pool)" frames in
AqualinkD iaqtouch.h are the oracle: 50F and 100F reproduce byte-for-byte
(checksum included). 85/94/104 are then computed, not guessed."""

import unittest

from jandy import frames


class TestTempSetpointCheck(unittest.TestCase):
    def test_pool_clamps_45_to_90(self):
        self.assertEqual(frames.pool_setpoint_check(85), 85)
        self.assertEqual(frames.pool_setpoint_check(40), 45)
        self.assertEqual(frames.pool_setpoint_check(200), 90)

    def test_spa_clamps_80_to_104(self):
        self.assertEqual(frames.spa_setpoint_check(94), 94)
        self.assertEqual(frames.spa_setpoint_check(70), 80)
        self.assertEqual(frames.spa_setpoint_check(200), 104)


class TestNum2IaqtTemp(unittest.TestCase):
    # The digit field is 6 bytes: ASCII digits, then NUL pad, with a '0' (0x30) at
    # index 4 for sub-1000 values (the num2iaqtRSset quirk). Oracles: captured
    # "Set Temp (pool)" 50 and 100 from iaqtouch.h.
    def test_captured_oracles(self):
        self.assertEqual(frames.num2iaqt_temp(50), bytes.fromhex("353000003000"))
        self.assertEqual(frames.num2iaqt_temp(100), bytes.fromhex("313030003000"))

    def test_our_targets(self):
        self.assertEqual(frames.num2iaqt_temp(85), bytes.fromhex("383500003000"))
        self.assertEqual(frames.num2iaqt_temp(94), bytes.fromhex("393400003000"))
        self.assertEqual(frames.num2iaqt_temp(104), bytes.fromhex("313034003000"))

    def test_field_is_always_six_bytes(self):
        for t in (45, 80, 90, 104):
            self.assertEqual(len(frames.num2iaqt_temp(t)), 6)


class TestBuildSettempFrame(unittest.TestCase):
    # Full captured frames (iaqtouch.h "Set Temp (pool)"): dest 00, cmd 24, sub 31,
    # 6-byte digit field, ten 0xcd, checksum, 10 03. 24 bytes total.
    CAPTURES = {
        50:  "10020024" + "31" + "353000003000" + "cd" * 10 + "fe" + "1003",
        100: "10020024" + "31" + "313030003000" + "cd" * 10 + "2a" + "1003",
    }

    def test_matches_captured_frames(self):
        for temp, hexstr in self.CAPTURES.items():
            self.assertEqual(
                frames.build_settemp_frame(temp), bytes.fromhex(hexstr),
                f"frame mismatch for {temp}F",
            )

    def test_our_targets_checksums(self):
        self.assertEqual(frames.build_settemp_frame(85)[-3], 0x06)
        self.assertEqual(frames.build_settemp_frame(94)[-3], 0x06)
        self.assertEqual(frames.build_settemp_frame(104)[-3], 0x2E)

    def test_frame_is_24_bytes_and_checksum_valid(self):
        for temp in (45, 85, 94, 104):
            fr = frames.build_settemp_frame(temp)
            self.assertEqual(len(fr), 24)
            extracted = frames.FrameExtractor().feed(fr)
            self.assertEqual(len(extracted), 1)
            self.assertTrue(extracted[0].checksum_valid())
            self.assertEqual(extracted[0].cmd, 0x24)

    def test_caller_is_responsible_for_clamping(self):
        # build_settemp_frame intentionally does NOT clamp (pool vs spa ranges
        # differ, so the caller clamps via pool/spa_setpoint_check). An unclamped
        # out-of-range value still yields a structurally valid 24-byte frame.
        fr = frames.build_settemp_frame(200)
        self.assertEqual(len(fr), 24)
        extracted = frames.FrameExtractor().feed(fr)
        self.assertEqual(len(extracted), 1)
        self.assertTrue(extracted[0].checksum_valid())
        self.assertEqual(extracted[0].cmd, 0x24)
        self.assertEqual(frames.num2iaqt_temp(200), bytes.fromhex("323030003000"))


class TestSettempWriteAllowed(unittest.TestCase):
    def test_true_only_on_set_temp_page(self):
        self.assertTrue(frames.settemp_write_allowed(frames.IAQ_PAGE_SET_TEMP))  # 0x39

    def test_false_elsewhere(self):
        for page in (frames.IAQ_PAGE_HOME, frames.IAQ_PAGE_DEVICES, frames.IAQ_PAGE_SET_VSP, 0x0F, 0x00):
            self.assertFalse(frames.settemp_write_allowed(page))


if __name__ == "__main__":
    unittest.main()
