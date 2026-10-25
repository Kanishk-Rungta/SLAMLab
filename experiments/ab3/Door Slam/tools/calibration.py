"""Translate the fixed standard camera calibration to ROS 1 CameraInfo/TF inputs.

No world, RangeFinder, GPS, layout or ground-truth reads. The right projection
matrix carries -fx*baseline; both cameras retain their standard optical frames.
"""
import argparse
import hashlib
import json
from pathlib import Path
import math
import yaml

ROOT = Path(__file__).resolve().parent.parent
STANDARD = ROOT.parent / 'Standard Environment'


def read_camera(path):
    text = path.read_text(encoding='utf-8-sig')
    # These are OpenCV/EuRoC YAML files; PyYAML does not accept %YAML:1.0.
    text = '\n'.join(line for line in text.splitlines() if not line.startswith('%YAML'))
    return yaml.safe_load(text)


def camera_info(camera, baseline=0.):
    fx, fy, cx, cy = map(float, camera['intrinsics'])
    width, height = map(int, camera['resolution'])
    return {'width': width, 'height': height, 'distortion_model': 'plumb_bob',
            'D': list(map(float, camera['distortion_coefficients'])),
            'K': [fx, 0., cx, 0., fy, cy, 0., 0., 1.],
            'R': [1., 0., 0., 0., 1., 0., 0., 0., 1.],
            'P': [fx, 0., cx, -fx*baseline, 0., fy, cy, 0., 0., 0., 1., 0.]}


def generate(standard=STANDARD):
    robot = standard / 'robot'
    spec = json.loads((robot / 'robot_spec.json').read_text(encoding='utf-8-sig'))
    left = read_camera(robot / 'stereo_left.yaml')
    right = read_camera(robot / 'stereo_right.yaml')
    st = spec['stereo']
    for side in (left, right):
        if side['resolution'] != [st['width'], st['height']]:
            raise ValueError('Camera resolution differs between standard calibration files')
        expected = [st['fx'], st['fy'], st['cx'], st['cy']]
        if any(abs(a-b) > 1e-6 for a, b in zip(side['intrinsics'], expected)):
            raise ValueError('Camera intrinsics differ between standard calibration files')
    left_t = left['T_BS']['data']
    right_t = right['T_BS']['data']
    baseline = math.sqrt(sum((left_t[i]-right_t[i])**2 for i in (3, 7, 11)))
    if abs(baseline-st['baseline_m']) > 1e-9:
        raise ValueError('Stereo baseline differs between standard calibration files')
    return {
        'left': camera_info(left), 'right': camera_info(right, baseline),
        'left_T_BS': left['T_BS'], 'right_T_BS': right['T_BS'],
        'camera_period_ms': spec['timing']['camera_period_ms'],
        'optical_to_body_quaternion_xyzw': [-.5, .5, -.5, .5],
        'image_encoding': 'bgr8', 'use_sim_time': True,
        'source_sha256': {name: hashlib.sha256((robot/name).read_bytes()).hexdigest()
                          for name in ('robot_spec.json', 'stereo_left.yaml', 'stereo_right.yaml')},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(generate(), indent=2)+'\n', encoding='utf-8')
    print('Prepared standard stereo calibration:', args.out)
