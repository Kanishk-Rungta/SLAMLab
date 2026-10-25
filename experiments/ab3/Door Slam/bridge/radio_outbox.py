"""Pace fragments BEFORE calling the shared radio, without bypassing its errors.

Large ROS responses must be spread across steps: blasting all their fragments in
one step would deterministically lose every fragment after the token bucket fills.
Repeated RPC fragments already queued need not be queued a second time.
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
        if raw in self.pending:
            return True
        if len(self.queue) >= self.limit:
            return False
        self.queue.append(raw)
        self.pending.add(raw)
        return True

    def offer(self, now):
        self.credit = min(self.bandwidth, self.credit+max(0., now-self.last_time)*self.bandwidth*.9)
        self.last_time = now
        packets = []
        while self.queue and len(self.queue[0]) <= self.credit:
            packet = self.queue.popleft()
            self.pending.remove(packet)
            self.credit -= len(packet)
            packets.append(packet)
        return packets
