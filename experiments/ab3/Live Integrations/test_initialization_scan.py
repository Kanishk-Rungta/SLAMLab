import math
import unittest

from initialization_scan import scan_command, ANGULAR_SPEED, SCAN_SECONDS


class InitializationScan(unittest.TestCase):
    def test_settles_then_rotates_without_translation(self):
        self.assertIsNone(scan_command(1.99, 1, False, 0.))
        self.assertEqual(scan_command(2., 1, False, .096), (0., ANGULAR_SPEED))
        self.assertEqual(scan_command(2., 2, False, .096), (0., -ANGULAR_SPEED))
        self.assertAlmostEqual(SCAN_SECONDS * ANGULAR_SPEED, 2 * math.pi)

    def test_scan_yields_to_reactive_motion_and_retries(self):
        self.assertIsNotNone(scan_command(2 + SCAN_SECONDS - .01, 1, False, .1))
        self.assertIsNone(scan_command(2 + SCAN_SECONDS + .01, 1, False, .1))
        self.assertIsNotNone(scan_command(2 + SCAN_SECONDS + 10.01, 1, False, .1))

    def test_first_native_pose_permanently_releases_scan(self):
        for now in (2., 12., 80., 200.):
            self.assertIsNone(scan_command(now, 1, True, .1))

    def test_stale_or_missing_stereo_never_commands_scan(self):
        for age in (.5, 1., float('inf'), -.01):
            self.assertIsNone(scan_command(4., 1, False, age))


if __name__ == '__main__':
    unittest.main()
