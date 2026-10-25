"""Local Linux-container lifecycle; no cross-robot socket routing."""
import hashlib
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent


def check_docker():
    if not shutil.which('docker'):
        raise RuntimeError('Docker is required for official DOOR-SLAM. Install/start Docker with Linux containers on the target laptop. Nothing was installed automatically.')
    result = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != 'linux':
        raise RuntimeError('Docker must be running in Linux-container mode: '+result.stderr.strip())


def build_identity():
    digest = hashlib.sha256()
    files = [ROOT/'Dockerfile', ROOT/'source_lock.json']
    for directory in ('native', 'bridge', 'config'):
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.append(ROOT/'tools/patch_runtime.py')
    for file in sorted(files):
        digest.update(file.relative_to(ROOT).as_posix().encode())
        digest.update(file.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def prepare_image(force=False):
    check_docker()
    image = 'door-slam-original:'+build_identity()[:16]
    exists = subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
    if force or not exists:
        print('Building the original native stack; first build downloads historical ROS/dependencies/model weights.', flush=True)
        log_path = ROOT/'build/logs'/('docker_build_%s.log' % datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        run_logged_build(['docker', 'build', '--progress=plain', '--platform', 'linux/amd64',
                          '-t', image, str(ROOT)], log_path)
    identifier = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
    return image, identifier


def run_logged_build(command, log_path):
    """Stream both Docker outputs to the console and a durable host log."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print('Full native build log: %s' % log_path, flush=True)
    with log_path.open('w', encoding='utf-8') as output:
        output.write('Command: %s\n' % json.dumps(command))
        output.flush()
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
            for line in process.stdout:
                output.write(line)
                output.flush()
                print(line, end='', flush=True)
            status = process.wait()
        output.write('\nBuild exit code: %d\n' % status)
    if status:
        raise RuntimeError('Native Docker build failed (exit %d). Full compiler/dependency output: %s' %
                           (status, log_path))


class Runtime:
    def __init__(self, image, run, robots, native_config, first_port=47000):
        self.image, self.run, self.robots = image, Path(run), robots
        self.ports = list(range(first_port, first_port+robots))
        self.names, self.ids = [], []
        self.logs = []
        self.config_dir = self.run/'native_config'
        self.config_dir.mkdir()
        (self.config_dir/'native_config.json').write_text(json.dumps(native_config, indent=1)+'\n')

    def start(self):
        for rid, port in enumerate(self.ports):
            output = self.run/('robot_%d' % (rid+1))/'native'
            output.mkdir(parents=True)
            name = 'door-original-%s-%d' % (self.run.name.replace('_', '-').lower(), rid)
            command = ['docker', 'run', '-d', '--platform', 'linux/amd64', '--name', name,
                       '-p', '127.0.0.1:%d:47000' % port, '-e', 'DOOR_ROBOT_ID=%d' % rid,
                       '--mount', 'type=bind,source=%s,target=/config,readonly' % self.config_dir,
                       '--mount', 'type=bind,source=%s,target=/output' % output,
                       self.image]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Native container start failed: '+result.stderr.strip())
            self.names.append(name)
            self.ids.append(result.stdout.strip())
            stream = (output/'native.log').open('w', encoding='utf-8')
            follow = subprocess.Popen(['docker', 'logs', '-f', name], stdout=stream, stderr=subprocess.STDOUT)
            self.logs.append((follow, stream))
        deadline, last_update = time.monotonic()+600, 0.
        while time.monotonic() < deadline:
            ready = []
            for rid, name in enumerate(self.names):
                alive = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Running}}', name], text=True).strip()
                if alive != 'true':
                    raise RuntimeError('Native robot %d exited; inspect robot_%d/native/native.log' % (rid+1, rid+1))
                path = self.run/('robot_%d' % (rid+1))/'native/native_ready.json'
                try:
                    ready.append(json.loads(path.read_text()).get('ready') is True)
                except (OSError, ValueError):
                    ready.append(False)
            if all(ready):
                return
            if time.monotonic()-last_update >= 30:
                print('Waiting for native DOOR-SLAM robots: %d/%d ready' % (sum(ready), self.robots), flush=True)
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
