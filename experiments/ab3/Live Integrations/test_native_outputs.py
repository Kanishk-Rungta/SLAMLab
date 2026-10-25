import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from native_output_state import NativeCorrection, transform
from pose_frames import planar_pose, quaternion_matrix, matrix_quaternion
from ros_routes import peer_address, service_routes
from finalize_native import finalize

FB = Path(__file__).resolve().parent.parent


def pose(x=0., y=0., yaw=0.):
    return transform([x, y, 0.], [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)])


class OutputAdapters(unittest.TestCase):
    def test_quaternion_round_trip_at_half_turns(self):
        for q in ([0, 0, 0, 1], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [-.5, .5, -.5, .5]):
            rotation = quaternion_matrix(q)
            np.testing.assert_allclose(quaternion_matrix(matrix_quaternion(rotation)), rotation, atol=1e-9)

    def test_optical_camera_offset_is_removed(self):
        spec = {'left_position_m': [.13, .0125, .02]}
        event = {'position': [0., 0., 1.], 'quaternion': [0., 0., 0., 1.], 'axes': 'optical'}
        p, z = planar_pose(event, spec)
        np.testing.assert_allclose(p, [.87, -.0125, 0.], atol=1e-9)
        self.assertAlmostEqual(z, -.02)

    def test_no_corrected_pose_before_native_backend_anchor(self):
        state = NativeCorrection(1)
        state.odom(1., pose(1.))
        self.assertIsNone(state.pose_event())
        self.assertFalse(state.anchor(1., pose(1., 5.), 'swarm_robot0_map'))
        state.keyframe(7, 1., pose(1.))
        self.assertTrue(state.anchor(1., pose(1., 5.), 'swarm_robot0_map'))
        state.odom(2., pose(2.))
        np.testing.assert_allclose(state.pose_event()['position'], [2., 5., 0.])

    def test_native_graph_correction_and_latest_odometry_are_composed(self):
        state = NativeCorrection(2)
        state.keyframe(0, 1., pose())
        state.keyframe(1, 2., pose(1.))
        state.odom(3., pose(2.))
        self.assertTrue(state.apply_optimization({0: pose(0., 5.), 1: pose(1., 5.)}, 0))
        event = state.pose_event()
        self.assertEqual(event['frame'], 'swarm_robot0_map')
        np.testing.assert_allclose(event['position'], [2., 5., 0.])
        graph = state.graph_event(3.)
        self.assertEqual(graph['nodes'][0]['t'], 1.)
        np.testing.assert_allclose(graph['nodes'][0]['position'], [0., 5., 0.])
        state.keyframe(2, 3., pose(2.))
        np.testing.assert_allclose(state.graph_event(3.)['nodes'][2]['position'], [2., 5., 0.])

    def test_frame_change_clears_old_native_optimized_values(self):
        state = NativeCorrection(1)
        state.keyframe(0, 1., pose())
        state.apply_optimization({0: pose(0., 5.)}, 0)
        state.anchor(1., pose(0., 10.), 'swarm_robot1_map')
        np.testing.assert_allclose(state.graph_event(1.)['nodes'][0]['position'], [0., 10., 0.])

    def test_lost_native_odometry_is_not_reported_as_tracked_pose(self):
        state = NativeCorrection(1)
        state.keyframe(0, 1., pose())
        state.anchor(1., pose(), 'swarm_robot0_map')
        state.odom(2., pose(1.), valid=False)
        self.assertIsNone(state.pose_event())

    def test_pinned_native_build_adapters_apply(self):
        from live_runner import check_adapters
        for folder in ('DVM Slam', 'Swarm Slam'):
            with self.subTest(folder=folder):
                root = FB / folder
                if not (root / 'algorithm/upstream').is_dir():
                    # Fresh clone: sources are restored by the first PREPARE/BUILD/RUN (restore_sources.py).
                    self.skipTest('pinned sources not downloaded yet (run PREPARE once)')
                check_adapters(root, json.loads((root / 'config/benchmark.json').read_text()))


class PeerRoutes(unittest.TestCase):
    def test_sensor_and_visualization_topics_never_become_peer_traffic(self):
        for stack in ('dvm_slam', 'swarm_slam'):
            for topic in ('/ab3/left/image', '/clock', '/ab3/imu', '/tf', '/cslam/viz/pose_graph', '/r0/odom'):
                self.assertIsNone(peer_address(stack, topic, 3))

    def test_native_target_numbering_and_broadcasts(self):
        self.assertEqual(peer_address('dvm_slam', '/robot2/new_key_frames', 3), 2)
        self.assertEqual(peer_address('dvm_slam', '/successfully_merged', 3), 0)
        self.assertEqual(peer_address('swarm_slam', '/r0/cslam/get_pose_graph', 3), 1)
        self.assertEqual(peer_address('swarm_slam', '/r2/cslam/heartbeat', 3), 0)
        self.assertEqual(peer_address('swarm_slam', '/cslam/local_descriptors', 3), 0)
        self.assertIsNone(peer_address('swarm_slam', '/r3/cslam/get_pose_graph', 3))
        self.assertIsNone(peer_address('dvm_slam', '/robot0/new_key_frames', 3))
        self.assertEqual(len(service_routes('dvm_slam', 1, 3)), 6)


class EvaluationMetadata(unittest.TestCase):
    def test_loop_times_are_resolved_without_ground_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a = root / 'benchmark/robots/bstem1/bench.jsonl'
            b = root / 'benchmark/robots/bstem2/bench.jsonl'
            a.parent.mkdir(parents=True)
            b.parent.mkdir(parents=True)
            a.write_text(json.dumps({'type': 'event', 'name': 'native_keyframe', 't': 4., 'key': '7'}) + '\n' +
                json.dumps({'type': 'loop', 't': 10., 'accepted': True, 'current_keyframe': 7,
                            'matched_keyframe': 2, 'matched_robot': 'bstem2', 'matched_time': None}) + '\n')
            b.write_text(json.dumps({'type': 'event', 'name': 'native_keyframe', 't': 3., 'key': '2'}) + '\n')
            result = finalize(root)
            self.assertEqual(result['resolved_loops'], 1)
            loop = json.loads(a.read_text().splitlines()[1])
            self.assertEqual((loop['t'], loop['matched_time'], loop['detection_time']), (4., 3., 10.))
            self.assertFalse(result['ground_truth_used'])


if __name__ == '__main__':
    unittest.main()
