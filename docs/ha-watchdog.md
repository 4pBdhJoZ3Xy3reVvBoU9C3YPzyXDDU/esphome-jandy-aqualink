# HA watchdog and HA-silent failsafe

The bridge serves one native API client at a time. If that slot is lost, nothing
remote can reconnect, and ESPHome's `api: reboot_timeout` did not reboot the device on
the test install. The watchdog checks for that from inside the device, using a
heartbeat from Home Assistant instead of the API's own idea of whether it is connected.

## How it behaves

| Time with no heartbeat | What the bridge does |
| --- | --- |
| under 20 min | nothing |
| 20 min | reboots itself (watchdog reboot 1) |
| 40, 80, 160 min | reboots again, each time only if still silent |
| every 6 h after that | reboots again (the cap) |
| 60 min and on | failsafe: holds the filter pump on at 2000 RPM |

All the times are settings in the `ha_watchdog:` block. Details:

- **Armed by the first heartbeat.** After a power-up nothing happens until Home
  Assistant sends its first heartbeat. A bench device, or an install without the
  automation below, never reboots itself.
- **Silence survives the watchdog's own reboots** (RTC memory), so the backoff and the
  failsafe carry on across them. A power cycle clears it.
- **No reboot in the first 5 minutes after boot**, so the API has time to come up.
- **Failsafe uses only the scheduler-safe writes** (pump speed and the Filter Pump
  key), so the Pool Scheduler switch must be on. It never acts in spa mode or while the
  spa or pump state is unknown. Filter Pump is a toggle, so it is pressed only after
  the pump has read off for 2 minutes, and never twice within 30 minutes. While the pump
  runs, the speed is re-sent every 10 minutes, because the panel's stored programs push
  their own speeds.
- **The first heartbeat after an outage clears everything.** Home Assistant's own
  schedule then takes back over.
- The **Pool HA Watchdog** switch turns both off for planned maintenance. It turns
  itself back on at the next boot.

## Home Assistant automation

```yaml
alias: "Pool: Bridge Heartbeat"
description: >-
  Presses the bridge's HA Heartbeat button every minute. The bridge reboots itself
  after 20 min without one and holds the pump at 2000 RPM after 60 min.
triggers:
  - trigger: time_pattern
    minutes: "/1"
conditions:
  - condition: not
    conditions:
      - condition: state
        entity_id: button.pool_rs485_bridge_pool_ha_heartbeat
        state: unavailable
actions:
  - action: button.press
    target:
      entity_id: button.pool_rs485_bridge_pool_ha_heartbeat
mode: single
```

Leave the heartbeat button out of the recorder, or it writes a row every minute.

## Entities

- `button.<device>_pool_ha_heartbeat`: what Home Assistant presses.
- `sensor.<device>_pool_ha_heartbeat_age`: minutes since the last heartbeat.
- `binary_sensor.<device>_pool_ha_failsafe_active`: on while the failsafe holds the pump.
- `switch.<device>_pool_ha_watchdog`: off for maintenance.

## Limits

- It reboots on any long silence, whatever the cause: Home Assistant down, Wi-Fi down,
  or the stuck API slot. The backoff keeps that to a handful of reboots a day.
- It cannot fix a bridge that has lost power or crashed hard. Switched power to the
  bridge is the answer to that.
- The failsafe holds one speed all day. That is the right default for freezing weather
  and filtration, not for saving power, and it only runs while Home Assistant is gone.
