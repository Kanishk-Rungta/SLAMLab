#!/usr/bin/env python3
"""ROS 1 / LCM endpoint for ONE robot. All peer traffic leaves through the radio.

Replaces only D2SLAM's inter-robot transport (LCM UDP multicast). Inside this
container LCM uses ttl=0, so the native nodes cannot reach another robot by
themselves; every LCM message they publish is returned to this robot's Webots
controller and passes through BstemSensors.send, and what BstemSensors.receive
delivers is republished locally, byte for byte. Never touches D2VINS, the
frontend, loop detection or D2PGO state.
"""
import json
import os
import socket
import sys
import threading
import time
import uuid
import queue

import cv2
import lcm
import numpy as np
import psutil
import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import String
from swarm_msgs.msg import DroneTraj, LoopEdge, swarm_fused

sys.path.insert(0, '/opt/benchmark/bridge')
from wire import send, receive, encode_bytes, decode_bytes
from radio_packets import Reassembler, fragments
from lcm_frames import pack, unpack, EchoFilter
from d2_outputs import frame_done, planar, stamp_key

PROTOCOL = 'd2slam-original-v1'


def pose_of(msg_pose):
    p, q = msg_pose.position, msg_pose.orientation
    return planar((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))


class Gateway(object):
    def __init__(self, config, number):
        self.config, self.number = config, number
        self.profile = config['profile']
        self.now = 0.
        self.closed = False
        self.lock = threading.Condition(threading.RLock())
        self.radio = queue.Queue(maxsize=512)
        self.events = queue.Queue(maxsize=65536)
        self.reassembler = Reassembler(number, self.profile['radio_timeout_sim_seconds'])
        self.echo = EchoFilter()
        self.state = None
        self.odometry = {}
        self.latest_traj = None
        self.latest_fused = None
        self.resource_wall = 0.
        self.resource_processes = {}
        self.resource_cpu = {}
        self.resource_total = 0.
        rospy.init_node('benchmark_gateway', disable_signals=True)
        self.clock = rospy.Publisher('/clock', Clock, queue_size=1, latch=True)
        self.clock.publish(Clock(rospy.Time(0)))
        self.imu = rospy.Publisher('/bench/imu', Imu, queue_size=500)
        self.images = [rospy.Publisher('/bench/%s/image_raw' % side, Image, queue_size=4)
                       for side in ('left', 'right')]
        rospy.Subscriber('/d2vins/benchmark_state', String, self.on_state, queue_size=10)
        rospy.Subscriber('/d2vins/odometry', Odometry, self.on_odometry, queue_size=200)
        rospy.Subscriber('/d2vins/loop', LoopEdge, self.on_loop, queue_size=200)
        rospy.Subscriber('/d2pgo/pose_%d' % number, PoseStamped, self.on_pgo_pose, queue_size=50)
        rospy.Subscriber('/d2pgo/pgo_traj', DroneTraj, self.on_traj, queue_size=50)
        rospy.Subscriber('/d2pgo/swarm_fused', swarm_fused, self.on_fused, queue_size=10)
        rospy.Subscriber('/d2pgo/benchmark_solve', String, self.on_solve, queue_size=100)
        self.lcm = lcm.LCM(self.profile['lcm_url'])
        self.lcm.subscribe('.*', self.on_lcm)
        thread = threading.Thread(target=self.lcm_loop)
        thread.daemon = True
        thread.start()

    # ---- native outputs (ROS callbacks run in rospy threads) ------------------------------
    def emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            raise RuntimeError('Benchmark telemetry queue overflow')

    def on_state(self, msg):
        try:
            state = json.loads(msg.data)
        except ValueError as error:
            self.emit({'kind': 'error', 't': self.now, 'message': 'Invalid native telemetry: %s' % error})
            return
        with self.lock:
            self.state = state
            self.lock.notify_all()

    def on_odometry(self, msg):
        stamp = msg.header.stamp.to_sec()
        pose = pose_of(msg.pose.pose)
        with self.lock:
            self.odometry[stamp_key(stamp)] = pose
            self.lock.notify_all()
        self.emit({'kind': 'odometry', 't': stamp, 'pose': pose})

    def on_loop(self, msg):
        p, q = msg.relative_pose.position, msg.relative_pose.orientation
        self.emit({'kind': 'loop', 'id': int(msg.id), 'ts_a': msg.ts_a.to_sec(), 'ts_b': msg.ts_b.to_sec(),
                   'drone_a': int(msg.drone_id_a), 'drone_b': int(msg.drone_id_b),
                   'relative': [p.x, p.y, p.z, q.x, q.y, q.z, q.w], 'inliers': int(msg.pnp_inlier_num)})

    def on_pgo_pose(self, msg):
        self.emit({'kind': 'pgo_pose', 't': msg.header.stamp.to_sec(), 'pose': pose_of(msg.pose)})

    def on_traj(self, msg):
        if msg.drone_id != self.number:
            return
        with self.lock:
            self.latest_traj = {'kind': 'pgo_traj', 'stamps': [s.to_sec() for s in msg.frame_stamps],
                                'poses': [pose_of(p) for p in msg.poses]}

    def on_fused(self, msg):
        peers = {}
        for i, drone in enumerate(msg.ids):
            if drone != self.number:
                position = msg.local_drone_position[i]
                peers[str(drone)] = [position.x, position.y, msg.local_drone_yaw[i]]
        with self.lock:
            self.latest_fused = {'kind': 'fused', 't': msg.header.stamp.to_sec(), 'peers': peers}

    def on_solve(self, msg):
        try:
            solve = json.loads(msg.data)
        except ValueError:
            return
        self.emit({'kind': 'solve', 't': solve['t'], 'duration': solve['duration'], 'success': solve['success']})

    # ---- LCM <-> standard radio -----------------------------------------------------------
    def lcm_loop(self):
        while not self.closed:
            try:
                self.lcm.handle_timeout(100)
            except Exception as error:  # LCM socket failure ends the run visibly
                if not self.closed:
                    self.emit({'kind': 'error', 't': self.now, 'message': 'LCM transport: %s' % error})
                return

    def on_lcm(self, channel, data):
        if self.echo.is_echo(channel, data):
            return  # a peer's message this gateway republished locally
        packets = fragments(self.number, -1, 'lcm', uuid.uuid4().bytes, pack(channel, data))
        try:
            self.radio.put_nowait(packets)
        except queue.Full:
            self.emit({'kind': 'radio_drop', 't': self.now, 'channel': channel,
                       'reason': 'native logical-message queue full'})

    def on_radio(self, raw):
        try:
            packet = self.reassembler.accept(raw, self.now)
        except ValueError as error:
            self.emit({'kind': 'radio_reject', 't': self.now, 'message': str(error)})
            return
        if packet is None:
            return
        channel, data = unpack(packet['payload'])
        self.echo.remember(channel, data)
        self.lcm.publish(channel, data)

    # ---- per-step sensor input ------------------------------------------------------------
    def ready(self):
        deadline = time.time()+self.profile['native_ready_wall_seconds']
        needed = {'/d2vins/benchmark_state', '/d2vins/odometry', '/d2pgo/swarm_fused', '/d2pgo/pgo_data',
                  '/d2pgo/benchmark_solve'}
        while time.time() < deadline:
            topics = {name for name, _ in rospy.get_published_topics()}
            with self.lock:
                if needed <= topics and self.state is not None:
                    return
            time.sleep(.5)
        raise RuntimeError('Native D2SLAM nodes are not ready; inspect native.log')

    def publish_imu(self, stamp, gyro, accel):
        msg = Imu()
        msg.header.stamp = rospy.Time.from_sec(stamp)
        msg.header.frame_id = 'robot_%d/base_link' % self.number
        msg.orientation_covariance[0] = -1.  # no orientation estimate
        # Standard 3-axis gyro (BstemSensors.imu()); body rates in rad/s.
        msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gyro
        msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = accel
        self.imu.publish(msg)

    def publish_images(self, stamp, encoded):
        for publisher, data in zip(self.images, encoded):
            image = cv2.imdecode(np.frombuffer(decode_bytes(data), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('Invalid lossless stereo image')
            # D2SLAM's stereo input is single channel (its mono path converts the same way).
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            msg = Image()
            msg.header.stamp = rospy.Time.from_sec(stamp)
            msg.header.frame_id = 'robot_%d/camera' % self.number
            msg.height, msg.width = gray.shape
            msg.encoding, msg.step, msg.data = 'mono8', gray.shape[1], gray.tobytes()
            publisher.publish(msg)

    def wait_frame(self, stamp):
        """Hold the simulation until the native pipeline has finished this frame."""
        started = time.time()
        deadline = started+self.profile['frame_wait_wall_seconds']
        with self.lock:
            while not frame_done(self.state, stamp):
                if time.time() >= deadline:
                    raise RuntimeError('D2SLAM did not finish the stereo frame at t=%.3f; inspect native.log' % stamp)
                self.lock.wait(.01)
            state = dict(self.state)
            # D2VINS publishes the frame's odometry before marking it done, but on
            # a different topic; give that message a moment to arrive.
            if state['forwarded'] and state['initialized'] and state['accepted']:
                odom_deadline = time.time()+2.
                while stamp_key(stamp) not in self.odometry and time.time() < odom_deadline:
                    self.lock.wait(.01)
        keyframe = bool(state['forwarded'] and state['keyframe'] and abs(state['backend']-stamp) < 1e-6)
        self.emit({'kind': 'frame', 't': stamp, 'latency_s': time.time()-started, 'keyframe': keyframe,
                   'frame_id': state['frame_id'] if keyframe else None, 'initialized': state['initialized']})

    @staticmethod
    def drain(q):
        values = []
        while True:
            try:
                values.append(q.get_nowait())
            except queue.Empty:
                return values

    def resources(self):
        if time.time()-self.resource_wall < 1:
            return None
        cpu_pct, rss, threads = 0., 0, 0
        for process in psutil.process_iter():
            try:
                proc = self.resource_processes.setdefault(process.pid, process)
                cpu_pct += proc.cpu_percent(None)
                rss += proc.memory_info().rss
                threads += proc.num_threads()
                current = sum(proc.cpu_times()[:2])
                self.resource_total += max(0., current-self.resource_cpu.get(proc.pid, current))
                self.resource_cpu[proc.pid] = current
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.resource_wall = time.time()
        return {'cpu_pct': cpu_pct, 'rss': rss, 'threads': threads, 'cpu_seconds': self.resource_total}

    def step(self, message):
        self.now = float(message['t'])
        self.clock.publish(Clock(rospy.Time.from_sec(self.now)))
        for raw in message.get('radio', []):
            self.on_radio(decode_bytes(raw))
        imu = message['imu']
        if len(imu) == 6:                     # [gx, gy, gz, ax, ay, az]
            gyro, accel = imu[:3], imu[3:]
        elif len(imu) == 4:                   # legacy [gz, ax, ay, az]
            gyro, accel = (0., 0., imu[0]), imu[1:]
        else:
            raise ValueError('IMU sample must have 6 (or legacy 4) values')
        self.publish_imu(self.now, gyro, accel)
        if message.get('images'):
            # Images arrive one control step late, after the IMU sample that
            # follows them: D2VINS waits for IMU data newer than the frame.
            stamp = float(message['image_stamp'])
            self.publish_images(stamp, message['images'])
            self.wait_frame(stamp)
        with self.lock:
            cutoff = stamp_key(self.now-30.)
            self.odometry = {k: v for k, v in self.odometry.items() if k >= cutoff}
            extra = [e for e in (self.latest_traj, self.latest_fused) if e is not None]
            self.latest_traj = self.latest_fused = None
        messages = self.drain(self.radio)
        return {'events': self.drain(self.events)+extra, 'resources': self.resources(),
                'radio_messages': [[encode_bytes(p) for p in message] for message in messages],
                'radio': [encode_bytes(p) for message in messages for p in message]}


def main():
    config = json.load(open('/config/native_config.json'))
    gateway = Gateway(config, int(os.environ['D2_ROBOT_NUMBER']))
    gateway.ready()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('0.0.0.0', 47000))
    listener.listen(1)
    with open('/output/native_ready.json', 'w') as stream:
        json.dump({'ready': True, 'protocol': PROTOCOL}, stream)
    client, _ = listener.accept()
    try:
        hello = receive(client)
        if hello.get('protocol') != PROTOCOL:
            raise ValueError('Different sensor bridge protocol')
        send(client, {'ready': True, 'protocol': PROTOCOL})
        while True:
            message = receive(client)
            if message.get('stop'):
                break
            send(client, gateway.step(message))
    finally:
        gateway.closed = True
        client.close()
        listener.close()
        rospy.signal_shutdown('Webots controller ended')


if __name__ == '__main__':
    main()
