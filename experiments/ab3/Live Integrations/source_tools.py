"""Read-only verification of the portable, pinned upstream source packages."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_child(root, name):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or '..' in relative.parts
            or ':' in name or '\\' in name or str(relative) != name):
        raise ValueError('Unsafe source path: ' + name)
    root = Path(root).resolve()
    target = root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError('Source path escapes package: ' + name)
    return target


def verify_package(lock_file, archive, source):
    """Check the archive AND its extracted files; never repair user edits implicitly."""
    lock = json.loads(Path(lock_file).read_text(encoding='utf-8'))
    commit = lock['commit']
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Source lock must identify a full Git commit')
    archive = Path(archive)
    digest = sha256(archive.read_bytes())
    restored = Path(str(archive) + '.restored.json')
    accepted = {lock['archive_sha256']}
    if restored.exists():          # re-downloaded archive; its files are still checked against the lock below
        accepted.add(json.loads(restored.read_text(encoding='utf-8'))['archive_sha256'])
    if digest not in accepted:
        raise ValueError('Source archive checksum mismatch: ' + str(archive))
    expected = lock['files']
    seen = set()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            if member.is_dir():
                continue
            parts = member.filename.split('/', 1)
            if len(parts) != 2:
                raise ValueError('Unexpected archive root')
            if not parts[0].endswith('-' + commit):
                raise ValueError('Archive root does not identify the locked commit')
            name = parts[1]
            path = safe_child(source, name)
            if name in seen or name not in expected:
                raise ValueError('Unexpected or duplicate archive member: ' + name)
            seen.add(name)
            blob = bundle.read(member)
            if sha256(blob) != expected[name]:
                raise ValueError('Archived source checksum mismatch: ' + name)
            if not path.is_file() or sha256(path.read_bytes()) != expected[name]:
                raise ValueError('Extracted source missing or modified: ' + str(path))
    if seen != set(expected):
        raise ValueError('Source archive entries differ from lock')
    # Added implementation files also affect the build. Refuse untracked additions.
    extras = [p.relative_to(source).as_posix() for p in Path(source).rglob('*')
              if p.is_file() and p.relative_to(source).as_posix() not in expected]
    if extras:
        raise ValueError('Untracked source files: ' + ', '.join(extras[:5]))
    return {'repository': lock['repository'], 'commit': commit,
            'archive_sha256': lock['archive_sha256'], 'files_checked': len(expected)}


def verify_algorithm(root):
    root = Path(root)
    main = verify_package(root / 'source_lock.json', root / 'algorithm/upstream-original.zip',
                          root / 'algorithm/upstream')
    dependencies = {}
    workspace = root / 'algorithm/workspace'
    for lock in sorted(workspace.glob('*.lock.json')):
        name = lock.name.removesuffix('.lock.json')
        dependencies[name] = verify_package(lock, workspace / (name + '.zip'), workspace / name)
    failure_file = workspace / 'dependency_failures.json'
    unavailable = json.loads(failure_file.read_text()) if failure_file.exists() else []
    return {'upstream': main, 'workspace': dependencies, 'unavailable_dependencies': unavailable,
            'transitive_dependency_closure_verified': False}
