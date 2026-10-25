"""Exercise the actual shared controller with fake devices and native protocol.

These are I/O tests, not native SLAM runs or accuracy measurements.
"""
import json
import os
from pathlib import Path
import runpy
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
from live_wire import encode, unb64, b64
from live_radio import RadioLink, fragments

FB = Path(__file__).resolve().parent.parent


class ReportingRadio(RadioLink):
    """Inject one expired peer exchange while exercising the real controller."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reported = False

    def drain(self, send_packet, now):
        sent = super().drain(send_packet, now)
        if now > .5 and not self.reported:
            self.reported = True
            self.failed(2, {'kind': 'service_request', 'id': 'expired-test-request',
                            'name': '/robot2/get_current_map'}, 'delivery_timeout')
        return sent


class Device:
    def __init__(self, robot, name):
        self.robot, self.name = robot, name
        self.velocity, self.angle = 0., 0.
        self.sent, self.queue = [], []
    def enable(self, period): pass
    def setPosition(self, value): pass
    def setChannel(self, value): pass
    def setVelocity(self, value): self.velocity = value
    def getValue(self): return self.angle
    def getValues(self): return [.01, 0., 9.81]
    def getRollPitchYaw(self): return [0., 0., 0.]
    def getWidth(self): return 320
    def getHeight(self): return 360
    def getFov(self): return 1.0472
    def getImage(self):
        return np.random.RandomState(1).randint(0, 256, (360, 320, 4), dtype=np.uint8).tobytes()
    def send(self, packet): self.sent.append(packet)
    def getQueueLength(self): return len(self.queue)
    def getBytes(self): return self.queue[0]
    def nextPacket(self): self.queue.pop(0)


class Robot:
    def __init__(self):
        self.time, self.devices = 0., {}
        self.end_time, self.drive_history = 1.6, []
    def getName(self): return 'bstem1'
    def getBasicTimeStep(self): return 32.
    def getTime(self): return self.time
    def getDevice(self, name): return self.devices.setdefault(name, Device(self, name))
    def step(self, ms):
        if self.time >= self.end_time:
            return -1
        self.drive_history.append((self.time, self.devices['left_motor'].velocity,
                                   self.devices['right_motor'].velocity))
        self.time = round(self.time + ms / 1000, 9)
        if abs(self.time - .608) < 1e-9:
            self.devices['receiver'].queue.extend(fragments(2, 1, b'p' * 16, b'peer-data'))
        for side in ('left', 'right'):
            self.devices[side + '_encoder'].angle += self.devices[side + '_motor'].velocity * ms / 1000
        return 0


class Native:
    def __init__(self):
        self.buffer = encode({'protocol': 'ab3-live-v1', 'number': 1})
        self.frames, self.polls, self.radio_in = 0, 0, []
        self.transport_failures = []
        self.pending = None
        self.nodes = []
        self.stopped = False
    def settimeout(self, timeout): pass
    def close(self): pass
    def recv(self, size):
        chunk = self.buffer[:min(size, 137)]
        self.buffer = self.buffer[len(chunk):]
        return chunk
    def filter_events(self, events):
        return events
    def sendall(self, data):
        size = struct.unpack('!I', data[:4])[0]
        request = json.loads(data[4:])
        assert size == len(data) - 4
        if request.get('stop'):
            self.stopped = True
            return
        self.radio_in.extend(request.get('radio', []))
        self.transport_failures.extend(request.get('transport_failures', []))
        events, radio = [], []
        if request.get('images'):
            assert len(unb64(request['images']['left'])) == 320 * 360 * 3
            assert len(unb64(request['images']['right'])) == 320 * 360 * 3
            assert len(request['accel']) == 3
            self.frames += 1
            self.pending = request['t']
        elif request.get('poll'):
            self.polls += 1
            if self.pending is not None:
                stamp, self.pending = self.pending, None
                node = {'key': self.frames, 't': stamp, 'position': [.05 * self.frames, 0., 0.],
                        'quaternion': [0., 0., 0., 1.]}
                self.nodes.append(node)
                if self.frames >= 8:
                    for value in self.nodes:
                        value['position'][1] = .1
                events += [dict(node, kind='pose3', frame='fake_native_frame', axes='body', metric=True),
                           {'kind': 'graph3', 't': stamp, 'frame': 'fake_native_frame',
                            'axes': 'body', 'nodes': list(self.nodes)},
                           {'kind': 'frame_done', 't': stamp, 'latency_s': .01, 'tracking': 'ok'}]
                if self.frames == 4:
                    radio.append({'destination': 2, 'reliable': False, 'data': b64(b'x' * 14000)})
                    events.append({'kind': 'peer_rpc_failed', 't': stamp, 'peer': 2,
                                   'service': '/robot2/get_current_map', 'reason': 'test_peer_unavailable'})
        self.buffer += encode({'protocol': 'ab3-live-v1', 't': request['t'], 'events': self.filter_events(events), 'radio': radio,
            'resources': {'cpu_pct': 1., 'rss': 10, 'threads': 1, 'cpu_seconds': .01}})


class ControllerBoundary(unittest.TestCase):
    def test_dvm_scan_yields_to_first_native_pose(self):
        class DelayedNative(Native):
            def filter_events(self, events):
                # Native frames finish, but no estimate exists before this time.
                result = []
                for event in events:
                    if event['t'] < 3.2:
                        if event['kind'] in ('pose3', 'graph3'):
                            continue
                        if event['kind'] == 'frame_done':
                            event = dict(event, tracking='initializing')
                    result.append(event)
                return result

        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'benchmark').mkdir()
            profile = json.loads((FB / 'DVM Slam/config/benchmark.json').read_text())
            config = {'output_dir': str(run), 'profile': profile, 'robots': 1, 'ports': [48000],
                      'upstream_commit': 'synthetic-scan-test', 'max_seconds': 6.5,
                      'live_map_wall_seconds': 1e9}
            path = run / 'run_config.json'
            path.write_text(json.dumps(config))
            robot, native = Robot(), DelayedNative()
            robot.end_time = 6.6
            clearance_calls = 0

            def clearance_with_noisy_sides(left, right):
                nonlocal clearance_calls
                clearance_calls += 1
                if robot.time < 4.2:
                    return [], (1., 1., 1.)
                sides = (.1, .3) if clearance_calls % 2 else (.3, .1)
                return [], (None, *sides)
            module = types.ModuleType('controller')
            module.Robot = lambda: robot
            environment = {'AB3_LIVE_CONFIG': str(path), 'STANDARD_ENV': str(FB / 'Standard Environment'),
                           'SLAM_BENCH_RUN_DIR': str(run / 'benchmark'), 'SLAM_BENCH_SCENARIO': ''}
            saved = list(sys.path)
            try:
                with mock.patch.dict(os.environ, environment), mock.patch.dict(sys.modules, {'controller': module}), \
                     mock.patch('socket.create_connection', return_value=native), \
                     mock.patch('stereo_output.StereoMapper.rays', side_effect=clearance_with_noisy_sides):
                    runpy.run_path(str(FB / 'Live Integrations/live_controller.py'), run_name='__main__')
            finally:
                sys.path[:] = saved
            rows = [json.loads(line) for line in (run / 'benchmark/robots/bstem1/bench.jsonl').read_text().splitlines()]
            modes = [row for row in rows if row.get('name') == 'motion_mode']
            self.assertEqual([row['mode'] for row in modes],
                             ['waiting_for_stereo', 'initialization_scan', 'periodic_scan',
                              'reactive_forward', 'reactive_turn'])
            self.assertFalse(modes[1]['initialized'])
            self.assertTrue(modes[2]['initialized'])
            first_pose = next(row['t'] for row in rows if row['type'] == 'pose')
            self.assertGreaterEqual(first_pose, 3.2)
            scanning = [(left, right) for stamp, left, right in robot.drive_history if 2. <= stamp < 3.2]
            self.assertTrue(scanning)
            self.assertTrue(all(left < 0 < right and abs(left + right) < 1e-9 for left, right in scanning))
            moving = [(left, right) for stamp, left, right in robot.drive_history if 4. <= stamp < 4.2]
            self.assertTrue(moving)
            self.assertTrue(all(left > 0 and right > 0 for left, right in moving))
            turning = [(left, right) for stamp, left, right in robot.drive_history if 4.4 <= stamp < 6.5]
            self.assertTrue(turning)
            self.assertTrue(all(left * right < 0 for left, right in turning))
            self.assertTrue(all(left * turning[0][0] > 0 for left, right in turning))
            summary = json.loads((run / 'robot_1/summary.json').read_text())
            self.assertEqual(summary['motion_mode'], 'reactive_turn')
            self.assertEqual(summary['clearance_m'][0], None)
            self.assertEqual(abs(summary['last_command']['angular_rad_s']), .45)

    def test_sensor_native_radio_and_benchmark_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'benchmark').mkdir()
            profile = json.loads((FB / 'DVM Slam/config/benchmark.json').read_text())
            config = {'output_dir': str(run), 'profile': profile, 'robots': 1, 'ports': [48000],
                      'upstream_commit': 'synthetic-interface-test', 'max_seconds': 1.2,
                      'live_map_wall_seconds': 1e9}
            path = run / 'run_config.json'
            path.write_text(json.dumps(config))
            robot, native = Robot(), Native()
            module = types.ModuleType('controller')
            module.Robot = lambda: robot
            environment = {'AB3_LIVE_CONFIG': str(path), 'STANDARD_ENV': str(FB / 'Standard Environment'),
                           'SLAM_BENCH_RUN_DIR': str(run / 'benchmark'), 'SLAM_BENCH_SCENARIO': ''}
            saved = list(sys.path)
            try:
                with mock.patch.dict(os.environ, environment), mock.patch.dict(sys.modules, {'controller': module}), \
                     mock.patch('socket.create_connection', return_value=native), \
                     mock.patch('live_radio.RadioLink', ReportingRadio):
                    runpy.run_path(str(FB / 'Live Integrations/live_controller.py'), run_name='__main__')
            finally:
                sys.path[:] = saved
            rows = [json.loads(line) for line in (run / 'benchmark/robots/bstem1/bench.jsonl').read_text().splitlines()]
            kinds = {row['type'] for row in rows}
            self.assertTrue({'meta', 'init', 'tracking', 'frame', 'pose', 'map', 'send', 'recv', 'resource', 'end'} <= kinds)
            self.assertGreater(native.frames, 8)
            self.assertEqual(native.polls, native.frames)
            self.assertEqual(len(native.radio_in), 1)
            self.assertEqual(unb64(native.radio_in[0]['data']), b'peer-data')
            self.assertEqual(native.transport_failures[0]['metadata']['id'], 'expired-test-request')
            failures = [row for row in rows if row.get('name') == 'peer_transport_failure']
            self.assertEqual(failures[0]['service'], '/robot2/get_current_map')
            poses = [row for row in rows if row['type'] == 'pose']
            self.assertAlmostEqual(poses[-1]['p'][1], .1)
            self.assertTrue(native.stopped)
            self.assertTrue((run / 'robot_1/final_map.png').exists())
            self.assertEqual(json.loads((run / 'robot_1/summary.json').read_text())['reason'], 'time_limit')
            summary = json.loads((run / 'robot_1/summary.json').read_text())
            self.assertEqual(summary['peer_rpc_failures'], 1)
            self.assertEqual(summary['radio_transport_failures'], 1)
            self.assertTrue((run / 'benchmark/STOP').exists())
            self.assertTrue(all(len(packet) <= 1200 for packet in robot.devices['emitter'].sent))


if __name__ == '__main__':
    unittest.main()
