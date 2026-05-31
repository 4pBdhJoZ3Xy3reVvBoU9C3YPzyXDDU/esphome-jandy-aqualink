# Pool Panel Capability Map

Date: 2026-05-31
Source: live read-only survey of the AquaLink RS power center via the iAqualink
emulator at address 0x33 (firmware HEAD with compact page logging). Navigation
was view-only: no equipment, value, or commit button was pressed. Pump is a
Pentair Intelliflo VS (variable speed). All values are as observed during the
survey (pool mode, filter pump running).

## Pages this panel exposes over iAqualink

| Page | Type | How reached | Contents |
|---|---|---|---|
| HOME | 0x01 | pushed automatically | equipment buttons + temperatures |
| DEVICES | 0x36 | Home then Other Devices (key 0x18) | full equipment list |
| DEVICES2 | 0x35 | Next Page (key 0x21) from Status | macros / modes |
| STATUS2 | 0x2A | Status (key 0x06) | live pump model, RPM, watts |

The panel enumerates a page in full only on the first visit after our device
registers, then sends only changed buttons. To re-capture a full page, drop and
re-add presence (forces a fresh registration), then navigate.

Reference (AqualinkD) also defines SET_VSP 0x1e, SET_TEMP 0x39, SET_SWG 0x30,
MENU 0x0f, ONETOUCH 0x4d, COLOR_LIGHT 0x48. These were not walked this session.

## Readable values

| Value | Source | Wire format | Observed |
|---|---|---|---|
| Pool water temp | HOME, value 4 indices before "Pool Temp" | int degF | 89 |
| Spa water temp | HOME, "Spa Temp" (spa mode only) | int degF | not in pool mode |
| Air temp | HOME, "Air Temp" | int degF | 168 (sun-baked sensor) |
| Pump model | STATUS2 message line | text | "Intelliflo VS 1" |
| Pump RPM | STATUS2 line "    RPM: NNNN" | int after "RPM:" | 2750 |
| Pump watts | STATUS2 line "  Watts: NNNN" | int after "Watts:" | 1263 |

Notes:
- Pump RPM/watts are NOT on the bus passively. The panel sends the pump (address
  0x60) only empty polls; RPM/watts appear only as text on the STATUS2 page. So
  reading speed requires viewing STATUS2 (a brief navigation), unlike temps which
  the HOME page provides on its own.
- SWG / salt readings were not found on any page walked. Phase 1 saw "Generating"
  via AqualinkD, so the SWG exists; it may live on a page not visited (Menu or a
  device-status page) or may not surface over iAqualink. To map another time.

## Controllable items: DEVICES page (0x36)

Keycode = 0x11 + slot, and is valid ONLY while the panel is displaying this page.

| Slot | Keycode | Device | Observed state | Risk |
|---|---|---|---|---|
| 0 | 0x11 | Filter Pump | ON | low (shipped) |
| 1 | 0x12 | Spa (valve) | OFF | medium (valves) |
| 2 | 0x13 | VSP1 Spd ADJ (opens the speed-set page) | - | medium (value set) |
| 3 | 0x14 | Pool Heat | OFF | high (heater) |
| 4 | 0x15 | Spa Heat | ENABLED | high (heater) |
| 5 | 0x16 | Cleaner | OFF | low (shipped) |
| 6 | 0x17 | Air Blower | OFF | low (shipped) |
| 7 | 0x18 | Pool Light | OFF | low (shipped) |
| 8 | 0x19 | Spa Light | OFF | low |
| 9 | 0x1a | HIGH SPEED | OFF | medium |
| 10 | 0x1b | Not Used | OFF | n/a (unconfigured) |
| 11 | 0x1c | Not Used | OFF | n/a (unconfigured) |
| 12 | 0x1d | Extra Aux | OFF | low |
| 13 | 0x1e | Sprinklers | OFF | low |
| 14 | 0x1f | Spa Mode | OFF | medium (valves) |

Slots 15-16 are blank scroll/indicator buttons (state 0xFF), not equipment.

## Controllable items: HOME page (0x01)

Keycode = 0x11 + slot, valid ONLY on the home page. These are the currently
shipped controls.

| Slot | Keycode | Device | Notes |
|---|---|---|---|
| 0 | 0x11 | Filter Pump | shipped toggle |
| 1 | 0x12 | Spa | shipped (pool/spa valve toggle) |
| 2 | 0x13 | Pool Heat | excluded (heater) |
| 3 | 0x14 | Spa Heat | excluded (heater) |
| 4 | 0x15 | Cleaner | shipped toggle |
| 5 | 0x16 | Air Blower | shipped toggle |
| 6 | 0x17 | Pool Light | shipped toggle |

## Macros: DEVICES2 page (0x35)

Keycode = 0x11 + slot, valid only on this page.

| Slot | Keycode | Macro |
|---|---|---|
| 0 | 0x11 | Clean Mode |
| 1 | 0x12 | Pool Mode |
| 2 | 0x13 | Day Party |
| 3 | 0x14 | All Off |

## CRITICAL: keycode meaning is page-dependent

The same keycode means different things on different pages. Examples:
- 0x13 = Pool Heat on HOME, but = VSP1 Spd ADJ on DEVICES, and = Day Party on DEVICES2.
- 0x14 = Spa Heat on HOME, but = Pool Heat on DEVICES, and = All Off on DEVICES2.

Any control that sends a grid keycode (0x11-0x1f) MUST confirm `current_page`
first. Sending the VSP-adjust keycode (0x13) while on HOME would toggle a heater.
This is the central safety rule for all future control work here.

## Pump speed SET path (next session, not built yet)

1. Navigate to DEVICES (Home, then Other Devices key 0x18); confirm page 0x36.
2. Press slot-2 keycode 0x13 (VSP1 Spd ADJ); confirm the panel opens SET_VSP (0x1e).
3. Value-set handshake (AqualinkD iaqtouch): reply ACK_CMD_READY_CTRL (0x80) to an
   ordinary poll to request the control slot; the panel then sends CMD_IAQ_CTRL_READY
   (0x31); reply with the 0x24 value frame carrying ASCII RPM digits (e.g. "2750").
4. Clamp 600-3450 RPM (Intelliflo VS = RPM/Speed mode, confirmed by the "Spd"
   label). The panel rejects out-of-range with an error popup.
5. Confirm by reading RPM back from STATUS2.

## Build roadmap (safe order)

1. Pump RPM/watts READING (this session): view STATUS2, decode, publish sensors.
2. Spa Light, Extra Aux, Sprinklers (DEVICES toggles, low risk): add to a
   devices-page allowlist; press on the devices page only.
3. Pump RPM SETTING (the value-set handshake above): heavily gated, founder watching.
4. Spa Mode and other valve modes (medium risk): investigate valve behavior first.
5. Pool Heat and Spa Heat (high risk, LAST per founder): heaters.
