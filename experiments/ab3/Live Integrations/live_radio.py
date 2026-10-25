"""Fragmentation and retransmission exclusively over BstemSensors packets.

No peers are reachable by host sockets. All attempts, ACKs and retransmissions
consume the same simulated radio budget. The reliable channel is for RPC/stream
traffic only; ordinary native topic broadcasts retain their loss semantics.
"""
from collections import OrderedDict, deque
import hashlib
import queue
import struct
import uuid

MAGIC = b'AB3L'
# magic, source (1-based Webots robot), destination (0 broadcast), flags,
# 16-byte identity, fragment index/count, total length, payload digest.
HEADER = struct.Struct('!4sBBB16sHHI16s')
PACKET_SIZE = 1200
CHUNK = PACKET_SIZE - HEADER.size
MAX_MESSAGE = 16 * 1024 * 1024
MAX_PENDING_BYTES = 64 * 1024 * 1024
RELIABLE, ACK = 1, 2


class ByteQueue(queue.Queue):
    """Bound encoded gateway radio records by bytes as well as record count."""
    def __init__(self, maxsize=1024, max_bytes=MAX_PENDING_BYTES):
        self.max_bytes, self.bytes_queued = max_bytes, 0
        super().__init__(maxsize)

    def _put(self, item):
        size = len(item['data']) + 128
        if self.bytes_queued + size > self.max_bytes:
            raise queue.Full
        super()._put(item)
        self.bytes_queued += size

    def _get(self):
        item = super()._get()
        self.bytes_queued -= len(item['data']) + 128
        return item


def packet_sender(packet):
    if len(packet) >= HEADER.size and packet[:4] == MAGIC:
        return HEADER.unpack_from(packet)[1]
    return None


