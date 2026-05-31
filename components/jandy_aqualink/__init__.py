import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    CONF_ID,
    ENTITY_CATEGORY_DIAGNOSTIC,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)

AUTO_LOAD = ["sensor"]

jandy_ns = cg.esphome_ns.namespace("jandy_aqualink")
JandyAqualink = jandy_ns.class_("JandyAqualink", cg.Component)

CONF_TX_PIN = "tx_pin"
CONF_RX_PIN = "rx_pin"
CONF_BAUD = "baud_rate"
CONF_KEYPAD_ADDRESS = "keypad_address"
CONF_POLLS_ANSWERED = "polls_answered"
CONF_REPLY_LATENCY = "reply_latency"
CONF_CHECKSUM_ERRORS = "checksum_errors"
CONF_AIR_TEMP = "air_temp"
CONF_POOL_TEMP = "pool_temp"
CONF_SPA_TEMP = "spa_temp"
CONF_PUMP_RPM = "pump_rpm"
CONF_PUMP_WATTS = "pump_watts"


def _temp_sensor():
    return sensor.sensor_schema(
        unit_of_measurement="°F",
        accuracy_decimals=0,
        device_class="temperature",
        state_class=STATE_CLASS_MEASUREMENT,
    )

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(JandyAqualink),
        cv.Optional(CONF_TX_PIN, default=19): cv.int_,
        cv.Optional(CONF_RX_PIN, default=22): cv.int_,
        cv.Optional(CONF_BAUD, default=9600): cv.positive_int,
        cv.Optional(CONF_KEYPAD_ADDRESS, default=0x08): cv.int_range(min=0, max=255),
        cv.Optional(CONF_POLLS_ANSWERED): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            icon="mdi:check-network-outline",
        ),
        cv.Optional(CONF_REPLY_LATENCY): sensor.sensor_schema(
            unit_of_measurement="µs",
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            icon="mdi:timer-outline",
        ),
        cv.Optional(CONF_CHECKSUM_ERRORS): sensor.sensor_schema(
            accuracy_decimals=0,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
            icon="mdi:alert-circle-outline",
        ),
        cv.Optional(CONF_AIR_TEMP): _temp_sensor(),
        cv.Optional(CONF_POOL_TEMP): _temp_sensor(),
        cv.Optional(CONF_SPA_TEMP): _temp_sensor(),
        cv.Optional(CONF_PUMP_RPM): sensor.sensor_schema(
            unit_of_measurement="RPM",
            accuracy_decimals=0,
            state_class=STATE_CLASS_MEASUREMENT,
            icon="mdi:pump",
        ),
        cv.Optional(CONF_PUMP_WATTS): sensor.sensor_schema(
            unit_of_measurement="W",
            accuracy_decimals=0,
            device_class="power",
            state_class=STATE_CLASS_MEASUREMENT,
            icon="mdi:flash",
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_tx_pin(config[CONF_TX_PIN]))
    cg.add(var.set_rx_pin(config[CONF_RX_PIN]))
    cg.add(var.set_baud(config[CONF_BAUD]))
    cg.add(var.set_keypad_address(config[CONF_KEYPAD_ADDRESS]))

    if CONF_POLLS_ANSWERED in config:
        s = await sensor.new_sensor(config[CONF_POLLS_ANSWERED])
        cg.add(var.set_polls_sensor(s))
    if CONF_REPLY_LATENCY in config:
        s = await sensor.new_sensor(config[CONF_REPLY_LATENCY])
        cg.add(var.set_latency_sensor(s))
    if CONF_CHECKSUM_ERRORS in config:
        s = await sensor.new_sensor(config[CONF_CHECKSUM_ERRORS])
        cg.add(var.set_errors_sensor(s))
    if CONF_AIR_TEMP in config:
        s = await sensor.new_sensor(config[CONF_AIR_TEMP])
        cg.add(var.set_air_temp_sensor(s))
    if CONF_POOL_TEMP in config:
        s = await sensor.new_sensor(config[CONF_POOL_TEMP])
        cg.add(var.set_pool_temp_sensor(s))
    if CONF_SPA_TEMP in config:
        s = await sensor.new_sensor(config[CONF_SPA_TEMP])
        cg.add(var.set_spa_temp_sensor(s))
    if CONF_PUMP_RPM in config:
        s = await sensor.new_sensor(config[CONF_PUMP_RPM])
        cg.add(var.set_pump_rpm_sensor(s))
    if CONF_PUMP_WATTS in config:
        s = await sensor.new_sensor(config[CONF_PUMP_WATTS])
        cg.add(var.set_pump_watts_sensor(s))
