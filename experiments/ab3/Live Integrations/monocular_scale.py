"""Metric scale for the OUTPUT of a monocular algorithm (CCM-SLAM), from the robot's own wheel odometry.

A monocular SLAM map has an arbitrary scale. The benchmark scores metric poses, and the occupancy
output adapter places metric stereo rays at the native poses, so the native output is scaled by

    s = sum(wheel path between consecutive native keyframes) / sum(native keyframe translation)

over straight segments (native heading change below 0.05 rad, where the 13 cm camera offset does not
bias the comparison). This is an output conversion only: the scale is never given to the algorithm,
uses no ground truth, and is recorded with the run (`native_scale` events).
"""
import bisect
import math
import numpy as np


class MonocularScale:
    def __init__(self, window=60, min_path_m=1.0, min_pairs=5):
        self.window, self.min_path, self.min_pairs = window, min_path_m, min_pairs
        self.times, self.path = [0.], [0.]          # cumulative wheel path length over simulation time
        self.scale = None

    def wheels(self, t, wheel_m):
        step = abs(float(np.mean(wheel_m)))
        if t > self.times[-1]:
            self.times.append(float(t))
            self.path.append(self.path[-1] + step)
        else:
            self.path[-1] += step

    def path_at(self, t):
        i = bisect.bisect_right(self.times, t) - 1
        return self.path[max(0, i)]

    def update(self, nodes):
        """nodes: native keyframes [{'t', 'position', 'quaternion'}] of this robot (one frame)."""
        nodes = sorted(nodes, key=lambda n: n['t'])
        wheel_sum = native_sum = 0.
        pairs = 0
        for a, b in list(zip(nodes, nodes[1:]))[-self.window:]:
            native = math.dist(a['position'], b['position'])
            if native < 1e-9 or _angle(a['quaternion'], b['quaternion']) > .05:
                continue
            wheel_sum += self.path_at(b['t']) - self.path_at(a['t'])
            native_sum += native
            pairs += 1
        if pairs >= self.min_pairs and wheel_sum >= self.min_path:
            self.scale = wheel_sum / native_sum
        return self.scale

    def apply(self, value):
        """Scaled copy of a native pose/node (position only; rotations are scale-free)."""
        out = dict(value)
        out['position'] = [self.scale * float(v) for v in value['position']]
        out['metric'] = True
        return out


def _angle(q1, q2):
    d = abs(sum(a * b for a, b in zip(q1, q2)))
    return 2 * math.acos(min(1., d))
