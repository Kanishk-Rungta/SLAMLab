"""Export/verify unchanged Git blobs from the official DOOR-SLAM runtime sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
REPOSITORIES = [
    ('', 'https://github.com/MISTLab/DOOR-SLAM.git'),
    ('tx2-setup/slam_front_end', 'https://github.com/bramtoula/multi_robot_SLAM_separators.git'),
    ('tx2-setup/robust_pose_graph_optimization', 'https://github.com/lajoiepy/robust_distributed_slam_module.git'),
    ('tx2-setup/robust_pose_graph_optimization/buzz_slam', 'https://github.com/lajoiepy/Buzz_SLAM.git'),
    ('tx2-setup/robust_pose_graph_optimization/buzz_slam/robust_distributed_mapper',
     'https://github.com/lajoiepy/robust_distributed_mapper.git'),
]


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', '-C', str(repo), *args])


def export(checkout):
    manifest = {'runtime_validated': False, 'repositories': [], 'files': {}}
    destination = ROOT / 'algorithm/DOOR-SLAM'
    for relative, url in REPOSITORIES:
        repo = checkout / relative
        commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
        manifest['repositories'].append({'path': relative, 'url': url, 'commit': commit})
        for entry in git(repo, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
            if not entry:
                continue
            info, name = entry.split(b'\t', 1)
            if info.split()[1] != b'blob':
                continue  # Submodules are exported separately at their pinned commits.
            name = name.decode('utf-8')
            if not relative and name.startswith('simulation/'):
                continue  # Separate ARGoS implementation is not the Webots visual stack.
            data = git(repo, 'cat-file', 'blob', info.split()[2].decode())
            path = destination / relative / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            manifest['files'][path.relative_to(destination).as_posix()] = hashlib.sha256(data).hexdigest()
    archive = ROOT/'algorithm/DOOR-SLAM-original.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for relative in sorted(manifest['files']):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (destination/relative).read_bytes())
    manifest['archive_file'] = archive.relative_to(ROOT).as_posix()
    manifest['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / 'source_lock.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('Exported %d exact upstream files from %d repositories.' %
          (len(manifest['files']), len(manifest['repositories'])))


def verify(root=ROOT):
    manifest = json.loads((root / 'source_lock.json').read_text(encoding='utf-8'))
    destination = root / 'algorithm/DOOR-SLAM'
    archive = root/manifest['archive_file']
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise RuntimeError('Original source archive is missing or differs from source_lock.json')
    # Rehydrate missing files after a fresh Git clone. Existing edits are never
    # overwritten: the normal verification below rejects them for review.
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(manifest['files']):
            raise RuntimeError('Source archive file list differs from source_lock.json')
        for relative, expected in manifest['files'].items():
            name = Path(relative)
            if name.is_absolute() or '..' in name.parts:
                raise RuntimeError('Invalid source archive path')
            path = destination/name
            if not path.is_file():
                data = bundle.read(relative)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise RuntimeError('Source archive blob differs: '+relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    errors = []
    for relative, expected in manifest['files'].items():
        path = destination / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(relative)
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    errors.extend(sorted(actual-set(manifest['files'])))
    if errors:
        raise RuntimeError('Upstream snapshot changed: '+', '.join(errors[:20]))
    print('Verified %d unchanged upstream source files.' % len(manifest['files']))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', type=Path, help='Existing recursive official checkout to export')
    args = parser.parse_args()
    if args.export:
        export(args.export.resolve())
    verify()
