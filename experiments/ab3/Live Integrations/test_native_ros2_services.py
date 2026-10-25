"""Real ROS service bridge checks without native SLAM or Webots."""
import json
import time
import unittest
from unittest import mock

try:
    import rclpy
except ModuleNotFoundError:
    rclpy = None

if rclpy is not None:
    import native_ros2
    from interfaces.srv import GetCurrentMap, GetMapPoints
    from live_wire import b64, unb64
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.serialization import serialize_message, deserialize_message


@unittest.skipIf(rclpy is None, 'Requires the DVM ROS 2 runtime image')
class NativeServices(unittest.TestCase):
    def setUp(self):
        rclpy.init()
        self.addCleanup(rclpy.shutdown)
        self.gateway = native_ros2.Gateway({'profile': {'id': 'dvm_slam'}, 'robots': 2}, 1)
        self.native = rclpy.create_node('ab3_dvm_service_test')
        self.addCleanup(self.gateway.node.destroy_node)
        self.addCleanup(self.native.destroy_node)
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.gateway.node)
        self.executor.add_node(self.native)
        self.addCleanup(lambda: self.executor.shutdown(timeout_sec=1.))
        self.addCleanup(self.finish_pending)

    def finish_pending(self):
        for future, kind, *_ in self.gateway.pending.values():
            if not future.done():
                future.set_result(kind.Response())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            self.executor.spin_once(timeout_sec=.05)
        self.fail('Timed out waiting for ROS service bridge; pending=%s radio=%d fatal=%s' % (
            list(self.gateway.pending), self.gateway.radio.qsize(), self.gateway.fatal))

    def request_remote_map(self):
        client = self.native.create_client(GetCurrentMap, '/robot2/get_current_map')
        self.wait_for(client.service_is_ready)
        future = client.call_async(GetCurrentMap.Request(sender_agent_id=1))
        self.wait_for(lambda: not self.gateway.radio.empty())
        record = self.gateway.radio.get_nowait()
        self.assertTrue(record['reliable'])
        self.assertEqual(record['destination'], 2)
        request = json.loads(unb64(record['data']))
        self.assertEqual(request['kind'], 'service_request')
        self.assertEqual(request['name'], '/robot2/get_current_map')
        decoded = deserialize_message(unb64(request['data']), GetCurrentMap.Request)
        self.assertEqual(decoded.sender_agent_id, 1)
        return future, request

    def test_outbound_request_and_radio_reply_complete_native_service(self):
        future, request = self.request_remote_map()
        response = GetCurrentMap.Response(sender_agent_id=2,
                                         serialized_map=[bytes([v]) for v in b'native-map-test'])
        self.gateway.deliver(2, {'kind': 'service_reply', 'id': request['id'],
                                 'data': b64(serialize_message(response))})
        self.wait_for(future.done)
        self.assertEqual(b''.join(future.result().serialized_map), b'native-map-test')
        self.assertFalse(self.gateway.pending)
        self.assertIsNone(self.gateway.fatal)

    def test_inbound_request_calls_local_service_and_replies_once(self):
        calls = []
        def local_map(request, response):
            calls.append(request.sender_agent_id)
            response.sender_agent_id = 1
            response.serialized_map = [bytes([v]) for v in b'local-map-test']
            return response
        self.native.create_service(GetCurrentMap, '/robot1/get_current_map', local_map)
        self.wait_for(self.gateway.clients['/robot1/get_current_map'].service_is_ready)
        request = GetCurrentMap.Request(sender_agent_id=2)
        record = {'kind': 'service_request', 'id': 'test-inbound',
                  'name': '/robot1/get_current_map', 'type': 'interfaces/srv/GetCurrentMap',
                  'data': b64(serialize_message(request))}
        self.gateway.deliver(2, record)
        self.gateway.deliver(2, record)  # A duplicate must not execute native work twice.
        self.wait_for(lambda: not self.gateway.radio.empty())
        outgoing = self.gateway.radio.get_nowait()
        self.assertTrue(outgoing['reliable'])
        self.assertEqual(outgoing['destination'], 2)
        reply = json.loads(unb64(outgoing['data']))
        self.assertEqual(reply['kind'], 'service_reply')
        self.assertEqual(reply['id'], 'test-inbound')
        response = deserialize_message(unb64(reply['data']), GetCurrentMap.Response)
        self.assertEqual(b''.join(response.serialized_map), b'local-map-test')
        self.assertEqual(calls, [2])
        self.assertIsNone(self.gateway.fatal)

    def test_slow_wall_clock_does_not_expire_simulated_radio_request(self):
        future, request = self.request_remote_map()
        # Advance only real time. Radio transport and algorithm timers have
        # advanced by one simulated second, well within their retry budget.
        old_wall = time.monotonic()
        self.gateway.last_resource_wall = old_wall + 301.
        with mock.patch.object(native_ros2.time, 'monotonic', return_value=old_wall + 301.):
            response = self.gateway.step({'t': 1., 'poll': True})
        self.assertNotIn('error', response)
        self.assertIn(request['id'], self.gateway.pending)
        reply = GetCurrentMap.Response(sender_agent_id=2,
                                      serialized_map=[bytes([v]) for v in b'late-wall-time-map'])
        self.gateway.deliver(2, {'kind': 'service_reply', 'id': request['id'],
                                 'data': b64(serialize_message(reply))})
        self.wait_for(future.done)
        self.assertEqual(b''.join(future.result().serialized_map), b'late-wall-time-map')

    def test_unanswered_request_still_expires_on_simulation_clock(self):
        future, request = self.request_remote_map()
        self.gateway.last_resource_wall = time.monotonic()
        self.gateway.step({'t': 301., 'poll': True})
        self.wait_for(future.done)
        self.assertFalse(future.result().serialized_map)
        self.assertNotIn(request['id'], self.gateway.pending)
        self.assertIsNone(self.gateway.fatal)
        late = GetCurrentMap.Response(sender_agent_id=2, serialized_map=[b'x'])
        self.gateway.deliver(2, {'kind': 'service_reply', 'id': request['id'],
                                 'data': b64(serialize_message(late))})
        self.assertIsNone(self.gateway.fatal)
        self.assertFalse(future.result().serialized_map)

    def test_request_duplicate_history_uses_simulation_clock(self):
        self.gateway.requests[(2, 'already-handled')] = 0.
        old_wall = time.monotonic()
        self.gateway.last_resource_wall = old_wall + 1000.
        with mock.patch.object(native_ros2.time, 'monotonic', return_value=old_wall + 1000.):
            self.gateway.step({'t': 1., 'poll': True})
        self.assertIn((2, 'already-handled'), self.gateway.requests)

    def test_busy_route_is_bounded_and_a_later_request_can_succeed(self):
        first, request = self.request_remote_map()
        client = self.native.create_client(GetCurrentMap, '/robot2/get_current_map')
        second = client.call_async(GetCurrentMap.Request(sender_agent_id=1))
        self.wait_for(second.done)
        self.assertFalse(second.result().serialized_map)
        self.assertEqual(len(self.gateway.pending), 1)
        self.assertTrue(self.gateway.radio.empty())
        self.gateway.fail_rpc(request['id'], 'test_peer_outage')
        self.wait_for(first.done)
        third, retry = self.request_remote_map()
        reply = GetCurrentMap.Response(sender_agent_id=2, serialized_map=[b'x'])
        self.gateway.deliver(2, {'kind': 'service_reply', 'id': retry['id'],
                                 'data': b64(serialize_message(reply))})
        self.wait_for(third.done)
        self.assertEqual(b''.join(third.result().serialized_map), b'x')
        self.assertFalse(self.gateway.pending)
        self.assertIsNone(self.gateway.fatal)

    def test_transport_timeout_is_reported_without_stopping_local_gateway(self):
        future, request = self.request_remote_map()
        self.gateway.last_resource_wall = time.monotonic()
        self.gateway.step({'t': 1., 'poll': True, 'transport_failures': [{
            'destination': 2, 'metadata': {'kind': 'service_request', 'id': request['id']},
            'reason': 'delivery_timeout'}]})
        self.wait_for(future.done)
        self.assertFalse(future.result().serialized_map)
        self.assertIsNone(self.gateway.fatal)

    def test_unready_local_service_returns_explicit_peer_failure(self):
        request = GetCurrentMap.Request(sender_agent_id=2)
        self.gateway.deliver(2, {'kind': 'service_request', 'id': 'unready-service',
            'name': '/robot1/get_current_map', 'type': 'interfaces/srv/GetCurrentMap',
            'data': b64(serialize_message(request))})
        record = self.gateway.radio.get_nowait()
        failure = json.loads(unb64(record['data']))
        self.assertEqual(failure['kind'], 'service_error')
        self.assertEqual(failure['reason'], 'local_service_not_ready')
        self.assertTrue(record['reliable'])
        self.assertIsNone(self.gateway.fatal)

    def test_full_byte_queue_completes_request_without_a_map(self):
        from live_radio import ByteQueue
        self.gateway.radio = ByteQueue(maxsize=1, max_bytes=1024)
        self.gateway.radio.put_nowait({'data': 'occupied'})
        client = self.native.create_client(GetCurrentMap, '/robot2/get_current_map')
        self.wait_for(client.service_is_ready)
        future = client.call_async(GetCurrentMap.Request(sender_agent_id=1))
        self.wait_for(future.done)
        self.assertFalse(future.result().serialized_map)
        self.assertFalse(self.gateway.pending)
        self.assertLessEqual(self.gateway.radio.bytes_queued, 1024)
        self.assertIsNone(self.gateway.fatal)

    def test_executor_exception_is_exposed_as_gateway_failure(self):
        executor = mock.Mock()
        executor.spin.side_effect = RuntimeError('test executor failure')
        with mock.patch.object(native_ros2.traceback, 'print_exc'):
            native_ros2.spin_gateway(executor, self.gateway)
        self.assertIn('test executor failure', self.gateway.fatal)

    def test_unavailable_map_points_returns_no_measurements(self):
        client = self.native.create_client(GetMapPoints, '/robot2/get_map_points')
        self.wait_for(client.service_is_ready)
        future = client.call_async(GetMapPoints.Request())
        self.wait_for(lambda: not self.gateway.radio.empty())
        request = json.loads(unb64(self.gateway.radio.get_nowait()['data']))
        self.gateway.deliver(2, {'kind': 'service_error', 'id': request['id'], 'reason': 'test_outage'})
        self.wait_for(future.done)
        self.assertFalse(future.result().map_points)
        self.assertIsNone(self.gateway.fatal)

    def test_stalled_local_ros_call_is_cancelled_and_reported(self):
        from rclpy.task import Future
        stalled = Future()
        client = self.gateway.clients['/robot1/get_current_map']
        request = GetCurrentMap.Request(sender_agent_id=2)
        record = {'kind': 'service_request', 'id': 'stalled-local',
                  'name': '/robot1/get_current_map', 'type': 'interfaces/srv/GetCurrentMap',
                  'data': b64(serialize_message(request))}
        with mock.patch.object(client, 'service_is_ready', return_value=True), \
             mock.patch.object(client, 'call_async', return_value=stalled):
            self.gateway.deliver(2, record)
        self.gateway.last_resource_wall = time.monotonic()
        response = self.gateway.step({'t': 301., 'poll': True})
        self.assertTrue(stalled.cancelled())
        self.assertFalse(self.gateway.local_requests)
        self.assertIsNone(self.gateway.fatal)
        self.assertTrue(any(event.get('reason') == 'local_service_timeout_sim' for event in response['events']))


if __name__ == '__main__':
    unittest.main()
