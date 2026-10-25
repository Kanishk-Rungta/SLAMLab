#!/usr/bin/env python3
"""One isolated ROS 1 runtime endpoint (Kimera-Multi, CCM-SLAM, COVINS-G). Same protocol as native_ros2.py.

Each robot's container has its own ROS master. This gateway:
  * publishes /clock (simulation time), /ab3/left|right/image (+ camera_info) and /ab3/imu from the
    robot's BstemSensors measurements sent by its Webots controller;
  * forwards ONLY the inter-robot topics listed in ros_routes.ros1_routes() to the controller, which
    sends them through BstemSensors (standard radio: range, loss, delay, bandwidth, outages), and
    republishes what the radio delivered from other robots;
  * returns the native adapter's outputs (/ab3/native_pose, /ab3/events) to the controller.
  * optionally tunnels the algorithm's own TCP client/server protocol (COVINS-G) through the radio:
    ordered, reliable byte streams per connection (profile "tcp_tunnel"), see TcpTunnel.
It never estimates a pose, optimises a graph or touches the algorithm's state.
"""
import json
import os
from pathlib import Path
import queue
import socket
import threading
import time

import psutil
import rospy
import roslib.message
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, CameraInfo, Imu
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String, UInt16MultiArray

from live_wire import send, receive, b64, unb64
from ros_routes import ros1_routes
from tcp_tunnel import TcpTunnel

