"""Integrity and readiness tests. These tests do not execute a SLAM algorithm."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from prepare import FB, SE, render_camera, standard_contract
from source_tools import safe_child, verify_package


class Sources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.archive = self.root / 'original.zip'
        self.lock = self.root / 'source_lock.json'
        self.blob = b'original upstream source\n'
        (self.source / 'main.cpp').write_bytes(self.blob)
        with zipfile.ZipFile(self.archive, 'w') as bundle:
            bundle.writestr('repo-' + 'a' * 40 + '/main.cpp', self.blob)
        self.manifest = {'repository': 'https://github.com/example/example', 'commit': 'a' * 40,
                         'archive_sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                         'files': {'main.cpp': hashlib.sha256(self.blob).hexdigest()}}
        self.save_lock()

    def save_lock(self):
        self.lock.write_text(json.dumps(self.manifest))

    def verify(self):
        return verify_package(self.lock, self.archive, self.source)

    def test_valid_archive_and_source(self):
        self.assertEqual(self.verify()['files_checked'], 1)

    def test_edited_source_preserved(self):
        path = self.source / 'main.cpp'
        path.write_bytes(b'local edit')
        with self.assertRaisesRegex(ValueError, 'missing or modified'):
            self.verify()
        self.assertEqual(path.read_bytes(), b'local edit')

    def test_modified_archive_rejected(self):
        self.archive.write_bytes(b'bad zip')
        with self.assertRaisesRegex(ValueError, 'archive checksum'):
            self.verify()

    def test_missing_source_rejected(self):
        (self.source / 'main.cpp').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or modified'):
            self.verify()

    def test_added_source_rejected(self):
        (self.source / 'replacement.cpp').write_text('not pinned')
        with self.assertRaisesRegex(ValueError, 'Untracked source'):
            self.verify()

    def test_duplicate_archive_member_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(self.archive, 'a') as bundle:
                bundle.writestr('repo-' + 'a' * 40 + '/main.cpp', self.blob)
        self.manifest['archive_sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.save_lock()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.verify()

    def test_unsafe_paths(self):
        for name in ('../escape', '/absolute', 'C:/drive', 'folder\\escape', 'a/../b', '', './main.cpp'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_child(self.source, name)

    def test_commit_requires_full_sha(self):
        self.manifest['commit'] = 'main'
        self.save_lock()
        with self.assertRaisesRegex(ValueError, 'full Git commit'):
            self.verify()

    def test_archive_must_match_selected_commit(self):
        self.manifest['commit'] = 'b' * 40
        self.save_lock()
        with self.assertRaisesRegex(ValueError, 'locked commit'):
            self.verify()


class Calibration(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((SE / 'robot/robot_spec.json').read_text(encoding='utf-8-sig'))

    def test_shared_stereo_projection_and_rates(self):
        contract = standard_contract(self.spec)
        camera = contract['camera']
        self.assertEqual(camera['P_right'][3], -self.spec['stereo']['fx'] * self.spec['stereo']['baseline_m'])
        self.assertEqual(camera['period_ms'], self.spec['timing']['camera_period_ms'])
        self.assertEqual(contract['imu']['period_ms'], self.spec['timing']['control_step_ms'])
        self.assertIn('unavailable', contract['imu']['orientation'])
        self.assertIn('3-axis', contract['imu']['angular_velocity'])

    def test_camera_uses_shared_intrinsics(self):
        for orb3 in (False, True):
            content = render_camera(self.spec, orb3)
            key = 'Camera1.fx' if orb3 else 'Camera.fx'
            self.assertIn(key + ': %.10g' % self.spec['stereo']['fx'], content)
            self.assertIn('Camera.RGB: 0', content)
            self.assertIn('Camera.width: 320', content)

    def test_orb3_camera_preserves_fractional_standard_rate(self):
        content = render_camera(self.spec, orb3=True)
        settings = dict(line.split(': ', 1) for line in content.splitlines() if ': ' in line)
        rate = float(settings['Camera.fps'])
        self.assertAlmostEqual(rate, 1000. / self.spec['timing']['camera_period_ms'], places=8)
        self.assertNotEqual(rate, round(rate))


class EntryPoints(unittest.TestCase):
    def test_all_doctors_match_explicit_validation_state(self):
        for folder, token in [('DVM Slam', 'dvm_slam'), ('Swarm Slam', 'swarm_slam'),
                              ('CCM Slam', 'ccm_slam'), ('COVINS G', 'covins_g'),
                              ('Kimera Multi', 'kimera_multi')]:
            with self.subTest(folder=folder):
                result = subprocess.run([sys.executable, str(FB / folder / ('run_' + token + '.py')), '--doctor'],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                status = json.loads(result.stdout)
                profile = json.loads((FB / folder / 'config/benchmark.json').read_text())
                self.assertEqual(status['live_adapter_implemented'], profile['live_adapter_implemented'])
                self.assertEqual(status['native_build_validated'], profile['native_build_validated'])
                self.assertEqual(status['webots_validated'], profile['webots_validated'])

    def test_invalid_robot_count_rejected_before_source_check(self):
        for folder, token, robots in [('DVM Slam', 'dvm_slam', 11), ('CCM Slam', 'ccm_slam', 5)]:
            with self.subTest(folder=folder):
                result = subprocess.run([sys.executable, str(FB / folder / ('run_' + token + '.py')),
                                         '--prepare-only', '--robots', str(robots)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('supports at most', result.stderr)


if __name__ == '__main__':
    unittest.main()
