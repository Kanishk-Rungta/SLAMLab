"""Audit live benchmark candidates without launching an unimplemented native adapter.

Source availability, build availability and benchmark readiness are separate facts.
An upstream build alone is not an AB3 integration.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from source_tools import verify_algorithm

FB = Path(__file__).resolve().parent.parent
SE = FB / 'Standard Environment'


def standard_contract(spec):
    stereo = spec['stereo']
    timing = spec['timing']
    fx, fy, cx, cy = (stereo[k] for k in ('fx', 'fy', 'cx', 'cy'))
    projection = [fx, 0, cx, 0, 0, fy, cy, 0, 0, 0, 1, 0]
    right_projection = projection.copy()
    right_projection[3] = -fx * stereo['baseline_m']
    return {
        'sensor_interface': 'BstemSensors',
        'camera': {'width': stereo['width'], 'height': stereo['height'],
                   'encoding': 'bgr8', 'period_ms': timing['camera_period_ms'],
                   'K': [fx, 0, cx, 0, fy, cy, 0, 0, 1],
                   'D': stereo['distortion'], 'R': [1, 0, 0, 0, 1, 0, 0, 0, 1],
                   'P_left': projection, 'P_right': right_projection,
                   'baseline_m': stereo['baseline_m'],
                   'left_position_body_m': stereo['left_position_m'],
                   'right_position_body_m': stereo['right_position_m'],
                   'optical_axes_in_body': {'x': [0, -1, 0], 'y': [0, 0, -1], 'z': [1, 0, 0]}},
        'imu': {'period_ms': timing['control_step_ms'],
                'angular_velocity': '3-axis body rates from BstemSensors.imu() (same error model per axis)',
                'linear_acceleration': 'standard noisy accelerometer in body axes',
                'orientation': 'unavailable; never synthesize from ground truth'},
        'radio': spec['radio'],
        'timestamps': 'Webots simulation seconds; synchronized clock, not wall clock',
        'peer_transport': 'All native messages and service requests/replies must traverse BstemSensors.send/receive',
        'ground_truth': 'Evaluation supervisor only; never mounted in native containers',
        'pose_output': 'Native tracked pose only, with timestamp, tracking validity, frame and units',
        'benchmark': 'Standard Environment/benchmark/benchlog.py',
    }


def render_camera(spec, orb3=False):
    st = spec['stereo']
    prefix = 'Camera1' if orb3 else 'Camera'
    lines = ['%YAML:1.0', '---']
    if orb3:
        lines += ['File.version: "1.0"', 'Camera.type: "PinHole"']
    for key in ('fx', 'fy', 'cx', 'cy'):
        lines.append('%s.%s: %.9f' % (prefix, key, st[key]))
    for key in ('k1', 'k2', 'p1', 'p2', 'k3'):
        lines.append('%s.%s: 0.0' % (prefix, key))
    lines += ['Camera.width: %d' % st['width'], 'Camera.height: %d' % st['height'],
              'Camera.fps: %.12g' % (1000 / spec['timing']['camera_period_ms']),
              'Camera.RGB: 0', 'Camera.bf: %.10g' % (st['fx'] * st['baseline_m']),
              'ORBextractor.nFeatures: 1000', 'ORBextractor.scaleFactor: 1.2',
              'ORBextractor.nLevels: 8', 'ORBextractor.iniThFAST: 20',
              'ORBextractor.minThFAST: 7', 'Viewer.KeyFrameSize: 0.05',
              'Viewer.KeyFrameLineWidth: 1.0', 'Viewer.GraphLineWidth: 0.9',
              'Viewer.PointSize: 2.0', 'Viewer.CameraSize: 0.08',
              'Viewer.CameraLineWidth: 3.0', 'Viewer.ViewpointX: 0.0',
              'Viewer.ViewpointY: -0.7', 'Viewer.ViewpointZ: -1.8', 'Viewer.ViewpointF: 500.0']
    return '\n'.join(lines) + '\n'


def prepare(root, robots):
    profile = json.loads((root / 'config/benchmark.json').read_text())
    maximum = profile.get('max_robots_adapter', profile['max_robots_upstream'])
    if not 1 <= robots <= maximum:
        raise ValueError('%s supports at most %d robots in the pinned implementation; no silent extension' %
                         (profile['algorithm'], maximum))
    from restore_sources import restore_algorithm
    restore_algorithm(root)        # fresh clone: download the pinned sources (verified per file)
    sources = verify_algorithm(root)
    missing = set(profile['required_workspace']) - set(sources['workspace'])
    if missing:
        raise ValueError('Missing pinned implementation repositories: ' + ', '.join(sorted(missing)))
    if profile.get('model_asset'):
        import hashlib
        model = root / 'third_party/models' / profile['model_asset']
        lock = json.loads((model.parent / 'model_lock.json').read_text())
        if lock['filename'] != model.name or hashlib.sha256(model.read_bytes()).hexdigest() != lock['sha256']:
            raise ValueError('Native model asset differs from its lock')
    spec = json.loads((SE / 'robot/robot_spec.json').read_text(encoding='utf-8-sig'))
    target = root / 'build/native_config'
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Build configuration resolves outside the algorithm directory')
    target.mkdir(parents=True, exist_ok=True)
    contract = standard_contract(spec)
    contract['algorithm_input_mode'] = profile['input_mode']
    contract['architecture'] = profile['architecture']
    contract['robots'] = robots
    for name, value in [('sensor_contract.json', contract), ('source_verification.json', sources),
                        ('integration_status.json', {'live_adapter_implemented': profile['live_adapter_implemented'],
                         'native_build_validated': False, 'webots_validated': False,
                         'blockers': profile['integration_work_remaining']})]:
        (target / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    if profile['id'] in ('dvm_slam', 'ccm_slam'):
        (target / 'camera.yaml').write_text(render_camera(spec, profile['id'] == 'dvm_slam'))
    print('Verified pinned sources and generated AB3 sensor contract:', target)
    for dependency in sources['unavailable_dependencies']:
        print('UNAVAILABLE upstream dependency:', dependency['name'], dependency['requested_ref'], dependency['error'])
    print('Native adapter code: %s; native build and Webots validation: pending.' %
          ('implemented' if profile['live_adapter_implemented'] else 'not implemented'))
    return profile


def main(root=None, *, default_seconds=120, default_robots=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--algorithm-dir', type=Path, default=root)
    parser.add_argument('--robots', type=int, default=default_robots,
                        help=('default: %(default)s robots' if default_robots is not None else
                              'default: the standard 10 robots, or the algorithm maximum if lower (CCM-SLAM: 4)'))
    parser.add_argument('--scenario', choices=['baseline', 'sensor_noise_x2', 'sensor_noise_x4', 'dynamic_obstacles', 'comm_failure'], default='baseline')
    parser.add_argument('--seconds', type=int, default=default_seconds,
                        help='simulation duration in seconds (default: %(default)s; 0 = until stopped)')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--rebuild-image', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--live-map-seconds', type=float, default=300.)
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--evaluate-last-run', action='store_true')
    args = parser.parse_args()
    if args.algorithm_dir is None:
        parser.error('--algorithm-dir is required')
    root = args.algorithm_dir.resolve()
    if args.robots is None:
        profile = json.loads((root / 'config/benchmark.json').read_text())
        args.robots = min(10, profile.get('max_robots_adapter', profile['max_robots_upstream']))
    if root.parent != FB.resolve():
        parser.error('Algorithm directory must be directly inside Benchmark')
    if args.seconds < 0:
        parser.error('--seconds must be nonnegative')
    if args.live_map_seconds <= 0:
        parser.error('--live-map-seconds must be positive')
    if args.stop or args.evaluate_last_run:
        from live_runner import latest, lc
        run_dir = latest(root)
        if args.stop:
            (run_dir / 'STOP').touch()
            (run_dir / 'benchmark/STOP').touch()
            print('Stop requested; the benchmark will save and evaluate:', run_dir)
        else:
            from finalize_native import finalize
            finalize(run_dir)
            lc.evaluate(run_dir)
        return
    if args.doctor:
        profile = json.loads((root / 'config/benchmark.json').read_text())
        print(json.dumps({'python': sys.executable, 'docker': shutil.which('docker'),
                          'live_adapter_implemented': profile['live_adapter_implemented'],
                          'native_build_validated': profile['native_build_validated'],
                          'webots_validated': profile['webots_validated']}, indent=2))
        return
    profile = prepare(root, args.robots)
    if profile['live_adapter_implemented']:
        from live_runner import run
        return run(root, args, profile)
    if args.prepare_only:
        return
    if args.build_only:
        dockerfile = root / 'Dockerfile'
        if not dockerfile.exists():
            raise RuntimeError('Native build recipe is not integrated yet. Read SETUP.md; no placeholder image was built.')
        if not shutil.which('docker'):
            raise RuntimeError('Docker is required for the native build. Install Docker Desktop using Linux containers.')
        subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '--tag',
                        'ab3-' + profile['id'] + ':source-build', str(root)], check=True)
        print('Upstream source build completed. This image has no AB3 runtime adapter yet.')
        return
    raise RuntimeError('Live AB3 integration is incomplete for ' + profile['algorithm'] +
                       '. Read VALIDATION.md and SOURCE_AND_ADAPTERS.md. '
                       'Refusing to launch an unrelated estimator or bypass the standard radio.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error))
