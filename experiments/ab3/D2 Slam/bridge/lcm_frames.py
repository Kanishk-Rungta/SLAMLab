"""Unchanged LCM bytes inside a radio payload, plus echo suppression.

D2SLAM's nodes talk to other robots only through LCM channels (VIOKF_*,
SWARM_LOOP_CONN, DISTRIB_VINS_DATA, SYNC_*, PGO_Sync_Data). In each container
LCM runs with ttl=0, so nothing leaves the container by itself; the gateway
copies every locally published message to the standard radio and republishes
what the radio delivers. Messages are never decoded, edited or re-encoded.
"""
import hashlib
import struct
import threading
import time

_LENGTH = struct.Struct('!B')


def pack(channel, data):
    name = channel.encode('utf-8')
    if not name or len(name) > 255:
        raise ValueError('Invalid LCM channel name')
    return _LENGTH.pack(len(name)) + name + bytes(data)


def unpack(payload):
    if len(payload) < 2:
        raise ValueError('Short LCM radio payload')
    size = _LENGTH.unpack_from(payload)[0]
    if size == 0 or len(payload) < 1+size:
        raise ValueError('Invalid LCM radio payload')
    return payload[1:1+size].decode('utf-8'), payload[1+size:]


class EchoFilter(object):
    """Remembers messages the gateway itself republished so they are not sent back out."""

    def __init__(self, lifetime=30., clock=time.monotonic):
        self.lifetime, self.clock = lifetime, clock
        self.injected = {}
        self.lock = threading.Lock()  # LCM handler thread and bridge step thread

    @staticmethod
    def key(channel, data):
        return hashlib.sha1(channel.encode('utf-8') + b'\0' + bytes(data)).digest()

    def remember(self, channel, data):
        key = self.key(channel, data)
        with self.lock:
            now = self.clock()
            self.injected = {k: v for k, v in self.injected.items() if now-v[0] <= self.lifetime}
            count = self.injected.get(key, (now, 0))[1]
            self.injected[key] = (now, count+1)

    def is_echo(self, channel, data):
        key = self.key(channel, data)
        with self.lock:
            entry = self.injected.get(key)
            if entry is None:
                return False
            if entry[1] <= 1:
                del self.injected[key]
            else:
                self.injected[key] = (entry[0], entry[1]-1)
            return True
