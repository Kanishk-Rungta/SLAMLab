"""Read native D2SLAM outputs into benchmark records. Python 3, no ROS imports.

Nothing here estimates a pose: it only re-expresses what D2VINS (odometry) and
D2PGO (optimized keyframes, loop edges) published.
"""
import math

from mapping import compose, inverse


def stamp_key(stamp):
    """Integer milliseconds: native and bridge stamps of one frame agree exactly."""
    return int(round(float(stamp)*1000))


def yaw_of(qx, qy, qz, qw):
    return math.atan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))


def planar(position, quaternion):
    """[x, y, yaw] of a 3-D pose (D2VINS/D2PGO frames are gravity aligned)."""
    return [float(position[0]), float(position[1]), yaw_of(*quaternion)]


def frame_done(state, stamp):
    """True when the native pipeline has finished the local stereo frame `stamp`:
    front end processed it, D2VINS consumed it if it was forwarded, and the loop
    detector has nothing queued or running."""
    if not state:
        return False
    if state['frontend'] < stamp-1e-6:
        return False
    if state['forwarded'] and state['backend'] < stamp-1e-6:
        return False
    return state['loop_queue'] == 0 and state['loop_busy'] == 0


def loop_measurement(edge, self_number):
    """benchlog loop fields from a D2SLAM LoopEdge seen by robot `self_number`.

    D2SLAM's relative_pose is frame b in frame a. The benchmark wants the CURRENT
    observation (this robot's, or the newer one of an intra-robot loop) in the
    MATCHED observation's frame. Returns (current_time, matched_number,
    matched_time, (dx, dy, dyaw)) or None if this robot is not part of the edge.
    """
    relative = planar(edge['relative'][:3], edge['relative'][3:])
    a, b = (edge['drone_a'], edge['ts_a']), (edge['drone_b'], edge['ts_b'])
    if b[0] == self_number and (a[0] != self_number or b[1] >= a[1]):
        return b[1], a[0], a[1], tuple(relative)
    if a[0] == self_number:
        return a[1], b[0], b[1], tuple(inverse(relative))
    return None


class PoseCorrection(object):
    """D2PGO's correction of D2VINS odometry, applied to every odometry sample.

    D2PGO publishes its latest corrected pose with the stamp of the D2VINS
    odometry it corrected; offset = pgo * vio^-1 then carries the correction to
    later odometry samples until the next solve, as D2PGO's own prediction does.
    """

    def __init__(self, keep=4000):
        self.keep = keep
        self.vio = {}
        self.offset = [0., 0., 0.]
        self.has_pgo = False

    def add_vio(self, stamp, pose):
        self.vio[stamp_key(stamp)] = list(pose)
        if len(self.vio) > self.keep:
            for key in sorted(self.vio)[:len(self.vio)-self.keep]:
                del self.vio[key]

    def vio_at(self, stamp):
        return self.vio.get(stamp_key(stamp))

    def set_pgo(self, stamp, pose):
        vio = self.vio_at(stamp)
        if vio is None:
            return False
        self.offset = list(compose(pose, inverse(vio)))
        self.has_pgo = True
        return True

    def apply(self, pose):
        return list(compose(self.offset, pose))
