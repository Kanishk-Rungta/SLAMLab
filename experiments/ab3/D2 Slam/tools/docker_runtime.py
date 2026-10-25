"""Model download, Linux-container build and lifecycle; no cross-robot socket routing."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / 'third_party/models'


def check_docker():
    if not shutil.which('docker'):
        raise RuntimeError('Docker is required for official D2SLAM. Install/start Docker Desktop with Linux '
                           'containers. Nothing was installed automatically.')
    result = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != 'linux':
        raise RuntimeError('Docker must be running in Linux-container mode: ' + result.stderr.strip())


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def models_ready(lock):
    return all((MODELS / Path(name).name).is_file() and sha256(MODELS / Path(name).name) == expected
               for name, expected in lock['files'].items())


def prepare_models():
    """The authors' CNN models (SuperPoint, MobileNetVLAD, PCA), verified against source_lock.json.
    A manually downloaded models.zip placed at third_party/d2slam_models.zip is used as is."""
    lock = json.loads((ROOT / 'source_lock.json').read_text(encoding='utf-8'))['models']
    if models_ready(lock):
        return
    archive = ROOT / 'third_party/d2slam_models.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file() or sha256(archive) != lock['archive_sha256']:
        print('Downloading the D2SLAM CNN models (about 300 MB, once) ...', flush=True)
        partial = archive.with_suffix('.part')
        urllib.request.urlretrieve(lock['url'], str(partial))
        if sha256(partial) != lock['archive_sha256']:
            partial.unlink()
            raise RuntimeError('Downloaded D2SLAM models.zip differs from source_lock.json. Download it manually '
                               'from the D2SLAM README link to %s' % archive)
        partial.replace(archive)
    MODELS.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(archive)) as bundle:
        for name in lock['files']:
            (MODELS / Path(name).name).write_bytes(bundle.read(name))
    if not models_ready(lock):
        raise RuntimeError('Extracted D2SLAM models differ from source_lock.json')


def build_identity():
    digest = hashlib.sha256()
    files = [ROOT/'Dockerfile', ROOT/'source_lock.json', ROOT/'algorithm/D2SLAM-original.zip',
             ROOT/'tools/patch_runtime.py']
    for directory in ('native', 'bridge', 'config'):
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for file in sorted(files):
        digest.update(file.relative_to(ROOT).as_posix().encode())
        digest.update(file.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def prepare_image(force=False):
    check_docker()
    image = 'd2slam-original:' + build_identity()[:16]
    exists = subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
    if force or not exists:
        prepare_models()
        jobs = os.environ.get('D2_BUILD_JOBS', '2')
        print('Building the original D2SLAM stack (CPU). The first build downloads and compiles ROS '
              'dependencies and takes about an hour.', flush=True)
        subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '--build-arg', 'BUILD_JOBS=%s' % jobs,
                        '-t', image, str(ROOT)], check=True)
    identifier = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
    return image, identifier


class Runtime:
    def __init__(self, image, run, robots, native_config, files, first_port):
        self.image, self.run, self.robots = image, Path(run), robots
        self.ports = list(range(first_port, first_port+robots))
        self.names, self.ids = [], []
        self.logs = []
        self.config_dir = self.run/'native_config'
        self.config_dir.mkdir()
        (self.config_dir/'native_config.json').write_text(json.dumps(native_config, indent=1)+'\n')
        for name, text in files.items():
            (self.config_dir/name).write_bytes(text.encode('utf-8'))

    def start(self):
        for index, port in enumerate(self.ports):
            number = index+1
            output = self.run/('robot_%d' % number)/'native'
            output.mkdir(parents=True)
            name = 'd2slam-original-%s-%d' % (self.run.name.replace('_', '-').lower(), number)
            command = ['docker', 'run', '-d', '--platform', 'linux/amd64', '--name', name,
                       '-p', '127.0.0.1:%d:47000' % port, '-e', 'D2_ROBOT_NUMBER=%d' % number,
                       '--mount', 'type=bind,source=%s,target=/config,readonly' % self.config_dir,
                       '--mount', 'type=bind,source=%s,target=/output' % output,
                       self.image]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Native container start failed: ' + result.stderr.strip())
            self.names.append(name)
            self.ids.append(result.stdout.strip())
            stream = (output/'native.log').open('w', encoding='utf-8')
            follow = subprocess.Popen(['docker', 'logs', '-f', name], stdout=stream, stderr=subprocess.STDOUT)
            self.logs.append((follow, stream))
        deadline, last_update = time.monotonic()+900, 0.
        while time.monotonic() < deadline:
            ready = []
            for index, name in enumerate(self.names):
                alive = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', name],
                                                text=True).strip()
                if alive != 'true':
                    raise RuntimeError('Native robot %d exited; inspect robot_%d/native/native.log' % (index+1, index+1))
                path = self.run/('robot_%d' % (index+1))/'native/native_ready.json'
                try:
                    ready.append(json.loads(path.read_text()).get('ready') is True)
                except (OSError, ValueError):
                    ready.append(False)
            if all(ready):
                return
            if time.monotonic()-last_update >= 30:
                print('Waiting for native D2SLAM robots (models load on the CPU): %d/%d ready'
                      % (sum(ready), self.robots), flush=True)
                last_update = time.monotonic()
            time.sleep(.5)
        raise RuntimeError('Native stack readiness timeout; inspect the per-robot native logs')

    def close(self):
        # Remove only exact IDs created by this Runtime. Output bind mounts stay.
        for identity in self.ids:
            subprocess.run(['docker', 'stop', '--time', '10', identity], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['docker', 'rm', identity], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for process, stream in self.logs:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
            stream.close()
