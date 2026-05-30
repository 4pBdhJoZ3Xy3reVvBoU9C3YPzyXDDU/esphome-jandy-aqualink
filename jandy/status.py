"""Binary (non-text) status messages.

Only the water-temp byte in the cmd-0x0C status frame to 0x38 is decoded so
far. In the one captured sample, 10 02 38 0C 12 57 66 5B 80 10 03, the final
data byte 0x5B = 91 matches the real pool temp. The offset is pinned to that
sample and MUST be confirmed live (watch it track the pool as it changes; learn
what 0x12/0x57/0x66 are). Salt/SWG (device 0x50) is decoded only once a real
frame is captured, not guessed.
"""

from .frames import Frame

_TEMP_STATUS_DEST = 0x38
_TEMP_STATUS_CMD = 0x0C
_POOL_TEMP_OFFSET = 3  # data[3] in the captured frame


def decode_status(frame: Frame) -> dict:
    """Return the values a status frame carries, or {} if it carries none we know."""
    if (
        frame.dest == _TEMP_STATUS_DEST
        and frame.cmd == _TEMP_STATUS_CMD
        and len(frame.data) > _POOL_TEMP_OFFSET
    ):
        return {"pool_temp": frame.data[_POOL_TEMP_OFFSET]}
    return {}
