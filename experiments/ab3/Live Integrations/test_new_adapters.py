"""Monocular output scale, server-side corrections and ROS 1 peer routes (no ROS needed)."""
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from monocular_scale import MonocularScale
from ros_routes import ros1_routes
from server_correction import ServerCorrection, matrix
from pose_frames import matrix_quaternion


def yaw_quaternion(yaw):
    return [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)]


class MonocularScaleTests(unittest.TestCase):
    def test_recovers_scale_from_straight_segments_and_ignores_turns(self):
        mono = MonocularScale()
        t, nodes, native_scale = 0., [], .37            # native map units per metre
        x = 0.
        for k in range(40):
            for _ in range(10):                          # 0.2 m/s for 10 steps of 0.032 s
                t += .032
                mono.wheels(t, [.0064, .0064])
            x += .064
            yaw = 1.2 if 20 <= k < 22 else 0.            # a turn in the middle (excluded)
            nodes.append({'t': t, 'position': [x * native_scale, 0., 0.], 'quaternion': yaw_quaternion(yaw)})
        self.assertAlmostEqual(mono.update(nodes), 1 / native_scale, places=3)
        scaled = mono.apply({'position': [1., 2., 3.], 'quaternion': [0, 0, 0, 1], 'metric': False})
        self.assertTrue(scaled['metric'])
        self.assertAlmostEqual(scaled['position'][1], 2 / native_scale, places=3)

    def test_no_scale_before_enough_travel(self):
        mono = MonocularScale()
        mono.wheels(.1, [.01, .01])
        self.assertIsNone(mono.update([{'t': 0., 'position': [0, 0, 0], 'quaternion': [0, 0, 0, 1]},
                                       {'t': .1, 'position': [.01, 0, 0], 'quaternion': [0, 0, 0, 1]}]))


class ServerCorrectionTests(unittest.TestCase):
    def test_vio_pose_is_carried_into_the_server_frame(self):
        with tempfile.TemporaryDirectory() as d:
            native = Path(d) / 'robot_1/native'
            native.mkdir(parents=True)
            # Server frame = VIO frame rotated 90 deg and shifted by (5, 1, 0).
            T_server_vio = matrix([5., 1., 0.], yaw_quaternion(math.pi / 2))
            kf_vio = matrix([2., 0., 0.], yaw_quaternion(0.))
            kf_server = T_server_vio @ kf_vio
            node = {'key': '3_1', 't': 4.0, 'position': kf_server[:3, 3].tolist(),
                    'quaternion': matrix_quaternion(kf_server[:3, :3]),
                    'vio_position': [2., 0., 0.], 'vio_quaternion': yaw_quaternion(0.)}
            (native / 'covins_clients.json').write_text(json.dumps({'0': 1, '1': 2}))
            (native / 'covins_backend.json').write_text(json.dumps({'t': 4.5, 'clients': {'1': {'frame': 'covins_map_0', 'nodes': [node]}}}))
            correction = ServerCorrection(d, 2)
            events = correction.process([], 5.)
            self.assertEqual(events[0]['kind'], 'graph3')
            self.assertEqual(events[0]['frame'], 'covins_map_0')
            pose = correction.apply({'kind': 'pose3', 't': 5., 'frame': 'covins_vio_2', 'position': [3., 0., 0.],
                                     'quaternion': yaw_quaternion(0.), 'axes': 'optical'})
            self.assertEqual(pose['frame'], 'covins_map_0')
            np.testing.assert_allclose(pose['position'], [5., 4., 0.], atol=1e-9)   # (3,0) rotated 90 deg + (5,1)


class RouteTests(unittest.TestCase):
    def test_every_outgoing_topic_has_a_receiver(self):
        for stack, robots in (('ccm_slam', 4), ('kimera_multi', 5)):
            routes = {n: ros1_routes(stack, n, robots) for n in range(1, robots + 1)}
            for n, r in routes.items():
                for out in r['outgoing']:
                    receivers = [m for m in routes if m != n and any(
                        i['topic'] == out['topic'] and n in i['sources'] for i in routes[m]['incoming'])]
                    expected = list(range(1, robots + 1)) if out['destination'] == 0 else [out['destination']]
                    self.assertEqual(sorted(receivers), sorted(m for m in expected if m != n), (stack, n, out))
                for inc in r['incoming']:
                    self.assertNotIn(n, inc['sources'])


if __name__ == '__main__':
    unittest.main()
