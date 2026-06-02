# Session 9 (Phase 2) design: heater temperature setpoint + status sensors

- Date: 2026-06-02
- Status: Approved by founder 2026-06-02 (brainstorm). Ready for implementation plan.
- Repo: esphome-jandy-aqualink, branch `master`, base commit `da1e9da` (after Session 9 Phase 1).
- Device `192.168.4.51`, ESPHome node `pool-bridge.yaml`, dashboard `http://192.168.1.126:6052`.
- Builds on: `docs/superpowers/specs/2026-06-02-heaters-design.md` (the Phase 1 on/off + survey design)
  and the Phase 1 plan `docs/superpowers/plans/2026-06-02-heater-onoff-and-survey.md`.

## Context and goal

Heater on/off (pool + spa) shipped and was live-tested in Session 9 Phase 1 (both heaters proven;
the spa heater physically fired). This Phase 2 adds the temperature TARGET so the **spa heats to 94F**
(the founder's old iAquaLink setting) instead of running toward the 104F hardware max, and the
**pool holds 85F**. Without a target, enabling spa heat runs toward the stored setpoint (believed
104), too hot, so spa heat was left off pending this build.

Scope chosen by the founder this session ("Fuller Phase 2"): the survey, the temperature setpoint,
the two heater on/off status sensors, the under-the-hood water-mode reliability fix, and the live test.

## The key finding that defines this session (corrects the Phase 1 assumption)

The HOME heat button is a **pure on/off toggle**; pressing it does NOT open a temperature screen
(proven live, Session 9). So SET_TEMP is reached another way, and there is genuine uncertainty about
how, or whether, it opens on this screenless RS-8 power center. Two candidate routes:

1. **Equipment-page (DEVICES) route, most promising here.** The pump's value screen (SET_VSP `0x1E`)
   was reachable on this panel by pressing the VSP-adjust item on DEVICES, bypassing the MENU. The
   heater analogue: navigate to DEVICES (`0x36`), press the heat item there (DEVICES Pool Heat `0x14`,
   Spa Heat `0x15`, per `docs/PANEL-CAPABILITY-MAP.md`), and watch for SET_TEMP (`0x39`). RISK: those
   heat items are plain toggle items (not labeled "ADJ" like the pump item), so a press there may just
   toggle the heater rather than open SET_TEMP. Unknown until surveyed.
2. **MENU route (what AqualinkD actually uses, doubtful here).** AqualinkD reaches SET_TEMP via the
   MENU: send `KEY_IAQTCH_MENU` (`0x02`) to reach MENU (`0x0F`), then `KEY_IAQTCH_SET_TEMP`
   (`0x14`, = KEY04) to reach SET_TEMP (`iaqtouch_aq_programmer.c` `goto_iaqt_page`). But this panel's
   MENU renders EMPTY (confirmed conclusively, Sessions 4 and 6), so this route may do nothing. Cheap
   to try as a fallback because the key is fixed, not discovered from the (empty) menu enumeration.

The survey (founder watching) tries both, equipment-page first, and captures whatever opens SET_TEMP.
If neither opens it, the status sensors and the water-mode fix still ship; only the target-temp part
defers (same fallback as the Phase 1 spec).

## What is already proven and reused (the hard part is done)

The temperature WRITE reuses the pump-speed value-set machinery verbatim. In AqualinkD,
`queue_iaqt_control_command(0, val)` builds the SAME `0x24` value frame for the pump RPM
(`iaqtouch_aq_programmer.c:976`) and the heater setpoint (`:1445`): `00 24 31 <digits> <0xcd pad to
18> cksum`, preceded by the `ACK_CMD_READY_CTRL` (`0x80`) control request. Our codebase already has
this, proven live on the pump in Session 6:

- `iaq_ctrl_ready_ack()` (the `0x80` control request), `frames.py`.
- `build_vsp_set_frame(rpm)` (the `0x24` value frame), `frames.py`.
- `num2iaqt_rpm(n)` (ASCII digits, NUL-padded to a 5-byte field), `frames.py`.
- The gated multi-step state machine `advance_set_sequence_` in `jandy_aqualink.cpp`.

So the only genuinely new wire detail is the **digit format for a 2-to-3-digit degrees-F value**
(85, 94, 104). The pump used 3-to-4-digit RPM; the padding/width for short numbers must be re-verified
against a real captured SET_TEMP frame (TDD), not guessed. AqualinkD uses the same `num2iaqtRSset`
for both, so the existing encoder is the strong candidate, but capture confirms it.

## Design

### 1. Survey (the gate, founder watching) -- confirm the route, capture the format

- Safe starting state: pool mode, filter pump running, presence on; then arm the interlock.
- Enable Pool Heat first (the founder's reported constraint: the temperature screen needs a heater
  on). On/off is shipped and proven.
- A small, heavily-gated **survey instrument**: a method that sends ONE specified keycode but ONLY
  while the decoder confirms the panel is on a specified page (interlock + presence + page-confirm +
  founder watching). This lets us try the candidate presses safely and reversibly. It is removed or
  left inert after the survey; the real setpoint path is the proper state machine in section 2.
- Try, in order, watching the compact page decoder for `IAQ PAGE ...(0x39)` (SET_TEMP):
  1. DEVICES route: HOME -> Other Devices (`0x18`) -> confirm DEVICES (`0x36`) -> press Pool Heat
     (`0x14`) -> does SET_TEMP open, or does the heater just toggle?
  2. MENU route: HOME -> MENU (`0x02`) -> send Set Temp key (`0x14`) -> does SET_TEMP open?
- On reaching SET_TEMP, capture: (a) the exact key + page that opened it for pool vs spa; (b) the page
  enumeration (AqualinkD shows button labels like "Pool Heat NN" / "Spa Heat NN", so this likely lets
  us READ the current 104 directly and may give free setpoint-readback); (c) at least one real `0x24`
  value frame per body, for the digit-format TDD.
- If neither route opens SET_TEMP, conclude it is not reachable on this panel; ship sections 4 and 5
  (status sensors + water-mode fix) and defer the setpoint.

### 2. Temperature setpoint write (built from the survey capture, TDD)

- A new gated routine mirroring the proven pump-speed setter: open SET_TEMP the way the survey found,
  select the body's setpoint, reply `ACK_CMD_READY_CTRL` (`0x80`) on a poll, the panel sends
  CMD_IAQ_CTRL_READY (`0x31`), transmit the `0x24` value frame with the ASCII degree digits, read
  back, return HOME. Same shape and mutual exclusion as `advance_set_sequence_`.
- Digit encoder for degrees F: re-verify width/padding for 2-to-3-digit values against the captured
  frame (TDD). Reuse `num2iaqt_rpm` if the capture matches; add a temperature-specific encoder only if
  it differs.
- Clamps: pool 45 to 90F, spa 80 to 104F. Refuse out of range (mirror `rpm_check`).
- HA controls: a `number` entity per body, "Pool Heat Setpoint" and "Spa Heat Setpoint", gated exactly
  like the pump-speed slider (master interlock + presence). Defaults seeded to 85 (pool) and 94 (spa).
- Spa note: setting the spa TARGET just stores a number, it does not fire the heater, so the setpoint
  write itself should not require spa mode (only ENABLING spa heat does, already gated). Reaching
  SET_TEMP may still require a heater enabled (the founder's constraint); confirm in the survey.

### 3. Safety model (non-negotiable)

- **Page-context guard on every keycode.** `0x14` is Spa Heat on HOME, Pool Heat on DEVICES, and Set
  Temp on MENU; the value-set keys are page-scoped too. Every keycode confirms `current_page()` first,
  re-checked at the transmit point. This is the central safety property of the whole project.
- The `0x24` temperature digits are transmitted ONLY when the decoder confirms `page == SET_TEMP
  (0x39)`.
- Master interlock + iAqualink presence gate everything; both off by default. One control sequence at
  a time (setpoint mutually exclusive with pump-set and device-toggle). Interlock-off aborts mid-run.

### 4. Heater on/off status sensors

- Two `binary_sensor`s, `pool_heat_enabled` and `spa_heat_enabled`, decoded from the HOME heater
  button states (Session 9 captures: enabled = `B2/B3 s3 t11`, off = `s0 t5`). The `IaqReader` already
  parses HOME buttons. Read-only, continuous from the HOME enumeration plus deltas. Useful on their own
  and a prerequisite for any future spa auto-off automation (so it never toggles the wrong way).

### 5. Water-mode reliability fix (root cause)

- The `IaqReader` resets `water_mode` to 0 ("unknown") on a partial HOME page, which made spa-mode
  reads briefly flaky (it spuriously refused Spa Heat and the mode switches in Session 9, worked around
  with the `cs_spa_` bit). Fix: the reader KEEPS the last-known `water_mode` instead of resetting to 0
  on a partial page. This also fixes the pool-temp "unknown" flicker.
- Keep the proven `cs_spa_` (0x08 status bit) gate for spa-mode-dependent checks as a backstop;
  belt and suspenders.

### 6. Live test (founder at the pad and spa)

- Refusal check: a setpoint while disarmed logs REFUSED and sends nothing.
- Pool: set 85, read back, confirm.
- Spa: switch to spa mode, set 94, read back, confirm at the spa that it heads toward 94 not 104.
- Spa auto-off (still UNSETTLED): switch spa -> pool with spa heat enabled and observe whether the
  panel drops spa heat on its own. Records whether a future HA auto-off automation is needed.
- Resting state: leave **Pool Heat enabled at 85** so the panel holds the pool at 85 going forward
  (June, pool above 85, so it will not fire until it drops); leave **spa heat off** until a soak.
  Confirm presence ON, interlock OFF at the end.

### 7. Testing (TDD)

- Python (pytest) + C++ on-device selftest mirror: the temperature digit encoder + the `0x24` value
  frame (against the captured SET_TEMP frame), the clamps (pool 45-90, spa 80-104), the page guard
  (temperature digits refused unless `page == SET_TEMP`), and the heat-state decode (HOME-button
  fixtures). Full suite green before any flash; new byte-builders mirrored in the on-device selftest.

## Build order (writing-plans splits at the survey seam)

1. Desk, TDD, route-independent: the clamps + temperature encoder candidate, the heat-state status
   decode + sensors, the water-mode reader fix, and the gated survey instrument.
2. Live survey (founder watching): confirm the route, capture the value frame + current setpoints.
3. Desk, TDD: finalize the gated setpoint state machine + the value frame from the real capture; HA
   number entities.
4. Live test: set spa 94 / pool 85, confirm, observe spa auto-off, set the resting state.

No guessed bytes: every desk-built byte-builder is verified against a real captured frame before the
setpoint is trusted, exactly as the Phase 1 plan deferred the value pieces to the survey.

## Non-goals / out of scope

- The HA brain (scheduling pump/cleaner/filtration with a filtration failsafe) -- next session.
- A spa auto-off HA automation -- only built if the live test shows the panel does NOT drop spa heat
  on spa-mode exit; decided by the test, not pre-built (YAGNI).
- Solar heat; decoding every circuit state (Phase 4 polish).

## Watchpoints

- Page-scoped keycodes: `0x14` means three different things on HOME / DEVICES / MENU; confirm the page
  first, every time. The temperature digits go out only on confirmed SET_TEMP.
- The temperature screen may be unreachable on this screenless panel (the MENU is empty, the DEVICES
  heat items may only toggle). Honest possibility; the on/off + sensors + reliability fix still ship.
- Gate spa-mode on `cs_spa_` (the reliable 0x08 bit), never the flaky `iaq_water_mode_` home label
  (kept as a backstop even after the reader fix).
- Pump-restore-after-spa-exit: switching spa -> pool drops the filter pump; the first re-press during
  the ~1-2 min valve transition does not take, a second press after the valves settle sticks.
- Build/flash recipe + live-log capture (`C:\Users\Falcon\poollog.ps1`) as in Sessions 8-9. ESPHome
  object-id REST URLs are deprecated; drive via HA service calls.
- No em dashes, no AI jargon, plain-English explanations for the founder.
