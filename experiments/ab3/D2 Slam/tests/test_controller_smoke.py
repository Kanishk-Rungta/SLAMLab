"""Runs the real Webots controller against a fake robot and a fake native gateway.

The fake gateway speaks the real local protocol and returns the kinds of events
the native side produces, so the controller's sensor stepping, one-step image
delay, radio handling and benchlog output are exercised without Webots or Docker.
It says nothing about D2SLAM's accuracy.
"""
import json
import math
import os
from pathlib import Path
import runpy
import socket
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT.parent / 'Standard Environment'
sys.path[:0] = [str(ROOT/'bridge')]
import numpy as np
from wire import send, receive, decode_bytes, encode_bytes
from radio_packets import fragments
from lcm_frames import pack


class Device(object):
    def __init__(self, robot, name):
        self.robot, self.name, self.velocity, self.angle, self.sent = robot, name, 0., 0., []
        self.queue = []

    def enable(self, period): pass
    def setPosition(self, value): pass
    def setChannel(self, value): pass
    def setVelocity(self, value): self.velocity = value
    def getValue(self): return self.angle
    def getValues(self): return [0.01, 0., 9.81]
    def getRollPitchYaw(self): return [0., 0., self.robot.yaw]
    def getWidth(self): return 320
    def getHeight(self): return 360
    def getFov(self): return 1.0472
    def getImage(self):
        rng = np.random.RandomState(int(self.robot.time*1000) % 1000)
        return rng.randint(0, 255, (360, 320, 4)).astype(np.uint8).tobytes()
    def send(self, packet): self.sent.append(packet)
    def getQueueLength(self): return len(self.queue)
    def getBytes(self): return self.queue[0]
    def nextPacket(self): self.queue.pop(0)


class FakeRobot(object):
    limit = 30.

    def __init__(self):
        self.time, self.yaw = 0., 0.
        self.devices = {}

    def getName(self): return 'bstem1'
    def getBasicTimeStep(self): return 32.
    def getTime(self): return self.time

    def getDevice(self, name):
        return self.devices.setdefault(name, Device(self, name))

    def step(self, ms):
        if self.time >= self.limit:
            return -1
        for side in ('left', 'right'):
            motor = self.devices['%s_motor' % side]
            self.devices['%s_encoder' % side].angle += motor.velocity*ms/1000.
        self.time = round(self.time+ms/1000., 6)
        if abs(self.time-4.992) < 1e-6:  # a peer's radio packet arrives (step 156)
            packet = fragments(2, -1, 'lcm', b'p'*16, pack('PGO_Sync_Data', b'peer-bytes'))[0]
            self.devices['receiver'].queue.append(packet)
        return 0


def fake_native(listener, record):
    client, _ = listener.accept()
    assert receive(client) == {'protocol': 'd2slam-original-v1'}
    send(client, {'ready': True, 'protocol': 'd2slam-original-v1'})
    frames = 0
    while True:
        message = receive(client)
        if message.get('stop'):
            break
        record['steps'] += 1
        record['radio_in'] += len(message['radio'])
        events = []
        if 'images' in message:
            stamp = message['image_stamp']
            assert stamp < message['t'], 'images must arrive one step after their stamp'
            assert len(message['images']) == 2
            frames += 1
            pose = [0.05*frames, 0., 0.]
            if frames > 3:  # D2VINS initialized
                events.append({'kind': 'odometry', 't': stamp, 'pose': pose})
            events.append({'kind': 'frame', 't': stamp, 'latency_s': .01, 'keyframe': frames > 3 and frames % 3 == 0,
                           'frame_id': frames, 'initialized': frames > 3})
            if frames == 30:
                events += [{'kind': 'pgo_pose', 't': stamp, 'pose': [pose[0], .1, 0.]},
                           {'kind': 'solve', 't': message['t'], 'duration': .02, 'success': True},
                           {'kind': 'loop', 'id': 7, 'ts_a': stamp, 'ts_b': 1.2, 'drone_a': 1, 'drone_b': 1,
                            'relative': [.1, 0., 0., 0., 0., 0., 1.], 'inliers': 42},
                           {'kind': 'fused', 't': message['t'], 'peers': {'2': [3., 4., .5]}},
                           {'kind': 'pgo_traj', 'stamps': [1.248], 'poses': [[0.6, .1, 0.]]}]
        radio = []
        if frames == 40 and 'images' in message:
            radio = [encode_bytes(p) for p in fragments(1, -1, 'lcm', b'm'*16, pack('VIOKF_HEADER', b'x'*30000))]
        send(client, {'events': events, 'radio': radio,
                      'resources': {'cpu_pct': 1., 'rss': 1, 'threads': 1, 'cpu_seconds': .1} if record['steps'] == 50 else None})
    client.close()


