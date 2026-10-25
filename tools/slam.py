"""Consistent readiness and launch interface for preserved native integrations."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / 'experiments/ab3'
ALGORITHMS = {
    'door-slam': ('Door Slam', 'run_door_slam_original.py', 'ROS 1 Melodic'),
    'd2slam': ('D2 Slam', 'run_d2slam.py', 'ROS 1 Noetic'),
    'kimera-multi': ('Kimera Multi', 'run_kimera_multi.py', 'ROS 1 Noetic'),
    'swarm-slam': ('Swarm Slam', 'run_swarm_slam.py', 'ROS 2 Humble'),
}


def main():
    # Keep the original doctor/prepare/build/run entry points compatible.
    # New operations dispatch to existing tools instead of duplicating estimators/metrics.
    if len(sys.argv) == 1 or sys.argv[1] in ('-h', '--help', 'list', 'info', 'setup', 'evaluate', 'visualize') or 'ekf-slam' in sys.argv:
        return platform_command()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('doctor', 'prepare', 'build', 'run'))
    parser.add_argument('algorithm', choices=ALGORITHMS)
    parser.add_argument('--robots', type=int, choices=range(1, 11), default=2)
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--scenario', default='baseline', choices=(
        'baseline', 'sensor_noise_x2', 'sensor_noise_x4', 'dynamic_obstacles', 'comm_failure'))
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be positive; use the original launchers for explicitly unbounded runs')
    folder, script, ros = ALGORITHMS[args.algorithm]
    path = WORKSPACE / folder
    lock = json.loads((path / 'source_lock.json').read_text(encoding='utf-8'))
    source_present = ((path / 'algorithm/DOOR-SLAM-original.zip').is_file() if args.algorithm == 'door-slam'
                      else (path / 'algorithm/D2SLAM-original.zip').is_file() if args.algorithm == 'd2slam'
                      else (path / 'algorithm/upstream-original.zip').is_file())
    if args.action == 'doctor':
        print(json.dumps({
            'algorithm': args.algorithm, 'ros': ros, 'python': sys.version.split()[0],
            'docker_available': shutil.which('docker') is not None,
            'source_archive_present': source_present,
            'source_commit': lock.get('commit', lock.get('repositories', [{}])[0].get('commit')),
            'adapter_available': (path / script).is_file(),
            'native_build_verified_in_slamlab': False,
            'native_webots_run_verified_in_slamlab': False,
            'note': 'Presence is not integrity verification; prepare verifies local source files.'
        }, indent=2))
        return
    if args.action in ('build', 'run') and not shutil.which('docker'):
        raise SystemExit('Docker with Linux containers is required; no download, build or simulation started.')
    if not source_present:
        raise SystemExit('Pinned external sources are missing. Read algorithms/' + args.algorithm +
                         '/README.md. No source or model is downloaded implicitly by this interface.')
    command = [sys.executable, '-B', str(path / script), '--robots', str(args.robots)]
    if args.action == 'prepare':
        command += ['--prepare-only']
    elif args.action == 'build':
        command += ['--build-only']
    else:
        command += ['--seconds', str(args.seconds), '--scenario', args.scenario, '--no-browser']
        if args.gui:
            command += ['--gui']
    result = subprocess.run(command, cwd=path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    raise SystemExit(result.returncode)


def platform_command():
    catalog = json.loads((ROOT / 'algorithms/catalog.json').read_text(encoding='utf-8'))
    names = {entry['id']: entry for entry in catalog}
    parser = argparse.ArgumentParser(description='SLAMLab experiments, research systems and result tools')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('list', help='List available experiments and research guides')
    info = commands.add_parser('info', help='Describe sensors, architecture and source')
    info.add_argument('algorithm', choices=names)
    for action in ('run', 'setup', 'prepare', 'doctor', 'build'):
        operation = commands.add_parser(action)
        operation.add_argument('algorithm', choices=names)
        operation.add_argument('--config', type=Path, default=ROOT / 'examples/landmark-slam/config.json')
        operation.add_argument('--robots', type=int)
        operation.add_argument('--seconds', type=float)
        operation.add_argument('--output', type=Path)
    evaluation = commands.add_parser('evaluate', help='Re-evaluate a recorded experiment with the existing trajectory toolkit')
    evaluation.add_argument('experiment', type=Path)
    evaluation.add_argument('--robot', default='robot-1')
    evaluation.add_argument('--output', type=Path, required=True)
    evaluation.add_argument('--alignment', choices=('none', 'se2'), default='none')
    visual = commands.add_parser('visualize', help='Export a browser-local replay bundle')
    visual.add_argument('experiment', type=Path)
    visual.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'list':
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
        return
    if args.action == 'info':
        print(json.dumps(names[args.algorithm], indent=2, ensure_ascii=False))
        return
    if args.action == 'visualize':
        from export_experiment import export_experiment
        export_experiment(args.experiment, args.output)
        print('Replay bundle:', args.output, '\nOpen it in the website Visualization Studio; files stay in your browser.')
        return
    if args.action == 'evaluate':
        import tempfile
        from export_experiment import safe_file
        experiment = json.loads((args.experiment / 'experiment.json').read_text(encoding='utf-8'))
        robot = next((r for r in experiment['robots'] if r['id'] == args.robot), None)
        if robot is None:
            parser.error('Robot is not in this experiment')
        original = json.loads(safe_file(args.experiment, robot['metrics']).read_text())
        with tempfile.TemporaryDirectory(prefix='slamlab-evaluate-') as directory:
            meta = Path(directory) / 'metadata.json'
            meta.write_text(json.dumps(original['experiment']), encoding='utf-8')
            subprocess.run([sys.executable, '-B', str(ROOT / 'benchmarks/evaluation/trajectory.py'), 'evaluate',
                '--estimate', str(safe_file(args.experiment, robot['estimate'])),
                '--reference', str(safe_file(args.experiment, robot['reference'])),
                '--metadata', str(meta), '--output', str(args.output), '--alignment', args.alignment], check=True)
            shutil.copyfile(meta, args.output / 'input-metadata.json')
        return
    if args.algorithm != 'ekf-slam':
        if names[args.algorithm]['operation'] == 'reference':
            parser.error('Use the upstream installation guide: ' + names[args.algorithm]['source'])
        action = 'prepare' if args.action == 'setup' else args.action
        command = [sys.executable, '-B', str(Path(__file__)), action, args.algorithm]
        if args.robots is not None:
            command += ['--robots', str(args.robots)]
        if args.seconds is not None:
            command += ['--seconds', str(int(args.seconds))]
        raise SystemExit(subprocess.run(command).returncode)
    if args.action == 'doctor':
        import importlib.util
        print(json.dumps({'algorithm': 'ekf-slam', 'python': sys.version.split()[0],
            'numpy': importlib.util.find_spec('numpy') is not None,
            'simulator': 'Webots R2025a', 'config': str(args.config), 'docker_required': False}, indent=2))
        return
    if args.action == 'build':
        parser.error('EKF-SLAM runs directly in Python; use setup or run')
    command = [sys.executable, '-B', str(ROOT / 'tools/run_reference_slam.py'), '--config', str(args.config)]
    if args.action in ('setup', 'prepare'):
        command += ['--prepare-only']
    for key in ('robots', 'seconds', 'output'):
        if getattr(args, key) is not None:
            command += ['--' + key, str(getattr(args, key))]
    raise SystemExit(subprocess.run(command).returncode)


if __name__ == '__main__':
    main()
