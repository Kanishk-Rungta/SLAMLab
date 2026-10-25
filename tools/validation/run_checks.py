"""Run the same lightweight offline checks locally and in CI."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_repository import repository_files


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', MPLBACKEND='Agg')
    commands = [
        ['tools/validation/check_repository.py'],
        ['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
        ['-m', 'unittest', 'discover', '-s', 'experiments/ab3/Standard Environment/benchmark/tests', '-v'],
        ['-m', 'unittest', 'discover', '-s', 'experiments/ab3/Live Integrations', '-p', 'test_live_transport.py', '-v'],
        ['-m', 'unittest', 'discover', '-s', 'experiments/ab3/Live Integrations', '-p', 'test_native_outputs.py', '-v'],
        ['-m', 'unittest', 'discover', '-s', 'experiments/ab3/Live Integrations', '-p', 'test_stereo_output.py', '-v'],
        ['experiments/ab3/Standard Environment/tools/standard_manifest.py'],
    ]
    for command in commands:
        print('Running:', ' '.join(command), flush=True)
        subprocess.run([sys.executable, '-B', *command], cwd=ROOT, env=env, check=True)
    bash = shutil.which('bash')
    if os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe'
        bash = str(candidate) if candidate.exists() else None
    if bash:
        scripts = [p for p in repository_files() if p.suffix in ('.sh', '.command')]
        for path in scripts:
            subprocess.run([bash, '-n', path.as_posix()], cwd=ROOT, check=True)
        print('Shell syntax passed:', len(scripts), 'scripts')
    else:
        print('Shell syntax skipped: bash unavailable')
    print('All available lightweight checks passed; native SLAM and GUI execution are separate local checks.')


if __name__ == '__main__':
    main()
