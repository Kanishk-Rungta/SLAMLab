"""Restore an algorithm's pinned upstream sources after a fresh Git clone (run automatically by PREPARE/BUILD/RUN).

The large upstream sources are not stored in Git. Every package keeps its locks instead:
  source_lock.json                    main repository, exact commit, sha256 of every file
  algorithm/workspace/<name>.lock.json  each workspace repository (Kimera-Multi, Swarm-SLAM, DVM-SLAM)
  third_party/models/model_lock.json  model weights (Swarm-SLAM)
Missing pieces are downloaded from GitHub at the locked commit and every extracted file is checked
against its lock hash; nothing is restored if any file differs. GitHub does not guarantee
byte-identical zip archives over time, so when a re-downloaded archive differs but every file in it
matches the lock, the new archive digest is recorded next to it (<archive>.restored.json) and
source_tools accepts it. Existing files are never overwritten.
"""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile


def download(url, what):
    print('Downloading %s (first run only) ...' % what, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'AB3-benchmark-restore'})
    chunks = []
    with urllib.request.urlopen(request, timeout=600) as response:
        while True:
            chunk = response.read(4 * 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    return b''.join(chunks)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def restore_package(lock_file, archive, source, label):
    """Download and extract one locked repository if its archive or extracted files are missing."""
    lock = json.loads(Path(lock_file).read_text(encoding='utf-8'))
    archive, source = Path(archive), Path(source)
    expected = lock['files']
    complete = archive.is_file() and source.is_dir() and all((source / name).is_file() for name in expected)
    if complete:
        return False
    repo = lock['repository'].rstrip('/').removeprefix('https://github.com/').removesuffix('.git')
    data = archive.read_bytes() if archive.is_file() else download(
        'https://codeload.github.com/%s/zip/%s' % (repo, lock['commit']), '%s @ %s' % (label, lock['commit'][:12]))
    blobs = {}
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        for member in bundle.infolist():
            if member.is_dir():
                continue
            root, _, name = member.filename.partition('/')
            if not root.endswith('-' + lock['commit']) or not name:
                raise RuntimeError('Downloaded archive does not identify the locked commit: ' + member.filename)
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError('Unsafe archive path: ' + name)
            blobs[name] = bundle.read(member)
    if set(blobs) != set(expected):
        raise RuntimeError('%s: downloaded files differ from the lock (%d extra, %d missing)' % (
            label, len(set(blobs) - set(expected)), len(set(expected) - set(blobs))))
    bad = [name for name, blob in blobs.items() if sha256(blob) != expected[name]]
    if bad:
        raise RuntimeError('%s: %d downloaded files differ from the lock, e.g. %s' % (label, len(bad), bad[0]))
    for name, blob in blobs.items():
        target = source / name
        if target.exists():
            continue                      # never overwrite; verification reports any difference
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    if not archive.is_file():
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(data)
    digest = sha256(archive.read_bytes())
    if digest != lock['archive_sha256']:
        Path(str(archive) + '.restored.json').write_text(json.dumps({
            'archive_sha256': digest, 'locked_archive_sha256': lock['archive_sha256'],
            'note': 'GitHub re-generated the archive; every extracted file matches the lock.'}, indent=2) + '\n')
    print('Restored %s: %d files verified against the lock.' % (label, len(expected)), flush=True)
    return True


def restore_model(root):
    lock_file = Path(root) / 'third_party/models/model_lock.json'
    if not lock_file.exists():
        return False
    lock = json.loads(lock_file.read_text())
    path = lock_file.parent / lock['filename']
    if path.is_file():
        return False
    data = download(lock['source_url'], lock['filename'])
    if sha256(data) != lock['sha256']:
        raise RuntimeError('Downloaded model differs from model_lock.json: ' + lock['filename'])
    path.write_bytes(data)
    return True


def restore_algorithm(root):
    root = Path(root)
    changed = restore_package(root / 'source_lock.json', root / 'algorithm/upstream-original.zip',
                              root / 'algorithm/upstream', root.name)
    for lock in sorted((root / 'algorithm/workspace').glob('*.lock.json')):
        name = lock.name.removesuffix('.lock.json')
        changed |= restore_package(lock, lock.parent / (name + '.zip'), lock.parent / name, '%s / %s' % (root.name, name))
    changed |= restore_model(root)
    return changed


if __name__ == '__main__':
    import sys
    for folder in sys.argv[1:]:
        restore_algorithm(folder)
