# ESPHome Jandy Aqualink (keypad presence + reads)

An ESPHome external component that emulates a Jandy Aqualink RS keypad on an
ESP32 wired to the panel's RS485 bus, so the panel streams its display and
status, which the component decodes into Home Assistant. It does this **at the
bus**, with the timing-critical reply on a core-1 FreeRTOS task, so there is no
computer and no WiFi in the real-time path.

Built and tested against a real Aqualink RS-8 panel with a Pentair IntelliFlo3
pump on the bus. Hardware: M5Stack Atom Lite + ATOM RS485 base.

## Status

Experimental. This is a learning build that aims to become a solid, reusable
example, since no public ESP32 Jandy keypad-presence implementation exists.

- Done and proven: protocol decoder (framing, byte de-stuffing, checksum,
  display label/value pairing, status decode). Validated against ~1,000 live
  frames at zero checksum errors, with a 32-test Python reference suite and an
  on-device self-test over the same vectors.
- In progress: keypad presence (the inert ACK that makes the panel talk) and
  reading temperatures into Home Assistant.
- Out of scope here: writes (setpoint changes, equipment toggles).

## How it works

The panel polls each device address and expects a reply within ~20-40 ms. When
it polls our keypad address, the component replies immediately with a fixed,
inert ACK (`10 02 00 01 00 00 13 10 03`): it announces a keypad is present but
sends **no key**, so it cannot change a setpoint or actuate equipment. Once the
panel believes a keypad is present, it streams that keypad's display and status,
which the component decodes (air/pool/spa temperature today).

## Safety

This controls real pool equipment via the panel. This build is read-only by
construction: the pending-key byte is hard-coded to `0x00` and there is no code
path that sends a non-zero key. Only one device may emulate a given keypad
address at a time.

## Layout

- `components/jandy_aqualink/` — the ESPHome component (pure protocol logic in
  `jandy_proto.*`, hardware/ESPHome glue in `jandy_aqualink.*`, codegen in
  `__init__.py`).
- `firmware/pool-bridge.yaml` — example device config.
- `jandy/`, `tests/`, `capture.py` — the Python reference decoder, its tests,
  and a read-only live TCP capture tool used to develop and validate the logic.
- `docs/superpowers/` — design spec and implementation plan.