class ControllerSmokeTest(unittest.TestCase):
    def test_controller_produces_benchmark_records(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run/'benchmark').mkdir()
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            profile = json.loads((ROOT/'config/benchmark.json').read_text())
            config = {'output_dir': str(run), 'robots': 1, 'max_seconds': 20, 'idle_seconds': 1800,
                      'live_map_wall_seconds': 1e9, 'profile': profile, 'upstream_commit': 'test',
                      'native_host': '127.0.0.1', 'native_ports': [port]}
            (run/'run_config.json').write_text(json.dumps(config))
            record = {'steps': 0, 'radio_in': 0}
            server = threading.Thread(target=fake_native, args=(listener, record))
            server.start()
            fake = types.ModuleType('controller')
            robot = FakeRobot()
            fake.Robot = lambda: robot
            environment = {'D2SLAM_RUN_CONFIG': str(run/'run_config.json'), 'STANDARD_ENV': str(STANDARD),
                           'SLAM_BENCH_RUN_DIR': str(run/'benchmark'), 'SLAM_BENCH_SCENARIO': ''}
            saved_path = list(sys.path)
            try:
                with mock.patch.dict(os.environ, environment), mock.patch.dict(sys.modules, {'controller': fake}):
                    runpy.run_path(str(ROOT/'webots_controller/d2slam.py'), run_name='__main__')
            finally:
                sys.path[:] = saved_path
                server.join(10)
                listener.close()
            records = [json.loads(line) for line in (run/'benchmark/robots/bstem1/bench.jsonl').read_text().splitlines()]
            kinds = {r['type'] for r in records}
            for kind in ('meta', 'tracking', 'init', 'pose', 'frame', 'keyframe', 'map_update', 'map', 'loop',
                         'optimization', 'merge', 'peer_pose', 'send', 'recv', 'resource', 'end'):
                self.assertIn(kind, kinds)
            self.assertEqual(records[0]['algorithm'], 'D2SLAM-Original-StereoIMU')
            self.assertEqual(records[0]['frame'], 'd2_map_robot_1')
            poses = [r for r in records if r['type'] == 'pose']
            self.assertGreaterEqual(len(poses)/(poses[-1]['t']-poses[0]['t']), 2.)
            self.assertNotIn('odom', poses[0])  # local wheel odometry is not passed as shared-frame odometry
            # After the D2PGO pose, odometry carries the correction (+0.1 m in y).
            self.assertAlmostEqual(poses[-1]['p'][1], .1, places=6)
            loop = [r for r in records if r['type'] == 'loop'][0]
            self.assertEqual((loop['matched_robot'], loop['matched_time'], loop['accepted']), ('bstem1', 1.2, True))
            np.testing.assert_allclose(loop['relative'], [-.1, 0., 0.], atol=1e-9)
            self.assertEqual([r['src'] for r in records if r['type'] == 'recv'], ['bstem2'])
            sent = robot.devices['emitter'].sent
            self.assertEqual(len(sent), 3)  # the 30 kB message, paced and fragmented
            self.assertTrue(all(len(p) <= 12000 for p in sent))
            summary = json.loads((run/'robot_1/summary.json').read_text())
            self.assertEqual(summary['reason'], 'time_limit')
            self.assertGreater(summary['keyframes'], 0)
            self.assertTrue((run/'robot_1/final_map.png').exists())
            self.assertGreater(len((run/'robot_1/estimate_tum.txt').read_text().splitlines()), 10)
            self.assertTrue((run/'benchmark/STOP').exists())  # robot 1 ends the run for the supervisor
            self.assertGreater(record['steps'], 600)


if __name__ == '__main__':
    unittest.main()
