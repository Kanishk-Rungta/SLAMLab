"""Resumable checkpoint download with bounded memory (container Python 3)."""
import hashlib
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
import zlib

CHUNK = 4 * 1024 * 1024


def valid_zip(path):
    try:
        with zipfile.ZipFile(str(path)) as archive:
            return bool(archive.infolist()) and archive.testzip() is None
    except (OSError, EOFError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error):
        return False


def download_file(url, destination, retries=15):
    destination = Path(destination)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            if destination.exists() and valid_zip(destination):
                return
            existing = destination.stat().st_size if destination.exists() else 0
            request = urllib.request.Request(url)
            if existing:
                request.add_header('Range', 'bytes=%d-' % existing)
            with urllib.request.urlopen(request, timeout=120) as response:
                length = response.getheader('Content-Length')
                length = int(length) if length is not None else None
                if response.status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',
                                         response.getheader('Content-Range') or '')
                    if not match:
                        raise ValueError('Missing or invalid Content-Range on resumed download')
                    start, end, total = map(int, match.groups())
                    if start != existing or end < start or end >= total:
                        raise ValueError('Content-Range does not match the local partial download')
                    expected = end - start + 1
                    if length is not None and length != expected:
                        raise ValueError('Conflicting download lengths')
                    mode = 'ab'
                elif response.status == 200:
                    existing, expected, mode = 0, length, 'wb'
                else:
                    raise ValueError('Unexpected HTTP status %s' % response.status)
                received = 0
                with destination.open(mode) as output:
                    while True:
                        data = response.read(CHUNK)
                        if not data:
                            break
                        output.write(data)
                        received += len(data)
                        print('Weights downloaded: %d MiB' % ((existing + received) // (1024 * 1024)), flush=True)
                if expected is not None and received != expected:
                    raise IOError('Incomplete response: %d of %d bytes' % (received, expected))
            if valid_zip(destination):
                print('Weights download complete; ZIP CRC checks passed.', flush=True)
                return
            if response.status == 206 and existing + received < total:
                raise IOError('Checkpoint download remains incomplete')
            destination.unlink()
            raise ValueError('Checkpoint ZIP integrity check failed; restarting download')
        except Exception as error:
            last_error = error
            if isinstance(error, urllib.error.HTTPError) and error.code == 416 and destination.exists():
                destination.unlink()
            print('Weights download attempt %d/%d failed: %s' % (attempt, retries, error), flush=True)
            if attempt < retries:
                time.sleep(5)
    raise RuntimeError('Failed to download %s after %d attempts: %s' %
                       (url, retries, last_error)) from last_error


def unpack_weights(weights, output):
    """Retain the original flattened model layout and record the archive digest."""
    digest = hashlib.sha256()
    with Path(weights).open('rb') as source:
        for data in iter(lambda: source.read(CHUNK), b''):
            digest.update(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(weights)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if name:
                with archive.open(info) as source, (output / name).open('wb') as target:
                    shutil.copyfileobj(source, target, CHUNK)
    return digest.hexdigest()
