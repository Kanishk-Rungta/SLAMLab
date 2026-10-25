"""Analytic metric, format, association and rejection cases; all poses are synthetic."""
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('slamlab_trajectory', Path(__file__).resolve().parents[1] / 'benchmarks/evaluation/trajectory.py')
trajectory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trajectory)


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.times = np.arange(5, dtype=np.int64) * 1_000_000_000
        self.poses = np.array([[0., 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]])

    def test_constant_translation_has_known_ate_and_zero_rpe(self):
        estimate = self.poses.copy()
        estimate[:, :2] += [3, 4]
        report, *_ = trajectory.evaluate(self.times, estimate, self.times, self.poses)
        self.assertAlmostEqual(report['ate_m']['rmse'], 5)
        self.assertAlmostEqual(report['rpe']['translation_m']['rmse'], 0)

    def test_rigid_alignment_recovers_rotated_translated_path(self):
        angle = .7
        rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        reference = np.array([[0., 0, 0], [1, 0, .2], [1, 1, .4], [0, 2, .5], [2, 3, .6]])
        estimate = reference.copy()
        estimate[:, :2] = reference[:, :2] @ rotation.T + [5, -2]
        estimate[:, 2] += angle
        report, *_ = trajectory.evaluate(self.times, estimate, self.times, reference, alignment='se2')
        self.assertLess(report['ate_m']['rmse'], 1e-12)
        self.assertLess(report['orientation_error_deg']['rmse'], 1e-12)
        self.assertEqual(report['alignment']['scale'], 1)

    def test_alignment_never_fits_scale(self):
        estimate = self.poses.copy()
        estimate[:, 0] *= 2
        report, *_ = trajectory.evaluate(self.times, estimate, self.times, self.poses, alignment='se2')
        self.assertGreater(report['ate_m']['rmse'], .5)
        self.assertEqual(report['alignment']['scale'], 1)

    def test_relative_pose_known_translation_and_rotation_error(self):
        reference = np.array([[0., 0, 0], [1, 0, 0]])
        estimate = np.array([[0., 0, 0], [1.1, 0, math.radians(5)]])
        report, *_ = trajectory.evaluate(self.times[:2], estimate, self.times[:2], reference)
        self.assertAlmostEqual(report['rpe']['translation_m']['rmse'], .1)
        self.assertAlmostEqual(report['rpe']['rotation_deg']['rmse'], 5)

    def test_association_unique_monotone_and_reports_coverage(self):
        estimated = np.array([0, 1, 2, 10], dtype=np.int64)
        reference = np.array([0, 2, 10], dtype=np.int64)
        pairs = trajectory.associate(estimated, reference, 1)
        self.assertEqual(len(set(pairs[:, 1])), len(pairs))
        self.assertTrue(np.all(np.diff(pairs[:, 1]) > 0))
        self.assertEqual(pairs.tolist(), [[0, 0], [1, 1], [3, 2]])

    def test_timestamp_precision_at_epoch_nanoseconds(self):
        a = trajectory.nanoseconds('1403636579.123456789')
        b = trajectory.nanoseconds('1403636579.123456790')
        self.assertEqual(b - a, 1)

    def test_no_valid_rpe_pairs_is_unavailable_not_zero(self):
        report, *_ = trajectory.evaluate(self.times, self.poses, self.times, self.poses,
                                         rpe_delta_ns=10_000_000_000)
        self.assertIsNone(report['rpe'])

    def test_stationary_alignment_and_zero_distance_handling(self):
        poses = np.zeros((5, 3))
        report, *_ = trajectory.evaluate(self.times, poses, self.times, poses)
        self.assertIsNone(report['endpoint_error_percent_of_distance'])
        with self.assertRaises(ValueError):
            trajectory.evaluate(self.times, poses, self.times, poses, alignment='se2')

    def test_csv_rejects_nonfinite_duplicate_and_malformed_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'poses.csv'
            for rows in ('0,0,0,0\n0,1,0,0', '0,0,0,0\n1,nan,0,0', '0,0,0,0\n1,1,0'):
                path.write_text('timestamp,x,y,yaw\n' + rows)
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    trajectory.load_csv(path)

    def test_planar_tum_conversion_preserves_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'poses.tum', Path(directory) / 'poses.csv'
            source.write_text('1403636579.123456789 0 0 0 0 0 0 1\n1403636580.123456790 1 2 0 0 0 0 1\n')
            trajectory.convert_tum(source, destination)
            times, poses = trajectory.load_csv(destination)
            self.assertEqual(times[0], 1403636579123456789)
            self.assertEqual(int(times[1] - times[0]), 1000000001)
            self.assertEqual(poses[1].tolist(), [1, 2, 0])
            with self.assertRaises(FileExistsError):
                trajectory.convert_tum(source, destination)

    def test_tum_rejects_nonplanar_motion(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'poses.tum', Path(directory) / 'poses.csv'
            source.write_text('0 0 0 0 0 0 0 1\n1 1 0 .2 0 0 0 1\n')
            with self.assertRaises(ValueError):
                trajectory.convert_tum(source, destination)
            self.assertFalse(destination.exists())

    def test_no_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            trajectory.evaluate(self.times, self.poses, self.times + 100_000_000_000, self.poses)


if __name__ == '__main__':
    unittest.main()
