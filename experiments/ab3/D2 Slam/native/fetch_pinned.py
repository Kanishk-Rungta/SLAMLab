"""Fetch one dependency at the exact commit recorded in source_lock.json (inside the build)."""
import json
from pathlib import Path
import subprocess
import sys


def main(name, destination):
    spec = json.loads(Path('/opt/benchmark/source_lock.json').read_text())['dependencies'][name]
    destination = Path(destination)
    subprocess.check_call(['git', 'init', '-q', str(destination)])
    subprocess.check_call(['git', '-C', str(destination), 'remote', 'add', 'origin', spec['url']])
    subprocess.check_call(['git', '-C', str(destination), 'fetch', '-q', '--depth', '1', 'origin', spec['commit']])
    subprocess.check_call(['git', '-C', str(destination), 'checkout', '-q', '--detach', 'FETCH_HEAD'])
    actual = subprocess.check_output(['git', '-C', str(destination), 'rev-parse', 'HEAD']).decode().strip()
    if actual != spec['commit']:
        raise RuntimeError('%s resolved to %s, expected %s' % (name, actual, spec['commit']))
    print('Fetched %s at %s' % (name, actual))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
