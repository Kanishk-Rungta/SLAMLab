"""Motion policy regressions, not native tracking or physics validation."""
import unittest

from reactive_drive import ReactiveDrive


class ReactiveDriveTests(unittest.TestCase):
    def test_alternating_side_clearance_cannot_reverse_active_turn(self):
        policy = ReactiveDrive(2)
        for frame in range(600):
            sides = (.1, .3) if frame % 2 == 0 else (.3, .1)
            linear, angular, mode = policy.command(10 + frame * .096, (None, *sides), 0.)
            self.assertEqual((linear, angular, mode), (0., -.45, 'reactive_turn'))

    def test_resume_requires_both_minimum_turn_and_wider_clearance(self):
        policy = ReactiveDrive(1)
        self.assertEqual(policy.command(10., (.2, .5, .1), 0.)[1], .45)
        self.assertEqual(policy.command(11., (.8, .1, .5), 0.)[2], 'reactive_turn')
        # Crossing the old .35 m threshold must not alternate forward/turn.
        for stamp, front in ((12., .36), (12.1, .34), (12.2, .44)):
            self.assertEqual(policy.command(stamp, (front, .1, .5), 0.)[2], 'reactive_turn')
        linear, angular, mode = policy.command(12.3, (.45, .1, .5), 0.)
        self.assertGreater(linear, 0.)
        self.assertEqual((angular, mode), (0., 'reactive_forward'))
        self.assertIsNone(policy.turn_sign)
        # A later obstacle may legitimately select the opposite direction.
        self.assertEqual(policy.command(13., (.2, .1, .5), 0.)[1], -.45)

    def test_stale_stereo_stops_motion_without_losing_turn_commitment(self):
        policy = ReactiveDrive(1)
        policy.command(10., (None, .1, .5), 0.)
        for age in (.5, 2., float('inf'), -.1):
            self.assertEqual(policy.command(11., (.8, .5, .1), age), (0., 0., 'waiting_for_stereo'))
        self.assertEqual(policy.command(12., (None, .5, .1), 0.)[1], -.45)

    def test_clear_path_and_periodic_scans_keep_existing_speeds(self):
        for number, direction in ((1, 1), (2, -1)):
            policy = ReactiveDrive(number)
            self.assertEqual(policy.command(1., (1., 1., 1.), 0.), (0., 0., 'waiting_for_stereo'))
            self.assertEqual(policy.command(10., (1., 1., 1.), 0.), (.15, 0., 'reactive_forward'))
            self.assertEqual(policy.command(60., (1., 1., 1.), 0.), (0., direction * .45, 'periodic_scan'))


if __name__ == '__main__':
    unittest.main()
