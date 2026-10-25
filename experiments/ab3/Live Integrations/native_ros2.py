#!/usr/bin/env python3
"""One isolated ROS 2 runtime endpoint. Peer messages leave only via Webots radio.

ROS interfaces and algorithms are loaded from the native source workspace.
Nothing here estimates a pose or performs a substitute graph optimization.
"""
from collections import deque
import json
import os
from pathlib import Path
import queue
import socket
import threading
import time
import traceback
import uuid
import psutil

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rclpy.serialization import serialize_message, deserialize_message
from rclpy.task import Future
from rosidl_runtime_py.utilities import get_message, get_service
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, CameraInfo, Imu
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String

from live_wire import send, receive, b64, unb64, stamp
from ros_routes import peer_address, service_routes
from native_output_state import NativeCorrection, transform, components
from live_radio import ByteQueue, MAX_MESSAGE


def message_time(message):
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


class Gateway:
    def __init__(self, config, number):
        self.config, self.number = config, number
        self.stack, self.robots = config['profile']['id'], config['robots']
        self.now = 0.
        self.events, self.radio = queue.Queue(8192), ByteQueue()
        self.pending, self.requests = {}, {}
        self.local_requests = {}
        self.lock = threading.RLock()
        self.fatal = None
        # Discovery/readiness is infrastructure and must run before /clock starts.
        # Algorithm nodes themselves always use the published simulation clock.
        self.node = rclpy.create_node('ab3_gateway_%d' % number)
        self.group = ReentrantCallbackGroup()
        self.last_resource_wall = 0.
        self.previous_cpu = {}
        self.cpu_total = 0.
        self.last_odom = None
        self.merged = set()
        self.output_state = NativeCorrection(number) if self.stack == 'swarm_slam' else None
        self.publishers, self.subscriptions, self.clients, self.services = {}, {}, {}, []
        self.clock = self.node.create_publisher(Clock, '/clock', 10)
        self.images = {side: self.node.create_publisher(Image, '/ab3/' + side + '/image', 10)
                       for side in ('left', 'right')}
        self.infos = {side: self.node.create_publisher(CameraInfo, '/ab3/' + side + '/camera_info',
                      QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)) for side in ('left', 'right')}
        self.imu = self.node.create_publisher(Imu, '/ab3/imu', 100)
        self.node.create_subscription(String, '/ab3/events', self.native_event, 1000, callback_group=self.group)
        self.node.create_subscription(PoseStamped, '/ab3/native_pose', self.native_pose, 1000, callback_group=self.group)
        if self.stack == 'swarm_slam':
            from cslam_common_interfaces.msg import KeyframeOdom, OptimizationResult, IntraRobotLoopClosure, InterRobotLoopClosure
            from rtabmap_msgs.msg import OdomInfo
            prefix = '/r%d/cslam/' % (number - 1)
            self.node.create_subscription(PoseStamped, '/r%d/cslam/current_pose_estimate' % (number - 1),
                                          self.native_pose, 1000, callback_group=self.group)
            self.node.create_subscription(Odometry, '/r%d/odom' % (number - 1), self.native_odom,
                QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT), callback_group=self.group)
            self.node.create_subscription(OdomInfo, '/r%d/odom_info' % (number - 1), self.odom_info,
                QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT), callback_group=self.group)
            self.node.create_subscription(KeyframeOdom, prefix + 'keyframe_odom', self.swarm_keyframe, 1000, callback_group=self.group)
            self.node.create_subscription(OptimizationResult, prefix + 'optimized_estimates', self.swarm_optimization, 1000, callback_group=self.group)
            self.node.create_subscription(IntraRobotLoopClosure, prefix + 'intra_robot_loop_closure',
                lambda message: self.swarm_loop(message, False), 1000, callback_group=self.group)
            self.node.create_subscription(InterRobotLoopClosure, '/cslam/inter_robot_loop_closure',
                lambda message: self.swarm_loop(message, True), 1000, callback_group=self.group)
        for route in service_routes(self.stack, number, self.robots):
            kind = get_service(route['type'])
            if route['target'] == number:
                self.clients[route['name']] = self.node.create_client(kind, route['name'], callback_group=self.group)
            else:
                async def callback(request, response, route=route, kind=kind):
                    identity = uuid.uuid4().hex
                    future = Future()
                    with self.lock:
                        if any(entry[3:] == (route['target'], route['name']) for entry in self.pending.values()):
                            self.event({'kind': 'peer_rpc_failed', 't': self.now, 'peer': route['target'],
                                        'service': route['name'], 'reason': 'request_already_pending'})
                            return response
                        self.pending[identity] = (future, kind, self.now, route['target'], route['name'])
                    self.event({'kind': 'peer_rpc_request', 't': self.now, 'id': identity,
                                'peer': route['target'], 'service': route['name']})
                    if not self.outgoing(route['target'], {'kind': 'service_request', 'id': identity,
                        'name': route['name'], 'type': route['type'], 'data': b64(serialize_message(request))}, True):
                        self.fail_rpc(identity, 'radio_queue_unavailable')
                    return await future
                self.services.append(self.node.create_service(kind, route['name'], callback, callback_group=self.group))
        self.node.create_timer(.25, self.discover, callback_group=self.group)

    def event(self, value):
        try:
            self.events.put_nowait(value)
        except queue.Full:
            self.fatal = 'Native event queue overflowed'

    def outgoing(self, destination, value, reliable=False):
        payload = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
        if len(payload) > MAX_MESSAGE and self.stack == 'dvm_slam':
            self.event({'kind': 'peer_transport_drop', 't': self.now, 'peer': destination,
                        'record_kind': value['kind'], 'reason': 'message_too_large'})
            return False
        try:
            self.radio.put_nowait({'destination': destination, 'reliable': reliable,
                                  'data': b64(payload)})
        except queue.Full:
            if self.stack != 'dvm_slam':
                self.fatal = 'Native peer message queue overflowed'
            self.event({'kind': 'peer_transport_drop', 't': self.now, 'peer': destination,
                        'record_kind': value['kind'], 'reason': 'radio_queue_full'})
            return False
        return True

    def fail_rpc(self, identity, reason, source=None):
        """Finish one unavailable exchange without supplying estimated map data."""
        with self.lock:
            pending = self.pending.get(identity)
            if pending is None:
                return
            if source is not None and pending[3] != source:
                raise ValueError('Peer service failure has the wrong sender')
            del self.pending[identity]
        self.event({'kind': 'peer_rpc_failed', 't': self.now, 'id': identity,
                    'peer': pending[3], 'service': pending[4], 'reason': reason,
                    'duration_sim_s': self.now - pending[2]})
        # DVM's build-copy response guards reject these empty responses before
        # map deserialization or scale correction. No merge success is emitted.
        pending[0].set_result(pending[1].Response())

    def service_error(self, destination, identity, reason):
        self.event({'kind': 'peer_rpc_failed', 't': self.now, 'id': identity,
                    'peer': destination, 'reason': reason, 'side': 'provider'})
        self.outgoing(destination, {'kind': 'service_error', 'id': identity, 'reason': reason}, True)

    def native_event(self, message):
        try:
            value = json.loads(message.data)
            if not isinstance(value, dict) or 'kind' not in value or 't' not in value:
                raise ValueError('Invalid native telemetry')
            self.event(value)
        except (ValueError, TypeError) as error:
            self.fatal = str(error)

    def native_pose(self, message):
        p, q = message.pose.position, message.pose.orientation
        if self.output_state is not None:
            with self.lock:
                self.output_state.anchor(message_time(message), transform([p.x, p.y, p.z], [q.x, q.y, q.z, q.w]),
                                         'swarm_' + message.header.frame_id)
                self.emit_swarm_output()
            return
        self.event({'kind': 'pose3', 't': message_time(message), 'frame': message.header.frame_id,
                    'position': [p.x, p.y, p.z], 'quaternion': [q.x, q.y, q.z, q.w],
                    'axes': 'optical' if self.stack == 'dvm_slam' else 'body',
                    'metric': True})

    def native_odom(self, message):
        # Native RTAB-Map odometry acknowledges frame processing. The reported
        # SLAM pose still comes only from cslam/current_pose_estimate above.
        self.last_odom = message_time(message)
        with self.lock:
            valid = message.pose.covariance[0] < 1000
            p, q = message.pose.pose.position, message.pose.pose.orientation
            if valid:
                value = transform([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])
                self.output_state.odom(self.last_odom, value)
                self.emit_swarm_output(graph=False)
            elif self.output_state.latest is not None:
                _, pose, _ = self.output_state.latest
                self.output_state.odom(self.last_odom, pose, valid=False)

    def odom_info(self, message):
        latency = getattr(message, 'time_estimation', None)
        self.event({'kind': 'frame_done', 't': message_time(message),
                    'latency_s': float(latency) if latency is not None else None,
                    'tracking': 'lost' if message.lost else 'ok'})

    def emit_swarm_output(self, graph=True):
        pose = self.output_state.pose_event()
        if pose is not None:
            self.event(pose)
        if graph:
            graph = self.output_state.graph_event(self.now)
            if graph is not None:
                self.event(graph)

    def swarm_keyframe(self, message):
        with self.lock:
            p, q = message.odom.pose.pose.position, message.odom.pose.pose.orientation
            timestamp = message_time(message.odom)
            self.output_state.keyframe(message.id, timestamp, transform([p.x, p.y, p.z], [q.x, q.y, q.z, q.w]))
            self.event({'kind': 'keyframe', 't': timestamp, 'key': message.id})
            self.emit_swarm_output()

    def swarm_optimization(self, message):
        if not message.success:
            return
        with self.lock:
            estimates = {}
            for value in message.estimates:
                if value.key.robot_id != self.number - 1:
                    continue
                p, q = value.pose.position, value.pose.orientation
                estimates[value.key.keyframe_id] = transform([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])
            self.output_state.apply_optimization(estimates, message.origin_robot_id)
            self.emit_swarm_output()

    def swarm_loop(self, message, inter):
        if inter:
            r0, r1 = message.robot0_id + 1, message.robot1_id + 1
            k0, k1 = message.robot0_keyframe_id, message.robot1_keyframe_id
            if self.number not in (r0, r1):
                return
        else:
            r0 = r1 = self.number
            k0, k1 = message.keyframe0_id, message.keyframe1_id
        query_is_one = r1 == self.number
        current, matched = (k1, k0) if query_is_one else (k0, k1)
        peer = r0 if query_is_one else r1
        relative = None
        if message.success:
            p, q = message.transform.translation, message.transform.rotation
            matrix = transform([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])
            if not query_is_one:
                import numpy as np
                matrix = np.linalg.inv(matrix)
            import math
            relative = [float(matrix[0, 3]), float(matrix[1, 3]), math.atan2(matrix[1, 0], matrix[0, 0])]
        self.event({'kind': 'loop', 't': self.now, 'accepted': message.success,
                    'matched_robot': 'bstem%d' % peer, 'current_keyframe': current,
                    'matched_keyframe': matched, 'relative': relative,
                    'reason': 'native Swarm-SLAM geometric verification; timestamps resolved after recording'})

    def peer_callback(self, topic, kind, target):
        # Capture each route in its own closure. Humble's older executor passes
        # only the message; newer executors can also supply publisher metadata.
        def callback(message, info=None):
            try:
                if info is None:
                    if self.stack != 'dvm_slam':
                        raise RuntimeError('This stack requires ROS publisher identity metadata')
                    # DVM unicast subscriptions exclude our own destination,
                    # so incoming radio republications cannot match them.
                    # Its one broadcast channel carries an explicit author ID.
                    if target == 0 and message.sender_agent_id != self.number:
                        return
                else:
                    publisher_gid = info['publisher_gid'] if isinstance(info, dict) else info.publisher_gid
                    endpoints = self.node.get_publishers_info_by_topic(topic)
                    for endpoint in endpoints:
                        if bytes(endpoint.endpoint_gid) == bytes(publisher_gid):
                            if endpoint.node_name.startswith('ab3_gateway_'):
                                return
                            break
                    else:
                        self.fatal = 'Could not identify publisher of native peer message: ' + topic
                        return
                if self.stack == 'dvm_slam' and topic == '/successfully_merged':
                    peer = int(message.receiver_agent_id)
                    if message.sender_agent_id == self.number and message.successfully_merged and peer not in self.merged:
                        self.merged.add(peer)
                        self.event({'kind': 'merge', 't': self.now, 'peer': peer})
                self.outgoing(target, {'kind': 'topic', 'topic': topic, 'type': kind,
                                       'data': b64(serialize_message(message))})
            except Exception as error:
                self.fatal = 'Native topic relay failed: ' + str(error)
        return callback

    def discover(self):
        try:
            ready = all(pub.get_subscription_count() > 0 for pub in self.images.values())
            ready = ready and all(client.service_is_ready() for client in self.clients.values())
            if ready and not Path('/output/native_ready.json').exists():
                Path('/output/native_ready.json').write_text(json.dumps({'protocol': 'ab3-live-v1',
                    'number': self.number, 'input_subscribers_ready': True}))
            for topic, kinds in self.node.get_topic_names_and_types():
                target = peer_address(self.stack, topic, self.robots)
                if target is None or target == self.number or topic in self.subscriptions:
                    continue
                if len(kinds) != 1:
                    raise ValueError('Ambiguous native peer topic type: ' + topic)
                kind = kinds[0]
                cls = get_message(kind)
                qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.RELIABLE)
                self.subscriptions[topic] = self.node.create_subscription(
                    cls, topic, self.peer_callback(topic, kind, target), qos, callback_group=self.group)
        except Exception as error:
            self.fatal = 'Native graph discovery failed: ' + str(error)

    def deliver(self, source, value):
        kind = value['kind']
        if kind == 'topic':
            topic, type_name = value['topic'], value['type']
            destination = peer_address(self.stack, topic, self.robots)
            if destination not in (0, self.number):
                raise ValueError('Peer attempted to publish a non-peer or incorrectly addressed topic')
            cls = get_message(type_name)
            if topic not in self.publishers:
                self.publishers[topic] = self.node.create_publisher(cls, topic, 100)
            self.publishers[topic].publish(deserialize_message(unb64(value['data']), cls))
        elif kind == 'service_request':
            routes = service_routes(self.stack, self.number, self.robots)
            route = next((r for r in routes if r['name'] == value['name'] and r['type'] == value['type']
                          and r['target'] == self.number), None)
            if not route:
                raise ValueError('Unrecognized native peer service')
            cls = get_service(route['type'])
            client = self.clients[route['name']]
            if not client.service_is_ready():
                self.service_error(source, value['id'], 'local_service_not_ready')
                return
            key = (source, value['id'])
            with self.lock:
                if key in self.requests:
                    return  # RadioLink already deduplicates; this is an additional RPC guard.
                if len(self.requests) >= 4096 or len(self.local_requests) >= 64:
                    self.service_error(source, value['id'], 'local_service_capacity')
                    return
                self.requests[key] = self.now
                future = client.call_async(deserialize_message(unb64(value['data']), cls.Request))
                self.local_requests[key] = (future, self.now, route['name'])
            def finished(result):
                with self.lock:
                    if self.local_requests.pop(key, None) is None:
                        return  # Already timed out and removed from the local ROS client.
                try:
                    if not self.outgoing(source, {'kind': 'service_reply', 'id': value['id'],
                                           'data': b64(serialize_message(result.result()))}, True):
                        self.service_error(source, value['id'], 'reply_queue_unavailable')
                except Exception as error:
                    self.service_error(source, value['id'], 'local_service_failed: ' + str(error))
            future.add_done_callback(finished)
        elif kind == 'service_reply':
            with self.lock:
                pending = self.pending.get(value['id'])
                if pending is None:
                    self.event({'kind': 'peer_rpc_late_reply', 't': self.now, 'id': value['id'], 'peer': source})
                    return
                if pending[3] != source:
                    raise ValueError('Unexpected native peer service reply sender')
                del self.pending[value['id']]
            pending[0].set_result(deserialize_message(unb64(value['data']), pending[1].Response))
            self.event({'kind': 'peer_rpc_reply', 't': self.now, 'id': value['id'],
                        'peer': source, 'service': pending[4], 'duration_sim_s': self.now - pending[2]})
        elif kind == 'service_error':
            self.fail_rpc(value['id'], value['reason'], source=source)
        else:
            raise ValueError('Unrecognized native peer record')

    def step(self, request):
        now = float(request['t'])
        if now < self.now:
            raise ValueError('Native clock moved backwards')
        self.now = now
        sec, nanosec = stamp(now)
        clock = Clock()
        clock.clock.sec, clock.clock.nanosec = sec, nanosec
        self.clock.publish(clock)
        for failure in request.get('transport_failures', []):
            metadata = failure.get('metadata', {})
            self.event({'kind': 'peer_transport_failure', 't': now, 'peer': failure['destination'],
                        'reason': failure['reason'], 'record_kind': metadata.get('kind')})
            if metadata.get('kind') == 'service_request':
                self.fail_rpc(metadata['id'], failure['reason'], source=failure['destination'])
            elif metadata.get('kind') == 'service_reply':
                self.service_error(failure['destination'], metadata['id'], failure['reason'])
        for entry in request.get('radio', []):
            source = entry['sender']
            if source == self.number or not 1 <= source <= self.robots:
                raise ValueError('Invalid peer address')
            self.deliver(source, json.loads(unb64(entry['data']).decode('utf-8')))
        if not request.get('poll'):
            imu = Imu()
            imu.header.stamp = clock.clock
            imu.header.frame_id = 'base_link'
            gyro = request['gyro'] if 'gyro' in request else (0., 0., request['gyro_z'])   # 3-axis standard gyro
            imu.angular_velocity.x, imu.angular_velocity.y, imu.angular_velocity.z = gyro
            imu.linear_acceleration.x, imu.linear_acceleration.y, imu.linear_acceleration.z = request['accel']
            imu.orientation_covariance[0] = -1.
            self.imu.publish(imu)
        images = request.get('images')
        if images:
            camera = self.config['contract']['camera']
            for side in ('left', 'right'):
                message = Image()
                message.header.stamp = clock.clock
                message.header.frame_id = side + '_optical'
                message.width, message.height = camera['width'], camera['height']
                message.encoding, message.step = 'bgr8', camera['width'] * 3
                blob = unb64(images[side])
                if len(blob) != message.height * message.step:
                    raise ValueError('Native image size differs from standard calibration')
                message.data = blob
                info = CameraInfo()
                info.header = message.header
                info.width, info.height = message.width, message.height
                # JSON preserves integer zeros; ROS 2 double arrays require
                # Python floats even when the numeric value is unchanged.
                info.distortion_model = 'plumb_bob'
                info.d = [float(value) for value in camera['D']]
                info.k = [float(value) for value in camera['K']]
                info.r = [float(value) for value in camera['R']]
                info.p = [float(value) for value in camera['P_' + side]]
                self.infos[side].publish(info)
                self.images[side].publish(message)
        with self.lock:
            # Radio queues, retries and native timers advance with simulation
            # time. A slow host must not expire an otherwise timely peer RPC.
            for identity, entry in list(self.pending.items()):
                if now - entry[2] > 300:
                    self.fail_rpc(identity, 'reply_timeout_sim')
            for key, (future, started, name) in list(self.local_requests.items()):
                if now - started > 300:
                    del self.local_requests[key]
                    future.cancel()
                    self.service_error(key[0], key[1], 'local_service_timeout_sim')
            self.requests = {k: t for k, t in self.requests.items() if now - t < 600}
        def drain(q):
            result = []
            while True:
                try:
                    result.append(q.get_nowait())
                except queue.Empty:
                    return result
        if self.fatal:
            raise RuntimeError(self.fatal)
        response = {'protocol': 'ab3-live-v1', 't': now, 'events': drain(self.events), 'radio': drain(self.radio)}
        wall = time.monotonic()
        if wall - self.last_resource_wall >= 1.:
            processes = [psutil.Process(1)] + psutil.Process(1).children(recursive=True)
            rss, threads, cpu_delta = 0, 0, 0.
            current = {}
            for process in processes:
                try:
                    with process.oneshot():
                        key = (process.pid, process.create_time())
                        value = sum(process.cpu_times()[:2])
                        cpu_delta += max(0., value - self.previous_cpu.get(key, value))
                        current[key] = value
                        rss += process.memory_info().rss
                        threads += process.num_threads()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            self.cpu_total += cpu_delta
            response['resources'] = {'cpu_pct': 100 * cpu_delta / max(wall - self.last_resource_wall, .001),
                                     'cpu_seconds': self.cpu_total, 'rss': rss, 'threads': threads}
            self.previous_cpu, self.last_resource_wall = current, wall
        return response


