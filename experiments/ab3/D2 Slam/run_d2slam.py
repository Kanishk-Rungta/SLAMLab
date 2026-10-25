"""Official D2SLAM on the unchanged AB3 standard (Docker native runtime, CPU).

Use --prepare-only to check the sources/configuration without Docker; the native
image is built and validated on the machine that runs the benchmark.
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
from calibration import generate, write
from patch_runtime import patch
from docker_runtime import prepare_image, Runtime, build_identity
import launcher_common as lc

CONTROLLER = 'd2slam'


def check_adapters():
    """The documented adapters still apply to the pinned sources (as the Docker build will)."""
    import tempfile
    names = ['d2frontend/CMakeLists.txt', 'd2frontend/include/d2frontend/CNN/onnx_generic.h',
             'd2frontend/src/CNN/superpoint_common.cpp', 'd2frontend/src/CNN/superpoint_onnx.cpp',
             'd2frontend/src/loop_cam.cpp', 'd2frontend/src/d2frontend_params.cpp',
             'd2frontend/include/d2frontend/d2frontend.h', 'd2frontend/src/d2frontend.cpp',
             'd2vins/src/d2vins_node.cpp', 'd2pgo/src/d2pgo_node.cpp',
             'd2common/src/solver/ConsensusSolver.cpp',
             'd2common/src/solver/ARock.cpp',
             'd2common/include/d2common/d2frontend_types.h']
    with tempfile.TemporaryDirectory() as directory:
        for name in names:
            target = Path(directory)/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/'algorithm/D2SLAM'/name, target)
        patch(Path(directory))


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
    check_adapters()
    profile = json.loads((ROOT/'config/benchmark.json').read_text(encoding='utf-8'))
    calibration = generate(profile=profile)
    if any(value < 0 for value in (args.seconds, args.idle_seconds)) or args.live_map_seconds <= 0:
        raise SystemExit('Time limits must be nonnegative; live map interval must be positive')
    if args.prepare_only:
        write(ROOT/'build/native_config', calibration)
        print('D2SLAM sources, adapters and standard configuration prepared in build/native_config. '
              'Native build/run remains unvalidated.')
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
    first_port = profile['first_port']
    config = {'output_dir': str(run), 'robots': args.robots, 'max_seconds': args.seconds,
              'idle_seconds': args.idle_seconds, 'live_map_wall_seconds': args.live_map_seconds,
              'profile': profile, 'upstream_commit': manifest['commit'],
              'native_host': '127.0.0.1', 'native_ports': list(range(first_port, first_port+args.robots))}
    lc.write_json(run/'run_config.json', config)
    lc.write_json(run/'bench_config.json', {'gt_map': str(lc.GT_MAP), 'max_sim_seconds': args.seconds})
    lc.write_json(run/'native_build.json', {'image': image, 'image_id': image_id,
                  'build_fingerprint': build_identity(), 'cnn_backend': 'ONNX Runtime CPU',
                  'runtime_validation': 'target-machine run required'})
    shutil.copyfile(ROOT/'source_lock.json', run/'source_lock.json')
    for command in ([sys.executable, lc.SE/'tools/make_algorithm_world.py', '--controller', CONTROLLER, '--robots', args.robots],
                    [sys.executable, lc.SE/'tools/install_controller.py', '--name', CONTROLLER,
                     '--source', ROOT/'webots_controller/d2slam.py', '--python', sys.executable],
                    [sys.executable, lc.SE/'tools/install_controller.py', '--name', 'bench_supervisor',
                     '--source', lc.SE/'benchmark/bench_supervisor.py', '--python', sys.executable]):
        if lc.run_quiet(command):
            raise SystemExit('Standard world/controller preparation failed')
    world = lc.SE/'webots/worlds'/('ab3_standard__%s.wbt' % CONTROLLER)
    cells = '\n'.join("<figure><figcaption>Robot %d — its local map frame</figcaption><img data-src='robot_%d/live_map.png'></figure>" % (n, n)
                      for n in range(1, args.robots+1))
    page = (ROOT/'live_view_template.html').read_text(encoding='utf-8').replace('{ROBOTS}', str(args.robots)).replace('{SCENARIO}', args.scenario).replace('{CELLS}', cells)
    (run/'live_view.html').write_text(page, encoding='utf-8')
    env = lc.bench_environment(run, scenario_file, webots_home, {'D2SLAM_RUN_CONFIG': str(run/'run_config.json')})
    runtime = Runtime(image, run, args.robots, {'robots': args.robots, 'profile': profile},
                      calibration['files'], first_port)
    simulation_started = False
    viewer = None
    try:
        runtime.start()  # Native nodes, CNN models and transport ready BEFORE physics starts.
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
