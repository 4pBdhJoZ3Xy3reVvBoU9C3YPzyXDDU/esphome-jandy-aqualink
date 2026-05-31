#include "jandy_aqualink.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"  // millis()

#include "driver/uart.h"
#include "esp_timer.h"

namespace esphome {
namespace jandy_aqualink {

static const char *const TAG = "jandy";
static constexpr uart_port_t JANDY_UART = UART_NUM_1;

void JandyAqualink::setup() {
  std::string detail;
  bool ok = jandy::selftest(detail);
  ESP_LOGI(TAG, "selftest %s -> %s", ok ? "PASS" : "FAIL", detail.c_str());

  uart_config_t cfg = {};
  cfg.baud_rate = baud_;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_1;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.source_clk = UART_SCLK_APB;

  uart_driver_install(JANDY_UART, 2048, 0, 0, nullptr, 0);
  uart_param_config(JANDY_UART, &cfg);
  uart_set_pin(JANDY_UART, tx_pin_, rx_pin_, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);

  // Pin the bus state machine to core 1, high priority, so WiFi on core 0 and
  // ESPHome's loop never delay an in-slot reply. The task blocks on the UART
  // read (yielding) whenever there is no data.
  xTaskCreatePinnedToCore(&JandyAqualink::task_trampoline, "jandy_bus", 8192, this, 20, &task_, 1);
  ESP_LOGI(TAG, "started: tx=%d rx=%d baud=%d keypad=0x%02X", tx_pin_, rx_pin_, baud_, keypad_addr_);
}

void JandyAqualink::task_trampoline(void *arg) { static_cast<JandyAqualink *>(arg)->task_loop(); }

void JandyAqualink::task_loop() {
  jandy::FrameExtractor extractor;
  uint8_t buf[256];
  std::vector<jandy::Frame> frames;
  frames.reserve(16);

  for (;;) {
    int n = uart_read_bytes(JANDY_UART, buf, sizeof(buf), pdMS_TO_TICKS(1));
    if (n <= 0) continue;

    frames.clear();
    extractor.feed(buf, static_cast<size_t>(n), frames);

    for (auto &f : frames) {
      if (!f.checksum_valid()) {
        portENTER_CRITICAL(&mux_);
        bad_cksum_++;
        portEXIT_CRITICAL(&mux_);
        continue;
      }

      if (jandy::is_poll_to(f, keypad_addr_)) {
        // Pick the reply: inert presence by default, a one-shot key only when
        // the interlock is on AND a key is armed. Consume it atomically. No
        // logging happens before the write, so the reply stays in-slot.
        const uint8_t *ack = jandy::ACK_PRESENCE;
        uint8_t keyack[jandy::ACK_PRESENCE_LEN];
        int sent_key = -1;
        portENTER_CRITICAL(&mux_);
        if (interlock_ && armed_key_ >= 0) {
          sent_key = armed_key_;
          armed_key_ = -1;  // one press, one time
        }
        portEXIT_CRITICAL(&mux_);
        if (sent_key >= 0) {
          jandy::build_key_ack(static_cast<uint8_t>(sent_key), keyack);
          ack = keyack;
        }

        int64_t t0 = esp_timer_get_time();
        uart_write_bytes(JANDY_UART, reinterpret_cast<const char *>(ack), jandy::ACK_PRESENCE_LEN);
        uint32_t dt = static_cast<uint32_t>(esp_timer_get_time() - t0);
        portENTER_CRITICAL(&mux_);
        frames_++;
        polls_to_us_++;
        acks_sent_++;
        last_reply_us_ = dt;
        if (sent_key >= 0) keys_sent_++;
        portEXIT_CRITICAL(&mux_);

        if (sent_key >= 0) {
          ESP_LOGW(TAG, "SENT KEY 0x%02X in ACK %02X %02X %02X %02X %02X %02X %02X %02X %02X (reply %u us)",
                   sent_key, ack[0], ack[1], ack[2], ack[3], ack[4], ack[5], ack[6], ack[7], ack[8], dt);
        }
        observe_frame(f);  // after the reply, never delays it
      } else {
        portENTER_CRITICAL(&mux_);
        frames_++;
        portEXIT_CRITICAL(&mux_);
        observe_frame(f);  // census + passive temperature decode
      }
    }
  }
}

// --- Phase 2 gated keypress controls (core 0) ---

void JandyAqualink::set_interlock(bool on) {
  portENTER_CRITICAL(&mux_);
  interlock_ = on;
  if (!on) armed_key_ = -1;  // hard abort: clear any armed key, revert to inert
  portEXIT_CRITICAL(&mux_);
  ESP_LOGW(TAG, "safety interlock %s%s", on ? "ON" : "OFF", on ? "" : " (armed key cleared)");
}

void JandyAqualink::arm_key(uint8_t key) {
  if (!interlock_) {
    ESP_LOGW(TAG, "keypress REFUSED: safety interlock is OFF (key=0x%02X)", key);
    return;
  }
  if (!jandy::is_safe_nav_key(key)) {
    ESP_LOGW(TAG, "keypress REFUSED: key 0x%02X is not a display-only nav key", key);
    return;
  }
  uint8_t ack[jandy::ACK_PRESENCE_LEN];
  jandy::build_key_ack(key, ack);
  if (ack[5] == 0x10 || ack[6] == 0x10) {  // would need wire stuffing; refuse
    ESP_LOGW(TAG, "keypress REFUSED: ack for 0x%02X contains a DLE byte", key);
    return;
  }
  portENTER_CRITICAL(&mux_);
  armed_key_ = key;
  portEXIT_CRITICAL(&mux_);
  ESP_LOGW(TAG, "ARMED key 0x%02X -> sends ACK %02X %02X %02X %02X %02X %02X %02X %02X %02X on next poll",
           key, ack[0], ack[1], ack[2], ack[3], ack[4], ack[5], ack[6], ack[7], ack[8]);
}

// Passive observation: feed every frame to the temperature decoder and log a
// one-time census of each distinct (dest,cmd) on the bus, so we can see what
// this panel actually broadcasts without sending any keys. This panel has no
// LCD keypad, so it emits no CMD_MSG display text; the temperatures live in
// binary broadcast frames instead.
void JandyAqualink::observe_frame(const jandy::Frame &f) {
  reader_.feed(f);

  uint16_t key = (static_cast<uint16_t>(f.dest()) << 8) | f.cmd();
  bool seen = false;
  for (uint16_t k : census_) {
    if (k == key) {
      seen = true;
      break;
    }
  }
  if (!seen && census_.size() < 64) {
    census_.push_back(key);
    char hex[3 * 40 + 1];
    char asc[40 + 1];
    static const char *const H = "0123456789ABCDEF";
    size_t n = f.raw.size() > 40 ? 40 : f.raw.size();
    size_t hp = 0;
    for (size_t i = 0; i < n; ++i) {
      uint8_t b = f.raw[i];
      hex[hp++] = H[b >> 4];
      hex[hp++] = H[b & 0x0F];
      hex[hp++] = ' ';
      asc[i] = (b >= 0x20 && b <= 0x7E) ? static_cast<char>(b) : '.';
    }
    hex[hp] = '\0';
    asc[n] = '\0';
    ESP_LOGI(TAG, "CENSUS dest=0x%02X cmd=0x%02X len=%u | %s| %s", f.dest(), f.cmd(),
             static_cast<unsigned>(f.raw.size()), hex, asc);
  }

  const auto &s = reader_.state;
  if (s.has_air && s.air != last_air_) {
    last_air_ = s.air;
    ESP_LOGW(TAG, "DECODED air=%d F", s.air);
  }
  if (s.has_pool && s.pool != last_pool_) {
    last_pool_ = s.pool;
    ESP_LOGW(TAG, "DECODED pool=%d F", s.pool);
  }
  if (s.has_spa && s.spa != last_spa_) {
    last_spa_ = s.spa;
    ESP_LOGW(TAG, "DECODED spa=%d F", s.spa);
  }
}

void JandyAqualink::loop() {
  uint32_t polls, errors, latency, frames;
  portENTER_CRITICAL(&mux_);
  polls = acks_sent_;
  errors = bad_cksum_;
  latency = last_reply_us_;
  frames = frames_;
  portEXIT_CRITICAL(&mux_);

  if (polls_sensor_ && polls != pub_polls_) {
    polls_sensor_->publish_state(polls);
    pub_polls_ = polls;
  }
  if (errors_sensor_ && errors != pub_errors_) {
    errors_sensor_->publish_state(errors);
    pub_errors_ = errors;
  }
  if (latency_sensor_ && latency != pub_latency_) {
    latency_sensor_->publish_state(latency);
    pub_latency_ = latency;
  }

  uint32_t now = millis();
  if (now - last_log_ms_ >= 10000) {
    last_log_ms_ = now;
    ESP_LOGI(TAG, "frames=%u polls_answered=%u checksum_errors=%u reply_us=%u", frames, polls,
             errors, latency);
  }
}

void JandyAqualink::dump_config() {
  ESP_LOGCONFIG(TAG, "Jandy Aqualink keypad presence:");
  ESP_LOGCONFIG(TAG, "  tx_pin=%d rx_pin=%d baud=%d keypad_address=0x%02X", tx_pin_, rx_pin_, baud_,
                keypad_addr_);
}

}  // namespace jandy_aqualink
}  // namespace esphome
