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


# --- Keypad equipment-LED status (CMD_STATUS 0x02 to the AllButton keypad) ---
#
# A registered AllButton keypad receives a steady stream of CMD_STATUS frames
# carrying the equipment LED bitmap. Each circuit LED occupies bits in the data
# payload (AqualinkD source/allbutton.c processLEDstate uses 2 bits per LED, an
# ON bit and an adjacent FLASH bit). The per-panel positions below were pinned
# live 2026-06-01 by toggling each circuit at the panel and diffing the frame.
# Only the ON bit is read (FLASH is not needed to tell whether a circuit is on).

KEYPAD_STATUS_CMD = 0x02

# circuit name -> (data byte index, ON-bit index within that byte)
CIRCUIT_BITS = {
    "air_blower": (0, 6),
    "cleaner": (1, 0),
    "spa_mode": (1, 2),
    "filter_pump": (1, 4),
}


def decode_keypad_status(frame: Frame, bits: dict = CIRCUIT_BITS) -> dict:
    """Decode tracked circuit on/off states from a keypad CMD_STATUS frame.

    Returns {} for any non-status frame. Each circuit is the ON bit at its
    (byte, bit) position in frame.data; a byte past the end reads as off.
    """
    if frame.cmd != KEYPAD_STATUS_CMD:
        return {}
    data = frame.data
    out = {}
    for name, (byte_i, bit_i) in bits.items():
        out[name] = bool(byte_i < len(data) and (data[byte_i] >> bit_i) & 1)
    return out
