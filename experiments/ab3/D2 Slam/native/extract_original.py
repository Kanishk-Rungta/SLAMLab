"""Verify and extract the portable D2SLAM source archive, and verify the model files, in the build."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path('/opt/benchmark')
lock = json.loads((root/'source_lock.json').read_text())
archive = root/'D2SLAM-original.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != lock['archive_sha256']:
    raise RuntimeError('Original D2SLAM source archive checksum differs')
with zipfile.ZipFile(str(archive)) as bundle:
    if set(bundle.namelist()) != set(lock['files']):
        raise RuntimeError('Original D2SLAM source archive has unexpected entries')
    for name, expected in lock['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Invalid original source path')
        data = bundle.read(name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('Original D2SLAM blob differs: '+name)
        destination = Path('/opt/source-original')/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
for name, expected in lock['models']['files'].items():
    path = Path('/opt/d2models')/Path(name).name
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('D2SLAM model file differs from source_lock.json: '+name)
print('Verified %d original D2SLAM files and %d model files.' % (len(lock['files']), len(lock['models']['files'])))
