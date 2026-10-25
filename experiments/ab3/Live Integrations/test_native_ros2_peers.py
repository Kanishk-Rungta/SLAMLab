"""Real ROS 2 subscription/executor regression checks; no SLAM or Webots run."""
import queue
import time
import unittest
from unittest import mock

try:
    import rclpy
except ModuleNotFoundError:
    rclpy = None

if rclpy is not None:
    import native_ros2
    from interfaces.msg import NewKeyFrameBows, SuccessfullyMerged
    from live_wire import b64, unb64
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.serialization import serialize_message, deserialize_message


@unittest.skipIf(rclpy is None, 'Requires the DVM ROS 2 runtime image')
class NativePeers(unittest.TestCase):
    def setUp(self):
        rclpy.init()
        self.addCleanup(rclpy.shutdown)
        self.gateway = gateway = native_ros2.Gateway.__new__(native_ros2.Gateway)
        gateway.stack, gateway.number, gateway.robots = 'dvm_slam', 1, 3
        gateway.images = {'left': mock.Mock(get_subscription_count=lambda: 0)}
        gateway.clients, gateway.subscriptions, gateway.publishers = {}, {}, {}
        gateway.group = ReentrantCallbackGroup()
        gateway.radio, gateway.events = queue.Queue(), queue.Queue()
        gateway.merged, gateway.now, gateway.fatal = set(), 0., None
        gateway.node = rclpy.create_node('ab3_gateway_1')
        self.native = rclpy.create_node('ab3_dvm_test_native')
        self.addCleanup(gateway.node.destroy_node)
        self.addCleanup(self.native.destroy_node)
        self.executor = MultiThreadedExecutor(num_threads=2)
        self.executor.add_node(gateway.node)
        self.executor.add_node(self.native)
        self.addCleanup(self.executor.shutdown)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            self.executor.spin_once(timeout_sec=.05)
        self.fail('Timed out waiting for isolated ROS peer test')

    def discover(self, publishers):
        def ready():
            self.gateway.discover()
            self.assertIsNone(self.gateway.fatal)
            return all(pub.get_subscription_count() for pub in publishers)
        self.wait_for(ready)

    def test_unicast_destinations_and_identical_messages_are_preserved(self):
        topics = ['/robot2/new_key_frame_bows', '/robot3/new_key_frame_bows']
        pubs = [self.native.create_publisher(NewKeyFrameBows, topic, 10) for topic in topics]
        self.discover(pubs)
        message = NewKeyFrameBows(sender_agent_id=1)
        pubs[0].publish(message)
        self.wait_for(lambda: self.gateway.radio.qsize() == 1)
        pubs[0].publish(message)  # Identical data is a legitimate second transmission.
        pubs[1].publish(message)
        self.wait_for(lambda: self.gateway.radio.qsize() == 3)
        rows = [self.gateway.radio.get_nowait() for _ in range(3)]
        self.assertEqual(sorted(row['destination'] for row in rows), [2, 2, 3])
        for row in rows:
            value = native_ros2.json.loads(unb64(row['data']))
            self.assertEqual(value['topic'], '/robot%d/new_key_frame_bows' % row['destination'])
            decoded = deserialize_message(unb64(value['data']), NewKeyFrameBows)
            self.assertEqual(decoded.sender_agent_id, 1)
        self.assertIsNone(self.gateway.fatal)

    def test_broadcast_republication_is_not_echoed_and_merges_are_recorded(self):
        topic = '/successfully_merged'
        native = self.native.create_publisher(SuccessfullyMerged, topic, 10)
        self.discover([native])
        local = SuccessfullyMerged(sender_agent_id=1, receiver_agent_id=2, successfully_merged=True)
        native.publish(local)
        self.wait_for(lambda: self.gateway.radio.qsize() == 1)
        peer = SuccessfullyMerged(sender_agent_id=2, receiver_agent_id=1, successfully_merged=True)
        value = {'kind': 'topic', 'topic': topic, 'type': 'interfaces/msg/SuccessfullyMerged',
                 'data': b64(serialize_message(peer))}
        self.gateway.deliver(2, value)
        # Confirm that the gateway's own republisher matched the subscription.
        self.wait_for(lambda: self.gateway.publishers[topic].get_subscription_count() > 0)
        self.gateway.deliver(2, value)
        native.publish(local)
        self.wait_for(lambda: self.gateway.radio.qsize() >= 2)
        deadline = time.monotonic() + .3
        while time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=.02)
        self.assertEqual(self.gateway.radio.qsize(), 2)
        self.assertEqual(self.gateway.events.qsize(), 1)
        self.assertEqual(self.gateway.events.get_nowait()['peer'], 2)
        self.assertIsNone(self.gateway.fatal)


if __name__ == '__main__':
    unittest.main()
