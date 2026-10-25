"""Known-answer joint-state, covariance, rejection and recorded-input replay checks."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'algorithms/ekf-slam'))
from ekf import EKFSLAM, Noise


class EKFTests(unittest.TestCase):
    def test_motion_known_arc_and_cross_covariance(self):
        slam = EKFSLAM()
        slam.observe('a', 2., 0.)
        self.assertGreater(np.linalg.norm(slam.cov[:3, 3:]), 0)
        slam.predict(1., math.pi / 2)
        np.testing.assert_allclose(slam.mean[:3], [math.sqrt(.5), math.sqrt(.5), math.pi / 2])
        np.testing.assert_allclose(slam.cov, slam.cov.T, atol=1e-12)

    def test_unknown_map_is_initialized_from_relative_observation(self):
        slam = EKFSLAM([1, 2, math.pi / 2])
        self.assertEqual(len(slam.landmarks), 0)
        slam.observe('a', 2, 0)
        np.testing.assert_allclose(slam.mean[3:], [1, 4], atol=1e-12)
        self.assertEqual(len(slam.mean), 5)

    def test_reobservation_corrects_robot_and_landmarks(self):
        slam = EKFSLAM()
        slam.observe('a', 3, 0)
        slam.observe('b', 3, math.pi / 2)
        slam.predict(1.04, .025)
        before = abs(slam.mean[0] - 1)
        landmark_before = slam.mean[3:].copy()
        slam.observe('a', 2, 0)
        slam.observe('b', math.sqrt(10), math.atan2(3, -1))
        self.assertLess(abs(slam.mean[0] - 1), before)
        self.assertGreater(np.linalg.norm(slam.mean[3:] - landmark_before), 0)
        self.assertEqual(slam.counts['corrected'], 2)

    def test_covariance_psd_after_many_joint_updates(self):
        rng = np.random.default_rng(7)
        slam = EKFSLAM()
        truth = np.zeros(3)
        landmarks = [(2, 1), (-2, 3), (0, -2), (3, 4)]
        for _ in range(40):
            d, a = .04, .025
            heading = truth[2] + a / 2
            truth += [d * math.cos(heading), d * math.sin(heading), a]
            slam.predict(d + rng.normal(0, .001), a + rng.normal(0, .002))
            for i, landmark in enumerate(landmarks):
                delta = np.asarray(landmark) - truth[:2]
                slam.observe(str(i), float(np.linalg.norm(delta)), math.atan2(delta[1], delta[0]) - truth[2])
        self.assertGreater(np.linalg.eigvalsh(slam.cov).min(), -1e-10)
        self.assertLess(np.linalg.norm(slam.mean[:2] - truth[:2]), .03)

    def test_large_innovation_rejected_without_changing_state(self):
        slam = EKFSLAM()
        slam.observe('a', 2, 0)
        before = slam.mean.copy()
        self.assertEqual(slam.observe('a', 20, 1), 'rejected')
        np.testing.assert_array_equal(slam.mean, before)

    def test_invalid_measurement_and_config_are_rejected(self):
        for args in [('', 1, 0), ('a', 0, 0), ('a', 1, float('nan'))]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                EKFSLAM().observe(*args)
        with self.assertRaises(ValueError):
            Noise(range_std=-1)

    def test_no_ground_truth_or_world_access_in_estimator(self):
        # The estimator API's only dynamic inputs are motion and relative observations.
        slam = EKFSLAM()
        slam.predict(.1, .01)
        slam.observe('new', 1, .1)
        snapshot = slam.snapshot()
        self.assertEqual(snapshot['observations']['initialized'], 1)
        self.assertNotIn('ground_truth', snapshot)


if __name__ == '__main__':
    unittest.main()