NODE = 'ab3_gateway'
class Gateway:
    def __init__(self, config, number):
        self.config, self.number = config, number
        self.stack, self.robots = config['profile']['id'], config['robots']
        self.now = 0.
        self.events, self.radio = queue.Queue(8192), queue.Queue(4096)
        self.lock = threading.RLock()
        self.fatal = None
        self.last_resource_wall, self.previous_cpu, self.cpu_total = 0., {}, 0.
        rospy.init_node(NODE, disable_signals=True)
        self.clock = rospy.Publisher('/clock', Clock, queue_size=10)
        camera = config['contract']['camera']
        self.camera = camera
        self.images = {side: rospy.Publisher('/ab3/%s/image' % side, Image, queue_size=10) for side in ('left', 'right')}
        self.infos = {side: rospy.Publisher('/ab3/%s/camera_info' % side, CameraInfo, queue_size=10, latch=True)
                      for side in ('left', 'right')}
        self.imu = rospy.Publisher('/ab3/imu', Imu, queue_size=200)
        rospy.Subscriber('/ab3/events', String, self.native_event, queue_size=1000)
        rospy.Subscriber('/ab3/native_pose', PoseStamped, self.native_pose, queue_size=1000)
        self.routes = ros1_routes(self.stack, number, self.robots)
        self.publishers = {}
        for route in self.routes['outgoing']:
            rospy.Subscriber(route['topic'], rospy.AnyMsg, self.relay, callback_args=route, queue_size=200)
        self.incoming = {r['topic']: r for r in self.routes['incoming']}
        # Neighbour monitor (profile "connectivity"): 1 s radio heartbeats; peers heard within the timeout
        # are published as connected (0-based ids), as a deployment's network monitor would.
        self.connectivity = config['profile'].get('connectivity')
        self.heard, self.last_heartbeat = {}, -1e9
        if self.connectivity:
            self.connected_pub = rospy.Publisher(self.connectivity['topic'] % number, UInt16MultiArray, queue_size=5, latch=True)
        tunnel = config['profile'].get('tcp_tunnel')
        self.tunnel = TcpTunnel(self, tunnel['port'], tunnel['server_robot'], tunnel['name']) if tunnel else None

    # ---- native outputs ---------------------------------------------------------------------------
    def event(self, value):
        try:
            self.events.put_nowait(value)
        except queue.Full:
            self.fatal = 'Native event queue overflowed'

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
        profile = self.config['profile']
        self.event({'kind': 'pose3', 't': message.header.stamp.to_sec(), 'frame': message.header.frame_id,
                    'position': [p.x, p.y, p.z], 'quaternion': [q.x, q.y, q.z, q.w],
                    'axes': profile.get('pose_axes', 'optical'), 'metric': profile.get('metric', True)})

    # ---- inter-robot topics -------------------------------------------------------------------------
    def relay(self, message, route):
        header = getattr(message, '_connection_header', {}) or {}
        if header.get('callerid') == '/' + NODE:
            return                        # our own republication of a peer message
        try:
            self.radio.put_nowait({'destination': route['destination'], 'reliable': route.get('reliable', False),
                                   'data': b64(json.dumps({'kind': 'topic', 'topic': route['topic'],
                                                           'type': header.get('type'),
                                                           'data': b64(message._buff)},
                                                          separators=(',', ':')).encode())})
        except queue.Full:
            self.fatal = 'Native peer message queue overflowed'

    def outgoing(self, destination, value, reliable=False):
        try:
            self.radio.put_nowait({'destination': destination, 'reliable': reliable,
                                   'data': b64(json.dumps(value, separators=(',', ':')).encode())})
        except queue.Full:
            self.fatal = 'Native peer message queue overflowed'

    def deliver(self, source, value):
        if value.get('kind') == 'heartbeat':
            self.heard[source] = self.now
            return
        if value.get('kind') in ('tcp', 'tcp_close') and self.tunnel is not None:
            if self.number != self.tunnel.server and source != self.tunnel.server:
                raise ValueError('Tunnel data from a robot other than the server robot')
            self.tunnel.deliver(source, value)
            return
        if value.get('kind') != 'topic':
            raise ValueError('Unrecognized native peer record')
        route = self.incoming.get(value['topic'])
        if route is None or source not in route['sources']:
            raise ValueError('Peer published a topic this robot does not accept: %s' % value['topic'])
        cls = roslib.message.get_message_class(value['type'])
        if cls is None:
            raise ValueError('Unknown native message type ' + str(value['type']))
        message = cls()
        message.deserialize(unb64(value['data']))
        if value['topic'] not in self.publishers:
            self.publishers[value['topic']] = rospy.Publisher(value['topic'], cls, queue_size=200)
            time.sleep(.05)           # let local subscribers connect to the new publisher
        self.publishers[value['topic']].publish(message)

    # ---- one control step ---------------------------------------------------------------------------
    def step(self, request):
        now = float(request['t'])
        if now < self.now:
            raise ValueError('Native clock moved backwards')
        self.now = now
        stamp = rospy.Time.from_sec(now)
        self.clock.publish(Clock(stamp))
        for entry in request.get('radio', []):
            source = entry['sender']
            if source == self.number or not 1 <= source <= self.robots:
                raise ValueError('Invalid peer address')
            self.deliver(source, json.loads(unb64(entry['data']).decode('utf-8')))
        if self.connectivity and now - self.last_heartbeat >= self.connectivity.get('period_s', 1.):
            self.last_heartbeat = now
            self.outgoing(0, {'kind': 'heartbeat'})
            timeout = self.connectivity.get('timeout_s', 5.)
            self.connected_pub.publish(UInt16MultiArray(data=sorted(s - 1 for s, t in self.heard.items() if now - t <= timeout)))
        if not request.get('poll'):
            imu = Imu()
            imu.header.stamp, imu.header.frame_id = stamp, 'base_link'
            imu.orientation_covariance[0] = -1.
            gyro = request['gyro'] if 'gyro' in request else (0., 0., request['gyro_z'])
            imu.angular_velocity.x, imu.angular_velocity.y, imu.angular_velocity.z = gyro
            imu.linear_acceleration.x, imu.linear_acceleration.y, imu.linear_acceleration.z = request['accel']
            self.imu.publish(imu)
        images = request.get('images')
        if images and self.images['left'].get_num_connections() == 0:
            # The algorithm is not subscribed yet (e.g. a COVINS-G agent still waiting for its server
            # id): the frame is dropped and acknowledged, so the controller does not wait for it.
            self.event({'kind': 'frame_done', 't': now, 'tracking': 'initializing', 'dropped': True})
            images = None
        if images:
            camera = self.camera
            for side in ('left', 'right'):
                message = Image()
                message.header.stamp, message.header.frame_id = stamp, side + '_optical'
                message.width, message.height = camera['width'], camera['height']
                message.encoding, message.step = 'bgr8', camera['width'] * 3
                blob = unb64(images[side])
                if len(blob) != message.height * message.step:
                    raise ValueError('Native image size differs from standard calibration')
                message.data = blob
                info = CameraInfo()
                info.header = message.header
                info.width, info.height = message.width, message.height
                info.distortion_model, info.D = 'plumb_bob', list(camera['D']) + [0.] * (5 - len(camera['D']))
                info.K, info.R, info.P = camera['K'], camera['R'], camera['P_' + side]
                self.infos[side].publish(info)
                self.images[side].publish(message)

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
            rss, threads, cpu_delta, current = 0, 0, 0., {}
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

    def ready(self):
        """Native input subscribers are connected (the algorithm can receive the first frame)."""
        if self.tunnel is not None and self.number != self.tunnel.server:
            # Remote clients finish starting only once the radio (the simulation) carries them to the server.
            return self.tunnel.listening
        needed = self.config['profile'].get('ready_inputs', ['left'])
        return all(self.images[side].get_num_connections() > 0 for side in needed if side in self.images) and \
            ('imu' not in needed or self.imu.get_num_connections() > 0)


def main():
    config = json.loads(Path('/config/native_config.json').read_text())
    number = int(os.environ['AB3_ROBOT_NUMBER'])
    gateway = Gateway(config, number)

    def watch_ready():
        while not rospy.is_shutdown():
            if gateway.ready():
                Path('/output/native_ready.json').write_text(json.dumps({'protocol': 'ab3-live-v1',
                    'number': number, 'input_subscribers_ready': True}))
                return
            time.sleep(.25)
    threading.Thread(target=watch_ready, daemon=True).start()
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
                    response = gateway.step(request)
                except Exception as error:
                    send(connection, {'error': str(error)})
                    raise
                send(connection, response)
    finally:
        listener.close()
        rospy.signal_shutdown('benchmark finished')


if __name__ == '__main__':
    main()
