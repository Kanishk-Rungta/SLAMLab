"""Joint robot/landmark EKF-SLAM with known marker identities and planar poses.

Only wheel travel and relative range/bearing observations enter this estimator.
The initial pose fixes the gauge. Landmark positions are estimated on first sight.
"""
from dataclasses import dataclass
import math

import numpy as np


def wrap(angle):
    return (angle + np.pi) % (2 * np.pi) - np.pi


@dataclass(frozen=True)
class Noise:
    distance_std: float = 0.003
    turn_std: float = 0.008
    range_std: float = 0.04
    bearing_std: float = 0.015

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError('Noise standard deviations must be finite and positive')


class EKFSLAM:
    def __init__(self, initial=(0., 0., 0.), noise=None, gate=9.21):
        self.mean = np.asarray(initial, dtype=float).copy()
        if self.mean.shape != (3,) or not np.isfinite(self.mean).all():
            raise ValueError('Initial pose must be finite x,y,yaw')
        self.cov = np.diag([1e-8, 1e-8, 1e-8])
        self.noise = noise or Noise()
        if not math.isfinite(gate) or gate <= 0:
            raise ValueError('Innovation gate must be positive')
        self.gate = gate
        self.landmarks = {}
        self.counts = {'initialized': 0, 'corrected': 0, 'rejected': 0}

    def predict(self, distance, turn):
        if not np.isfinite([distance, turn]).all():
            raise ValueError('Motion must be finite')
        heading = self.mean[2] + turn / 2
        c, s = math.cos(heading), math.sin(heading)
        transition = np.eye(len(self.mean))
        transition[0, 2] = -distance * s
        transition[1, 2] = distance * c
        control = np.array([[c, -distance * s / 2], [s, distance * c / 2], [0, 1.]])
        process = np.diag([self.noise.distance_std ** 2, self.noise.turn_std ** 2])
        self.cov = transition @ self.cov @ transition.T
        self.cov[:3, :3] += control @ process @ control.T
        self.mean[:3] += [distance * c, distance * s, turn]
        self.mean[2] = wrap(self.mean[2])
        self.cov = (self.cov + self.cov.T) / 2

    def observe(self, identity, distance, bearing):
        if not isinstance(identity, str) or not identity or len(identity) > 80:
            raise ValueError('Marker identity must be a nonempty short string')
        if not np.isfinite([distance, bearing]).all() or distance <= 0:
            raise ValueError('Observation must have positive finite range and finite bearing')
        measurement_cov = np.diag([self.noise.range_std ** 2, self.noise.bearing_std ** 2])
        if identity not in self.landmarks:
            angle = self.mean[2] + bearing
            c, s = math.cos(angle), math.sin(angle)
            gx = np.zeros((2, len(self.mean)))
            gx[:, :3] = [[1, 0, -distance * s], [0, 1, distance * c]]
            gz = np.array([[c, -distance * s], [s, distance * c]])
            cross = self.cov @ gx.T
            block = gx @ self.cov @ gx.T + gz @ measurement_cov @ gz.T
            self.landmarks[identity] = len(self.mean)
            self.cov = np.block([[self.cov, cross], [cross.T, block]])
            self.mean = np.r_[self.mean, self.mean[:2] + distance * np.array([c, s])]
            self.counts['initialized'] += 1
            return 'initialized'
        index = self.landmarks[identity]
        dx, dy = self.mean[index:index + 2] - self.mean[:2]
        q = dx * dx + dy * dy
        if q < 1e-12:
            self.counts['rejected'] += 1
            return 'rejected'
        predicted_range = math.sqrt(q)
        predicted = np.array([predicted_range, wrap(math.atan2(dy, dx) - self.mean[2])])
        residual = np.array([distance - predicted[0], wrap(bearing - predicted[1])])
        h = np.zeros((2, len(self.mean)))
        h[:, :3] = [[-dx / predicted_range, -dy / predicted_range, 0], [dy / q, -dx / q, -1]]
        h[:, index:index + 2] = [[dx / predicted_range, dy / predicted_range], [-dy / q, dx / q]]
        innovation = h @ self.cov @ h.T + measurement_cov
        if float(residual @ np.linalg.solve(innovation, residual)) > self.gate:
            self.counts['rejected'] += 1
            return 'rejected'
        gain = np.linalg.solve(innovation, h @ self.cov).T
        self.mean += gain @ residual
        self.mean[2] = wrap(self.mean[2])
        identity_matrix = np.eye(len(self.mean))
        a = identity_matrix - gain @ h
        self.cov = a @ self.cov @ a.T + gain @ measurement_cov @ gain.T
        self.cov = (self.cov + self.cov.T) / 2
        self.counts['corrected'] += 1
        return 'corrected'

    def snapshot(self):
        return {'pose': self.mean[:3].tolist(), 'pose_covariance': self.cov[:3, :3].tolist(),
                'landmarks': [{'id': identity, 'x': float(self.mean[index]), 'y': float(self.mean[index + 1]),
                               'covariance': self.cov[index:index + 2, index:index + 2].tolist()}
                              for identity, index in sorted(self.landmarks.items())],
                'observations': dict(self.counts)}
