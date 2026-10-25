"""Restore DOOR/D2 pinned Git blobs without vendoring histories or model weights.

Downloads are explicit, size-bounded, verified against per-file hashes, then
packed using the original deterministic recipe. Existing edits are preserved.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def safe_child(root, name):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or '..' in relative.parts or
            ':' in name or '\\' in name or str(relative) != name or '.git' in relative.parts):
        raise ValueError('Unsafe locked source path: ' + name)
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Source path escapes destination: ' + name)
    return target


def download(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'SLAMLab-source-restore'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Source archive exceeds configured download limit')
    return data


def restore(root, limit):
    lock = json.loads((root / 'source_lock.json').read_text(encoding='utf-8'))
    repos = lock.get('repositories') or [dict(path='', url=lock['repository'], commit=lock['commit'])]
    blobs = {}
    for repo in repos:
        prefix = repo['path'] + '/' if repo['path'] else ''
        # Select files owned by this repository, excluding separately pinned subrepositories.
        wanted = {name for name in lock['files'] if name.startswith(prefix) and
                  not any(other['path'] and other['path'] != repo['path'] and
                          other['path'].startswith(prefix) and name.startswith(other['path'] + '/')
                          for other in repos)}
        if not wanted:
            continue
        slug = repo['url'].removeprefix('https://github.com/').removesuffix('.git')
        if repo['url'] != 'https://github.com/' + slug + '.git' or len(slug.split('/')) != 2:
            raise ValueError('Only reviewed GitHub repository URLs are accepted')
        print('Fetching', slug, repo['commit'], flush=True)
        data = download('https://codeload.github.com/' + slug + '/zip/' + repo['commit'], limit)
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            members = {}
            for member in bundle.infolist():
                if member.is_dir():
                    continue
                archive_root, separator, name = member.filename.partition('/')
                if not separator or not archive_root.endswith('-' + repo['commit']):
                    raise ValueError('Archive does not identify pinned commit')
                safe_child(root, name)
                if name in members:
                    raise ValueError('Duplicate archive member')
                members[name] = member
            for name in wanted:
                local = name[len(prefix):]
                if local not in members:
                    raise ValueError('Locked file absent from archive: ' + name)
                if members[local].file_size > limit or sum(len(v) for v in blobs.values()) + members[local].file_size > 4 * limit:
                    raise ValueError('Uncompressed source limit exceeded')
                blob = bundle.read(members[local])
                if hashlib.sha256(blob).hexdigest() != lock['files'][name]:
                    raise ValueError('Pinned file checksum mismatch: ' + name)
                blobs[name] = blob
    if set(blobs) != set(lock['files']):
        raise ValueError('Incomplete source restoration')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as bundle:
        for name in sorted(blobs):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, blobs[name])
    data = buffer.getvalue()
    if hashlib.sha256(data).hexdigest() != lock['archive_sha256']:
        raise ValueError('Rebuilt archive hash differs; no output written. Review compression/version differences.')
    destination = safe_child(root, lock['archive_file'])
    if destination.exists() and destination.read_bytes() != data:
        raise ValueError('Existing archive differs; refusing overwrite')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with destination.open('xb') as stream:
            stream.write(data)
    print('Verified original archive:', destination, '; files:', len(blobs))
    print('Models and transitive build dependencies were not fetched. Review upstream license notices before redistribution.')


def restore_local(root, archive):
    """Accept only the exact original archive and its complete locked blob set."""
    lock = json.loads((root / 'source_lock.json').read_text(encoding='utf-8'))
    if archive.is_symlink():
        raise ValueError('Symlink input is not accepted')
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != lock['archive_sha256']:
        raise ValueError('Local archive differs from source lock')
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        if len(bundle.namelist()) != len(set(bundle.namelist())) or set(bundle.namelist()) != set(lock['files']):
            raise ValueError('Archive members differ from source lock')
        for name, expected in lock['files'].items():
            safe_child(root, name)
            if hashlib.sha256(bundle.read(name)).hexdigest() != expected:
                raise ValueError('Archived blob differs: ' + name)
    target = safe_child(root, lock['archive_file'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError('Existing archive differs; refusing overwrite')
    else:
        with target.open('xb') as stream:
            stream.write(data)
    print('Verified local archive and', len(lock['files']), 'locked files:', target)


def restore_git(root):
    """Sparse filtered fetch avoids fetching model blobs omitted by the source lock."""
    lock = json.loads((root / 'source_lock.json').read_text(encoding='utf-8'))
    repos = lock.get('repositories') or [dict(path='', url=lock['repository'], commit=lock['commit'])]
    blobs = {}
    with tempfile.TemporaryDirectory(prefix='slamlab-sources-') as directory:
        stage = Path(directory)
        for index, repo in enumerate(repos):
            prefix = repo['path'] + '/' if repo['path'] else ''
            wanted = {name for name in lock['files'] if name.startswith(prefix) and
                      not any(other['path'] and other['path'] != repo['path'] and
                              other['path'].startswith(prefix) and name.startswith(other['path'] + '/')
                              for other in repos)}
            checkout = stage / str(index)
            checkout.mkdir()
            def git(*args, input=None):
                return subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(checkout), *args],
                                      input=input, text=True, check=True, timeout=180,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
            print('Sparse fetch:', repo['url'], repo['commit'], flush=True)
            git('init', '--quiet')
            git('remote', 'add', 'origin', repo['url'])
            git('sparse-checkout', 'init', '--no-cone')
            patterns = []
            for name in sorted(wanted):
                local = name[len(prefix):]
                safe_child(checkout, local)
                # Escape sparse-checkout's gitignore pattern metacharacters.
                escaped = ''.join('\\' + c if c in '*?[]#! ' else c for c in local)
                patterns.append('/' + escaped)
            git('sparse-checkout', 'set', '--no-cone', '--stdin', input='\n'.join(patterns) + '\n')
            git('fetch', '--quiet', '--depth=1', '--filter=blob:none', 'origin', repo['commit'])
            git('checkout', '--quiet', '--detach', 'FETCH_HEAD')
            for name in wanted:
                path = safe_child(checkout, name[len(prefix):])
                if path.is_symlink():
                    raise ValueError('Upstream symlinks require separate review: ' + name)
                blob = path.read_bytes()
                # Git may convert text line endings; retrieve exact blobs for the archive.
                if hashlib.sha256(blob).hexdigest() != lock['files'][name]:
                    blob = subprocess.check_output(['git', '-C', str(checkout), 'show',
                                                    repo['commit'] + ':' + name[len(prefix):]], timeout=30)
                if hashlib.sha256(blob).hexdigest() != lock['files'][name]:
                    raise ValueError('Fetched file differs from lock: ' + name)
                blobs[name] = blob
        archive = stage / 'original.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            for name in sorted(blobs):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, blobs[name])
        restore_local(root, archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('algorithm', choices=('door-slam', 'd2slam'))
    parser.add_argument('--max-download-mib', type=int, default=64)
    parser.add_argument('--local-archive', type=Path, help='Offline exact source archive from a previously verified cache')
    parser.add_argument('--transport', choices=('git', 'archive'), default='git',
                        help='Filtered sparse Git fetch (default), or size-bounded full upstream ZIP')
    args = parser.parse_args()
    if not 1 <= args.max_download_mib <= 512:
        parser.error('Download cap must be 1..512 MiB per source repository')
    name = 'Door Slam' if args.algorithm == 'door-slam' else 'D2 Slam'
    root = ROOT / 'experiments/ab3' / name
    if args.local_archive:
        restore_local(root, args.local_archive)
    elif args.transport == 'git':
        restore_git(root)
    else:
        restore(root, args.max_download_mib * 1024 * 1024)


if __name__ == '__main__':
    main()
