#!/usr/bin/env python
"""ROS 1 / Python 2 endpoint for ONE robot. All peer traffic leaves through radio.

This replaces upstream's ROS communication node and Blabbermouth transport,
never its visual features, NetVLAD, stereo registration, PCM or optimizer.
"""
from __future__ import division, print_function
import io
import json
import os
import socket
import sys
import threading
import time
import uuid
try:
    import Queue as queue
except ImportError:
    import queue
import numpy as np
import cv2
import psutil
import rospy
import rosservice
import tf2_ros
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
from std_srvs.srv import Empty
from rtabmap_ros.msg import OdomInfo
from multi_robot_separators.srv import FindMatches, ReceiveSeparators

sys.path.insert(0, '/opt/benchmark/bridge')
from wire import send, receive, read_exact, encode_bytes, decode_bytes
from radio_packets import Reassembler, fragments
from buzz_transport import compact, expand


class Gateway(object):
    def __init__(self, config, robot_id):
        self.config, self.rid = config, robot_id
        self.peer = (robot_id+1) % config['robots']
        self.now = 0.
        self.closed = False
        self.condition = threading.Condition(threading.RLock())
        self.radio = queue.Queue(maxsize=512)
        self.events = queue.Queue(maxsize=4096)
        self.pending = {}
        self.reply_cache = {}
        self.reply_resend = {}
        self.reassembler = Reassembler(robot_id, config['profile']['rpc_timeout_sim_seconds'])
        self.kf_count = 0
        self.loop_times = {}
        self.frame_received = -1.
        self.last_lost = True
        self.resource_wall = 0.
        self.resource_processes = {}
        self.resource_cpu = {}
        self.resource_total = 0.
        self.visual_poses = {}
        self.last_pose = None
        self.native_state = None
        self.last_trigger = 0.
        self.last_health = -1e9
        self.frontend_failed_reported = False
        self.native = None
        self.native_send_lock = threading.Lock()
        self.namespace = '/robot_%d/' % robot_id
        rospy.init_node('benchmark_gateway')
        self.clock = rospy.Publisher('/clock', Clock, queue_size=1, latch=True)
        self.clock.publish(Clock(rospy.Time(0)))
        self.images = {side: rospy.Publisher(side+'/image_rect', Image, queue_size=2)
                       for side in ('left', 'right', 'rgb')}
        self.infos = {side: rospy.Publisher(side+'/camera_info', CameraInfo, queue_size=1, latch=True)
                      for side in ('left', 'right')}
        self.static_tf = tf2_ros.StaticTransformBroadcaster()
        self.publish_calibration()
        rospy.Subscriber('odom', Odometry, self.on_odom, queue_size=20)
        rospy.Subscriber('odom_info', OdomInfo, self.on_frame, queue_size=20)
        rospy.Subscriber('benchmark_state', String, self.on_state, queue_size=2)
        # Upstream checks the remote service's presence before querying. Each ROS
        # master is isolated; this local discovery proxy only sends RADIO RPCs.
        self.services = [
            rospy.Service('find_matches_query', FindMatches, lambda req: self.rpc('matches', FindMatches, req)),
            rospy.Service('found_separators_query', ReceiveSeparators, lambda req: self.rpc('separators', ReceiveSeparators, req)),
        ]
        if config['robots'] > 1:
            self.services.append(rospy.Service('/robot_%d/find_matches_query' % self.peer,
                                               FindMatches, lambda req: self.rpc('matches', FindMatches, req)))
        thread = threading.Thread(target=self.buzz_reader)
        thread.daemon = True
        thread.start()

    def emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            raise RuntimeError('Benchmark telemetry queue overflow')

    def publish_calibration(self):
        calibration = self.config['calibration']
        transforms = []
        for side in ('left', 'right'):
            info = CameraInfo()
            for key, value in calibration[side].items():
                setattr(info, key, value)
            info.header.frame_id = 'robot_%d/%s_optical' % (self.rid, side)
            self.infos[side].publish(info)
            tr = TransformStamped()
            tr.header.frame_id = 'robot_%d/base_link' % self.rid
            tr.child_frame_id = info.header.frame_id
            matrix = calibration[side+'_T_BS']['data']
            tr.transform.translation.x, tr.transform.translation.y, tr.transform.translation.z = [matrix[i] for i in (3, 7, 11)]
            q = calibration['optical_to_body_quaternion_xyzw']
            tr.transform.rotation.x, tr.transform.rotation.y, tr.transform.rotation.z, tr.transform.rotation.w = q
            transforms.append(tr)
        self.static_tf.sendTransform(transforms)

    @staticmethod
    def planar(pose):
        q = pose.orientation
        yaw = np.arctan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        return [pose.position.x, pose.position.y, float(yaw)]

    def on_odom(self, msg):
        stamp = msg.header.stamp.to_sec()
        with self.condition:
            self.visual_poses[stamp] = self.planar(msg.pose.pose)
            self.last_pose = (stamp, self.visual_poses[stamp])
            # Keep only the small synchronization window. Keyframe poses are
            # forwarded as events and retained by the Webots adapter separately.
            for key in list(self.visual_poses):
                if stamp-key > 5:
                    del self.visual_poses[key]
            self.condition.notifyAll()

    def on_frame(self, msg):
        stamp = msg.header.stamp.to_sec()
        with self.condition:
            keyframe = None
            if msg.keyFrameAdded:
                self.kf_count += 1
                keyframe = self.kf_count  # backend adds node 1 on first odometry keyframe
                self.loop_times[str(self.kf_count-1)] = stamp  # upstream frontend uses zero-based IDs
            self.emit({'kind': 'frame', 't': stamp, 'lost': bool(getattr(msg, 'lost', False)),
                       'latency_s': float(getattr(msg, 'timeEstimation', 0.)), 'keyframe': keyframe})
            self.frame_received = max(self.frame_received, stamp)
            self.last_lost = bool(getattr(msg, 'lost', False))
            self.condition.notifyAll()

    def on_state(self, msg):
        try:
            state = json.loads(msg.data)
        except ValueError as error:
            self.emit({'kind': 'error', 't': self.now, 'message': 'Invalid native pose telemetry: '+str(error)})
            return
        with self.condition:
            self.native_state = state

    def enqueue(self, target, channel, payload, identity=None):
        identity = identity or uuid.uuid4().bytes
        for packet in fragments(self.rid, target, channel, identity, payload):
            try:
                self.radio.put_nowait(packet)
            except queue.Full:
                self.emit({'kind': 'error', 't': self.now, 'message': 'Native radio outbox overflow'})
                break
        return identity

    def buzz_reader(self):
        try:
            deadline = time.time()+300
            while not self.closed:
                try:
                    self.native = socket.create_connection(('127.0.0.1', 24580), 2)
                    self.native.settimeout(None)
                    break
                except socket.error:
                    if time.time() > deadline:
                        raise RuntimeError('Native Buzz socket did not become ready')
                    time.sleep(.2)
            while not self.closed:
                frame = read_exact(self.native, 10000)
                self.enqueue(-1, 'buzz', compact(frame))
        except Exception as error:
            if not self.closed:
                self.emit({'kind': 'error', 't': self.now, 'message': 'Buzz transport: '+str(error)})

    @staticmethod
    def serialize(message):
        stream = io.BytesIO()
        message.serialize(stream)
        return encode_bytes(stream.getvalue())

    def rpc(self, method, service_type, request):
        identity = uuid.uuid4().bytes
        waiter = {'done': False, 'response': None, 'error': None, 'started': self.now}
        with self.condition:
            self.pending[identity] = waiter
            envelope = {'method': method, 'body': self.serialize(request), 'times': dict(self.loop_times)}
            payload = json.dumps(envelope).encode('utf-8')
            self.enqueue(self.peer, 'service_request', payload, identity)
            last_retry = self.now
            while not waiter['done'] and not self.closed:
                if self.now-waiter['started'] >= self.config['profile']['rpc_timeout_sim_seconds']:
                    break
                # ROS services expect reliable delivery. Retries consume the
                # same standard radio budget; they never use a peer socket.
                if self.now-last_retry >= 1.:
                    self.enqueue(self.peer, 'service_request', payload, identity)
                    last_retry = self.now
                self.condition.wait(.1)
            self.pending.pop(identity, None)
            if not waiter['done'] or waiter['error']:
                raise rospy.ServiceException(waiter['error'] or 'Standard radio RPC timed out')
            response = service_type._response_class()
            response.deserialize(decode_bytes(waiter['response']))
            return response

    def serve_rpc(self, packet):
        identity = packet['message_id']
        request = json.loads(packet['payload'].decode('utf-8'))
        try:
            service_type, name = {'matches': (FindMatches, 'find_matches_compute'),
                                  'separators': (ReceiveSeparators, 'receive_separators_py')}[request['method']]
            message = service_type._request_class()
            message.deserialize(decode_bytes(request['body']))
            response = rospy.ServiceProxy(name, service_type)(message)
            value = {'body': self.serialize(response), 'times': dict(self.loop_times)}
        except Exception as error:
            value = {'error': str(error), 'times': dict(self.loop_times)}
        payload = json.dumps(value).encode('utf-8')
        with self.condition:
            self.reply_cache[(packet['sender'], identity)] = (self.now, payload)
        self.enqueue(packet['sender'], 'service_response', payload, identity)

    def on_radio(self, raw):
        from radio_packets import HEADER, MAGIC
        # Repeated RPCs are answered from the cache without applying separators
        # twice. This also recovers a response whose radio fragments were lost.
        if len(raw) >= HEADER.size:
            header = HEADER.unpack(raw[:HEADER.size])
            key = (header[1], header[4])
            if header[0] == MAGIC and header[2] == self.rid and header[3] == 2:
                with self.condition:
                    cached = self.reply_cache.get(key)
                    if cached and self.now-cached[0] <= 2*self.config['profile']['rpc_timeout_sim_seconds']:
                        if self.now-self.reply_resend.get(key, -1e9) >= 1.:
                            self.enqueue(header[1], 'service_response', cached[1], header[4])
                            self.reply_resend[key] = self.now
                        return
        packet = self.reassembler.accept(raw, self.now)
        if packet is None:
            return
        if packet['channel'] == 1:
            if self.native is not None:
                with self.native_send_lock:
                    self.native.sendall(expand(packet['payload'], 10000))
        elif packet['channel'] == 2:
            request = json.loads(packet['payload'].decode('utf-8'))
            self.emit({'kind': 'peer_times', 'robot': packet['sender'], 'times': request.get('times', {})})
            thread = threading.Thread(target=self.serve_rpc, args=(packet,))
            thread.daemon = True
            thread.start()
        elif packet['channel'] == 3:
            response = json.loads(packet['payload'].decode('utf-8'))
            self.emit({'kind': 'peer_times', 'robot': packet['sender'], 'times': response.get('times', {})})
            with self.condition:
                waiter = self.pending.get(packet['message_id'])
                if waiter is not None:
                    waiter.update(done=True, response=response.get('body'), error=response.get('error'))
                    self.condition.notifyAll()

    def ready(self):
        deadline = time.time()+300
        required = ['get_pose_estimates', 'estimate_transformation']
        if self.config['robots'] > 1:
            required.append('find_matches_compute')
        while time.time() < deadline:
            available = set(rosservice.get_service_list())
            if self.native is not None and all(self.namespace+x in available for x in required):
                return
            time.sleep(.2)
        raise RuntimeError('Native nodes are not ready; inspect native.log')

    @staticmethod
    def drain(q):
        values = []
        while True:
            try:
                values.append(q.get_nowait())
            except queue.Empty:
                return values

    def step(self, message):
        self.now = float(message['t'])
        self.clock.publish(Clock(rospy.Time.from_sec(self.now)))
        with self.condition:
            self.condition.notifyAll()
            self.reply_cache = {k: v for k, v in self.reply_cache.items()
                                if self.now-v[0] <= 2*self.config['profile']['rpc_timeout_sim_seconds']}
            self.reply_resend = {k: t for k, t in self.reply_resend.items() if k in self.reply_cache}
        for raw in message.get('radio', []):
            self.on_radio(decode_bytes(raw))
        if message.get('images'):
            for side, data in zip(('left', 'right'), message['images']):
                image = cv2.imdecode(np.frombuffer(decode_bytes(data), np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    raise ValueError('Invalid lossless stereo image')
                msg = Image()
                msg.header.stamp = rospy.Time.from_sec(self.now)
                msg.header.frame_id = 'robot_%d/%s_optical' % (self.rid, side)
                msg.height, msg.width = image.shape[:2]
                msg.encoding, msg.step, msg.data = 'bgr8', image.shape[1]*3, image.tobytes()
                self.images[side].publish(msg)
                if side == 'left':
                    self.images['rgb'].publish(msg)
                info = CameraInfo()
                for key, value in self.config['calibration'][side].items():
                    setattr(info, key, value)
                info.header = msg.header
                self.infos[side].publish(info)
            deadline = time.time()+self.config['profile']['frame_wait_wall_seconds']
            with self.condition:
                while self.frame_received < self.now-1e-6 or (not self.last_lost and
                        (self.last_pose is None or self.last_pose[0] < self.now-1e-6)):
                    if time.time() >= deadline:
                        raise RuntimeError('Stereo odometry did not process the supplied frame')
                    self.condition.wait(.01)
        if self.rid == 0 and self.native_state and self.native_state['keyframes'] > 1:
            if self.now-self.last_trigger >= self.config['profile']['optimizer_trigger_seconds']:
                rospy.ServiceProxy('start_optimization', Empty)()
                self.last_trigger = self.now
        if self.config['robots'] > 1 and self.now-self.last_health >= 5.:
            available = set(rosservice.get_service_list())
            if self.namespace+'find_matches_compute' not in available and not self.frontend_failed_reported:
                self.emit({'kind': 'component_error', 't': self.now,
                           'message': 'Original inter-robot frontend stopped; native stereo odometry/backend continue. Inspect native.log.'})
                self.frontend_failed_reported = True
            self.last_health = self.now
        # Cache ROS messages and states under one lock; no cross-robot access.
        with self.condition:
            events = self.drain(self.events)
            odometry = {str(t): p for t, p in self.visual_poses.items()}
            state = self.native_state
            latest = self.last_pose
        resources = None
        if time.time()-self.resource_wall >= 1:
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
            resources = {'cpu_pct': cpu_pct, 'rss': rss, 'threads': threads,
                         'cpu_seconds': self.resource_total}
            self.resource_wall = time.time()
        return {'events': events, 'state': state, 'odometry': odometry, 'latest': latest, 'resources': resources,
                'radio': [encode_bytes(p) for p in self.drain(self.radio)]}


def main():
    config = json.load(open('/config/native_config.json'))
    gateway = Gateway(config, int(os.environ['DOOR_ROBOT_ID']))
    gateway.ready()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('0.0.0.0', 47000))
    listener.listen(1)
    with open('/output/native_ready.json', 'w') as stream:
        json.dump({'ready': True, 'protocol': 'door-original-v1'}, stream)
    client, _ = listener.accept()
    try:
        hello = receive(client)
        if hello.get('protocol') != 'door-original-v1':
            raise ValueError('Different sensor bridge protocol')
        send(client, {'ready': True, 'protocol': 'door-original-v1'})
        while True:
            message = receive(client)
            if message.get('stop'):
                break
            send(client, gateway.step(message))
    finally:
        gateway.closed = True
        with gateway.condition:
            gateway.condition.notifyAll()
        client.close()
        listener.close()
        rospy.signal_shutdown('Webots controller ended')


if __name__ == '__main__':
    main()