def spin_gateway(executor, gateway):
    try:
        executor.spin()
    except Exception as error:
        gateway.fatal = 'ROS executor failed: ' + str(error)
        traceback.print_exc()


def main():
    config = json.loads(Path('/config/native_config.json').read_text())
    number = int(os.environ['AB3_ROBOT_NUMBER'])
    rclpy.init()
    gateway = Gateway(config, number)
    executor = MultiThreadedExecutor(num_threads=8)
    executor.add_node(gateway.node)
    worker = threading.Thread(target=spin_gateway, args=(executor, gateway), daemon=True)
    worker.start()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('0.0.0.0', 48000))
    listener.listen(1)
    Path('/output/bridge_ready.json').write_text(json.dumps({'protocol': 'ab3-live-v1', 'number': number}))
    try:
        connection, _ = listener.accept()
        connection.settimeout(300.)
        with connection:
            send(connection, {'protocol': 'ab3-live-v1', 'number': number})
            while True:
                request = receive(connection)
                if request.get('stop'):
                    break
                try:
                    if not worker.is_alive():
                        raise RuntimeError(gateway.fatal or 'ROS executor stopped unexpectedly')
                    response = gateway.step(request)
                except Exception as error:
                    send(connection, {'error': str(error)})
                    raise
                send(connection, response)
    finally:
        listener.close()
        executor.shutdown()
        gateway.node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
