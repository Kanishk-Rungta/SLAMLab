"""Run a complete Webots landmark EKF-SLAM experiment and evaluate its outputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'algorithms/ekf-slam'))
from ekf import Noise


def load_config(path, robots=None, seconds=None):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if robots is not None:
        config['robots'] = robots
    if seconds is not None:
        config['seconds'] = seconds
    if config.get('algorithm') != 'ekf-slam' or config.get('world') != 'landmark-lab':
        raise ValueError('Expected ekf-slam / landmark-lab configuration')
    if type(config.get('robots')) is not int or config['robots'] not in (1, 2):
        raise ValueError('Supported robot counts: 1 or 2')
    if not isinstance(config.get('seconds'), (int, float)) or not 1 <= config['seconds'] <= 180:
        raise ValueError('Duration must be 1..180 simulated seconds')
    if type(config.get('seed')) is not int or not 0 <= config['seed'] <= 2 ** 31 - 1:
        raise ValueError('Seed must be an integer in 0..2^31-1')
    Noise(**config['noise'])
    for key in ('wheel_radius_m', 'track_m', 'linear_speed_m_s', 'angular_speed_rad_s'):
        if not isinstance(config.get(key), (float, int)) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError('Expected positive finite configuration value: ' + key)
    if config['wheel_radius_m'] != .05 or config['track_m'] != .24:
        raise ValueError('The reference robot geometry is fixed at 0.05 m wheel radius and 0.24 m track')
    if max(abs(config['linear_speed_m_s'] + sign * config['track_m'] * config['angular_speed_rad_s'] / 2)
           / config['wheel_radius_m'] for sign in (-1, 1)) > 20:
        raise ValueError('Requested motion exceeds motor speed')
    starts = config.get('initial_poses', [])
    if len(starts) < config['robots'] or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in starts):
        raise ValueError('Supply a finite initial x,y,yaw for every robot')
    return config


def robot_node(index, pose):
    wheels = []
    for side, y in [('left', .12), ('right', -.12)]:
        wheels.append('''HingeJoint {
          jointParameters HingeJointParameters { axis 0 1 0 anchor 0 %s 0 }
          device [ RotationalMotor { name "%s_motor" maxVelocity 20 maxTorque 2 }
                   PositionSensor { name "%s_encoder" } ]
          endPoint Solid {
            translation 0 %s 0
            contactMaterial "wheel"
            children [ Pose { rotation 1 0 0 1.57079632679 children [
              Shape { appearance PBRAppearance { baseColor 0.12 0.17 0.23 roughness 0.8 }
                      geometry Cylinder { radius 0.05 height 0.025 } } ] } ]
            boundingObject Pose { rotation 1 0 0 1.57079632679 children [ Cylinder { radius 0.05 height 0.025 } ] }
            physics Physics { density -1 mass 0.05 }
          }
        }''' % (y, side, side, y))
    return '''DEF ROBOT%d Robot {
      translation %s %s 0.05 rotation 0 0 1 %s
      name "robot-%d" controller "landmark_slam" supervisor FALSE
      children [
        Shape { appearance PBRAppearance { baseColor %s roughness 0.45 metalness 0.1 }
                geometry Box { size 0.22 0.18 0.08 } }
        %s
        Solid { translation -0.08 0 -0.035 contactMaterial "caster"
                children [ Shape { geometry Sphere { radius 0.015 } } ]
                boundingObject Sphere { radius 0.015 } }
        Camera { name "front_camera" translation 0 0 0.25 width 320 height 160 fieldOfView 2.8
                 recognition Recognition { maxRange 6 occlusion 1 } }
        Camera { name "rear_camera" translation 0 0 0.25 rotation 0 0 1 3.14159265359
                 width 320 height 160 fieldOfView 2.8
                 recognition Recognition { maxRange 6 occlusion 1 } }
      ]
      boundingObject Box { size 0.22 0.18 0.08 }
      physics Physics { density -1 mass 0.8 centerOfMass [ 0 0 -0.015 ] }
    }
    ''' % (index, *pose, index, '0.08 0.55 0.54' if index == 1 else '0.78 0.32 0.14', '\n'.join(wheels))


def prepare(output, config):
    project = output / 'webots'
    world = project / 'worlds/landmark_lab.wbt'
    world.parent.mkdir(parents=True)
    header = '''#VRML_SIM R2025a utf8
WorldInfo { title "SLAMLab Landmark Lab" basicTimeStep 32 coordinateSystem "ENU" randomSeed %d
 contactProperties [ ContactProperties { material1 "ground" material2 "wheel" coulombFriction [ 1 ] }
 ContactProperties { material1 "ground" material2 "caster" coulombFriction [ 0.01 ] } ] }
Viewpoint { orientation -0.28 0.5 0.82 1.2 position 5 -7 9 }
Background { skyColor [ 0.91 0.94 0.96 ] }
DirectionalLight { direction -0.2 0.2 -1 intensity 1.5 }
Solid { translation 0 1 -0.05 contactMaterial "ground"
 children [ Shape { appearance PBRAppearance { baseColor 0.82 0.86 0.88 roughness 1 metalness 0 }
 geometry Box { size 12 12 0.1 } } ] boundingObject Box { size 12 12 0.1 } }
''' % config['seed']
    markers = []
    for index in range(12):
        angle = index * math.tau / 12
        x, y = 3.1 * math.cos(angle), 1 + 3.1 * math.sin(angle)
        markers.append('''Solid { translation %.8f %.8f 0.3 model "marker-%02d" name "marker-%02d"
 recognitionColors [ 1 0.3 0.1 ]
 children [ Shape { appearance PBRAppearance { baseColor 0.95 0.35 0.12 roughness 0.6 }
 geometry Sphere { radius 0.09 } } ] boundingObject Sphere { radius 0.09 } }''' % (x, y, index, index))
    world.write_text(header + '\n'.join(markers) + '\n' +
        '\n'.join(robot_node(i + 1, config['initial_poses'][i]) for i in range(config['robots'])) +
        '\nRobot { name "truth-recorder" controller "landmark_truth" supervisor TRUE }\n', encoding='utf-8')
    for name in ('landmark_slam', 'landmark_truth'):
        folder = project / 'controllers' / name
        folder.mkdir(parents=True)
        source = str(ROOT / 'simulations/webots/controllers' / (name + '.py'))
        (folder / (name + '.py')).write_text('import runpy\nrunpy.run_path(%r, run_name="__main__")\n' % source)
        (folder / 'runtime.ini').write_text('[python]\nCOMMAND = %s\n' % sys.executable)
    (output / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    return world


def finalize(output, config):
    sys.path.insert(0, str(ROOT / 'benchmarks/evaluation'))
    import trajectory
    reference_map = {p['id']: p for p in json.loads((output / 'reference_landmarks.json').read_text())}
    result = {'schema_version': 1, 'id': output.name, 'algorithm': 'EKF-SLAM', 'kind': 'simulation_measurement',
        'world': 'landmark-lab', 'robot_count': config['robots'], 'configuration': config,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'versions': {'python': platform.python_version(), 'numpy': trajectory.np.__version__, 'webots': 'R2025a'},
        'sensor_model': 'Webots camera-recognition relative marker range/bearing plus seeded noise; wheel encoders',
        'initial_prior': 'Known configured starting body pose; all landmark positions initially unknown',
        'robots': [], 'reproduce': 'python -B tools/run_reference_slam.py --config examples/landmark-slam/config.json'}
    for index in range(1, config['robots'] + 1):
        folder = output / ('robot-%d' % index)
        completion = json.loads((folder / 'complete.json').read_text())
        if completion['landmarks'] < 3 or completion['corrections'] < 5:
            raise RuntimeError('Insufficient landmark initialization/corrections: ' + folder.name)
        metadata = {'algorithm': 'Educational landmark EKF-SLAM', 'version': '0.2.0', 'environment': 'Webots R2025a landmark-lab',
                    'robot_count': config['robots'], 'dataset': output.name, 'experiment_date': result['created_utc'],
                    'dependencies': result['versions'], 'configuration': config, 'kind': 'simulation_measurement'}
        truth = output / ('robot-%d-reference.csv' % index)
        times, poses = trajectory.load_csv(folder / 'estimate.csv')
        rt, rp = trajectory.load_csv(truth)
        metrics, matched_times, estimate, reference = trajectory.evaluate(times, poses, rt, rp)
        metrics['experiment'] = metadata
        metrics['inputs'] = {k: {'filename': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                             for k, p in [('estimate', folder / 'estimate.csv'), ('reference', truth)]}
        state = json.loads((folder / 'map.json').read_text())
        errors = [math.hypot(p['x'] - reference_map[p['id']]['x'], p['y'] - reference_map[p['id']]['y'])
                  for p in state['landmarks'] if p['id'] in reference_map]
        metrics['landmark_map'] = {'matched': len(errors), 'rmse_m': math.sqrt(sum(e * e for e in errors) / len(errors))}
        metrics['processing'] = state['processing']
        ot, op = trajectory.load_csv(folder / 'odometry.csv')
        baseline, *_ = trajectory.evaluate(ot, op, rt, rp)
        metrics['odometry_baseline_ate_m'] = baseline['ate_m']
        trajectory.write_outputs(output / 'evaluation' / folder.name, metrics, matched_times, estimate, reference)
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(poses[:, 0], poses[:, 1], color='#087e8b', label='EKF-SLAM trajectory')
        ax.plot(rp[:, 0], rp[:, 1], '--', color='#687d93', label='Reference trajectory')
        ax.scatter([p['x'] for p in state['landmarks']], [p['y'] for p in state['landmarks']],
                   color='#c35522', marker='o', label='Estimated landmarks')
        ax.scatter([p['x'] for p in reference_map.values()], [p['y'] for p in reference_map.values()],
                   color='#52616e', marker='+', label='Reference landmarks')
        ax.set(xlabel='x [m]', ylabel='y [m]', title='Webots landmark EKF-SLAM: ' + folder.name)
        ax.set_aspect('equal')
        ax.legend(loc='upper left', fontsize=8)
        fig.tight_layout()
        fig.savefig(output / 'evaluation' / folder.name / 'map.png', dpi=160)
        plt.close(fig)
        result['robots'].append({'id': folder.name, 'estimate': folder.name + '/estimate.csv',
            'reference': truth.name, 'map': folder.name + '/map.json',
            'metrics': 'evaluation/' + folder.name + '/metrics.json', 'observations': completion})
    (output / 'experiment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (output / 'REPRODUCE.md').write_text('# Reproduce\n\nRun from the SLAMLab root:\n\n```sh\n' + result['reproduce'] +
        '\n```\n\nUse this experiment config.json to preserve the exact settings. Real-time resource measurements vary.\n', encoding='utf-8')
    from export_experiment import export_experiment
    export_experiment(output, output / 'viewer.json')
    print(json.dumps({'output': str(output), 'robots': [dict(id=r['id'], **r['observations']) for r in result['robots']]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'examples/landmark-slam/config.json')
    parser.add_argument('--robots', type=int)
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--webots-home', type=Path)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    try:
        config = load_config(args.config, args.robots, args.seconds)
        output = (args.output or ROOT / 'outputs' / ('landmark-slam-' + str(time.time_ns()))).resolve()
        if not output.is_relative_to(ROOT) or output == ROOT or output.exists():
            raise ValueError('Choose a new output directory inside SLAMLab')
        if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 600:
            raise ValueError('Wall-time timeout must be 1..600 seconds')
        output.mkdir(parents=True)
        world = prepare(output, config)
        if args.prepare_only:
            print('Prepared Webots project:', world)
            return
        sys.path.insert(0, str(ROOT / 'experiments/ab3/Standard Environment/tools'))
        import launcher_common
        if args.webots_home:
            os.environ['WEBOTS_HOME'] = str(args.webots_home)
        home, executable = launcher_common.find_webots()
        env = dict(os.environ, SLAMLAB_ROOT=str(ROOT), SLAMLAB_CONFIG=str(output / 'config.json'),
                   SLAMLAB_OUTPUT=str(output), WEBOTS_HOME=home, PYTHONDONTWRITEBYTECODE='1')
        print('Running Webots landmark SLAM:', output, flush=True)
        with (output / 'execution.log').open('w') as log:
            process = subprocess.Popen([executable, '--batch', '--minimize', '--no-rendering', '--mode=fast',
                                        '--stdout', '--stderr', str(world)], env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.kill()
                process.wait()
                raise RuntimeError('Webots timed out; inspect ' + str(output / 'execution.log'))
        if code or not (output / 'simulation_complete.json').exists():
            raise RuntimeError('Webots did not finish; inspect ' + str(output / 'execution.log'))
        finalize(output, config)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
