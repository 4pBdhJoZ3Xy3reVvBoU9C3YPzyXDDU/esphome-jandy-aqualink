"""Jandy Aqualink RS-485 frame layer: extraction, de-stuffing, checksum.

Wire format:
    [optional 0x00 ...] 10 02 <dest> <cmd> <data...> <cksum> 10 03
    0x10 = DLE, 0x02 = STX, 0x03 = ETX.

Byte-stuffing: a 0x10 inside the payload is sent as "10 00". On receive, a 0x00
immediately following a non-marker 0x10 is dropped and the 0x10 kept as a
literal data byte.

Checksum: sum(logical_frame[:-3]) & 0xFF, i.e. every byte from the leading 0x10
up to but not including the checksum byte. Verified against 107/107 live frames.

FrameExtractor is a deliberately tiny per-byte state machine so it ports
straight to an ESP-IDF C ISR/task. feed() is incremental: state persists across
calls, so a frame split across TCP/UART reads still assembles cleanly.
"""

DLE = 0x10
STX = 0x02
ETX = 0x03
STUFF = 0x00

# Extractor states.
_SEARCH = 0   # outside a frame, hunting for DLE then STX
_DLE_OUT = 1  # saw DLE while searching, expecting STX next
_IN = 2       # inside a frame, collecting bytes
_DLE_IN = 3   # inside a frame, saw DLE, classifying the next byte


class Frame:
    """An un-stuffed logical frame: 10 02 dest cmd data... cksum 10 03."""

    __slots__ = ("raw",)

    def __init__(self, raw):
        self.raw = bytes(raw)

    @property
    def dest(self) -> int:
        return self.raw[2]

    @property
    def cmd(self) -> int:
        return self.raw[3]

    @property
    def data(self) -> bytes:
        return self.raw[4:-3]

    @property
    def checksum(self) -> int:
        return self.raw[-3]

    def checksum_valid(self) -> bool:
        return (sum(self.raw[:-3]) & 0xFF) == self.raw[-3]

    def __eq__(self, other):
        return isinstance(other, Frame) and other.raw == self.raw

    def __repr__(self):
        return f"Frame({self.raw.hex(' ')})"


class FrameExtractor:
    """Streaming extractor. feed(bytes) -> list[Frame] of complete frames."""

    def __init__(self):
        self._state = _SEARCH
        self._buf = bytearray()

    def feed(self, data) -> list:
        out = []
        for b in data:
            st = self._state
            if st == _IN:
                if b == DLE:
                    self._state = _DLE_IN
                else:
                    self._buf.append(b)
            elif st == _DLE_IN:
                if b == ETX:
                    self._buf.append(DLE)
                    self._buf.append(ETX)
                    out.append(Frame(self._buf))
                    self._buf = bytearray()
                    self._state = _SEARCH
                elif b == STUFF:
                    self._buf.append(DLE)  # de-stuff: literal data 0x10
                    self._state = _IN
                elif b == STX:
                    self._buf = bytearray((DLE, STX))  # fresh STX, resync
                    self._state = _IN
                else:
                    self._buf = bytearray()  # DLE + junk, abandon and resync
                    self._state = _SEARCH
            elif st == _SEARCH:
                if b == DLE:
                    self._state = _DLE_OUT
                # else: idle/lead byte (e.g. 0x00) or garbage -> ignore
            else:  # _DLE_OUT
                if b == STX:
                    self._buf = bytearray((DLE, STX))
                    self._state = _IN
                elif b == DLE:
                    self._state = _DLE_OUT  # consecutive DLEs, keep waiting
                else:
                    self._state = _SEARCH  # DLE not followed by STX
        return out


