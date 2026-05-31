# Roadmap

## v1 (done): keypad presence + health diagnostics

Hold an emulated AllButton keypad on the bus, reply to polls in-slot on core 1,
and publish presence-health sensors (polls answered, reply latency, checksum
errors). Read-only, no equipment actuation. Proven on a real RS-8 panel.

## Phase 2: read temperatures and setpoints

**The problem.** A registered keypad receives two kinds of traffic: binary
status frames (equipment/LED states), which the panel sends continuously, and
display-text frames, which carry the human-readable temperatures and setpoints.
On the test panel the display-text channel is only pushed in response to keypad
button presses. Sitting passively yields status but not the temperature text.

**The approach.** Emulate the keypad more fully: send button presses to walk the
panel's menu so it redraws the display, then parse the redrawn text. This is the
technique AqualinkD uses. The reference is `allbutton_aq_programmer.c` in
AqualinkD (select_menu_item, the read loop that waits for the display, parses
the value, and presses a navigation key). The pending-key byte in our
acknowledgement is the mechanism: instead of always `0x00`, send a navigation
keycode for one reply, then read the display the panel sends back.

**The risk.** Keycodes can actuate equipment, not just navigate. This phase must
map keycodes carefully, send one key at a time, log every transmitted byte, keep
a hard abort, and ideally be tested while someone can watch the equipment. It is
the same machinery as writing.

**Decode targets.** For AllButton, the display text arrives as `CMD_MSG` (0x03)
and `CMD_MSG_LONG` (0x04); the existing `Reader` in `jandy_proto` already pairs
label lines with value lines and can be extended to these command codes. For the
iAqualink protocol (address 0x33 on this panel) the text arrives as page
messages (`CMD_IAQ_PAGE_MSG` 0x25, framed by 0x23 start and 0x28 end); that path
also registered successfully in testing and is an alternative for panels with a
free iAqualink slot.

## Phase 3: setpoint control

Once the menu-walk read loop is solid, extend it to change the pool and spa
heater setpoints: navigate to the setpoint menu, press up or down while reading
the displayed value back after each press, then commit. This is a write and must
stay behind an explicit, off-by-default config flag, with the same safety rules
as Phase 2.

## Phase 4: equipment status decode

Decode the binary `CMD_STATUS` (0x02) frames we already receive into named
equipment on/off states (pump, heater, aux circuits). The raw LED bitmap is
universal, but mapping each position to a named circuit is install-specific, so
this needs a small per-panel mapping config.

## Smaller improvements

- Make the acknowledgement type and the pending-key configurable (some panels or
  keypad types may want a different ack type than the AllButton `0x80`).
- Auto-detect a free keypad address by listening before answering.
- Desync and bus-error recovery hardening for long-term unattended operation.
- A debug build flag that re-enables raw per-frame logging for field diagnosis.
