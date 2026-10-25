"""Exercises native/gateway.py with stand-in ROS and LCM modules (no ROS install needed).

Checks the per-step order (clock, IMU, then the previous step's images), the
hold until D2SLAM reports the frame finished, and the LCM <-> radio relay with
echo suppression. It does not show that the real native nodes behave this way.
"""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'bridge')]
import cv2
import numpy as np
from wire import encode_bytes, decode_bytes
from radio_packets import fragments, Reassembler
from lcm_frames import pack, unpack


class Message(object):
    """Attribute bag that creates nested fields on first use, like a genpy message."""
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        if args:
            self.clock = args[0]
        self.orientation_covariance = [0.]*9

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        value = Message()
        setattr(self, name, value)
        return value


class Time(object):
    def __init__(self, secs=0.):
        self.secs = float(secs)

    @staticmethod
    def from_sec(value):
        return Time(value)

    def to_sec(self):
        return self.secs


def fake_modules(log, subscribers):
    rospy = types.ModuleType('rospy')
    rospy.Time = Time
    rospy.init_node = lambda *a, **k: None
    rospy.signal_shutdown = lambda *a: None
    rospy.get_published_topics = lambda: [(t, 'x') for t in (
        '/d2vins/benchmark_state', '/d2vins/odometry', '/d2pgo/swarm_fused', '/d2pgo/pgo_data', '/d2pgo/benchmark_solve')]

    class Publisher(object):
        def __init__(self, topic, kind, **kwargs):
            self.topic = topic

        def publish(self, msg):
            log.append((self.topic, msg))
    rospy.Publisher = Publisher
    rospy.Subscriber = lambda topic, kind, callback, **k: subscribers.__setitem__(topic, callback)

    lcm = types.ModuleType('lcm')

    class LCM(object):
        def __init__(self, url):
            self.url, self.handlers = url, []

        def subscribe(self, channel, handler):
            self.handlers.append(handler)

        def publish(self, channel, data):
            log.append(('lcm:'+channel, data))

        def handle_timeout(self, ms):
            time.sleep(ms/1000.)
    lcm.LCM = LCM
    modules = {'rospy': rospy, 'lcm': lcm}
    for package, names in {'geometry_msgs': ['PoseStamped'], 'nav_msgs': ['Odometry'],
                           'rosgraph_msgs': ['Clock'], 'sensor_msgs': ['Image', 'Imu'], 'std_msgs': ['String'],
                           'swarm_msgs': ['DroneTraj', 'LoopEdge', 'swarm_fused']}.items():
        module = types.ModuleType(package+'.msg')
        for name in names:
            setattr(module, name, Message)
        modules[package] = types.ModuleType(package)
        modules[package+'.msg'] = module
    return modules


def png(value):
    return encode_bytes(cv2.imencode('.png', np.full((360, 320, 3), value, np.uint8))[1].tobytes())


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.log, self.subscribers = [], {}
        patcher = mock.patch.dict(sys.modules, fake_modules(self.log, self.subscribers))
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location('d2_gateway', ROOT/'native/gateway.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        profile = json.loads((ROOT/'config/benchmark.json').read_text())
        profile['frame_wait_wall_seconds'] = 3.
        self.gateway = self.module.Gateway({'profile': profile, 'robots': 2}, 1)
        self.addCleanup(setattr, self.gateway, 'closed', True)

    def native_finishes(self, stamp, keyframe=True, delay=.2):
        def finish():
            time.sleep(delay)
            odometry = Message()
            odometry.header.stamp = Time(stamp)
            odometry.pose.pose.position.x, odometry.pose.pose.position.y, odometry.pose.pose.position.z = 1., 2., 0.
            q = odometry.pose.pose.orientation
            q.x, q.y, q.z, q.w = 0., 0., 0., 1.
            self.subscribers['/d2vins/odometry'](odometry)
            state = {'frontend': stamp, 'forwarded': True, 'backend': stamp, 'keyframe': keyframe, 'frame_id': 4,
                     'accepted': True, 'initialized': True, 'loop_queue': 0, 'loop_busy': 0}
            self.subscribers['/d2vins/benchmark_state'](Message(data=json.dumps(state)))
        thread = threading.Thread(target=finish)
        thread.start()
        return thread

    def test_step_order_and_frame_hold(self):
        self.subscribers['/d2vins/benchmark_state'](Message(data=json.dumps(
            {'frontend': -1, 'forwarded': False, 'backend': -1, 'keyframe': False, 'frame_id': -1, 'accepted': False,
             'initialized': False, 'loop_queue': 0, 'loop_busy': 0})))
        self.gateway.ready()
        del self.log[:]  # the latched t=0 clock from start-up
        worker = self.native_finishes(.096)
        started = time.time()
        reply = self.gateway.step({'t': .128, 'imu': [.002, -.003, .01, 0., 0., 9.81], 'radio': [],
                                   'image_stamp': .096, 'images': [png(10), png(20)]})
        worker.join()
        self.assertGreaterEqual(time.time()-started, .15)  # held until the native frame finished
        topics = [topic for topic, _ in self.log]
        self.assertEqual(topics[:4], ['/clock', '/bench/imu', '/bench/left/image_raw', '/bench/right/image_raw'])
        imu = self.log[1][1]
        self.assertEqual((imu.header.stamp.to_sec(), imu.angular_velocity.x, imu.angular_velocity.y,
                          imu.angular_velocity.z, imu.linear_acceleration.z), (.128, .002, -.003, .01, 9.81))
        left = self.log[2][1]
        self.assertEqual((left.header.stamp.to_sec(), left.encoding, left.height, left.width), (.096, 'mono8', 360, 320))
        kinds = [e['kind'] for e in reply['events']]
        self.assertEqual(kinds, ['odometry', 'frame'])
        self.assertTrue(reply['events'][1]['keyframe'])
        self.assertEqual(reply['events'][0]['pose'], [1., 2., 0.])

    def test_unfinished_frame_stops_with_an_error(self):
        with self.assertRaisesRegex(RuntimeError, 'did not finish the stereo frame'):
            self.gateway.step({'t': .128, 'imu': [0., 0., 0., 9.81], 'radio': [],
                               'image_stamp': .096, 'images': [png(1), png(2)]})

    def test_lcm_relay_through_radio_without_echo(self):
        self.gateway.on_lcm('VIOKF_HEADER', b'local-keyframe')
        reply = self.gateway.step({'t': .032, 'imu': [0., 0., 0., 9.81], 'radio': []})
        packets = [decode_bytes(p) for p in reply['radio']]
        message = Reassembler(2).accept(packets[0], .032)
        self.assertEqual(unpack(message['payload']), ('VIOKF_HEADER', b'local-keyframe'))
        peer = fragments(2, -1, 'lcm', b'q'*16, pack('PGO_Sync_Data', b'from-robot-2'))
        reply = self.gateway.step({'t': .064, 'imu': [0., 0., 0., 9.81], 'radio': [encode_bytes(p) for p in peer]})
        self.assertIn(('lcm:PGO_Sync_Data', b'from-robot-2'), self.log)
        self.gateway.on_lcm('PGO_Sync_Data', b'from-robot-2')  # LCM loops it back to our subscription
        self.assertEqual(self.gateway.step({'t': .096, 'imu': [0., 0., 0., 9.81], 'radio': []})['radio'], [])


if __name__ == '__main__':
    unittest.main()
