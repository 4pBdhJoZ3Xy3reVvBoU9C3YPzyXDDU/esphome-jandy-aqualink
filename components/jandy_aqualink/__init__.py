import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    CONF_ID,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
)

AUTO_LOAD = ["sensor"]

jandy_ns = cg.esphome_ns.namespace("jandy_aqualink")
JandyAqualink = jandy_ns.class_("JandyAqualink", cg.Component)

CONF_TX_PIN = "tx_pin"
CONF_RX_PIN = "rx_pin"
CONF_BAUD = "baud_rate"
CONF_KEYPAD_ADDRESS = "keypad_address"
CONF_AIR = "air_temperature"
CONF_POOL = "pool_temperature"
CONF_SPA = "spa_temperature"


def _temp_schema():
    return sensor.sensor_schema(
        unit_of_measurement="°F",
        accuracy_decimals=0,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    )


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(JandyAqualink),
        cv.Optional(CONF_TX_PIN, default=19): cv.int_,
        cv.Optional(CONF_RX_PIN, default=22): cv.int_,
        cv.Optional(CONF_BAUD, default=9600): cv.positive_int,
        cv.Optional(CONF_KEYPAD_ADDRESS, default=0x08): cv.int_range(min=0, max=255),
        cv.Optional(CONF_AIR): _temp_schema(),
        cv.Optional(CONF_POOL): _temp_schema(),
        cv.Optional(CONF_SPA): _temp_schema(),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_tx_pin(config[CONF_TX_PIN]))
    cg.add(var.set_rx_pin(config[CONF_RX_PIN]))
    cg.add(var.set_baud(config[CONF_BAUD]))
    cg.add(var.set_keypad_address(config[CONF_KEYPAD_ADDRESS]))

    if CONF_AIR in config:
        s = await sensor.new_sensor(config[CONF_AIR])
        cg.add(var.set_air_sensor(s))
    if CONF_POOL in config:
        s = await sensor.new_sensor(config[CONF_POOL])
        cg.add(var.set_pool_sensor(s))
    if CONF_SPA in config:
        s = await sensor.new_sensor(config[CONF_SPA])
        cg.add(var.set_spa_sensor(s))
