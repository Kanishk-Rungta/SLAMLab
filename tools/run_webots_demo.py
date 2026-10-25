"""Prepare/run a bounded wheel-odometry example in the imported AB3 world."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / 'experiments/ab3/Standard Environment'


def main():
    if '--example' in sys.argv and sys.argv[sys.argv.index('--example') + 1:][:1] == ['landmark-slam']:
        forwarded = sys.argv[1:]
        index = forwarded.index('--example')
        del forwarded[index:index + 2]
        if '--world' in forwarded:
            index = forwarded.index('--world')
            if forwarded[index + 1:index + 2] != ['landmark-lab']:
                raise SystemExit('landmark-slam uses --world landmark-lab')
            del forwarded[index:index + 2]
        raise SystemExit(subprocess.run([sys.executable, '-B', str(ROOT / 'tools/run_reference_slam.py'), *forwarded]).returncode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', choices=('odometry', 'landmark-slam'), default='odometry')
    parser.add_argument('--world', choices=('ab3', 'landmark-lab'), default='ab3')
    parser.add_argument('--robots', type=int, choices=(1, 2), default=1)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--webots-home', type=Path, default=os.environ.get('WEBOTS_HOME'))
    parser.add_argument('--timeout', type=float, default=120, help='Wall-time limit, seconds')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.world != 'ab3':
        parser.error('The odometry example uses --world ab3')
    if not 0 < args.seconds <= 60 or not 0 < args.timeout <= 600:
        parser.error('Use 0 < seconds <= 60 and 0 < timeout <= 600')
    sys.path.insert(0, str(STANDARD / 'tools'))
    import launcher_common
    if args.webots_home:
        os.environ['WEBOTS_HOME'] = str(args.webots_home)
    # Preparation is offline and does not require an installed simulator.
    executable = None if args.prepare_only else launcher_common.find_webots()[1]
    for name, source in [('odometry_demo', ROOT / 'simulations/webots/controllers/odometry_demo.py'),
                         ('bench_supervisor', ROOT / 'simulations/webots/controllers/demo_supervisor.py')]:
        subprocess.run([sys.executable, '-B', str(STANDARD / 'tools/install_controller.py'),
                        '--name', name, '--source', str(source), '--python', sys.executable], check=True)
    subprocess.run([sys.executable, '-B', str(STANDARD / 'tools/make_algorithm_world.py'),
                    '--controller', 'odometry_demo', '--robots', str(args.robots)], check=True)
    world = STANDARD / 'webots/worlds/ab3_standard__odometry_demo.wbt'
    print('Prepared world:', world)
    if args.prepare_only:
        return
    output = (args.output or ROOT / 'outputs' / ('webots-demo-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns()))).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error('Choose a new output directory inside SLAMLab')
    output.mkdir(parents=True)
    env = dict(os.environ, STANDARD_ENV=str(STANDARD), SLAMLAB_DEMO_OUTPUT=str(output),
               SLAMLAB_DEMO_SECONDS=str(args.seconds), SLAMLAB_DEMO_ROBOTS=str(args.robots),
               PYTHONDONTWRITEBYTECODE='1', SLAM_BENCH_RUN_DIR=str(output / 'benchmark'))
    command = [executable, '--batch', '--minimize', '--no-rendering', '--mode=fast',
               '--stdout', '--stderr', str(world)]
    print('Output:', output, flush=True)
    with (output / 'webots.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            # End only this invocation's process tree, not unrelated simulator sessions.
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
            else:
                process.kill()
            process.wait()
            raise SystemExit('Simulator timed out; inspect ' + str(output / 'webots.log'))
    complete = output / 'simulation_complete.json'
    if code or not complete.is_file() or (output / 'controller_errors.txt').exists():
        raise SystemExit('Simulation did not finish successfully; inspect ' + str(output / 'webots.log'))
    for i in range(1, args.robots + 1):
        for kind in ('estimate', 'groundtruth'):
            path = output / ('bstem%d_%s.csv' % (i, kind))
            if not path.is_file() or len(path.read_text().splitlines()) < 3:
                raise SystemExit('Missing/nonempty trajectory check failed: ' + str(path))
    print(json.dumps(json.loads(complete.read_text()), indent=2))


if __name__ == '__main__':
    main()
