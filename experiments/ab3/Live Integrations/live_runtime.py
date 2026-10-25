"""Build verified local sources and manage one isolated native container per robot."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
RUNTIME_FILES = ['live_wire.py', 'ros_routes.py', 'native_ros2.py', 'native_ros1.py', 'tcp_tunnel.py', 'native_supervisor.py',
                 'entrypoint_ros2.sh', 'entrypoint_ros1.sh', 'native_output_state.py', 'pose_frames.py', 'live_radio.py']


def docker_ready():
    if not shutil.which('docker'):
        raise RuntimeError('Docker Desktop with Linux containers is required; no Docker executable was found.')
    result = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != 'linux':
        raise RuntimeError('Start Docker in Linux-container mode: ' + result.stderr.strip())


def identity(root):
    root = Path(root)
    files = [root / 'Dockerfile', root / 'source_lock.json', root / 'config/benchmark.json']
    files += list((root / 'algorithm/workspace').glob('*.lock.json'))
    files += [p for p in (root / 'native').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [HERE / name for name in RUNTIME_FILES]
    if (root / 'third_party/models/model_lock.json').exists():
        files.append(root / 'third_party/models/model_lock.json')
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def build(root, profile, rebuild=False):
    root = Path(root)
    docker_ready()
    fingerprint = identity(root)
    image = 'ab3-' + profile['id'] + ':' + fingerprint[:16]
    exists = subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
    if rebuild or not exists:
        build_dir = root / 'build'
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='native-context-', dir=build_dir) as directory:
            context = Path(directory)
            if not context.resolve().is_relative_to(build_dir.resolve()):
                raise RuntimeError('Native build context escaped the algorithm build directory')
            shutil.copyfile(root / 'Dockerfile', context / 'Dockerfile')
            shutil.copytree(root / 'algorithm/upstream', context / 'sources/upstream')
            for name in profile['required_workspace']:
                shutil.copytree(root / 'algorithm/workspace' / name, context / 'sources/workspace' / name)
            shutil.copytree(root / 'native', context / 'native', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            (context / 'runtime').mkdir()
            for name in RUNTIME_FILES:
                (context / 'runtime' / name).write_bytes((HERE / name).read_bytes().replace(b'\r\n', b'\n'))
            if profile.get('model_asset'):
                (context / 'assets').mkdir()
                shutil.copyfile(root / 'third_party/models' / profile['model_asset'],
                                context / 'assets' / profile['model_asset'])
            subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '-t', image, str(context)], check=True)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
    return image, image_id, fingerprint


class Runtime:
    def __init__(self, image, run, robots, config, calibration, first_port=48200):
        self.image, self.run, self.robots = image, Path(run), robots
        self.ports = list(range(first_port, first_port + robots))
        self.names, self.networks, self.logs = [], [], []
        self.config_dir = self.run / 'native_config'
        self.config_dir.mkdir()
        (self.config_dir / 'native_config.json').write_text(json.dumps(config, indent=2) + '\n')
        for name, value in calibration.items():
            if '/' in name or '\\' in name or name in ('.', '..'):
                raise ValueError('Invalid generated native configuration filename')
            (self.config_dir / name).write_text(value, encoding='utf-8')

    def start(self):
        for number, port in enumerate(self.ports, 1):
            output = self.run / ('robot_%d' % number) / 'native'
            output.mkdir(parents=True)
            suffix = hashlib.sha256(str(self.run).encode()).hexdigest()[:12] + '-%d' % number
            network = 'ab3-live-net-' + suffix
            name = 'ab3-live-' + suffix
            subprocess.run(['docker', 'network', 'create', network], check=True, capture_output=True)
            self.networks.append(network)
            command = ['docker', 'run', '-d', '--platform', 'linux/amd64', '--name', name,
                       '--network', network, '-p', '127.0.0.1:%d:48000' % port,
                       '-e', 'AB3_ROBOT_NUMBER=%d' % number,
                       '-e', 'ROS_LOCALHOST_ONLY=1', '-e', 'ROS_DOMAIN_ID=42',
                       '--mount', 'type=bind,source=%s,target=/config,readonly' % self.config_dir,
                       '--mount', 'type=bind,source=%s,target=/output' % output, self.image]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Native container startup failed: ' + result.stderr.strip())
            self.names.append(name)
            stream = (output / 'native.log').open('w', encoding='utf-8')
            follow = subprocess.Popen(['docker', 'logs', '-f', name], stdout=stream, stderr=subprocess.STDOUT)
            self.logs.append((follow, stream))
        deadline, update = time.monotonic() + 900, 0.
        while time.monotonic() < deadline:
            for name in self.names:
                running = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', name], text=True).strip()
                if running != 'true':
                    raise RuntimeError('Native algorithm process exited; inspect robot_N/native/native.log')
            if all((self.run / ('robot_%d/native/native_ready.json' % n)).exists()
                   for n in range(1, self.robots + 1)):
                return
            if time.monotonic() - update >= 30:
                print('Waiting for native frontend subscriptions and peer services to be ready ...', flush=True)
                update = time.monotonic()
            time.sleep(.2)
        raise TimeoutError('Native stack was not ready after 15 minutes; inspect native logs')

    def close(self):
        errors = []
        for name in reversed(self.names):
            result = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
            if result.returncode:
                errors.append(result.stderr.strip())
        for follow, stream in self.logs:
            if follow.poll() is None:
                follow.terminate()
            try:
                follow.wait(timeout=10)
            except subprocess.TimeoutExpired:
                follow.kill()
                follow.wait(timeout=5)
            stream.close()
        for network in reversed(self.networks):
            result = subprocess.run(['docker', 'network', 'rm', network], capture_output=True, text=True)
            if result.returncode:
                errors.append(result.stderr.strip())
        if errors:
            raise RuntimeError('Some native containers/networks need cleanup: ' + '; '.join(errors))