def fragments(source, destination, identity, data, reliable=False):
    data = bytes(data)
    if not 1 <= source <= 10 or not 0 <= destination <= 10 or destination == source:
        raise ValueError('Invalid radio address')
    if reliable and destination == 0:
        raise ValueError('Reliable messages require one destination')
    if len(data) > MAX_MESSAGE or len(identity) != 16:
        raise ValueError('Invalid native radio message')
    count = max(1, (len(data) + CHUNK - 1) // CHUNK)
    digest = hashlib.sha256(data).digest()[:16]
    return [HEADER.pack(MAGIC, source, destination, RELIABLE if reliable else 0,
                        identity, index, count, len(data), digest) + data[index * CHUNK:(index + 1) * CHUNK]
            for index in range(count)]


class RadioLink:
    def __init__(self, robot, bytes_per_second=50000, retry_seconds=2., timeout_seconds=60.,
                 recoverable=False):
        if not 1 <= robot <= 10 or bytes_per_second <= 0 or retry_seconds <= 0 or timeout_seconds <= 0:
            raise ValueError('Invalid radio configuration')
        self.robot, self.rate = robot, float(bytes_per_second)
        self.retry, self.timeout = float(retry_seconds), float(timeout_seconds)
        self.outbox = deque()
        self.outbox_bytes = 0
        self.incoming = OrderedDict()
        self.incoming_bytes = 0
        self.completed = OrderedDict()
        self.reliable = {}
        self.credit = 0.
        self.last_time = None
        self.recoverable = recoverable
        self.failures = deque(maxlen=1024)

    def failed(self, destination, metadata, reason):
        self.failures.append({'destination': destination, 'metadata': metadata or {}, 'reason': reason})

    def take_failures(self):
        failures = list(self.failures)
        self.failures.clear()
        return failures

    def _discard(self, identity):
        self.reliable.pop(identity, None)
        self.outbox = deque(p for p in self.outbox if HEADER.unpack_from(p)[4] != identity)
        self.outbox_bytes = sum(map(len, self.outbox))

    def _queue(self, packets, front=False):
        size = sum(map(len, packets))
        if self.outbox_bytes + size > MAX_PENDING_BYTES:
            raise BufferError('Native radio outbox is full')
        if front:
            self.outbox.extendleft(reversed(packets))
        else:
            self.outbox.extend(packets)
        self.outbox_bytes += size

    def enqueue(self, destination, payload, now, reliable=False, metadata=None):
        identity = uuid.uuid4().bytes
        if self.recoverable and len(payload) > MAX_MESSAGE:
            fragments(self.robot, destination, identity, b'', reliable)  # Validate addressing first.
            self.failed(destination, metadata, 'message_too_large')
            return None
        packets = fragments(self.robot, destination, identity, payload, reliable)
        if reliable and sum(value['size'] for value in self.reliable.values()) + len(payload) > MAX_PENDING_BYTES:
            if self.recoverable:
                self.failed(destination, metadata, 'unacknowledged_byte_limit')
                return None
            raise BufferError('Unacknowledged native radio data exceeded the memory limit')
        try:
            self._queue(packets)
        except BufferError:
            if not self.recoverable:
                raise
            self.failed(destination, metadata, 'outbox_byte_limit')
            return None
        if reliable:
            self.reliable[identity] = {'destination': destination, 'packets': packets,
                                       'start': now, 'last': now, 'size': len(payload), 'metadata': metadata}
        return identity

    def advance(self, now):
        now = float(now)
        if self.last_time is not None and now < self.last_time:
            raise ValueError('Simulation clock went backwards')
        self.credit = min(self.rate, self.credit + (0 if self.last_time is None else now - self.last_time) * self.rate)
        self.last_time = now
        for key, value in list(self.incoming.items()):
            if now - value['start'] > max(self.timeout, 2 * value['metadata'][3] / self.rate + self.retry):
                self.incoming_bytes -= value['bytes']
                del self.incoming[key]
        self.completed = OrderedDict((key, value) for key, value in self.completed.items()
                                     if now - value['time'] <= max(2 * self.timeout,
                                         8 * value['metadata'][3] / self.rate + self.retry))
        for identity, value in list(self.reliable.items()):
            if now - value['start'] > max(self.timeout, 4 * value['size'] / self.rate + self.retry):
                if self.recoverable:
                    self._discard(identity)
                    self.failed(value['destination'], value['metadata'], 'delivery_timeout')
                    continue
                raise TimeoutError('Native radio RPC/stream message timed out')
            # Wait for the previous attempt to leave the paced outbox before retrying.
            if now - value['last'] >= self.retry + sum(map(len, value['packets'])) / self.rate:
                queued = any(HEADER.unpack_from(packet)[4] == identity for packet in self.outbox)
                if not queued:
                    try:
                        self._queue(value['packets'])
                    except BufferError:
                        if not self.recoverable:
                            raise
                        # Other traffic may occupy the bounded outbox. Retry
                        # later; the existing delivery deadline still applies.
                    else:
                        value['last'] = now

    def drain(self, send_packet, now):
        self.advance(now)
        sent = []
        while self.outbox and len(self.outbox[0]) <= self.credit:
            packet = self.outbox[0]
            if not send_packet(packet):
                break
            self.outbox.popleft()
            self.outbox_bytes -= len(packet)
            self.credit -= len(packet)
            sent.append(packet)
        return sent

    def _ack(self, sender, identity):
        packet = HEADER.pack(MAGIC, self.robot, sender, ACK, identity, 0, 1, 0, b'\0' * 16)
        try:
            self._queue([packet], front=True)
        except BufferError:
            if not self.recoverable:
                raise
            # The completed-message cache prevents duplicate delivery, and a
            # sender retry will request another ACK after the outbox drains.
            self.failed(sender, {'kind': 'ack'}, 'ack_queue_full')

    def accept(self, packet, now):
        self.advance(now)
        if not HEADER.size <= len(packet) <= PACKET_SIZE:
            raise ValueError('Invalid radio packet length')
        magic, sender, destination, flags, identity, index, count, size, digest = HEADER.unpack_from(packet)
        if magic != MAGIC or not 1 <= sender <= 10 or not 0 <= destination <= 10 or flags not in (0, RELIABLE, ACK):
            raise ValueError('Invalid native radio envelope')
        if sender == self.robot or destination not in (0, self.robot):
            return None
        if flags == ACK:
            if destination == 0 or size or index or count != 1 or len(packet) != HEADER.size or digest != b'\0' * 16:
                raise ValueError('Invalid radio acknowledgement')
            pending = self.reliable.get(identity)
            if pending and pending['destination'] == sender:
                del self.reliable[identity]
                retained = deque(p for p in self.outbox if HEADER.unpack_from(p)[4] != identity)
                self.outbox = retained
                self.outbox_bytes = sum(map(len, retained))
            return None
        if flags == RELIABLE and destination == 0:
            raise ValueError('Reliable broadcast is invalid')
        if size > MAX_MESSAGE or count != max(1, (size + CHUNK - 1) // CHUNK) or not 0 <= index < count:
            raise ValueError('Invalid native radio fragmentation')
        payload = packet[HEADER.size:]
        if len(payload) != min(CHUNK, max(0, size - index * CHUNK)):
            raise ValueError('Invalid native radio fragment size')
        key = (sender, identity)
        metadata = (destination, flags, count, size, digest)
        if key in self.completed:
            if self.completed[key]['metadata'] != metadata:
                raise ValueError('Conflicting completed message metadata')
            if flags == RELIABLE and index == 0:
                self._ack(sender, identity)
            return None
        if key not in self.incoming:
            if len(self.incoming) >= 128:
                if self.recoverable:
                    self.failed(sender, {'kind': 'fragment'}, 'reassembly_message_limit')
                    return None
                raise BufferError('Too many incomplete native radio messages')
            self.incoming[key] = {'start': now, 'metadata': metadata, 'parts': {}, 'bytes': 0}
        state = self.incoming[key]
        if state['metadata'] != metadata:
            raise ValueError('Conflicting native radio fragment metadata')
        if index in state['parts']:
            if state['parts'][index] != payload:
                raise ValueError('Conflicting duplicate radio fragment')
            return None
        if self.incoming_bytes + len(payload) > MAX_PENDING_BYTES:
            if self.recoverable:
                self.failed(sender, {'kind': 'fragment'}, 'reassembly_byte_limit')
                return None
            raise BufferError('Native radio reassembly memory is full')
        state['parts'][index] = payload
        state['bytes'] += len(payload)
        self.incoming_bytes += len(payload)
        if len(state['parts']) != count:
            return None
        result = b''.join(state['parts'][i] for i in range(count))
        self.incoming_bytes -= state['bytes']
        del self.incoming[key]
        if hashlib.sha256(result).digest()[:16] != digest:
            raise ValueError('Native radio message checksum mismatch')
        self.completed[key] = {'time': now, 'metadata': metadata}
        if len(self.completed) > 4096:
            self.completed.popitem(last=False)
        if flags == RELIABLE:
            self._ack(sender, identity)
        return {'sender': sender, 'destination': destination, 'payload': result}
