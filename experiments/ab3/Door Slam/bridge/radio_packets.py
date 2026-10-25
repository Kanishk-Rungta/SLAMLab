"""Radio envelopes for native ROS service/Buzz bytes; Python 2.7/3 compatible.

Only BstemSensors delivers these packets. Local TCP to a robot's own native
process is not a peer link. Fragment loss discards the incomplete message;
timeouts use simulation time, not wall time. No file bus or central peer router.
"""
from __future__ import division
import hashlib
import struct

MAGIC = b'DOR1'
# magic, sender robot ID, target (-1 broadcast), channel, message ID,
# fragment index/count, original message length, SHA256 of original message.
HEADER = struct.Struct('!4sHhB16sHHI32s')
MAX_PACKET = 12000
MAX_MESSAGE = 4*1024*1024
CHANNELS = {'buzz': 1, 'service_request': 2, 'service_response': 3}


def fragments(sender, target, channel, message_id, payload):
    payload = bytes(payload)
    if len(message_id) != 16:
        raise ValueError('Message ID must have 16 bytes')
    if len(payload) > MAX_MESSAGE:
        raise ValueError('Message exceeds reassembly memory limit')
    channel = CHANNELS.get(channel, channel)
    if channel not in CHANNELS.values():
        raise ValueError('Unknown channel')
    chunk = MAX_PACKET-HEADER.size
    count = max(1, (len(payload)+chunk-1)//chunk)
    digest = hashlib.sha256(payload).digest()
    return [HEADER.pack(MAGIC, sender, target, channel, message_id, i, count, len(payload), digest)
            + payload[i*chunk:(i+1)*chunk] for i in range(count)]


class Reassembler(object):
    def __init__(self, local_id, timeout=10., max_pending=32):
        self.local_id, self.timeout, self.max_pending = local_id, timeout, max_pending
        self.pending = {}
        self.completed = {}

    def accept(self, packet, now):
        self.pending = {k: v for k, v in self.pending.items() if now-v['started'] <= self.timeout}
        self.completed = {k: t for k, t in self.completed.items() if now-t <= self.timeout}
        if len(packet) < HEADER.size or len(packet) > MAX_PACKET:
            raise ValueError('Invalid radio packet length')
        magic, sender, target, channel, identity, index, count, size, digest = HEADER.unpack(packet[:HEADER.size])
        if magic != MAGIC or channel not in CHANNELS.values() or not (0 <= index < count):
            raise ValueError('Invalid radio envelope')
        chunk = MAX_PACKET-HEADER.size
        if size > MAX_MESSAGE or count != max(1, (size+chunk-1)//chunk):
            raise ValueError('Invalid radio message size')
        expected_size = min(chunk, max(0, size-index*chunk))
        if len(packet)-HEADER.size != expected_size:
            raise ValueError('Invalid fragment size')
        if sender == self.local_id or target not in (-1, self.local_id):
            return None
        key = (sender, identity)
        if key in self.completed:
            return None
        metadata = (target, channel, count, size, digest)
        if key not in self.pending:
            if len(self.pending) >= self.max_pending:
                raise ValueError('Too many incomplete radio messages')
            self.pending[key] = {'started': now, 'metadata': metadata, 'parts': {}}
        entry = self.pending[key]
        if entry['metadata'] != metadata:
            del self.pending[key]
            raise ValueError('Conflicting radio fragment metadata')
        entry['parts'][index] = packet[HEADER.size:]
        if len(entry['parts']) != count:
            return None
        payload = b''.join(entry['parts'][i] for i in range(count))
        del self.pending[key]
        if len(payload) != size or hashlib.sha256(payload).digest() != digest:
            raise ValueError('Reassembled radio message failed verification')
        self.completed[key] = now
        return {'sender': sender, 'target': target, 'channel': channel,
                'message_id': identity, 'payload': payload}
