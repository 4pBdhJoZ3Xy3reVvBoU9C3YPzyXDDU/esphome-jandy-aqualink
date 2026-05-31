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
        // Reply in-slot with the inert presence ACK (no key). Time the
        // detect-to-write gap.
        int64_t t0 = esp_timer_get_time();
        uart_write_bytes(JANDY_UART, reinterpret_cast<const char *>(jandy::ACK_PRESENCE),
                         jandy::ACK_PRESENCE_LEN);
        uint32_t dt = static_cast<uint32_t>(esp_timer_get_time() - t0);
        portENTER_CRITICAL(&mux_);
        frames_++;
        polls_to_us_++;
        acks_sent_++;
        last_reply_us_ = dt;
        portEXIT_CRITICAL(&mux_);
      } else {
        portENTER_CRITICAL(&mux_);
        frames_++;
        portEXIT_CRITICAL(&mux_);
      }
    }
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
