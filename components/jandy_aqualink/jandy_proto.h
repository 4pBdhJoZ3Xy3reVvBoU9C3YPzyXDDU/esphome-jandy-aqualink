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

// --- Phase 2 keypress layer (mirror of jandy/frames.py) ---
// The pending-key byte (index 5) in our ACK is the button press: 0x00 = inert
// presence, a keycode = a press, which makes the panel redraw and push display
// text. ack_type 0x80 = ACK_ALLB_SIM (Jandy's AllButton simulator ack).
static constexpr uint8_t ACK_ALLB_SIM = 0x80;   // AllButton keypad simulator ack
static constexpr uint8_t ACK_IAQ_TOUCH = 0x00;  // iAqualink (Aqualink Touch) ack
static constexpr uint8_t IAQ_DEV_ID = 0x33;     // iAqualink device address
static constexpr uint8_t CMD_IAQ_PAGE_MSG = 0x25;  // iAqualink display page line

// Safe, display-only navigation keys (AqualinkD source/aq_serial.h). These move
// the menu/display and never actuate equipment, so they are the ONLY keys this
// build will transmit. Equipment keys (pump 0x02, spa 0x01, pool heater 0x12,
// spa heater 0x17, aux*, override 0x1e, hold 0x19) have no constant here and are
// refused by is_safe_nav_key.
static constexpr uint8_t KEY_MENU = 0x09, KEY_CANCEL = 0x0E, KEY_LEFT = 0x13,
                         KEY_RIGHT = 0x18, KEY_ENTER = 0x1D;

inline bool is_safe_nav_key(uint8_t key) {
  return key == KEY_MENU || key == KEY_CANCEL || key == KEY_LEFT || key == KEY_RIGHT ||
         key == KEY_ENTER;
}

// Build a 9-byte ACK into out[9]: 10 02 00 01 <ack_type> <key> <cksum> 10 03.
// ack_type selects the emulated device (ACK_ALLB_SIM 0x80 = AllButton,
// ACK_IAQ_TOUCH 0x00 = iAqualink); key 0x00 = inert presence.
inline void build_ack(uint8_t ack_type, uint8_t key, uint8_t out[9]) {
  out[0] = DLE;
  out[1] = STX;
  out[2] = 0x00;
  out[3] = CMD_ACK;
  out[4] = ack_type;
  out[5] = key;
  uint32_t s = 0;
  for (int i = 0; i < 6; ++i) s += out[i];
  out[6] = static_cast<uint8_t>(s & 0xFF);
  out[7] = DLE;
  out[8] = ETX;
}

// AllButton ACK carrying `key`. key=0x00 yields ACK_PRESENCE exactly.
inline void build_key_ack(uint8_t key, uint8_t out[9]) { build_ack(ACK_ALLB_SIM, key, out); }

// iAqualink Touch presence ACK (inert): 10 02 00 01 00 00 13 10 03. Replying with
// this to every frame the panel sends the iAqualink device (0x33) makes the panel
// push its display pages, which carry the temperatures.
static const uint8_t ACK_IAQ_PRESENCE[9] = {0x10, 0x02, 0x00, 0x01, 0x00, 0x00, 0x13, 0x10, 0x03};

// iAqualink HOME-page equipment keycodes (home button index N -> these). Specific
// to this panel's home layout (from captured 0x24 buttons): 0 Filter Pump,
// 1 Spa, 2 Pool Heat, 3 Spa Heat, 6 Pool Light. is_allowed_iaq_key is the
// allowlist of keys this build will transmit; it deliberately EXCLUDES the heater
// buttons (0x13, 0x14) and everything else.
static constexpr uint8_t KEY_IAQ_FILTER_PUMP = 0x11, KEY_IAQ_SPA = 0x12, KEY_IAQ_CLEANER = 0x15,
                         KEY_IAQ_AIR_BLOWER = 0x16, KEY_IAQ_POOL_LIGHT = 0x17;

inline bool is_allowed_iaq_key(uint8_t key) {
  return key == KEY_IAQ_FILTER_PUMP || key == KEY_IAQ_SPA || key == KEY_IAQ_CLEANER ||
         key == KEY_IAQ_AIR_BLOWER || key == KEY_IAQ_POOL_LIGHT;
}

// iAqualink global navigation keys (AqualinkD aq_serial.h KEY_IAQTCH_*): page
// movement only, never equipment, on any page. 0x18 (Other Devices) is NOT here
// because it is only safe from the HOME page; iaq_nav() gates it separately.
static constexpr uint8_t KEY_IAQT_HOME = 0x01, KEY_IAQT_MENU = 0x02, KEY_IAQT_ONETOUCH = 0x03,
                         KEY_IAQT_BACK = 0x05, KEY_IAQT_STATUS = 0x06, KEY_IAQT_PREV_PAGE = 0x20,
                         KEY_IAQT_NEXT_PAGE = 0x21, KEY_IAQT_OTHER_DEVICES = 0x18;

inline bool is_iaq_nav_key(uint8_t key) {
  return key == KEY_IAQT_HOME || key == KEY_IAQT_MENU || key == KEY_IAQT_ONETOUCH ||
         key == KEY_IAQT_BACK || key == KEY_IAQT_STATUS || key == KEY_IAQT_PREV_PAGE ||
         key == KEY_IAQT_NEXT_PAGE;
}

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

// iAqualink HOME-page temperature decoder (mirror of jandy/iaq.py). Feed it the
// frames the panel sends the iAqualink device (0x33): page start 0x23 (carries
// the page type), page messages 0x25 (index byte + text), page end 0x28. On the
// HOME page (type 0x01) a temperature value sits 4 indices before its label.
class IaqReader {
 public:
  void feed(const Frame &f);
  Decoded state;
  // Current home-page water label: 0 none, 2 pool, 3 spa. Used to gate the
  // pool-mode control so it only fires while the panel is actually in spa mode.
  int water_mode() const { return water_mode_; }

 private:
  void commit_home();
  static constexpr int MAX_LINES = 20;
  static constexpr int LINE_LEN = 20;
  uint8_t page_type_ = 0;
  int water_mode_ = 0;
  bool present_[MAX_LINES] = {false};
  char lines_[MAX_LINES][LINE_LEN]{};
};

// Runs the known frame vectors through the logic and reports e.g. "6/6".
// Returns true only if every check passes.
bool selftest(std::string &detail);

}  // namespace jandy
