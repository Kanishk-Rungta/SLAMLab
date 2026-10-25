"""Render D2SLAM's configuration and camera files from the fixed standard robot files.

No world, layout, error-model or ground-truth reads. Calibration and timing come
from Standard Environment/robot; depth limits are upstream's stereo values scaled
to the standard baseline; IMU noise is upstream's default (config/benchmark.json).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from string import Template

import yaml

ROOT = Path(__file__).resolve().parent.parent
STANDARD = ROOT.parent / 'Standard Environment'
CAMERA = '''%YAML:1.0
---
model_type: PINHOLE
camera_name: $name
image_width: $width
image_height: $height
distortion_parameters:
   k1: $k1
   k2: $k2
   p1: $p1
   p2: $p2
projection_parameters:
   fx: $fx
   fy: $fy
   cx: $cx
   cy: $cy
'''


def read_camera(path):
    text = path.read_text(encoding='utf-8-sig')
    # OpenCV/EuRoC YAML files; PyYAML does not accept %YAML:1.0.
    return yaml.safe_load('\n'.join(line for line in text.splitlines() if not line.startswith('%YAML')))


def number(value):
    return repr(float(value))


def camera_file(name, camera):
    fx, fy, cx, cy = map(float, camera['intrinsics'])
    k1, k2, p1, p2 = map(float, camera['distortion_coefficients'])
    width, height = map(int, camera['resolution'])
    return Template(CAMERA).substitute(name=name, width=width, height=height, k1=number(k1), k2=number(k2),
                                       p1=number(p1), p2=number(p2), fx=number(fx), fy=number(fy),
                                       cx=number(cx), cy=number(cy))


def generate(standard=STANDARD, profile=None):
    profile = profile or json.loads((ROOT / 'config/benchmark.json').read_text(encoding='utf-8'))
    robot = standard / 'robot'
    spec = json.loads((robot / 'robot_spec.json').read_text(encoding='utf-8-sig'))
    left, right = read_camera(robot / 'stereo_left.yaml'), read_camera(robot / 'stereo_right.yaml')
    st = spec['stereo']
    for side in (left, right):
        if side['resolution'] != [st['width'], st['height']]:
            raise ValueError('Camera resolution differs between standard calibration files')
        expected = [st['fx'], st['fy'], st['cx'], st['cy']]
        if any(abs(a-b) > 1e-6 for a, b in zip(side['intrinsics'], expected)):
            raise ValueError('Camera intrinsics differ between standard calibration files')
    left_t, right_t = left['T_BS']['data'], right['T_BS']['data']
    baseline = math.sqrt(sum((left_t[i]-right_t[i])**2 for i in (3, 7, 11)))
    if abs(baseline-st['baseline_m']) > 1e-9:
        raise ValueError('Stereo baseline differs between standard calibration files')
    timing = spec['timing']
    dt = timing['control_step_ms']/1000.
    reference = profile['reference_stereo']
    scale = baseline/reference['baseline_m']
    values = {
        'imu_freq': number(1./dt),
        'image_freq': number(1000./timing['camera_period_ms']),
        'image_width': int(st['width']), 'image_height': int(st['height']),
        'body_T_cam0': ', '.join(number(v) for v in left_t),
        'body_T_cam1': ', '.join(number(v) for v in right_t),
        'depth_far_thres': number(reference['depth_far_thres']*scale),
        'depth_estimate_baseline': number(reference['depth_estimate_baseline']*scale),
        # Upstream's IMU noise defaults: nothing is fitted to the simulated sensors.
        'acc_n': number(profile['imu_noise']['acc_n']),
        'gyr_n': number(profile['imu_noise']['gyr_n']),
        'acc_w': number(profile['imu_noise']['acc_w']),
        'gyr_w': number(profile['imu_noise']['gyr_w']),
        'g_norm': number(profile['g_norm']),
    }
    template = (ROOT / 'config/d2slam_template.yaml').read_text(encoding='utf-8')
    return {
        'files': {'d2slam.yaml': Template(template).substitute(values),
                  'left.yaml': camera_file('left_cam', left), 'right.yaml': camera_file('right_cam', right)},
        'values': values,
        'baseline_m': baseline,
        'source_sha256': {name: hashlib.sha256((robot/name).read_bytes()).hexdigest()
                          for name in ('robot_spec.json', 'stereo_left.yaml', 'stereo_right.yaml')},
    }


def write(directory, calibration):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in calibration['files'].items():
        (directory / name).write_bytes(text.encode('utf-8'))  # LF on every host


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    write(args.out, generate())
    print('Prepared D2SLAM configuration from the standard robot:', args.out)
