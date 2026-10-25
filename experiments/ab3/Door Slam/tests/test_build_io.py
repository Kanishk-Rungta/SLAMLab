"""Offline build I/O regressions; these do not compile or run native SLAM."""
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'native'), str(ROOT / 'tools')]
from download_weights import download_file, unpack_weights, valid_zip
from docker_runtime import run_logged_build


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None, interrupt=False):
        super().__init__(data)
        self.status = status
        self.headers = headers if headers is not None else {'Content-Length': str(len(data))}
        self.interrupt = interrupt
        self.reads = 0

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, size=-1):
        if size < 0:
            raise AssertionError('Unbounded download read')
        self.reads += 1
        if self.interrupt and self.reads > 1:
            raise OSError('connection interrupted')
        return super().read(size)


def checkpoint():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('model/weights.data', b'checkpoint-tensor-data' * 100)
    return buffer.getvalue()


class BuildIO(unittest.TestCase):
    def test_interrupted_download_resumes_at_actual_local_length(self):
        data = checkpoint()
        split = len(data) // 2
        responses = [Response(data[:split], headers={'Content-Length': str(len(data))}, interrupt=True),
                     Response(data[split:], 206, {'Content-Length': str(len(data) - split),
                              'Content-Range': 'bytes %d-%d/%d' % (split, len(data) - 1, len(data))})]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights.zip'
            with patch('download_weights.urllib.request.urlopen', side_effect=responses) as open_url, \
                 patch('download_weights.time.sleep'):
                download_file('https://example.test/weights.zip', path, retries=2)
            self.assertEqual(open_url.call_args_list[1].args[0].get_header('Range'), 'bytes=%d-' % split)
            self.assertEqual(path.read_bytes(), data)

    def test_server_ignoring_range_replaces_partial_file(self):
        data = checkpoint()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights.zip'
            path.write_bytes(b'partial')
            with patch('download_weights.urllib.request.urlopen', return_value=Response(data)):
                download_file('https://example.test/weights.zip', path, retries=1)
            self.assertEqual(path.read_bytes(), data)

    def test_incorrect_range_is_rejected_without_appending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights.zip'
            path.write_bytes(b'partial')
            with patch('download_weights.urllib.request.urlopen', return_value=Response(
                    b'bad', 206, {'Content-Length': '3', 'Content-Range': 'bytes 0-2/10'})):
                with self.assertRaisesRegex(RuntimeError, 'Content-Range does not match'):
                    download_file('https://example.test/weights.zip', path, retries=1)
            self.assertEqual(path.read_bytes(), b'partial')

    def test_crc_corruption_with_valid_footer_restarts_download(self):
        data = checkpoint()
        damaged = bytearray(data)
        name_size, extra_size = struct.unpack_from('<HH', damaged, 26)
        damaged[30 + name_size + extra_size] ^= 1
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(damaged)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights.zip'
            with patch('download_weights.urllib.request.urlopen', side_effect=[Response(damaged), Response(data)]), \
                 patch('download_weights.time.sleep'):
                download_file('https://example.test/weights.zip', path, retries=2)
            self.assertEqual(path.read_bytes(), data)
            self.assertTrue(valid_zip(path))

    def test_complete_archive_is_reused_and_extracted_without_whole_file_reads(self):
        data = checkpoint()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights.zip'
            path.write_bytes(data)
            with patch('download_weights.urllib.request.urlopen') as open_url:
                download_file('https://example.test/weights.zip', path)
            open_url.assert_not_called()
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('whole file read')), \
                 patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('whole member read')):
                digest = unpack_weights(path, Path(directory) / 'checkpoints')
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())
            self.assertEqual((Path(directory) / 'checkpoints/weights.data').read_bytes(),
                             b'checkpoint-tensor-data' * 100)

    def test_failed_build_preserves_stdout_stderr_and_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'build.log'
            command = [sys.executable, '-c',
                       "import sys; print('compile started'); print('compiler: missing library', file=sys.stderr); sys.exit(7)"]
            with self.assertRaisesRegex(RuntimeError, r'exit 7.*build.log'):
                run_logged_build(command, log)
            output = log.read_text()
            self.assertIn('compile started', output)
            self.assertIn('compiler: missing library', output)
            self.assertIn('Build exit code: 7', output)


if __name__ == '__main__':
    unittest.main()
