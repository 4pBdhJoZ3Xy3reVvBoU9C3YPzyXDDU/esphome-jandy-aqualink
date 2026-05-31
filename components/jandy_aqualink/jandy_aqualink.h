// ESPHome component: owns the RS485 UART via the ESP-IDF driver and runs the
// time-critical poll-and-reply in a FreeRTOS task pinned to core 1. WiFi/API
// run on core 0, so a reply is never delayed by the network. ESPHome's loop
// (core 0) publishes decoded values to HA and logs presence counters.
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
  void set_air_sensor(sensor::Sensor *s) { air_sensor_ = s; }
  void set_pool_sensor(sensor::Sensor *s) { pool_sensor_ = s; }
  void set_spa_sensor(sensor::Sensor *s) { spa_sensor_ = s; }

 protected:
  static void task_trampoline(void *arg);
  void task_loop();

  int tx_pin_{19};
  int rx_pin_{22};
  int baud_{9600};
  uint8_t keypad_addr_{0x08};

  sensor::Sensor *air_sensor_{nullptr};
  sensor::Sensor *pool_sensor_{nullptr};
  sensor::Sensor *spa_sensor_{nullptr};

  TaskHandle_t task_{nullptr};
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;

  // Shared snapshot: written by the core-1 task, read by loop() on core 0.
  jandy::Decoded shared_{};
  volatile uint32_t frames_{0};
  volatile uint32_t polls_to_us_{0};
  volatile uint32_t acks_sent_{0};
  volatile uint32_t display_to_us_{0};
  volatile uint32_t bad_cksum_{0};
  volatile uint32_t ack_echo_{0};  // our own ACK heard back on RX -> TX reaches the bus
  volatile uint32_t last_reply_us_{0};

  // loop()-owned, for publish-on-change and periodic logging.
  jandy::Decoded last_pub_{};
  uint32_t last_log_ms_{0};
};

}  // namespace jandy_aqualink
}  // namespace esphome
