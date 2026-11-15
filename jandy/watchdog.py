"""HA watchdog and HA-silent failsafe: the pure decision logic.

Reference implementation for the C++ in components/jandy_aqualink/jandy_proto.*
(watchdog_decide, failsafe_action), which self-tests the same vectors on boot.
All times are milliseconds.
"""

from enum import IntEnum

MIN = 60 * 1000

# Give the API time to come up after a boot before judging the silence, because
# silence carried across a watchdog reboot can already exceed the next threshold.
MIN_UPTIME = 5 * MIN

# The panel drops the filter pump for a few seconds on valve moves. Only treat it
# as off after this long.
PUMP_OFF_CONFIRM = 2 * MIN

# Filter Pump is a toggle. Never press it twice inside this window, so a stale
# reading can at worst cost one wrong press, not a flip-flop.
PRESS_MIN_GAP = 30 * MIN

# Re-assert the failsafe speed this often while the pump runs, because the panel's
# stored programs push their own speeds.
RPM_REASSERT = 10 * MIN


def reboot_threshold(reboot_count: int, reboot_after: int, max_backoff: int) -> int:
    """Silence that triggers the next watchdog reboot: doubles per reboot, capped."""
    t = reboot_after
    for _ in range(reboot_count):
        t *= 2
        if t >= max_backoff:
            return max_backoff
    return min(t, max_backoff)


def watchdog_decide(silence: int, armed: bool, enabled: bool, uptime: int, reboot_count: int,
                    reboot_after: int, failsafe_after: int, max_backoff: int):
    """Return (reboot_now, failsafe_active)."""
    if not (armed and enabled):
        return (False, False)
    failsafe = silence >= failsafe_after
    reboot = (uptime >= MIN_UPTIME and
              silence >= reboot_threshold(reboot_count, reboot_after, max_backoff))
    return (reboot, failsafe)


class FailsafeAction(IntEnum):
    NONE = 0
    PRESS_FILTER_PUMP = 1
    SET_RPM = 2


def failsafe_action(spa_mode: int, pump_on: int, pump_off_for: int, since_press: int,
                    since_rpm: int, busy: bool) -> FailsafeAction:
    """What the failsafe does this tick. spa_mode / pump_on: -1 unknown, 0 off, 1 on."""
    if busy or spa_mode != 0:
        return FailsafeAction.NONE
    if pump_on == 0:
        if pump_off_for >= PUMP_OFF_CONFIRM and since_press >= PRESS_MIN_GAP:
            return FailsafeAction.PRESS_FILTER_PUMP
        return FailsafeAction.NONE
    if pump_on == 1 and since_rpm >= RPM_REASSERT:
        return FailsafeAction.SET_RPM
    return FailsafeAction.NONE
