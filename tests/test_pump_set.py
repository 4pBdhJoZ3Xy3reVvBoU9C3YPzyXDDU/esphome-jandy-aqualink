"""Pump speed SET path: RPM clamp/snap, digit encoder, 0x24 value frame,
control-request ACK, and the page gate for the 0x13 VSP-adjust key.

The captured 0x24 frames are the oracle (Session 5 kickoff / iaqtouch.h). Each
checksum was reconstructed by hand and matches, and the frame layout matches
AqualinkD queue_iaqt_control_command: dest 00, cmd 24, sub 31, a 5-byte ASCII
digit field (NUL-padded), eleven 0xcd, checksum, 10 03."""

import unittest

from jandy import frames


class TestRpmCheck(unittest.TestCase):
    def test_in_range_multiple_of_five_unchanged(self):
        self.assertEqual(frames.rpm_check(1600), 1600)
        self.assertEqual(frames.rpm_check(2750), 2750)

    def test_clamps_low_and_high(self):
        self.assertEqual(frames.rpm_check(0), 600)
        self.assertEqual(frames.rpm_check(599), 600)
        self.assertEqual(frames.rpm_check(9000), 3450)
        self.assertEqual(frames.rpm_check(3451), 3450)

    def test_snaps_to_nearest_five(self):
        self.assertEqual(frames.rpm_check(1622), 1620)
        self.assertEqual(frames.rpm_check(1623), 1625)
        self.assertEqual(frames.rpm_check(601), 600)


class TestNum2IaqtRpm(unittest.TestCase):
    def test_four_digit_field_one_trailing_nul(self):
        self.assertEqual(frames.num2iaqt_rpm(1600), bytes.fromhex("3136303000"))
        self.assertEqual(frames.num2iaqt_rpm(2750), bytes.fromhex("3237353000"))
        self.assertEqual(frames.num2iaqt_rpm(3200), bytes.fromhex("3332303000"))
        self.assertEqual(frames.num2iaqt_rpm(1100), bytes.fromhex("3131303000"))

    def test_three_digit_field_two_trailing_nuls(self):
        # The under-1000 case: "600" then two NULs, total field width 5.
        self.assertEqual(frames.num2iaqt_rpm(600), bytes.fromhex("3630300000"))

    def test_field_is_always_five_bytes(self):
        for r in (600, 999, 1000, 3450):
            self.assertEqual(len(frames.num2iaqt_rpm(r)), 5)


class TestBuildVspSetFrame(unittest.TestCase):
    # Captured frames (iaqtouch.h). dest 00, cmd 24, sub 31, 5-byte digit field,
    # eleven 0xcd, checksum, 10 03.
    CAPTURES = {
        1600: "10020024" + "31" + "3136303000" + "cd" * 11 + "fd" + "1003",
        2000: "10020024" + "31" + "3230303000" + "cd" * 11 + "f8" + "1003",
        3000: "10020024" + "31" + "3330303000" + "cd" * 11 + "f9" + "1003",
        1000: "10020024" + "31" + "3130303000" + "cd" * 11 + "f7" + "1003",
        600:  "10020024" + "31" + "3630300000" + "cd" * 11 + "cc" + "1003",
    }

    def test_matches_captured_frames(self):
        for rpm, hexstr in self.CAPTURES.items():
            self.assertEqual(
                frames.build_vsp_set_frame(rpm), bytes.fromhex(hexstr),
                f"frame mismatch for {rpm} RPM",
            )

    def test_frame_is_24_bytes(self):
        self.assertEqual(len(frames.build_vsp_set_frame(2750)), 24)

    def test_out_of_range_is_clamped_then_encoded(self):
        self.assertEqual(frames.build_vsp_set_frame(5000), frames.build_vsp_set_frame(3450))
        self.assertEqual(frames.build_vsp_set_frame(100), frames.build_vsp_set_frame(600))

    def test_no_trailing_nul_before_checksum(self):
        # The byte right before the checksum (index -3) must be 0xcd, not 0x00.
        self.assertEqual(frames.build_vsp_set_frame(1600)[-3], 0xCD)

    def test_frame_is_checksum_valid(self):
        # Reuse the extractor to confirm the frame round-trips cleanly.
        for rpm in (600, 1600, 3450):
            extracted = frames.FrameExtractor().feed(frames.build_vsp_set_frame(rpm))
            self.assertEqual(len(extracted), 1)
            self.assertTrue(extracted[0].checksum_valid())
            self.assertEqual(extracted[0].cmd, 0x24)


class TestCtrlReadyAck(unittest.TestCase):
    def test_exact_bytes(self):
        # Control-request reply: iAqualink ack (ack_type 0x00) carrying key 0x80
        # (ACK_CMD_READY_CTRL). Same convention as every other iAqualink ack.
        self.assertEqual(frames.iaq_ctrl_ready_ack(), bytes.fromhex("100200010080931003"))

    def test_is_a_valid_ack_of_key_0x80(self):
        self.assertEqual(frames.iaq_ctrl_ready_ack(), frames.build_ack(frames.ACK_IAQ_TOUCH, 0x80))


class TestVspAdjustAllowed(unittest.TestCase):
    def test_true_only_on_devices_page(self):
        self.assertTrue(frames.vsp_adjust_allowed(frames.IAQ_PAGE_DEVICES))  # 0x36

    def test_false_on_home_page_where_0x13_is_pool_heat(self):
        # The safety crux: 0x13 means Pool Heat on HOME, so it must be refused there.
        self.assertFalse(frames.vsp_adjust_allowed(frames.IAQ_PAGE_HOME))  # 0x01

    def test_false_on_other_pages(self):
        for page in (frames.IAQ_PAGE_SET_VSP, frames.IAQ_PAGE_STATUS2, 0x00, 0x2D):
            self.assertFalse(frames.vsp_adjust_allowed(page))


if __name__ == "__main__":
    unittest.main()
