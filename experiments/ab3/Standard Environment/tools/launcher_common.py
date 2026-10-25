"""Cross-platform launcher helpers (macOS, Linux, Windows) shared by every algorithm's run_<algo>.py.

The Windows .cmd launchers use the equivalent PowerShell (common.ps1 + run_<algo>.ps1); the macOS
.command launchers use this module. Both do the same steps in the same order (BENCHMARK_GUIDE.md §4).
Run with the benchmark Python environment (.venv), which tools/bench_python.sh creates on macOS/Linux.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

SE = Path(__file__).resolve().parent.parent          # Standard Environment
FB = SE.parent                                       # Benchmark
GT_MAP = SE / 'ground_truth' / 'ab3_gt_map.npz'
SYSTEM = platform.system()                           # 'Darwin', 'Linux', 'Windows'


def say(text, colour=None):
    codes = {'cyan': '36', 'green': '32', 'yellow': '33'}
    if colour and sys.stdout.isatty() and SYSTEM != 'Windows':
        text = '\033[%sm%s\033[0m' % (codes[colour], text)
    print(text, flush=True)


def find_webots():
    """(WEBOTS_HOME, executable) of Webots R2025a."""
    homes = [os.environ['WEBOTS_HOME']] if os.environ.get('WEBOTS_HOME') else []
    if SYSTEM == 'Darwin':
        homes += ['/Applications/Webots.app', str(Path.home() / 'Applications' / 'Webots.app')]
        rel = ['Contents/MacOS/webots']
    elif SYSTEM == 'Windows':
        homes += [os.path.join(os.environ.get(v, ''), 'Webots') for v in ('ProgramFiles', 'ProgramFiles(x86)')]
        homes += [os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Webots')]
        rel = ['msys64/mingw64/bin/webots.exe']
    else:
        homes += ['/usr/local/webots', '/opt/webots', '/snap/webots/current/usr/share/webots']
        rel = ['webots']
    for home in homes:
        for r in rel:
            exe = Path(home) / r
            if exe.exists():
                return str(home), str(exe)
    raise SystemExit('Webots R2025a was not found. Install it from https://cyberbotics.com '
                     '(default location, e.g. /Applications/Webots.app on macOS), or set WEBOTS_HOME.')


def webots_running():
    try:
        import psutil
    except ImportError:
        return False
    for proc in psutil.process_iter(['name']):
        name = (proc.info.get('name') or '').lower()
        if name.startswith('webots'):
            return True
    return False


def run_quiet(args):
    """Run a helper script; show its output only if it fails."""
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True)
    if result.returncode != 0:
        print(result.stdout)
    return result.returncode


def open_path(path):
    path = str(path)
    try:
        if SYSTEM == 'Darwin':
            subprocess.Popen(['open', path])
        elif SYSTEM == 'Windows':
            os.startfile(path)
        else:
            subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def evaluate(run, open_folder=True):
    run = Path(run)
    bench = run / 'benchmark'
    # Final overview, ground-truth trajectories and error series for algorithms that do not write them.
    run_quiet([sys.executable, SE / 'tools' / 'run_outputs.py', 'finalize', run])
    say('Evaluating the benchmark ...', 'cyan')
    run_quiet([sys.executable, SE / 'benchmark' / 'evaluate.py', bench, '--gt-map', GT_MAP, '--name', run.name])
    if (bench / 'report.md').exists():
        shutil.copyfile(str(bench / 'report.md'), str(run / 'benchmark_report.md'))
        shutil.copyfile(str(bench / 'metrics.json'), str(run / 'benchmark_metrics.json'))
        say('Benchmark report: %s' % (run / 'benchmark_report.md'), 'green')
    else:
        say('Evaluation did not produce a report (see messages above).', 'yellow')
    run_quiet([sys.executable, SE / 'tools' / 'run_outputs.py', 'summary', run])   # run_summary.json + RUN_SUMMARY.md
    if open_folder:
        open_path(run)


def backup_previous_runs(algo_dir):
    """Evaluate any never-evaluated earlier run, then move every earlier run to backup_runs/."""
    runs, backup = Path(algo_dir) / 'runs', Path(algo_dir) / 'backup_runs'
    runs.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)
    for old in sorted(p for p in runs.iterdir() if p.is_dir()):
        if (old / 'benchmark' / 'run_meta.json').exists() and not (old / 'benchmark_report.md').exists():
            say('Previous run %s was never evaluated; evaluating it first ...' % old.name)
            evaluate(old, open_folder=False)
        dest = backup / old.name
        if dest.exists():
            dest = backup / (old.name + '_' + time.strftime('%H%M%S'))
        try:
            shutil.move(str(old), str(dest))
            say('Previous run saved to backup_runs/%s' % dest.name)
        except OSError:
            say('Could not move %s (a file is in use); it stays in runs/.' % old.name, 'yellow')


def new_run_dir(algo_dir, scenario, robots):
    run = Path(algo_dir) / 'runs' / ('%s_%s_%drobots' % (time.strftime('%Y-%m-%d_%H-%M-%S'), scenario, robots))
    (run / 'benchmark').mkdir(parents=True)
    (Path(algo_dir) / 'runs' / 'LATEST.txt').write_text(str(run) + '\n', encoding='ascii')
    return run


def check_standard(run):
    if run_quiet([sys.executable, SE / 'tools' / 'standard_manifest.py', '--check', run / 'standard_environment.json']):
        say('The standard environment was modified: this run is not comparable with others.', 'yellow')
    else:
        print('standard environment verified')


def prepare_world_and_controllers(controller, source, robots):
    """The algorithm's run world (standard world + controller name) and its controllers."""
    run_quiet([sys.executable, SE / 'tools' / 'make_algorithm_world.py', '--controller', controller, '--robots', robots])
    run_quiet([sys.executable, SE / 'tools' / 'install_controller.py', '--name', controller, '--source', source,
               '--python', sys.executable])
    run_quiet([sys.executable, SE / 'tools' / 'install_controller.py', '--name', 'bench_supervisor',
               '--source', SE / 'benchmark' / 'bench_supervisor.py', '--python', sys.executable])
    return SE / 'webots' / 'worlds' / ('ab3_standard__%s.wbt' % controller)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8')


