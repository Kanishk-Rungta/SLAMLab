"""Exercise sensor publication with real ROS 2 messages, without starting SLAM.

Run inside a ROS 2 image with its setup.bash sourced. No ROS node or Webots
process is started; publishers are mocked and messages are really serialized.
"""
import json
import queue
import threading
import unittest
from unittest import mock

try:
    import rclpy
except ModuleNotFoundError:
    rclpy = None

if rclpy is not None:
    import native_ros2
    from rclpy.serialization import serialize_message, deserialize_message
    from sensor_msgs.msg import CameraInfo, Image, Imu


@unittest.skipIf(rclpy is None, 'Requires the ROS 2 runtime image')
class NativeSensors(unittest.TestCase):
    def test_mixed_json_numbers_publish_both_stereo_calibrations(self):
        # Integer zeros survive JSON in all four calibration arrays. This
        # reproduces the shared standard contract's numeric types.
        camera = json.loads(json.dumps({
            'width': 2, 'height': 1,
            'D': [0, 0, 0, 0],
            'K': [277.1273, 0, 160.0, 0, 277.1273, 180.0, 0, 0, 1],
            'R': [1, 0, 0, 0, 1, 0, 0, 0, 1],
            'P_left': [277.1273, 0, 160.0, 0, 0, 277.1273, 180.0, 0, 0, 0, 1, 0],
            'P_right': [277.1273, 0, 160.0, -6.9281825, 0, 277.1273, 180.0, 0, 0, 0, 1, 0],
        }))
        gateway = native_ros2.Gateway.__new__(native_ros2.Gateway)
        gateway.config = {'contract': {'camera': camera}}
        gateway.now = 0.
        gateway.number, gateway.robots = 1, 2
        gateway.clock, gateway.imu = mock.Mock(), mock.Mock()
        gateway.images = {side: mock.Mock() for side in ('left', 'right')}
        gateway.infos = {side: mock.Mock() for side in ('left', 'right')}
        gateway.lock = threading.RLock()
        gateway.pending, gateway.requests = {}, {}
        gateway.local_requests = {}
        gateway.events, gateway.radio = queue.Queue(), queue.Queue()
        gateway.fatal = None
        gateway.last_resource_wall = 100.
        pixels = bytes([0, 1, 2, 3, 4, 5])
        request = {'t': .096, 'gyro': [0., 0., .1], 'accel': [0., 0., 9.81],
                   'images': {side: native_ros2.b64(pixels) for side in ('left', 'right')}}
        with mock.patch.object(native_ros2.time, 'monotonic', return_value=100.):
            response = gateway.step(request)
        self.assertEqual(response['t'], .096)
        self.assertNotIn('error', response)
        for side in ('left', 'right'):
            info = gateway.infos[side].publish.call_args.args[0]
            decoded = deserialize_message(serialize_message(info), CameraInfo)
            self.assertEqual(list(decoded.d), camera['D'])
            self.assertEqual(list(decoded.k), camera['K'])
            self.assertEqual(list(decoded.r), camera['R'])
            self.assertEqual(list(decoded.p), camera['P_' + side])
            self.assertEqual(decoded.header.frame_id, side + '_optical')
            self.assertEqual(decoded.header.stamp.nanosec, 96000000)
            image = gateway.images[side].publish.call_args.args[0]
            image = deserialize_message(serialize_message(image), Image)
            self.assertEqual(bytes(image.data), pixels)
            self.assertEqual(image.encoding, 'bgr8')
            self.assertEqual(image.step, 6)
        imu = gateway.imu.publish.call_args.args[0]
        imu = deserialize_message(serialize_message(imu), Imu)
        self.assertAlmostEqual(imu.angular_velocity.z, .1)
        self.assertAlmostEqual(imu.linear_acceleration.z, 9.81)


if __name__ == '__main__':
    unittest.main()
