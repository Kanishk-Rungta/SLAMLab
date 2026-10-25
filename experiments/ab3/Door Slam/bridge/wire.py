"""Bounded local sensor/outputs connection. Python 2.7/3; never a peer transport."""
from __future__ import division
import base64
import json
import struct

MAX_FRAME = 16*1024*1024


def encode_bytes(data):
    return base64.b64encode(data).decode('ascii')


def decode_bytes(data):
    return base64.b64decode(data.encode('ascii'))


def read_exact(sock, count):
    parts = []
    while count:
        data = sock.recv(count)
        if not data:
            raise EOFError('Native bridge disconnected')
        parts.append(data)
        count -= len(data)
    return b''.join(parts)


def receive(sock):
    count = struct.unpack('!I', read_exact(sock, 4))[0]
    if not 0 < count <= MAX_FRAME:
        raise ValueError('Invalid local bridge frame size')
    return json.loads(read_exact(sock, count).decode('utf-8'))


def send(sock, value):
    payload = json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(payload) > MAX_FRAME:
        raise ValueError('Local bridge frame too large')
    sock.sendall(struct.pack('!I', len(payload))+payload)
