"""Native 3D camera/body pose to the benchmark plane; no pose estimation."""
import math
import numpy as np

OPTICAL_TO_BODY = np.array([[0., 0., 1.], [-1., 0., 0.], [0., -1., 0.]])


def matrix_quaternion(matrix):
    r = np.asarray(matrix, float)
    if r.shape != (3, 3) or not np.allclose(r.T @ r, np.eye(3), atol=1e-5) or np.linalg.det(r) < .99:
        raise ValueError('Invalid native rotation matrix')
    trace = float(np.trace(r))
    if trace > 0:
        s = math.sqrt(trace + 1.) * 2
        q = [(r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s,
             (r[1, 0] - r[0, 1]) / s, .25 * s]
    else:
        i = int(np.argmax(np.diag(r)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(max(0., 1. + r[i, i] - r[j, j] - r[k, k])) * 2
        q = [0., 0., 0., (r[k, j] - r[j, k]) / s]
        q[i] = .25 * s
        q[j] = (r[j, i] + r[i, j]) / s
        q[k] = (r[k, i] + r[i, k]) / s
    return q


def quaternion_matrix(quaternion):
    q = np.asarray(quaternion, dtype=float)
    if q.shape != (4,) or not np.all(np.isfinite(q)) or abs(np.linalg.norm(q) - 1.) > .01:
        raise ValueError('Native pose has an invalid unit quaternion')
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
                     [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
                     [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)]])


def planar_pose(event, stereo):
    position = np.asarray(event['position'], float)
    if position.shape != (3,) or not np.all(np.isfinite(position)):
        raise ValueError('Native pose has an invalid translation')
    rotation = quaternion_matrix(event['quaternion'])
    if event['axes'] == 'optical':
        # Native world starts at the initial left optical camera. Express both
        # map axes and camera attitude in the corresponding body axes.
        rotation = OPTICAL_TO_BODY @ rotation @ OPTICAL_TO_BODY.T
        position = OPTICAL_TO_BODY @ position - rotation @ np.asarray(stereo['left_position_m'])
    elif event['axes'] != 'body':
        raise ValueError('Unrecognized native coordinate convention')
    yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    return [float(position[0]), float(position[1]), yaw], float(position[2])