def bench_environment(run, scenario_file, webots_home, extra=None):
    """Environment variables inherited by Webots and its controllers."""
    env = dict(os.environ)
    env.update({'STANDARD_ENV': str(SE), 'SLAM_BENCH_HOME': str(SE / 'benchmark'),
                'SLAM_BENCH_RUN_DIR': str(Path(run) / 'benchmark'),
                'SLAM_BENCH_CONFIG': str(Path(run) / 'bench_config.json'),
                'SLAM_BENCH_SCENARIO': str(scenario_file), 'WEBOTS_HOME': str(webots_home)})
    env['PATH'] = os.path.dirname(sys.executable) + os.pathsep + env.get('PATH', '')
    env.update(extra or {})
    return env


def run_webots(exe, world, env, run, gui=False, live_seconds=None):
    """Start Webots on the world, keep the computer awake (macOS), print progress every minute, wait.

    live_seconds: every this many wall seconds, refresh the run outputs built from the benchmark
    recordings (overview + overview_history + coverage_history when the algorithm does not draw its
    own overview, and robot_N/map_history copies). Leave None for algorithms that do all of it themselves.
    """
    args = [exe, '--stdout', '--stderr', '--mode=fast']
    if not gui:
        args += ['--batch', '--minimize', '--no-rendering']
    args.append(str(world))
    log = open(str(Path(run) / 'webots_output.txt'), 'w')      # never a pipe: Webots would block on it
    proc = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if SYSTEM == 'Darwin':
        # Sleep would kill the simulation; caffeinate keeps the Mac awake while Webots runs.
        subprocess.Popen(['caffeinate', '-i', '-w', str(proc.pid)])
    started = time.time()
    last_refresh = -1e9
    while proc.poll() is None:
        try:
            proc.wait(timeout=60)
            break
        except subprocess.TimeoutExpired:
            pass
        minutes = int((time.time() - started) / 60)
        line = '%02d:%02d elapsed' % (minutes // 60, minutes % 60)
        try:
            status = json.loads((Path(run) / 'robot_1' / 'status.json').read_text())
            line += ' | simulated %.1f min' % (status['time'] / 60)
        except Exception:
            pass
        try:
            last = (Path(run) / 'coverage_history.jsonl').read_text().strip().splitlines()[-1]
            c = json.loads(last)
            line += ' | covered %.0f m2 (%.1f%% of the floor)' % (c['covered_m2'], c['covered_pct'])
        except Exception:
            pass
        if (Path(run) / 'controller_errors.txt').exists():
            line += ' | CONTROLLER ERRORS: see controller_errors.txt'
        print(line, flush=True)
        try:
            with open(str(Path(run) / 'progress_log.txt'), 'a') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + line + '\n')
        except OSError:
            pass
        wall = time.time() - started
        if live_seconds and wall - last_refresh >= live_seconds:
            last_refresh = wall
            if run_quiet([sys.executable, SE / 'tools' / 'run_outputs.py', 'refresh', run, '--wall-seconds', '%.1f' % wall]):
                say('Live overview refresh failed (the run continues).', 'yellow')
    log.close()


def open_live_view(path):
    webbrowser.open(Path(path).resolve().as_uri())
