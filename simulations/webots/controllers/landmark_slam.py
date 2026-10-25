"""Webots relative marker observations -> joint-state EKF-SLAM; no Supervisor API."""
import csv
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
from controller import Robot

ROOT = Path(os.environ['SLAMLAB_ROOT'])
sys.path.insert(0, str(ROOT / 'algorithms/ekf-slam'))
from ekf import EKFSLAM, Noise, wrap


def main():
    robot = Robot()
    config = json.loads(Path(os.environ['SLAMLAB_CONFIG']).read_text(encoding='utf-8'))
    index = int(robot.getName().split('-')[-1])
    initial = config['initial_poses'][index - 1]
    noise = Noise(**config['noise'])
    estimator = EKFSLAM(initial, noise)
    odometry = np.array(initial, dtype=float)
    rng = np.random.default_rng(config['seed'] + index * 100)
    step = int(robot.getBasicTimeStep())
    motors = [robot.getDevice(name) for name in ('left_motor', 'right_motor')]
    encoders = [robot.getDevice(name) for name in ('left_encoder', 'right_encoder')]
    cameras = [(robot.getDevice('front_camera'), 0.), (robot.getDevice('rear_camera'), math.pi)]
    for motor in motors:
        motor.setPosition(float('inf'))
        motor.setVelocity(0.)
    for encoder in encoders:
        encoder.enable(step)
    for camera, _ in cameras:
        camera.enable(step * 3)
        camera.recognitionEnable(step * 3)
    output = Path(os.environ['SLAMLAB_OUTPUT']) / robot.getName()
    output.mkdir()
    previous, tick, processing = None, 0, []
    cpu_start = time.process_time()
    with (output / 'estimate.csv').open('x', newline='') as estimates, \
            (output / 'odometry.csv').open('x', newline='') as odom, \
            (output / 'sensors.jsonl').open('x') as sensors, \
            (output / 'states.jsonl').open('x') as states:
        estimate_writer, odom_writer = csv.writer(estimates), csv.writer(odom)
        for writer in (estimate_writer, odom_writer):
            writer.writerow(['timestamp', 'x', 'y', 'yaw'])
        while robot.step(step) != -1:
            started = time.perf_counter()
            tick += 1
            angles = np.array([encoder.getValue() for encoder in encoders])
            if not np.isfinite(angles).all():
                continue
            travel = np.zeros(2) if previous is None else (angles - previous) * config['wheel_radius_m']
            previous = angles
            # Encoder scale bias is deliberately unknown to the estimator.
            measured = travel * np.array([1.006, 0.994]) + rng.normal(0, 0.00004, 2)
            distance, turn = float(measured.mean()), float((measured[1] - measured[0]) / config['track_m'])
            estimator.predict(distance, turn)
            heading = odometry[2] + turn / 2
            odometry += [distance * math.cos(heading), distance * math.sin(heading), turn]
            odometry[2] = wrap(odometry[2])
            observations = []
            if tick % 3 == 0:
                for camera, camera_yaw in cameras:
                    for obj in camera.getRecognitionObjects():
                        identity = obj.getModel()
                        if not identity.startswith('marker-'):
                            continue
                        relative = obj.getPosition()
                        # R2025a camera frame: +X forward, +Y left, +Z up.
                        measured_range = math.hypot(relative[0], relative[1]) + rng.normal(0, noise.range_std)
                        bearing = wrap(math.atan2(relative[1], relative[0]) + camera_yaw + rng.normal(0, noise.bearing_std))
                        if measured_range <= .05:
                            continue
                        outcome = estimator.observe(identity, measured_range, bearing)
                        observations.append({'id': identity, 'range_m': float(measured_range),
                                             'bearing_rad': float(bearing), 'outcome': outcome})
            now = robot.getTime()
            sensors.write(json.dumps({'t': now, 'distance_m': distance, 'turn_rad': turn,
                                      'observations': observations}) + '\n')
            estimate_writer.writerow([format(now, '.9f'), *estimator.mean[:3].tolist()])
            odom_writer.writerow([format(now, '.9f'), *odometry.tolist()])
            if tick % 3 == 0:
                states.write(json.dumps({'t': now, **estimator.snapshot()}) + '\n')
            processing.append(time.perf_counter() - started)
            v, w = config['linear_speed_m_s'], config['angular_speed_rad_s']
            motors[0].setVelocity((v - config['track_m'] * w / 2) / config['wheel_radius_m'])
            motors[1].setVelocity((v + config['track_m'] * w / 2) / config['wheel_radius_m'])
            if now >= config['seconds']:
                break
    for motor in motors:
        motor.setVelocity(0.)
    state = estimator.snapshot()
    state['processing'] = {'samples': len(processing), 'mean_step_s': float(np.mean(processing)),
                           'max_step_s': float(max(processing)), 'controller_cpu_s': time.process_time() - cpu_start}
    (output / 'map.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    (output / 'complete.json').write_text(json.dumps({'time_s': robot.getTime(), 'poses': tick,
        'landmarks': len(estimator.landmarks), 'corrections': estimator.counts['corrected']}), encoding='utf-8')


if __name__ == '__main__':
    main()
