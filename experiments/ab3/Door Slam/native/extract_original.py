"""Verify and extract the portable source archive inside the native build."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path('/opt/benchmark')
lock = json.loads((root/'source_lock.json').read_text())
archive = root/'DOOR-SLAM-original.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != lock['archive_sha256']:
    raise RuntimeError('Original source archive checksum differs')
with zipfile.ZipFile(str(archive)) as bundle:
    if set(bundle.namelist()) != set(lock['files']):
        raise RuntimeError('Original source archive has unexpected entries')
    for name, expected in lock['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Invalid original source path')
        data = bundle.read(name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('Original source blob differs: '+name)
        destination = Path('/opt/source-original')/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
