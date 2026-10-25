"""Pace complete logical messages before calling the shared radio.

Large ROS responses must be spread across steps: blasting all their fragments in
one step would deterministically lose every fragment after the token bucket fills.
Fragments from different logical messages must not be allowed to evict or
interleave an incomplete message.
"""
from collections import deque


class RadioOutbox:
    def __init__(self, bandwidth, limit=512):
        self.bandwidth = float(bandwidth)
        self.credit = float(bandwidth)
        self.limit = limit
        self.last_time = 0.
        self.queue = deque()
        self.pending = set()

    def enqueue(self, raw):
        return self.enqueue_message([raw])

    def enqueue_message(self, packets):
        packets = tuple(bytes(packet) for packet in packets)
        if not packets:
            return True
        if len(self.queue) >= self.limit:
            return False
        identity = tuple(packets)
        if identity in self.pending:
            return True
        self.queue.append({'packets': packets, 'index': 0})
        self.pending.add(identity)
        return True

    def offer(self, now):
        self.credit = min(self.bandwidth, self.credit+max(0., now-self.last_time)*self.bandwidth*.9)
        self.last_time = now
        packets = []
        while self.queue:
            entry = self.queue[0]
            packet = entry['packets'][entry['index']]
            if len(packet) > self.credit:
                break
            self.credit -= len(packet)
            packets.append(packet)
            entry['index'] += 1
            if entry['index'] == len(entry['packets']):
                self.queue.popleft()
                self.pending.remove(entry['packets'])
        return packets
