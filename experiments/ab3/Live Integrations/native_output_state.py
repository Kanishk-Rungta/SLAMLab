"""Compose native backend corrections with native VIO. No filtering or optimization."""
from collections import OrderedDict
import numpy as np
from pose_frames import quaternion_matrix, matrix_quaternion


def transform(position, quaternion):
    result = np.eye(4)
    result[:3, :3] = quaternion_matrix(quaternion)
    position = np.asarray(position, float)
    if position.shape != (3,) or not np.all(np.isfinite(position)):
        raise ValueError('Invalid native pose translation')
    result[:3, 3] = position
    return result


def components(value):
    return value[:3, 3].tolist(), matrix_quaternion(value[:3, :3])


class NativeCorrection:
    def __init__(self, robot):
        self.robot = robot
        self.frame = 'swarm_robot%d_map' % (robot - 1)
        self.correction = None
        self.odometry = OrderedDict()
        self.keyframes = {}
        self.optimized = {}
        self.latest = None

    def odom(self, time, pose, valid=True):
        key = int(round(time * 1e9))
        self.odometry[key] = pose.copy()
        self.latest = (time, pose.copy(), valid)
        while len(self.odometry) > 4096:
            self.odometry.popitem(last=False)

    def keyframe(self, identity, time, pose):
        if identity in self.keyframes and abs(self.keyframes[identity][0] - time) > 1e-7:
            raise ValueError('Native keyframe ID was reused without a frame reset')
        self.keyframes[identity] = (time, pose.copy())

    def anchor(self, time, corrected, frame):
        # The stamp is instrumented at the native backend's latest keyframe.
        original = next((pose for stamp, pose in self.keyframes.values() if abs(stamp - time) < 1e-7), None)
        if original is None:
            return False
        if frame != self.frame:
            self.optimized.clear()
        self.frame = frame
        self.correction = corrected @ np.linalg.inv(original)
        return True

    def apply_optimization(self, estimates, origin):
        frame = 'swarm_robot%d_map' % origin
        own = {key: pose for key, pose in estimates.items() if key in self.keyframes}
        if not own:
            return False
        if frame != self.frame:
            self.optimized.clear()
        self.frame = frame
        self.optimized.update(own)
        latest = max(own, key=lambda key: self.keyframes[key][0])
        self.correction = own[latest] @ np.linalg.inv(self.keyframes[latest][1])
        return True

    def pose_event(self):
        if self.latest is None or self.correction is None or not self.latest[2]:
            return None
        stamp, original, _ = self.latest
        p, q = components(self.correction @ original)
        return {'kind': 'pose3', 't': stamp, 'frame': self.frame, 'axes': 'body',
                'position': p, 'quaternion': q, 'metric': True}

    def graph_event(self, now):
        if self.correction is None:
            return None
        nodes = []
        for identity, (stamp, original) in sorted(self.keyframes.items()):
            corrected = self.optimized.get(identity, self.correction @ original)
            p, q = components(corrected)
            nodes.append({'key': identity, 't': stamp, 'position': p, 'quaternion': q})
        return {'kind': 'graph3', 't': now, 'frame': self.frame, 'axes': 'body', 'nodes': nodes}
