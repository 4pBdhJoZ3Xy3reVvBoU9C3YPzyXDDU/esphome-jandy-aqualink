#include "jandy_proto.h"

namespace jandy {

void FrameExtractor::feed(const uint8_t *data, size_t len, std::vector<Frame> &out) {
  for (size_t k = 0; k < len; ++k) {
    uint8_t b = data[k];
    switch (state_) {
      case IN:
        if (b == DLE)
          state_ = DLE_IN;
        else
          buf_.push_back(b);
        break;
      case DLE_IN:
        if (b == ETX) {
          buf_.push_back(DLE);
          buf_.push_back(ETX);
          Frame f;
          f.raw = buf_;
          out.push_back(std::move(f));
          buf_.clear();
          state_ = SEARCH;
        } else if (b == STUFF) {
          buf_.push_back(DLE);  // de-stuff: literal data 0x10
          state_ = IN;
        } else if (b == STX) {
          buf_.clear();
          buf_.push_back(DLE);
          buf_.push_back(STX);
          state_ = IN;  // fresh STX, resync
        } else {
          buf_.clear();
          state_ = SEARCH;  // DLE + junk, abandon
        }
        break;
      case SEARCH:
        if (b == DLE)
          state_ = DLE_OUT;
        break;
      case DLE_OUT:
        if (b == STX) {
          buf_.clear();
          buf_.push_back(DLE);
          buf_.push_back(STX);
          state_ = IN;
        } else if (b == DLE) {
          state_ = DLE_OUT;  // consecutive DLEs
        } else {
          state_ = SEARCH;
        }
        break;
    }
  }
}

// --- display helpers (mirror jandy/display.py) ---

static int label_key(const std::string &text) {
  // Normalize: upper-case, collapse runs of whitespace to one space, trim ends.
  std::string n;
  bool prev_space = true;  // start true to trim leading whitespace
  for (char c : text) {
    char u = (c >= 'a' && c <= 'z') ? static_cast<char>(c - 32) : c;
    if (u == ' ' || u == '\t') {
      if (!prev_space) {
        n.push_back(' ');
        prev_space = true;
      }
    } else {
      n.push_back(u);
      prev_space = false;
    }
  }
  while (!n.empty() && n.back() == ' ') n.pop_back();
  if (n == "AIR TEMP") return 1;
  if (n == "POOL TEMP") return 2;
  if (n == "SPA TEMP") return 3;
  return 0;
}

static bool parse_leading_int(const std::string &text, int &out) {
  size_t i = 0;
  while (i < text.size() && (text[i] == ' ' || text[i] == '\t')) ++i;
  bool neg = false;
  if (i < text.size() && text[i] == '-') {
    neg = true;
    ++i;
  }
  if (i >= text.size() || text[i] < '0' || text[i] > '9') return false;
  long v = 0;
  while (i < text.size() && text[i] >= '0' && text[i] <= '9') {
    v = v * 10 + (text[i] - '0');
    ++i;
  }
  out = static_cast<int>(neg ? -v : v);
  return true;
}

void Reader::feed(const Frame &f) {
  if (f.cmd() != CMD_DISPLAY) {
    // Binary pool-temp status: dest 0x38, cmd 0x0C, data[3] = temp (0x5B = 91).
    if (f.dest() == 0x38 && f.cmd() == 0x0C && f.data_len() > 3) {
      state.pool = f.data()[3];
      state.has_pool = true;
    }
    return;
  }
  if (f.data_len() < 1) return;
  // data[0] is the LCD line byte; data[1:] is a NUL-terminated string. Keep only
  // printable ASCII, dropping the NUL and the high-byte degree glyph.
  std::string text;
  for (size_t i = 1; i < f.data_len(); ++i) {
    uint8_t b = f.data()[i];
    if (b >= 0x20 && b <= 0x7E) text.push_back(static_cast<char>(b));
  }
  int key = label_key(text);
  if (key != 0) {
    pending_ = key;
    return;
  }
  if (pending_ != 0) {
    int val;
    if (parse_leading_int(text, val)) {
      if (pending_ == 1) {
        state.air = val;
        state.has_air = true;
      } else if (pending_ == 2) {
        state.pool = val;
        state.has_pool = true;
      } else if (pending_ == 3) {
        state.spa = val;
        state.has_spa = true;
      }
    }
    pending_ = 0;  // move off the screen either way; never mispair
  }
}

// --- self-test over the same vectors the Python suite uses ---

bool selftest(std::string &detail) {
  int ok = 0, total = 0;

  struct V {
    std::vector<uint8_t> wire;
    bool valid;
    uint8_t dest, cmd;
  };
  const std::vector<V> fv = {
      {{0x10, 0x02, 0x60, 0x00, 0x72, 0x10, 0x03}, true, 0x60, 0x00},
      {{0x10, 0x02, 0x33, 0x25, 0x05, 0x41, 0x69, 0x72, 0x20, 0x54, 0x65, 0x6D, 0x70, 0x00, 0x41, 0x10, 0x03},
       true, 0x33, 0x25},
      {{0x10, 0x02, 0x38, 0x0C, 0x12, 0x57, 0x66, 0x5B, 0x80, 0x10, 0x03}, true, 0x38, 0x0C},
      {{0x10, 0x02, 0x33, 0x25, 0x10, 0x00, 0x41, 0xBB, 0x10, 0x03}, true, 0x33, 0x25},  // stuffed 0x10
  };
  for (const auto &v : fv) {
    total++;
    FrameExtractor ex;
    std::vector<Frame> fr;
    ex.feed(v.wire.data(), v.wire.size(), fr);
    if (fr.size() == 1 && fr[0].checksum_valid() == v.valid && fr[0].dest() == v.dest &&
        fr[0].cmd() == v.cmd)
      ok++;
  }

  // Poll detection + ACK checksum.
  {
    total++;
    FrameExtractor ex;
    std::vector<Frame> fr;
    const uint8_t poll[] = {0x10, 0x02, 0x60, 0x00, 0x72, 0x10, 0x03};
    ex.feed(poll, sizeof(poll), fr);
    uint32_t s = 0;
    for (int i = 0; i < 6; ++i) s += ACK_PRESENCE[i];
    bool pass = fr.size() == 1 && is_poll_to(fr[0], 0x60) && !is_poll_to(fr[0], 0x08) &&
                static_cast<uint8_t>(s & 0xFF) == 0x13 && ACK_PRESENCE[6] == 0x13;
    if (pass) ok++;
  }

  // Decode: air-temp label/value pair, then the pool-temp status frame.
  {
    total++;
    Reader r;
    auto feed_one = [&](const std::vector<uint8_t> &w) {
      FrameExtractor ex;
      std::vector<Frame> fr;
      ex.feed(w.data(), w.size(), fr);
      for (const auto &f : fr) r.feed(f);
    };
    feed_one({0x10, 0x02, 0x33, 0x25, 0x05, 0x41, 0x69, 0x72, 0x20, 0x54, 0x65, 0x6D, 0x70, 0x00, 0x41, 0x10, 0x03});
    feed_one({0x10, 0x02, 0x33, 0x25, 0x01, 0x31, 0x36, 0x37, 0xC2, 0xBA, 0x00, 0x85, 0x10, 0x03});
    feed_one({0x10, 0x02, 0x38, 0x0C, 0x12, 0x57, 0x66, 0x5B, 0x80, 0x10, 0x03});
    if (r.state.has_air && r.state.air == 167 && r.state.has_pool && r.state.pool == 91) ok++;
  }

  detail = std::to_string(ok) + "/" + std::to_string(total);
  return ok == total;
}

}  // namespace jandy