# --- Phase 2 keypress layer: the ACK that carries a button press ------------
#
# A registered AllButton keypad answers each poll with an ACK. The pending-key
# byte in that ACK is the press: 0x00 means "no key" (inert presence), and a
# keycode there tells the panel a button was pressed, which makes it redraw and
# push display text. ACK shape: 10 02 00 01 80 <key> <cksum> 10 03, where cmd
# 0x01 = CMD_ACK and ack_type 0x80 = ACK_ALLB_SIM (Jandy's AllButton simulator
# ack). Checksum is the usual sum over the logical frame up to the checksum.
ACK_ALLB_SIM = 0x80   # AllButton keypad simulator ack type
ACK_IAQ_TOUCH = 0x00  # iAqualink (Aqualink Touch) device ack type


def build_ack(ack_type: int, key: int) -> bytes:
    """Build a 9-byte ACK: 10 02 00 01 <ack_type> <key> <cksum> 10 03.

    cmd 0x01 = CMD_ACK. ack_type selects the emulated device family
    (ACK_ALLB_SIM 0x80 for AllButton, ACK_IAQ_TOUCH 0x00 for iAqualink). key is
    the pending button (0x00 = none). The result is checksum-valid.
    """
    body = bytes([DLE, STX, 0x00, 0x01, ack_type & 0xFF, key & 0xFF])
    cksum = sum(body) & 0xFF
    return body + bytes([cksum, DLE, ETX])


# iAqualink Touch presence ACK (inert: ack_type 0x00, no key). Sending this in
# reply to every frame the panel addresses to the iAqualink device (0x33) makes
# the panel run its startup and push display pages, which carry the temperatures.
ACK_IAQ_PRESENCE = build_ack(ACK_IAQ_TOUCH, 0x00)  # 10 02 00 01 00 00 13 10 03

# iAqualink HOME-page equipment keycodes. These are home-button presses (the
# panel maps home button index N to KEY_IAQTCH_KEY0(N+1)). They are specific to
# THIS panel's home layout, confirmed from its captured 0x24 button frames:
# index 0 Filter Pump, 1 Spa (pool/spa valve toggle), 2 Pool Heat, 3 Spa Heat,
# 6 Pool Light.
KEY_IAQ_FILTER_PUMP = 0x11  # home button 0
KEY_IAQ_SPA = 0x12          # home button 1 (toggles spa mode / valves)
KEY_IAQ_POOL_LIGHT = 0x17   # home button 6

# Allowlist of iAqualink equipment keys this build will transmit. Deliberately
# EXCLUDES the heater buttons (Pool Heat 0x13, Spa Heat 0x14) and everything
# else, so a control press can never fire a heater.
_ALLOWED_IAQ_KEYS = frozenset({KEY_IAQ_FILTER_PUMP, KEY_IAQ_SPA, KEY_IAQ_POOL_LIGHT})


def is_allowed_iaq_key(key: int) -> bool:
    """True only for the allowlisted iAqualink equipment keys (never a heater)."""
    return key in _ALLOWED_IAQ_KEYS

# Safe, display-only navigation keys (AqualinkD source/aq_serial.h). These move
# the menu/display and never actuate equipment, so they are the only keys this
# build will ever transmit. Equipment keys (pump 0x02, spa 0x01, pool heater
# 0x12, spa heater 0x17, aux* , override 0x1e, hold 0x19) are deliberately
# absent: there is no constant for them here and is_safe_nav_key refuses them.
KEY_MENU = 0x09
KEY_CANCEL = 0x0E
KEY_LEFT = 0x13
KEY_RIGHT = 0x18
KEY_ENTER = 0x1D

_SAFE_NAV_KEYS = frozenset({KEY_MENU, KEY_CANCEL, KEY_LEFT, KEY_RIGHT, KEY_ENTER})


def is_safe_nav_key(key: int) -> bool:
    """True only for display-only navigation keys (never equipment)."""
    return key in _SAFE_NAV_KEYS


def build_key_ack(key: int) -> bytes:
    """Build the 9-byte AllButton ACK carrying `key` in the pending-key slot.

    key=0x00 reproduces the proven inert presence ACK. The result is a
    self-consistent (checksum-valid) frame. For the allowlisted nav keys it
    contains no 0x10, so it can be written to the bus without byte-stuffing.
    """
    return build_ack(ACK_ALLB_SIM, key)
