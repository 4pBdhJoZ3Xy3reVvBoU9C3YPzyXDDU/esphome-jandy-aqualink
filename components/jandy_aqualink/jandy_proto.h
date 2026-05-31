// Pure Jandy Aqualink RS protocol logic. No Arduino / ESPHome dependencies, so
// this is a faithful mirror of the Python reference in esp32-experiment/jandy/
// and is validated on-device by selftest() against the same frame vectors.
//
// Wire format: [optional 0x00] 10 02 <dest> <cmd> <data...> <cksum> 10 03
//   0x10 DLE, 0x02 STX, 0x03 ETX. A 0x10 in the payload is stuffed as "10 00".
//   Checksum = sum(logical_frame[:-3]) & 0xFF.
#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>

namespace jandy {

static constexpr uint8_t DLE = 0x10, STX = 0x02, ETX = 0x03, STUFF = 0x00;
static constexpr uint8_t CMD_POLL = 0x00, CMD_ACK = 0x01, CMD_DISPLAY = 0x25;

// Inert presence ACK for AllButton keypad emulation: dest 0x00 (master),
// cmd 0x01, [ack_type=0x80 (ACK_ALLB_SIM), key=0x00], checksum 0x93. The key
// byte is 0x00 (no key), which announces presence but issues no command. There
// is deliberately no path in this build that sends a non-zero key.
static const uint8_t ACK_PRESENCE[9] = {0x10, 0x02, 0x00, 0x01, 0x80, 0x00, 0x93, 0x10, 0x03};
static constexpr size_t ACK_PRESENCE_LEN = 9;

// An un-stuffed logical frame: 10 02 dest cmd data... cksum 10 03.
struct Frame {
  std::vector<uint8_t> raw;

  uint8_t dest() const { return raw[2]; }
  uint8_t cmd() const { return raw[3]; }
  uint8_t checksum() const { return raw[raw.size() - 3]; }
  const uint8_t *data() const { return raw.data() + 4; }
  size_t data_len() const { return raw.size() >= 7 ? raw.size() - 7 : 0; }

  bool checksum_valid() const {
    uint32_t s = 0;
    for (size_t i = 0; i + 3 < raw.size(); ++i) s += raw[i];
    return static_cast<uint8_t>(s & 0xFF) == raw[raw.size() - 3];
  }
};

// Streaming extractor: feed bytes, get complete logical frames. State persists
// across calls so a frame split across UART reads still assembles.
class FrameExtractor {
 public:
  void feed(const uint8_t *data, size_t len, std::vector<Frame> &out);

 private:
  enum State { SEARCH, DLE_OUT, IN, DLE_IN } state_ = SEARCH;
  std::vector<uint8_t> buf_;
};

inline bool is_poll_to(const Frame &f, uint8_t keypad_addr) {
  return f.cmd() == CMD_POLL && f.dest() == keypad_addr;
}

// Accumulated readings.
struct Decoded {
  bool has_air = false, has_pool = false, has_spa = false;
  int air = 0, pool = 0, spa = 0;
};

// Pairs keypad display labels with the value line that immediately follows, and
// decodes the binary pool-temp status frame. Feed it checksum-valid frames.
class Reader {
 public:
  void feed(const Frame &f);
  Decoded state;

 private:
  int pending_ = 0;  // 0 none, 1 air, 2 pool, 3 spa
};

// Runs the known frame vectors through the logic and reports e.g. "6/6".
// Returns true only if every check passes.
bool selftest(std::string &detail);

}  // namespace jandy
