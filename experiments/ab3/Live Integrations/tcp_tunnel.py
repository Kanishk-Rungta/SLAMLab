"""The algorithm's own TCP protocol carried over the standard radio (no ROS dependency; see TcpTunnel)."""
import json
import queue
import socket
import threading
import time
from pathlib import Path

from live_wire import b64, unb64

CHUNK = 16 * 1024


class TcpTunnel:
    """The algorithm's TCP protocol over the standard radio (reliable radio mode, in-order delivery).

    Robots other than the server robot listen on 127.0.0.1:port (where the algorithm's client expects
    the server) and forward each connection's bytes to the server robot. The server robot opens one
    local connection to the real server per remote stream, strictly one after another, so the server's
    accept order (= its client ids) is known: client 0 is the server robot's own client, which
    connects locally before the simulation starts. The id -> robot map is written to
    /output/<name>_clients.json for evaluation.
    """

    def __init__(self, gateway, port, server_robot, name, output='/output', server_port=None):
        self.gateway, self.port, self.server, self.name = gateway, int(port), int(server_robot), name
        self.output, self.server_port = Path(output), int(server_port or port)
        self.number = gateway.number
        self.lock = threading.RLock()
        self.sockets, self.out_seq, self.in_seq, self.pending = {}, {}, {}, {}
        self.clients = {0: self.server}
        self.connect_queue = queue.Queue()
        self.listening = False
        if self.number == self.server:
            self.write_clients()
            threading.Thread(target=self.connector, daemon=True).start()
        else:
            threading.Thread(target=self.listen, daemon=True).start()

    def write_clients(self):
        path = self.output / ('%s_clients.json' % self.name)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps({str(k): v for k, v in self.clients.items()}))
        tmp.replace(path)

    def send(self, peer, stream, kind, data=b''):
        with self.lock:
            seq = self.out_seq.get((peer, stream), 0)
            self.out_seq[(peer, stream)] = seq + 1
        self.gateway.outgoing(peer, {'kind': kind, 'stream': stream, 'seq': seq, 'data': b64(data)}, True)

    def pump(self, peer, stream, sock):
        try:
            while True:
                data = sock.recv(CHUNK)
                if not data:
                    break
                self.send(peer, stream, 'tcp', data)
        except OSError:
            pass
        self.send(peer, stream, 'tcp_close')

    def listen(self):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', self.port))
        server.listen(8)
        self.listening = True
        count = 0
        while True:
            sock, _ = server.accept()
            stream = '%d-%d' % (self.number, count)
            count += 1
            with self.lock:
                self.sockets[(self.server, stream)] = sock
            threading.Thread(target=self.pump, args=(self.server, stream, sock), daemon=True).start()

    def connector(self):
        """Server robot: open local connections to the real server one at a time (fixes client ids)."""
        while True:
            peer, stream = self.connect_queue.get()
            sock = socket.create_connection(('127.0.0.1', self.server_port), timeout=30)
            sock.settimeout(None)
            with self.lock:
                self.clients[len(self.clients)] = peer
                self.write_clients()
                self.sockets[(peer, stream)] = sock
                for data in self.pending.pop((peer, stream), []):
                    sock.sendall(data)
            threading.Thread(target=self.pump, args=(peer, stream, sock), daemon=True).start()
            time.sleep(.5)                 # let the server accept before the next connection

    def deliver(self, source, value):
        key = (source, value['stream'])
        with self.lock:
            buffer = self.in_seq.setdefault(key, {'next': 0, 'held': {}})
            buffer['held'][int(value['seq'])] = value
            while buffer['next'] in buffer['held']:
                item = buffer['held'].pop(buffer['next'])
                buffer['next'] += 1
                self.apply(key, item)

    def apply(self, key, item):
        data = unb64(item['data'])
        sock = self.sockets.get(key)
        if item['kind'] == 'tcp_close':
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            return
        if sock is None:
            if self.number != self.server:
                return                     # stream already closed locally
            first = key not in self.pending
            self.pending.setdefault(key, []).append(data)
            if first:
                self.connect_queue.put(key)
            return
        sock.sendall(data)
