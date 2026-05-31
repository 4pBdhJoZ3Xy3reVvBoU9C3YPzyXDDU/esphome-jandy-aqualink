"""iAqualink (Aqualink Touch) page decoder.

The panel pushes display pages to the emulated iAqualink device (0x33) as a run
of page-message lines (CMD_IAQ_PAGE_MSG 0x25) bracketed by page start (0x23) and
page end (0x28). The page start carries the page type (0x01 = HOME). Each 0x25
line is: index byte, then NUL-terminated text (temperature values carry a
trailing degree glyph 0xC2 0xBA which we drop).

On the HOME page the temperatures sit at a fixed offset from their labels: the
value line is 4 indices before the label line. Confirmed against AqualinkD
source/iaqtouch.c (air = value[1] for "Air Temp" at index 5; pool/spa = value[0]
for the label at index 4) and against real frames from this RS panel.
"""

CMD_IAQ_PAGE_START = 0x23
CMD_IAQ_PAGE_MSG = 0x25
CMD_IAQ_PAGE_END = 0x28
IAQ_PAGE_HOME = 0x01

# A temperature value sits this many indices before its label line.
_VALUE_OFFSET = 4


def _norm_label(text: str) -> str:
    """Upper-case, collapse internal whitespace to one space, trim ends."""
    out = []
    prev_space = True
    for ch in text:
        u = ch.upper()
        if u in (" ", "\t"):
            if not prev_space:
                out.append(" ")
                prev_space = True
        else:
            out.append(u)
            prev_space = False
    while out and out[-1] == " ":
        out.pop()
    return "".join(out)


def _leading_int(text: str):
    s = text.strip()
    i = 0
    neg = False
    if i < len(s) and s[i] == "-":
        neg = True
        i += 1
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    if j == i:
        return None
    v = int(s[i:j])
    return -v if neg else v


class IaqReader:
    """Accumulates iAqualink HOME-page lines and decodes air/pool/spa temps."""

    def __init__(self):
        self.air = 0
        self.pool = 0
        self.spa = 0
        self.has_air = False
        self.has_pool = False
        self.has_spa = False
        self._page_type = 0
        self._lines = {}  # index -> text

    def feed(self, frame):
        cmd = frame.cmd
        if cmd == CMD_IAQ_PAGE_START:
            data = frame.data
            self._page_type = data[0] if len(data) >= 1 else 0
            self._lines = {}
        elif cmd == CMD_IAQ_PAGE_MSG:
            data = frame.data
            if len(data) < 1:
                return
            idx = data[0]
            text = "".join(chr(b) for b in data[1:] if 0x20 <= b <= 0x7E)
            self._lines[idx] = text
        elif cmd == CMD_IAQ_PAGE_END:
            if self._page_type == IAQ_PAGE_HOME:
                self._commit_home()
            self._lines = {}

    def _commit_home(self):
        for idx, text in self._lines.items():
            label = _norm_label(text)
            if label not in ("AIR TEMP", "POOL TEMP", "SPA TEMP", "WATER TEMP"):
                continue
            value_text = self._lines.get(idx - _VALUE_OFFSET)
            if value_text is None:
                continue
            val = _leading_int(value_text)
            if val is None:
                continue
            if label == "AIR TEMP":
                self.air = val
                self.has_air = True
            elif label in ("POOL TEMP", "WATER TEMP"):
                self.pool = val
                self.has_pool = True
            elif label == "SPA TEMP":
                self.spa = val
                self.has_spa = True
