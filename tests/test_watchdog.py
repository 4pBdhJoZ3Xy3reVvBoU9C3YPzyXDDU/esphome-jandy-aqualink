"""HA watchdog and HA-silent failsafe decisions.

Home Assistant presses a heartbeat button every minute. `silence` is the time since
the last heartbeat, carried across the bridge's own watchdog reboots. The bridge
reboots itself when the silence passes a threshold that doubles after each
watchdog reboot (capped), and after a longer silence it holds the filter pump on
at a safe speed until Home Assistant is back. Both stay off until the first
heartbeat after a cold boot, so a bench device or a config without the HA
automation never reboots itself.
"""

import unittest

from jandy.watchdog import (
    MIN,
    FailsafeAction,
    failsafe_action,
    reboot_threshold,
    watchdog_decide,
)

CFG = dict(reboot_after=20 * MIN, failsafe_after=60 * MIN, max_backoff=360 * MIN)


def decide(silence, armed=True, enabled=True, uptime=30 * MIN, reboots=0):
    return watchdog_decide(silence=silence, armed=armed, enabled=enabled, uptime=uptime,
                           reboot_count=reboots, **CFG)


class TestRebootThreshold(unittest.TestCase):
    def test_doubles_per_reboot(self):
        self.assertEqual(reboot_threshold(0, 20 * MIN, 360 * MIN), 20 * MIN)
        self.assertEqual(reboot_threshold(1, 20 * MIN, 360 * MIN), 40 * MIN)
        self.assertEqual(reboot_threshold(2, 20 * MIN, 360 * MIN), 80 * MIN)

    def test_capped(self):
        self.assertEqual(reboot_threshold(5, 20 * MIN, 360 * MIN), 360 * MIN)
        self.assertEqual(reboot_threshold(40, 20 * MIN, 360 * MIN), 360 * MIN)


class TestWatchdogDecide(unittest.TestCase):
    def test_quiet_when_heartbeat_fresh(self):
        self.assertEqual(decide(1 * MIN), (False, False))

    def test_reboots_after_20_min_silence(self):
        self.assertEqual(decide(19 * MIN), (False, False))
        self.assertEqual(decide(20 * MIN), (True, False))

    def test_never_acts_before_first_heartbeat(self):
        self.assertEqual(decide(500 * MIN, armed=False), (False, False))

    def test_disabled_does_nothing(self):
        self.assertEqual(decide(500 * MIN, enabled=False), (False, False))

    def test_no_reboot_in_first_5_min_of_uptime(self):
        # silence carried across a reboot can already exceed the threshold; give
        # the API time to come up before judging it.
        self.assertEqual(decide(45 * MIN, reboots=1, uptime=4 * MIN), (False, False))
        self.assertEqual(decide(45 * MIN, reboots=1, uptime=6 * MIN), (True, False))

    def test_backoff_after_a_watchdog_reboot(self):
        self.assertEqual(decide(30 * MIN, reboots=1), (False, False))
        self.assertEqual(decide(40 * MIN, reboots=1), (True, False))

    def test_failsafe_after_60_min(self):
        self.assertEqual(decide(59 * MIN, reboots=2)[1], False)
        self.assertEqual(decide(60 * MIN, reboots=2)[1], True)

    def test_failsafe_needs_armed_and_enabled(self):
        self.assertEqual(decide(90 * MIN, armed=False)[1], False)
        self.assertEqual(decide(90 * MIN, enabled=False)[1], False)


def act(**kw):
    base = dict(spa_mode=0, pump_on=0, pump_off_for=5 * MIN, since_press=60 * MIN,
                since_rpm=60 * MIN, busy=False)
    base.update(kw)
    return failsafe_action(**base)


class TestFailsafeAction(unittest.TestCase):
    def test_pump_off_long_enough_presses_filter_pump(self):
        self.assertEqual(act(), FailsafeAction.PRESS_FILTER_PUMP)

    def test_pump_off_briefly_waits(self):
        # the panel drops the pump for a few seconds on valve moves; never toggle on that.
        self.assertEqual(act(pump_off_for=90 * 1000), FailsafeAction.NONE)

    def test_filter_pump_press_at_most_every_30_min(self):
        # Filter Pump is a TOGGLE: a second press inside 30 min could turn it back off.
        self.assertEqual(act(since_press=29 * MIN), FailsafeAction.NONE)
        self.assertEqual(act(since_press=30 * MIN), FailsafeAction.PRESS_FILTER_PUMP)

    def test_pump_on_sets_rpm_every_10_min(self):
        self.assertEqual(act(pump_on=1, since_rpm=10 * MIN), FailsafeAction.SET_RPM)
        self.assertEqual(act(pump_on=1, since_rpm=9 * MIN), FailsafeAction.NONE)

    def test_spa_mode_on_or_unknown_never_acts(self):
        self.assertEqual(act(spa_mode=1), FailsafeAction.NONE)
        self.assertEqual(act(spa_mode=-1), FailsafeAction.NONE)
        self.assertEqual(act(spa_mode=1, pump_on=1), FailsafeAction.NONE)

    def test_pump_state_unknown_never_acts(self):
        self.assertEqual(act(pump_on=-1), FailsafeAction.NONE)

    def test_busy_sequence_waits(self):
        self.assertEqual(act(busy=True), FailsafeAction.NONE)
        self.assertEqual(act(pump_on=1, busy=True), FailsafeAction.NONE)


if __name__ == "__main__":
    unittest.main()
