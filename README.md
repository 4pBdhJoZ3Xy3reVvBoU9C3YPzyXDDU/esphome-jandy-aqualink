# ESPHome Jandy Aqualink keypad

An ESPHome component that emulates a Jandy Aqualink RS keypad on an ESP32 wired
to the panel's RS485 bus. It does the timing-critical work **at the bus**, on a
dedicated CPU core, so there is no separate computer and no WiFi in the
real-time path. It reports into Home Assistant natively.

This was built and proven against a real Aqualink RS-8 panel (with a Pentair
IntelliFlo3 pump on the same bus) using an M5Stack Atom Lite.

## Status

**v1: keypad presence + health diagnostics. Read-only. No equipment is actuated.**

Proven on real hardware:
- The ESP32 holds a live emulated keypad. The panel polls it and we reply
  in-slot in about **110 microseconds**, every time, against the panel's
  ~20-40 ms reply window.
- Reading the bus directly, it frames the entire bus with **zero checksum
  errors** over many thousands of frames.
- When we answer, the panel registers our keypad and starts sending it targeted
  status, which it does not send when nothing is there. That is the proof the
  emulation is accepted.

Not in v1 (see [Roadmap](docs/ROADMAP.md)):
- Numeric temperatures and setpoints. On this panel those arrive over the
  display-text channel, which the panel only pushes in response to keypad
  button presses. Reading them needs an emulated menu-walk, which is the same
  machinery as writing and carries equipment risk. It is a deliberate later
  phase.
- Any control (setpoint changes, equipment toggles).

## Why this is interesting

Existing local Jandy control (AqualinkD, the gold standard) runs on a separate
always-on Linux box wired to the bus, because the reply window is too tight for
a WiFi bridge. This component meets that window on the ESP32 itself: the bus
state machine runs in a FreeRTOS task pinned to core 1, while WiFi and the Home
Assistant API run on core 0, so the network can never delay a reply. The result
is keypad presence on roughly $20 of hardware with native Home Assistant
integration and over-the-air updates.

## Hardware

- An ESP32. Tested on an **M5Stack Atom Lite**.
- An RS485 transceiver. Tested with the **M5Stack ATOM RS485 base** (SP3485,
  automatic direction control, so no direction GPIO is needed).
- A connection to the panel's RS485 bus (the AUX/RS485 terminals): A, B, and
  ground. Get A/B polarity right; if it is reversed you will see no valid
  frames. Correct polarity shows a steady stream of checksum-clean frames.

Default pins match the M5 ATOM RS485 base: **GPIO19 = TX, GPIO22 = RX**, 9600
baud, 8N1. Override them in the config if your wiring differs.

## Install

This is an ESPHome external component. Add it to your device YAML:

```yaml
external_components:
  - source: github://4pBdhJoZ3Xy3reVvBoU9C3YPzyXDDU/esphome-jandy-aqualink
    refresh: 0s

jandy_aqualink:
  keypad_address: 0x08        # a free AllButton keypad slot, see below
  polls_answered:
    name: Jandy Keypad Polls Answered
  reply_latency:
    name: Jandy Keypad Reply Latency
  checksum_errors:
    name: Jandy Bus Checksum Errors
```

A complete example device config is in [`firmware/pool-bridge.yaml`](firmware/pool-bridge.yaml).
Flash it with the ESPHome dashboard or `esphome run`. After it boots, the
`Polls Answered` sensor should climb steadily and `Checksum Errors` should stay
at zero.

## Picking a keypad address

The panel supports up to four AllButton keypads at addresses `0x08` to `0x0B`.
You must emulate one that no real keypad uses, or two devices will answer the
same poll and corrupt the bus. If you have a spare slot (most installs do),
`0x08` is a good first try. After flashing, watch `Checksum Errors`: if it stays
at zero you are not colliding with anything. If it climbs, switch to another
address.

## How it works

The panel is the bus master and polls each device address in turn. When it polls
our address with a probe (command `0x00`), we immediately reply with a fixed
AllButton acknowledgement (`10 02 00 01 80 00 93 10 03`). The acknowledgement
carries a "pending key" byte that we hard-code to `0x00`, meaning no key. That
announces a keypad is present but issues no command, so it cannot change a
setpoint or toggle equipment. There is no code path in this version that ever
sends a non-zero key.

## Safety

- This talks to equipment-controlling hardware. v1 is read-only by construction
  (the pending-key byte is always `0x00`).
- Only one device may emulate a given keypad address at a time. If you also run
  AqualinkD or another emulator, stop it first.
- Get A/B polarity right and confirm checksum-clean frames before relying on it.

## Repository layout

- `components/jandy_aqualink/` the ESPHome component. `jandy_proto.*` is the
  pure protocol logic (framing, de-stuffing, checksum, the decoders) with no
  Arduino or ESPHome dependency; `jandy_aqualink.*` is the hardware and ESPHome
  glue; `__init__.py` is the config codegen.
- `firmware/pool-bridge.yaml` a complete example device config.
- `jandy/`, `tests/`, `capture.py` a Python reference implementation of the same
  protocol logic, its unit tests, and a read-only TCP capture tool used to
  develop and validate the decoder.
- `docs/ROADMAP.md` the plan for temperatures and control.

## Credits

Protocol understanding stands on the shoulders of
[AqualinkD](https://github.com/sfeakes/AqualinkD) and
[aquaweb](https://github.com/earlephilhower/aquaweb). This project is an
independent ESP32-native reimplementation, not affiliated with Jandy or Zodiac.
