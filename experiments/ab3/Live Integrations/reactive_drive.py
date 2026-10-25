"""Stateful DVM benchmark motion from local stereo clearance only."""


class ReactiveDrive:
    STOP_DISTANCE = .35
    RESUME_DISTANCE = .45
    MIN_TURN_SECONDS = 2.
    TURN_SPEED = .45

    def __init__(self, number):
        self.number = number
        self.reset()

    def reset(self):
        self.turn_sign = None
        self.turn_started = None

    def command(self, now, clearance, stereo_age):
        """Return linear/ angular velocity and the policy state.

        Commit to an obstacle-turn direction until at least two simulated
        seconds have elapsed AND the front clears the wider resume threshold.
        Side-clearance noise cannot reverse an active avoidance turn.
        """
        if now < 2. or not 0. <= stereo_age < .5:
            return 0., 0., 'waiting_for_stereo'
        front, left, right = clearance
        blocked = front is None or front < self.STOP_DISTANCE
        if self.turn_sign is None and blocked:
            self.turn_sign = 1 if (left or 0.) >= (right or 0.) else -1
            self.turn_started = now
        if self.turn_sign is not None:
            cleared = front is not None and front >= self.RESUME_DISTANCE
            if now - self.turn_started < self.MIN_TURN_SECONDS or not cleared:
                return 0., self.TURN_SPEED * self.turn_sign, 'reactive_turn'
            self.reset()
        if now % 60 < 4:
            return 0., self.TURN_SPEED * (1 if self.number % 2 else -1), 'periodic_scan'
        linear = min(.15, max(0., (front - self.STOP_DISTANCE) * .3))
        return linear, 0., 'reactive_forward'
