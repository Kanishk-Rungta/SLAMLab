"""Offline restoration checks exercise hashes, traversal and edit preservation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('fetch_original', Path(__file__).resolve().parents[1] / 'tools/setup/fetch_original_sources.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class RestorationTests(unittest.TestCase):
    def fixture(self, root):
        blob, commit = b'original\n', 'a' * 40
        download = io.BytesIO()
        with zipfile.ZipFile(download, 'w') as archive:
            archive.writestr('repo-' + commit + '/main.py', blob)
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, 'w') as archive:
            info = zipfile.ZipInfo('main.py', date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, blob)
        lock = {'repository': 'https://github.com/team/repo.git', 'commit': commit,
                'archive_file': 'algorithm/original.zip',
                'archive_sha256': hashlib.sha256(packed.getvalue()).hexdigest(),
                'files': {'main.py': hashlib.sha256(blob).hexdigest()}}
        (root / 'source_lock.json').write_text(json.dumps(lock))
        return download.getvalue(), packed.getvalue()

    def test_restores_exact_locked_archive_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            downloaded, packed = self.fixture(root)
            with patch.object(fetch, 'download', return_value=downloaded):
                fetch.restore(root, 1024)
                fetch.restore(root, 1024)
            self.assertEqual((root / 'algorithm/original.zip').read_bytes(), packed)

    def test_rejects_tampered_blob_without_writing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            downloaded, _ = self.fixture(root)
            lock = json.loads((root / 'source_lock.json').read_text())
            lock['files']['main.py'] = 'b' * 64
            (root / 'source_lock.json').write_text(json.dumps(lock))
            with patch.object(fetch, 'download', return_value=downloaded), self.assertRaises(ValueError):
                fetch.restore(root, 1024)
            self.assertFalse((root / 'algorithm').exists())

    def test_preserves_existing_edited_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            downloaded, _ = self.fixture(root)
            (root / 'algorithm').mkdir()
            target = root / 'algorithm/original.zip'
            target.write_bytes(b'user edit')
            with patch.object(fetch, 'download', return_value=downloaded), self.assertRaises(ValueError):
                fetch.restore(root, 1024)
            self.assertEqual(target.read_bytes(), b'user edit')

    def test_rejects_windows_and_posix_path_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('../escape', '/absolute', 'C:/drive', 'folder\\escape', '.git/config'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    fetch.safe_child(Path(directory), name)


if __name__ == '__main__':
    unittest.main()
