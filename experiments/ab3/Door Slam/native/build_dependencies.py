"""Fetch pinned upstream build dependencies inside the Linux container."""
import json
from pathlib import Path
import subprocess

from download_weights import download_file, unpack_weights


def main():
    lock = json.loads(Path('/opt/benchmark/config/dependencies.json').read_text())
    root = Path('/opt/deps')
    root.mkdir(exist_ok=True)
    for name in ('gtsam', 'rtabmap', 'rtabmap_ros', 'buzz', 'netvlad'):
        spec = lock[name]
        destination = root / name
        subprocess.check_call(['git', 'init', str(destination)])
        subprocess.check_call(['git', '-C', str(destination), 'remote', 'add', 'origin', spec['url']])
        subprocess.check_call(['git', '-C', str(destination), 'fetch', '--depth', '1', 'origin', spec['commit']])
        subprocess.check_call(['git', '-C', str(destination), 'checkout', '--detach', 'FETCH_HEAD'])
    weights = root / 'weights.zip'
    download_file(lock['netvlad_weights_url'], weights)
    digest = unpack_weights(weights, root / 'netvlad/checkpoints')
    Path('/opt/benchmark/weights_sha256.txt').write_text(digest + '\n')
    weights.unlink()


if __name__ == '__main__':
    main()
