"""Export/verify unchanged Git blobs of the official D2SLAM repository.

The pinned commit's files (except models/, whose ONNX networks are byte-identical
to the pinned authors' models.zip, see source_lock.json) are kept in a checksummed
archive so a fresh clone of this project can rebuild without depending on GitHub.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = 'https://github.com/HKUST-Aerial-Robotics/D2SLAM.git'
EXCLUDED_PREFIXES = ('models/',)


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', '-C', str(repo), *args])


def export(checkout):
    commit = git(checkout, 'rev-parse', 'HEAD').decode().strip()
    destination = ROOT / 'algorithm/D2SLAM'
    manifest = {'repository': REPOSITORY, 'commit': commit, 'excluded': list(EXCLUDED_PREFIXES),
                'runtime_validated': False, 'files': {}}
    for entry in git(checkout, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not entry:
            continue
        info, name = entry.split(b'\t', 1)
        if info.split()[1] != b'blob':
            raise RuntimeError('Unexpected submodule in D2SLAM: %s' % name.decode())
        name = name.decode('utf-8')
        if name.startswith(EXCLUDED_PREFIXES):
            continue
        data = git(checkout, 'cat-file', 'blob', info.split()[2].decode())
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest['files'][name] = hashlib.sha256(data).hexdigest()
    archive = ROOT / 'algorithm/D2SLAM-original.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for relative in sorted(manifest['files']):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (destination / relative).read_bytes())
    manifest['archive_file'] = archive.relative_to(ROOT).as_posix()
    manifest['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    lock = ROOT / 'source_lock.json'
    previous = json.loads(lock.read_text(encoding='utf-8')) if lock.exists() else {}
    for key in ('models', 'dependencies'):
        if key in previous:
            manifest[key] = previous[key]
    lock.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Exported %d exact upstream files at %s.' % (len(manifest['files']), commit))


def verify(root=ROOT):
    manifest = json.loads((root / 'source_lock.json').read_text(encoding='utf-8'))
    destination = root / 'algorithm/D2SLAM'
    archive = root / manifest['archive_file']
    if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise RuntimeError('Original D2SLAM archive is missing or differs from source_lock.json')
    # Rehydrate missing files after a fresh Git clone. Existing edits are never
    # overwritten: the verification below rejects them for review.
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(manifest['files']):
            raise RuntimeError('Source archive file list differs from source_lock.json')
        for relative, expected in manifest['files'].items():
            name = Path(relative)
            if name.is_absolute() or '..' in name.parts:
                raise RuntimeError('Invalid source archive path')
            path = destination / name
            if not path.is_file():
                data = bundle.read(relative)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise RuntimeError('Source archive blob differs: ' + relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    errors = []
    for relative, expected in manifest['files'].items():
        path = destination / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(relative)
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    errors.extend(sorted(actual - set(manifest['files'])))
    if errors:
        raise RuntimeError('Upstream D2SLAM snapshot changed: ' + ', '.join(errors[:20]))
    print('Verified %d unchanged upstream D2SLAM files.' % len(manifest['files']))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', type=Path, help='Existing official D2SLAM checkout to export')
    args = parser.parse_args()
    if args.export:
        export(args.export.resolve())
    verify()
