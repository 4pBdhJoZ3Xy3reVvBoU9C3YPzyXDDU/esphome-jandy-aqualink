"""Binary status layer: extract values carried in non-text status frames.

Currently this is just the pool-water-temp byte in the cmd-0x0C status frame
to 0x38 (0x5B = 91 in the one captured sample). The byte offset is pinned to
that fixture and must be confirmed against the live bus (watch data[3] track
the real pool temp as it changes). Salt (SWG, device 0x50) has no fixture yet,
so it is intentionally not decoded here until a real frame is captured.
"""

import unittest

from jandy.frames import FrameExtractor
from jandy.status import decode_status
from tests import fixtures as fx


def frame(raw):
    return FrameExtractor().feed(raw)[0]


class TestDecodeStatus(unittest.TestCase):
    def test_decodes_pool_temp_from_0x0c_status_frame(self):
        self.assertEqual(decode_status(frame(fx.STATUS_38_TEMP)), {"pool_temp": 91})

    def test_poll_frame_yields_nothing(self):
        self.assertEqual(decode_status(frame(fx.POLL_PUMP)), {})

    def test_display_frame_yields_nothing(self):
        self.assertEqual(decode_status(frame(fx.DISPLAY_AIR_LABEL)), {})

    def test_other_binary_status_yields_nothing(self):
        # cmd 0x28 to 0x33 is a different status message we don't decode yet
        self.assertEqual(decode_status(frame(fx.STATUS_33_BIN)), {})


if __name__ == "__main__":
    unittest.main()
