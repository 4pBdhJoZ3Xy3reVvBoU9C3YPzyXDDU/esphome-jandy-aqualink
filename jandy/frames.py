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
