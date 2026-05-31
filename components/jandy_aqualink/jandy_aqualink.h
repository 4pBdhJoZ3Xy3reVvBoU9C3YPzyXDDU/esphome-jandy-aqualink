// ESPHome component: emulates a Jandy Aqualink RS AllButton keypad on an ESP32
// wired to the panel's RS485 bus. The time-critical poll-and-reply runs in a
// FreeRTOS task pinned to core 1; WiFi/API run on core 0, so a reply is never
// delayed by the network. v1 holds presence and publishes presence-health
// diagnostics. Decoding the display for temperatures needs the keypad
// navigation layer and is a later phase (see docs).
#pragma once

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "jandy_proto.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace esphome {
namespace jandy_aqualink {

class JandyAqualink : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

  void set_tx_pin(int p) { tx_pin_ = p; }
  void set_rx_pin(int p) { rx_pin_ = p; }
  void set_baud(int b) { baud_ = b; }
  void set_keypad_address(uint8_t a) { keypad_addr_ = a; }
  void set_polls_sensor(sensor::Sensor *s) { polls_sensor_ = s; }
  void set_latency_sensor(sensor::Sensor *s) { latency_sensor_ = s; }
  void set_errors_sensor(sensor::Sensor *s) { errors_sensor_ = s; }
  void set_air_temp_sensor(sensor::Sensor *s) { air_temp_sensor_ = s; }
  void set_pool_temp_sensor(sensor::Sensor *s) { pool_temp_sensor_ = s; }
  void set_spa_temp_sensor(sensor::Sensor *s) { spa_temp_sensor_ = s; }

  // Phase 2 gated keypress controls. Called from core 0 (HA/web/lambda). The
  // master interlock is OFF by default; with it off the device is exactly v1
  // (inert presence). arm_key queues one display-only nav key for the next
  // poll, and only if the interlock is on and the key is in the allowlist.
  void arm_key(uint8_t key);
  void set_interlock(bool on);
  bool interlock() const { return interlock_; }

  // iAqualink read. When enabled, the device also answers every frame the panel
  // sends the iAqualink slot (0x33) with the inert iAqualink ACK, which makes the
  // panel push its display pages (carrying the temperatures). Read-only: no keys
  // are ever sent on this path. Off by default.
  void set_iaq_presence(bool on);
  bool iaq_presence() const { return iaq_presence_; }

  // Switch the panel to Pool Mode by pressing the iAqualink Spa toggle (keycode
  // 0x12, the home-page Spa button). Heavily gated: requires the master
  // interlock on, iAqualink presence on, and the panel currently in spa mode.
  // Sends exactly that one keycode, never anything else, so it cannot reach Spa
  // Drain/Fill. Idempotent: refuses if not currently in spa mode.
  void request_pool_mode();

 protected:
  static void task_trampoline(void *arg);
  void task_loop();
  void observe_frame(const jandy::Frame &f);
  void dump_observations();
  void log_iaq_frame(const jandy::Frame &f);

  int tx_pin_{19};
  int rx_pin_{22};
  int baud_{9600};
  uint8_t keypad_addr_{0x08};

  sensor::Sensor *polls_sensor_{nullptr};
  sensor::Sensor *latency_sensor_{nullptr};
  sensor::Sensor *errors_sensor_{nullptr};
  sensor::Sensor *air_temp_sensor_{nullptr};
  sensor::Sensor *pool_temp_sensor_{nullptr};
  sensor::Sensor *spa_temp_sensor_{nullptr};

  TaskHandle_t task_{nullptr};
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;

  // Counters: written by the core-1 task, read by loop() on core 0.
  volatile uint32_t frames_{0};
  volatile uint32_t polls_to_us_{0};
  volatile uint32_t acks_sent_{0};
  volatile uint32_t bad_cksum_{0};
  volatile uint32_t last_reply_us_{0};

  // Keypress gating. interlock_ is the master safety switch; armed_key_ is the
  // one-shot key to send on the next poll (-1 = none). Touched by core-0
  // controls and the core-1 task, guarded by mux_.
  volatile bool interlock_{false};
  volatile int16_t armed_key_{-1};
  volatile uint32_t keys_sent_{0};

  // iAqualink read state. iaq_presence_ gates whether we answer 0x33 frames.
  uint8_t iaq_addr_{jandy::IAQ_DEV_ID};
  volatile bool iaq_presence_{false};
  volatile uint32_t iaq_acks_{0};

  // iAqualink home-page decoder (core-1 task) + temperature mirrors. -999 means
  // not yet read. loop() on core 0 publishes them on change.
  jandy::IaqReader iaq_reader_;
  volatile int t_air_{-999}, t_pool_{-999}, t_spa_{-999};
  int pub_air_{-1000}, pub_pool_{-1000}, pub_spa_{-1000};

  // iAqualink one-shot keypress: -1 none, else the keycode to send in the next
  // ACK to 0x33. iaq_water_mode_ mirrors the decoder's current mode to core 0.
  volatile int16_t iaq_armed_key_{-1};
  volatile int iaq_water_mode_{0};
  volatile uint32_t iaq_keys_sent_{0};

  // Passive decode + bus census (core-1 task only; not shared). reader_
  // accumulates temperatures from the panel's broadcast frames; census_ records
  // each unique (dest,cmd) so it is logged once; last_* throttle the decoded
  // log to first-seen and changes.
  jandy::Reader reader_;
  struct CensusEntry {
    uint16_t key;                 // (dest << 8) | cmd
    std::vector<uint8_t> sample;  // first raw frame seen of this type
  };
  std::vector<CensusEntry> census_;
  uint32_t last_dump_us_{0};
  int last_air_{-999}, last_pool_{-999}, last_spa_{-999};

  // loop()-owned, for publish-on-change.
  uint32_t pub_polls_{0xFFFFFFFF};
  uint32_t pub_errors_{0xFFFFFFFF};
  uint32_t pub_latency_{0xFFFFFFFF};
  uint32_t last_log_ms_{0};
};

}  // namespace jandy_aqualink
}  // namespace esphome
