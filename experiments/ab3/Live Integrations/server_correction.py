"""Back-end-corrected output for centralized algorithms (COVINS-G), applied by each robot's controller.

COVINS-G's server optimises every agent's keyframes, but the agents' front-ends keep their own VIO
estimate. The benchmark scores the system's best estimate, so each robot's output combines:
  * the server's optimised keyframes of this robot (graph3; frame = the server map it belongs to),
    read from robot 1's export (robot_1/native/covins_backend.json, written by ab3_covins_backend);
  * the robot's live VIO pose, carried into the server frame with the correction of its newest
    server keyframe: T = Tws_server(kf) * Tws_vio(kf)^-1.
This is an output conversion for evaluation only. It travels through the host file system, not the
radio, because nothing in it is used by the algorithm; it never reaches the native front-end.
"""
import json
import time
from pathlib import Path

import numpy as np

from pose_frames import matrix_quaternion, quaternion_matrix


def matrix(position, quaternion):
    T = np.eye(4)
    T[:3, :3] = quaternion_matrix(quaternion)
    T[:3, 3] = position
    return T


class ServerCorrection:
    def __init__(self, run, number, name='covins', server_robot=1):
        native = Path(run) / ('robot_%d' % server_robot) / 'native'
        self.export, self.clients = native / ('%s_backend.json' % name), native / ('%s_clients.json' % name)
        self.number = number
        self.correction, self.frame = None, None
        self.last_read, self.last_stamp = 0., None

    def poll(self, now):
        """New graph3 event for this robot if the server export changed (checked once per wall second)."""
        if time.monotonic() - self.last_read < 1.:
            return None
        self.last_read = time.monotonic()
        try:
            clients = json.loads(self.clients.read_text())
            data = json.loads(self.export.read_text())
        except (OSError, ValueError):
            return None
        ids = [int(c) for c, robot in clients.items() if int(robot) == self.number]
        entry = data.get('clients', {}).get(str(ids[0])) if ids else None
        if not entry or not entry.get('nodes') or data.get('t') == self.last_stamp:
            return None
        self.last_stamp = data.get('t')
        nodes = sorted(entry['nodes'], key=lambda n: n['t'])
        newest = nodes[-1]
        self.correction = matrix(newest['position'], newest['quaternion']) @ np.linalg.inv(
            matrix(newest['vio_position'], newest['vio_quaternion']))
        self.frame = entry['frame']
        return {'kind': 'graph3', 't': min(now, max(n['t'] for n in nodes)), 'frame': self.frame, 'axes': 'optical',
                'nodes': [{'key': n['key'], 't': n['t'], 'position': n['position'], 'quaternion': n['quaternion']}
                          for n in nodes]}

    def apply(self, event):
        """The live VIO pose3 event expressed in the server frame (unchanged until a correction exists)."""
        if self.correction is None or event.get('kind') != 'pose3':
            return event
        T = self.correction @ matrix(event['position'], event['quaternion'])
        return dict(event, frame=self.frame, position=T[:3, 3].tolist(), quaternion=matrix_quaternion(T[:3, :3]))

    def process(self, events, now):
        out = [self.apply(e) for e in events]
        graph = self.poll(now)
        if graph is not None:
            out.append(graph)
        return out
