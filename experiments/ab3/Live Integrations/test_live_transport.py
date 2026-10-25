"""Tests use deterministic simulated packets; no ROS or real network is needed."""
import json
import random
import queue
import unittest
from unittest import mock

from live_radio import RadioLink, ByteQueue, fragments, HEADER, MAX_MESSAGE, packet_sender
from live_wire import encode, receive, b64, unb64, stamp


class BytesConnection:
    def __init__(self, value):
        self.data = value

    def recv(self, size):
        chunk = self.data[:min(size, 3)]
        self.data = self.data[len(chunk):]
        return chunk


class Wire(unittest.TestCase):
    def test_partial_reads_binary_and_sim_stamp(self):
        data = {'t': 1.9999999998, 'payload': b64(bytes(range(256)))}
        self.assertEqual(receive(BytesConnection(encode(data))), data)
        self.assertEqual(unb64(data['payload']), bytes(range(256)))
        self.assertEqual(stamp(data['t']), (2, 0))

    def test_eof_and_nonfinite_values(self):
        with self.assertRaises(EOFError):
            receive(BytesConnection(b'\0'))
        with self.assertRaises(ValueError):
            encode({'t': float('nan')})
        with self.assertRaises(ValueError):
            stamp(-1)


class Radio(unittest.TestCase):
    def test_reordering_duplicates_and_wrong_recipient(self):
        data = bytes(range(256)) * 100
        packets = fragments(1, 2, b'a' * 16, data)
        random.Random(12).shuffle(packets)
        link = RadioLink(2)
        delivered = [value for p in packets + packets for value in [link.accept(p, 0.)] if value]
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0]['payload'], data)
        self.assertEqual(delivered[0]['sender'], 1)
        self.assertIsNone(RadioLink(3).accept(packets[0], 0.))

    def test_pacing_includes_envelope_and_respects_rate(self):
        link = RadioLink(1, 50000)
        link.enqueue(2, b'x' * 30000, 0.)
        all_packets = []
        for i in range(100):
            now = i * .032
            all_packets.extend(link.drain(lambda p: True, now))
            self.assertLessEqual(sum(map(len, all_packets)), 50000 * now + 1e-6)
        self.assertEqual(sum(len(p) - HEADER.size for p in all_packets), 30000)

    def test_rejected_sensor_send_does_not_lose_packet_or_credit(self):
        link = RadioLink(1)
        link.enqueue(2, b'payload', 0.)
        self.assertEqual(link.drain(lambda p: False, 1.), [])
        # First clock tick starts at zero credit; advance once more.
        self.assertEqual(link.drain(lambda p: False, 2.), [])
        credit = link.credit
        packets = link.drain(lambda p: True, 2.)
        self.assertEqual(len(packets), 1)
        self.assertEqual(link.credit, credit - len(packets[0]))

    def test_reliable_delivery_recovers_data_and_ack_loss(self):
        a, b = RadioLink(1), RadioLink(2)
        payload = b'data over the standard simulated radio' * 1000
        identity = a.enqueue(2, payload, 0., reliable=True)
        rng = random.Random(34)
        received = []
        for i in range(1500):
            now = i * .032
            for packet in a.drain(lambda p: True, now):
                if rng.random() > .12:
                    message = b.accept(packet, now)
                    if message:
                        received.append(message)
            for packet in b.drain(lambda p: True, now):
                if rng.random() > .4:
                    a.accept(packet, now)
            if identity not in a.reliable:
                break
        self.assertEqual([x['payload'] for x in received], [payload])
        self.assertNotIn(identity, a.reliable)

    def test_outage_expires_reliable_request(self):
        link = RadioLink(1, timeout_seconds=3.)
        link.enqueue(2, b'unreachable service', 0., reliable=True)
        link.drain(lambda p: True, 0.)
        with self.assertRaises(TimeoutError):
            link.advance(4.)

    def test_recoverable_outage_clears_buffers_and_next_exchange_succeeds(self):
        a, b = RadioLink(1, timeout_seconds=3., recoverable=True), RadioLink(2, recoverable=True)
        identity = a.enqueue(2, b'unreachable', 0., reliable=True,
                             metadata={'kind': 'service_request', 'id': 'failed-rpc'})
        a.advance(4.)
        self.assertNotIn(identity, a.reliable)
        self.assertEqual(a.outbox_bytes, 0)
        self.assertEqual(a.take_failures()[0]['metadata']['id'], 'failed-rpc')
        next_id = a.enqueue(2, b'peer is back', 4., reliable=True)
        received = []
        for i in range(100):
            now = 4. + i * .032
            for packet in a.drain(lambda p: True, now):
                value = b.accept(packet, now)
                if value:
                    received.append(value['payload'])
            for packet in b.drain(lambda p: True, now):
                a.accept(packet, now)
            if next_id not in a.reliable:
                break
        self.assertEqual(received, [b'peer is back'])
        self.assertFalse(a.reliable)

    def test_recoverable_outbox_overload_is_bounded_and_reported(self):
        link = RadioLink(1, recoverable=True)
        with mock.patch('live_radio.MAX_PENDING_BYTES', 200):
            first = link.enqueue(2, b'x' * 50, 0., reliable=True)
            rejected = link.enqueue(2, b'y' * 100, 0., reliable=True, metadata={'id': 'full'})
            self.assertIsNotNone(first)
            self.assertIsNone(rejected)
            self.assertLessEqual(link.outbox_bytes, 200)
            self.assertEqual(len(link.reliable), 1)
        self.assertEqual(link.take_failures()[0]['reason'], 'outbox_byte_limit')

    def test_ack_overload_retries_without_duplicate_delivery(self):
        a, b = RadioLink(1, recoverable=True), RadioLink(2, recoverable=True)
        identity = a.enqueue(2, b'data', 0., reliable=True)
        with mock.patch('live_radio.MAX_PENDING_BYTES', 200):
            b.enqueue(3, b'x' * 150, 0.)
            delivered = b.accept(a.reliable[identity]['packets'][0], 0.)
            self.assertEqual(delivered['payload'], b'data')
            self.assertEqual(b.take_failures()[0]['reason'], 'ack_queue_full')
            b.drain(lambda p: True, 1.)
            self.assertIsNone(b.accept(a.reliable[identity]['packets'][0], 2.))
            for packet in b.drain(lambda p: True, 2.):
                a.accept(packet, 2.)
        self.assertNotIn(identity, a.reliable)

    def test_gateway_byte_queue_releases_budget_after_drain(self):
        outbox = ByteQueue(maxsize=10, max_bytes=200)
        record = {'data': 'a' * 50}
        outbox.put_nowait(record)
        with self.assertRaises(queue.Full):
            outbox.put_nowait(record)
        self.assertEqual(outbox.get_nowait(), record)
        self.assertEqual(outbox.bytes_queued, 0)
        outbox.put_nowait(record)

    def test_bad_digest_and_conflicting_fragment(self):
        packets = fragments(1, 2, b'b' * 16, b'x' * 2500)
        link = RadioLink(2)
        link.accept(packets[0], 0.)
        changed = packets[0][:-1] + b'y'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            link.accept(changed, 0.)
        link = RadioLink(2)
        corrupted = [p[:-1] + b'z' for p in packets]
        with self.assertRaisesRegex(ValueError, 'checksum'):
            for packet in corrupted:
                link.accept(packet, 0.)

    def test_invalid_addresses_and_oversized_messages(self):
        for source, destination in [(0, 2), (1, 1), (1, 11)]:
            with self.assertRaises(ValueError):
                fragments(source, destination, b'a' * 16, b'')
        with self.assertRaises(ValueError):
            fragments(1, 0, b'a' * 16, b'', reliable=True)
        self.assertEqual(packet_sender(fragments(1, 2, b'a' * 16, b'')[0]), 1)
        self.assertIsNone(packet_sender(b'unrelated robot packet'))


if __name__ == '__main__':
    unittest.main()
