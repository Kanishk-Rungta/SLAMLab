"""Original visual DOOR-SLAM on the unchanged AB3 standard (Docker native runtime).

Use --prepare-only here; build and validate the native image on the target laptop.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'tools'), str(ROOT.parent/'Standard Environment/tools')]
from upstream_source import verify
from calibration import generate
from docker_runtime import prepare_image, Runtime, build_identity
import launcher_common as lc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robots', type=int, choices=range(1, 11), default=10)
    parser.add_argument('--scenario', default='baseline')
    parser.add_argument('--seconds', type=int, default=0)
    parser.add_argument('--idle-seconds', type=int, default=1800)
    parser.add_argument('--live-map-seconds', type=int, default=300)
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--evaluate-run')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--rebuild-image', action='store_true')
    args = parser.parse_args()
    if args.evaluate_run:
        if not (Path(args.evaluate_run)/'benchmark').is_dir():
            raise SystemExit('Not a run folder: '+args.evaluate_run)
        lc.evaluate(args.evaluate_run)
        return
    manifest = verify()
    calibration = generate()
    profile = json.loads((ROOT/'config/benchmark.json').read_text())
    if any(value < 0 for value in (args.seconds, args.idle_seconds)) or args.live_map_seconds <= 0:
        raise SystemExit('Time limits must be nonnegative; live map interval must be positive')
    if args.prepare_only:
        output = ROOT/'build'
        output.mkdir(exist_ok=True)
        lc.write_json(output/'stereo_calibration.json', calibration)
        print('Original sources and standard stereo calibration prepared. Native build/run remains unvalidated.')
        return
    scenario_file = lc.SE/'benchmark/scenarios'/('%s.json' % args.scenario)
    if not scenario_file.exists():
        raise SystemExit('Unknown scenario: '+args.scenario)
    if not args.build_only:
        webots_home, webots_exe = lc.find_webots()
    image, image_id = prepare_image(force=args.rebuild_image)
    if args.build_only:
        print('Built native image:', image, image_id)
        return
    # Validate Windows recursive-move paths before using the shared backup step.
    for name in ('runs', 'backup_runs'):
        directory = ROOT/name
        if directory.exists() and directory.resolve().parent != ROOT.resolve():
            raise SystemExit('Run directory resolves outside this algorithm folder')
    runs = ROOT/'runs'
    if runs.exists():
        for previous in runs.iterdir():
            if previous.is_dir() and previous.resolve().parent != runs.resolve():
                raise SystemExit('Previous run resolves outside the run directory')
    lc.backup_previous_runs(ROOT)
    run = lc.new_run_dir(ROOT, args.scenario, args.robots)
    lc.check_standard(run)
    if not json.loads((run/'standard_environment.json').read_text())['matches_standard']:
        raise SystemExit('The standard environment changed; refusing an incomparable original-code run')
    config = {'output_dir': str(run), 'robots': args.robots, 'max_seconds': args.seconds,
              'idle_seconds': args.idle_seconds, 'live_map_wall_seconds': args.live_map_seconds,
              'profile': profile, 'upstream_commit': manifest['repositories'][0]['commit'],
              'native_host': '127.0.0.1', 'native_ports': list(range(47000, 47000+args.robots))}
    lc.write_json(run/'run_config.json', config)
    lc.write_json(run/'bench_config.json', {'gt_map': str(lc.GT_MAP), 'max_sim_seconds': args.seconds})
    lc.write_json(run/'native_build.json', {'image': image, 'image_id': image_id,
                  'build_fingerprint': build_identity(), 'runtime_validation': 'target-laptop run required'})
    shutil.copyfile(ROOT/'source_lock.json', run/'source_lock.json')
    shutil.copyfile(ROOT/'config/dependencies.json', run/'native_dependencies.json')
    controller = 'door_slam_original'
    for command in ([sys.executable, lc.SE/'tools/make_algorithm_world.py', '--controller', controller, '--robots', args.robots],
                    [sys.executable, lc.SE/'tools/install_controller.py', '--name', controller,
                     '--source', ROOT/'webots_controller/door_slam_original.py', '--python', sys.executable],
                    [sys.executable, lc.SE/'tools/install_controller.py', '--name', 'bench_supervisor',
                     '--source', lc.SE/'benchmark/bench_supervisor.py', '--python', sys.executable]):
        if lc.run_quiet(command):
            raise SystemExit('Standard world/controller preparation failed')
    world = lc.SE/'webots/worlds/ab3_standard__door_slam_original.wbt'
    cells = '\n'.join("<figure><figcaption>Robot %d — its local map frame</figcaption><img data-src='robot_%d/live_map.png'></figure>" % (n, n)
                      for n in range(1, args.robots+1))
    page = (ROOT/'live_view_template.html').read_text(encoding='utf-8').replace('{ROBOTS}', str(args.robots)).replace('{SCENARIO}', args.scenario).replace('{CELLS}', cells)
    (run/'live_view.html').write_text(page, encoding='utf-8')
    env = lc.bench_environment(run, scenario_file, webots_home,
                              {'DOOR_ORIGINAL_RUN_CONFIG': str(run/'run_config.json')})
    runtime = Runtime(image, run, args.robots, {'robots': args.robots, 'profile': profile, 'calibration': calibration})
    simulation_started = False
    viewer = None
    try:
        runtime.start()  # Native services, model and transport ready BEFORE physics starts.
        viewer = subprocess.Popen([sys.executable, str(ROOT/'tools/live_view.py'), str(run),
                                   '--robots', str(args.robots), '--period', str(args.live_map_seconds)])
        if not args.no_browser:
            lc.open_live_view(run/'live_view.html')
        print('Run folder:', run, flush=True)
        simulation_started = True
        lc.run_webots(webots_exe, world, env, run, gui=args.gui, live_seconds=args.live_map_seconds)
    finally:
        try:
            runtime.close()
        finally:
            try:
                if viewer is not None:
                    (run/'VIEW_STOP').touch()
                    try:
                        viewer.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        viewer.terminate()
                        viewer.wait(timeout=10)
                    # Refresh after shutdown even if the background renderer crashed.
                    from live_view import render
                    render(run, args.robots, final=True)
            finally:
                if simulation_started and (run/'benchmark/run_meta.json').exists():
                    lc.evaluate(run, open_folder=not args.no_browser)



if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error))
