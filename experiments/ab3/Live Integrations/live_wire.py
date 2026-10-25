"""Bounded local controller/native protocol. This socket never connects robots."""
import base64
import json
import math
import struct

LIMIT = 32 * 1024 * 1024


def encode(value):
    data = json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(data) > LIMIT:
        raise ValueError('Native frame exceeds protocol limit')
    return struct.pack('!I', len(data)) + data


def exact(connection, size):
    chunks = []
    while size:
        chunk = connection.recv(min(size, 65536))
        if not chunk:
            raise EOFError('Native endpoint closed the connection')
        chunks.append(chunk)
        size -= len(chunk)
    return b''.join(chunks)


def send(connection, value):
    connection.sendall(encode(value))


def receive(connection):
    size = struct.unpack('!I', exact(connection, 4))[0]
    if size > LIMIT or not size:
        raise ValueError('Invalid native frame length')
    value = json.loads(exact(connection, size).decode('utf-8'),
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    if not isinstance(value, dict):
        raise ValueError('Native protocol requires an object')
    return value


def b64(data):
    return base64.b64encode(data).decode('ascii')


def unb64(data):
    return base64.b64decode(data, validate=True)


def stamp(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid simulation timestamp')
    nanoseconds = int(round(value * 1e9))
    return divmod(nanoseconds, 1000000000)
