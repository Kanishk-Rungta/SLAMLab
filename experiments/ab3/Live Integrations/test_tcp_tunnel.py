"""TcpTunnel: a client's TCP stream reaches the server robot's local server intact and in order,
even when the radio delivers the fragments out of order, and client ids follow connection order."""
import json
import random
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from live_wire import unb64
from tcp_tunnel import TcpTunnel


class FakeGateway:
    def __init__(self, number, wire):
        self.number, self.wire = number, wire

    def outgoing(self, destination, value, reliable=False):
        self.wire.append((self.number, destination, value))


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    return port


class TcpTunnelTests(unittest.TestCase):
    def test_stream_round_trip_with_reordering(self):
        backend_port, client_port = free_port(), free_port()
        backend = socket.socket(); backend.bind(('127.0.0.1', backend_port)); backend.listen(4)

        def echo():                                    # the "COVINS back-end": echoes upper-cased
            conn, _ = backend.accept()
            with conn:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    conn.sendall(data.upper())
        threading.Thread(target=echo, daemon=True).start()
        wire, rng = [], random.Random(1)
        with tempfile.TemporaryDirectory() as out:
            server = TcpTunnel(FakeGateway(1, wire), client_port, 1, 'covins', out, server_port=backend_port)
            client = TcpTunnel(FakeGateway(2, wire), client_port, 1, 'covins', out)
            tunnels = {1: server, 2: client}

            def radio():                               # deliver in random order, like lost/retried fragments
                while True:
                    if wire:
                        rng.shuffle(wire)
                        src, dst, value = wire.pop()
                        tunnels[dst].deliver(src, json.loads(json.dumps(value)))
                    else:
                        time.sleep(.001)
            threading.Thread(target=radio, daemon=True).start()
            deadline = time.time() + 5
            while not client.listening and time.time() < deadline:
                time.sleep(.01)
            app = socket.create_connection(('127.0.0.1', client_port))
            payload = bytes(range(256)) * 400 + b'end'
            app.sendall(payload)
            app.shutdown(socket.SHUT_WR)
            received = b''
            app.settimeout(10)
            while len(received) < len(payload):
                chunk = app.recv(65536)
                if not chunk:
                    break
                received += chunk
            self.assertEqual(received, payload.upper())
            clients = json.loads((Path(out) / 'covins_clients.json').read_text())
            self.assertEqual(clients, {'0': 1, '1': 2})


if __name__ == '__main__':
    unittest.main()
