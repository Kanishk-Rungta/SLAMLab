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


if __name__ == '__main__':
    main()
