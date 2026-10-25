"""Preparation checks without Webots, Docker or ROS."""
import json
import math
from pathlib import Path
import py_compile
import re
import shutil
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'bridge')]
import cv2
import numpy as np
from calibration import generate, write
from upstream_source import verify
from patch_runtime import patch as patch_native
from radio_packets import fragments, Reassembler, MAX_PACKET, sender_of
from radio_outbox import RadioOutbox
from lcm_frames import pack, unpack, EchoFilter
from mapping import StereoMapper, compose
from d2_outputs import frame_done, loop_measurement, PoseCorrection, planar, stamp_key
from wire import send, receive
from docker_runtime import check_docker, build_identity

PATCHED = ['d2frontend/CMakeLists.txt', 'd2frontend/include/d2frontend/CNN/onnx_generic.h',
           'd2frontend/src/CNN/superpoint_common.cpp', 'd2frontend/src/CNN/superpoint_onnx.cpp',
           'd2frontend/src/loop_cam.cpp', 'd2frontend/src/d2frontend_params.cpp',
           'd2frontend/include/d2frontend/d2frontend.h', 'd2frontend/src/d2frontend.cpp',
           'd2vins/src/d2vins_node.cpp', 'd2pgo/src/d2pgo_node.cpp']
PATCHED.append('d2common/src/solver/ConsensusSolver.cpp')
PATCHED.append('d2common/src/solver/ARock.cpp')
PATCHED.append('d2common/include/d2common/d2frontend_types.h')


def quaternion(yaw):
    return [0., 0., math.sin(yaw/2), math.cos(yaw/2)]


class SourceTests(unittest.TestCase):
    def test_all_original_source_blobs_unchanged(self):
        manifest = verify()
        self.assertEqual(manifest['commit'], '4c33871083e4ae97b97973eb5bd88dc6735359d7')
        self.assertGreater(len(manifest['files']), 350)
        self.assertFalse(any(name.startswith('models/') for name in manifest['files']))

    def test_portable_archive_rehydrates_fresh_copy_and_preserves_edits(self):
        lock = json.loads((ROOT/'source_lock.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            (fresh/'algorithm').mkdir()
            shutil.copyfile(ROOT/'source_lock.json', fresh/'source_lock.json')
            shutil.copyfile(ROOT/lock['archive_file'], fresh/lock['archive_file'])
            verify(fresh)
            license_file = fresh/'algorithm/D2SLAM/README.md'
            self.assertEqual(license_file.read_bytes(), (ROOT/'algorithm/D2SLAM/README.md').read_bytes())
            license_file.write_bytes(b'user edit preserved')
            with self.assertRaisesRegex(RuntimeError, 'snapshot changed'):
                verify(fresh)
            self.assertEqual(license_file.read_bytes(), b'user edit preserved')

    def test_every_build_dependency_is_pinned(self):
        lock = json.loads((ROOT/'source_lock.json').read_text())
        names = set(re.findall(r'fetch_pinned\.py (\w+)', (ROOT/'Dockerfile').read_text()))
        names |= set(re.findall(r'fetch_pinned\.py (\w+)', (ROOT/'native/build_d2slam.sh').read_text()))
        self.assertTrue(names)
        for name in names:
            self.assertRegex(lock['dependencies'][name]['commit'], r'^[0-9a-f]{40}$')
        self.assertEqual(len(lock['models']['files']), 5)


class AdapterTests(unittest.TestCase):
    def patched_copy(self, directory):
        copy = Path(directory)
        for relative in PATCHED:
            (copy/relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/'algorithm/D2SLAM'/relative, copy/relative)
        patch_native(copy)
        return copy

    def test_adapters_apply_only_to_build_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = self.patched_copy(directory)
            loop_cam = (copy/'d2frontend/src/loop_cam.cpp').read_text()
            self.assertIn('#elif defined(D2_CPU_CNN)', loop_cam)
            self.assertIn('superpoint_ptr = new SuperPointONNX(', loop_cam)
            self.assertIn('nh.param<std::string>("pca_netvlad", pca_netvlad, "");\n',
                          (copy/'d2frontend/src/d2frontend_params.cpp').read_text())
            node = (copy/'d2vins/src/d2vins_node.cpp').read_text()
            self.assertIn('createWallTimer', node)
            self.assertNotIn('make_unique<ros::Rate>', node)
            self.assertNotIn('make_unique<ros::Rate>', (copy/'d2frontend/src/d2frontend.cpp').read_text())
            self.assertIn('benchmark_solve', (copy/'d2pgo/src/d2pgo_node.cpp').read_text())
            self.assertNotIn('D2_CPU_CNN', (ROOT/'algorithm/D2SLAM/d2frontend/src/loop_cam.cpp').read_text())

    def test_adapters_change_no_estimator_or_optimizer_source(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = self.patched_copy(directory)
            changed = [r for r in PATCHED if (copy/r).read_bytes() != (ROOT/'algorithm/D2SLAM'/r).read_bytes()]
            self.assertEqual(sorted(changed), sorted(PATCHED))
            self.assertFalse(any('estimator/' in r or r.startswith('d2pgo/src/') and r != 'd2pgo/src/d2pgo_node.cpp'
                                 for r in changed))

    def test_patch_keeps_unix_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = self.patched_copy(directory)
            self.assertNotIn(b'\r\n', (copy/'d2vins/src/d2vins_node.cpp').read_bytes())


class ConfigurationTests(unittest.TestCase):
    def test_rendered_configuration_parses_with_standard_values(self):
        calibration = generate()
        with tempfile.TemporaryDirectory() as directory:
            write(directory, calibration)
            config = cv2.FileStorage(str(Path(directory)/'d2slam.yaml'), cv2.FILE_STORAGE_READ)
            self.assertAlmostEqual(config.getNode('imu_freq').real(), 31.25)
            self.assertAlmostEqual(config.getNode('image_freq').real(), 1000/96)
            for key in ('lcm_thread_freq', 'loop_detection_freq', 'image_freq', 'solver_timer_freq'):
                self.assertGreater(config.getNode(key).real(), 0, key)  # zero would stall a native thread
            self.assertEqual(int(config.getNode('camera_configuration').real()), 0)
            self.assertEqual(int(config.getNode('margin_sparse_solver').real()), 0)
            left = config.getNode('body_T_cam0').mat()
            right = config.getNode('body_T_cam1').mat()
            self.assertAlmostEqual(left[1, 3]-right[1, 3], .025)
            np.testing.assert_allclose(left[:3, :3], [[0, 0, 1], [-1, 0, 0], [0, -1, 0]])
            # Stereo pairs must be able to triangulate with the 25 mm baseline.
            self.assertLess(config.getNode('depth_estimate_baseline').real(), .025)
            self.assertAlmostEqual(config.getNode('depth_far_thres').real(), 1.5)
            self.assertEqual(config.getNode('output_path').string(), '/output/')
            camera = cv2.FileStorage(str(Path(directory)/'right.yaml'), cv2.FILE_STORAGE_READ)
            self.assertEqual(camera.getNode('model_type').string(), 'PINHOLE')
            self.assertAlmostEqual(camera.getNode('projection_parameters').getNode('fx').real(), 277.1273)
        self.assertNotIn('$', calibration['files']['d2slam.yaml'])

    def test_imu_noise_is_upstream_default_not_fitted(self):
        values = generate()['values']
        self.assertEqual([float(values[k]) for k in ('acc_n', 'gyr_n', 'acc_w', 'gyr_w')], [.1, .05, .002, .0004])

    def test_launch_runs_original_nodes_without_lidar_or_gpu(self):
        launch = ET.parse(ROOT/'native/robot.launch')
        types = {node.attrib['type'] for node in launch.findall('.//node')}
        self.assertEqual(types, {'d2vins_node', 'd2pgo_node', 'd2comm_node'})
        params = {p.attrib['name']: p.attrib.get('value') for p in launch.findall('.//param')}
        self.assertEqual(params['lcm_uri'], '$(arg lcm_uri)')
        self.assertEqual(params['enable_loop'], 'true')
        profile = json.loads((ROOT/'config/benchmark.json').read_text())
        self.assertTrue(profile['lcm_url'].endswith('ttl=0'))
        self.assertFalse(profile['known_docks'])

    def test_native_scripts_compile(self):
        for name in ('native/gateway.py', 'native/start_robot.py', 'native/fetch_pinned.py',
                     'native/extract_original.py', 'webots_controller/d2slam.py', 'run_d2slam.py'):
            py_compile.compile(str(ROOT/name), doraise=True, cfile=str(Path(tempfile.gettempdir())/'d2_compile.pyc'))


class TransportTests(unittest.TestCase):
    def test_radio_reassembles_reordered_bytes_and_filters_other_robot(self):
        data = bytes(range(256))*400
        packets = fragments(1, -1, 'lcm', b'x'*16, data)
        self.assertGreater(len(packets), 1)
        self.assertTrue(all(len(p) <= MAX_PACKET < 50000 for p in packets))
        self.assertEqual(sender_of(packets[0]), 1)
        receiver = Reassembler(2)
        result = None
        for packet in reversed(packets):
            result = receiver.accept(packet, .1) or result
        self.assertEqual(result['payload'], data)
        self.assertIsNone(receiver.accept(packets[-1], .2))
        self.assertTrue(all(Reassembler(1).accept(p, .1) is None for p in packets))

    def test_missing_fragment_expires_in_simulation_time(self):
        packets = fragments(1, -1, 'lcm', b'y'*16, b'z'*30000)
        receiver = Reassembler(2, timeout=1)
        self.assertIsNone(receiver.accept(packets[0], 0))
        for packet in packets[1:]:
            self.assertIsNone(receiver.accept(packet, 2))

    def test_corrupted_payload_is_rejected(self):
        packet = fragments(1, -1, 'lcm', b'z'*16, b'abcdef')[0]
        with self.assertRaises(ValueError):
            Reassembler(2).accept(packet[:-1]+b'x', 0)

    def test_large_messages_are_paced_across_steps(self):
        packets = fragments(1, -1, 'lcm', b'o'*16, bytes(range(256))*400)
        outbox = RadioOutbox(50000)
        self.assertTrue(outbox.enqueue_message(packets))
        first = outbox.offer(0)
        self.assertLessEqual(sum(map(len, first)), 50000)
        delivered = first
        for stamp in (1., 2., 3.):
            delivered += outbox.offer(stamp)
        self.assertEqual(delivered, packets)

    def test_logical_messages_are_not_interleaved(self):
        first = fragments(1, -1, 'lcm', b'a'*16, b'a'*20000)
        second = fragments(1, -1, 'lcm', b'b'*16, b'b'*20000)
        outbox = RadioOutbox(50000)
        self.assertTrue(outbox.enqueue_message(first))
        self.assertTrue(outbox.enqueue_message(second))
        delivered = []
        for stamp in (0., 1., 2., 3.):
            delivered.extend(outbox.offer(stamp))
        self.assertEqual(delivered[:len(first)], first)
        self.assertEqual(delivered[len(first):], second)

    def test_lcm_bytes_round_trip_unchanged(self):
        data = b'\x00\x01lcm-encoded\xff'*100
        self.assertEqual(unpack(pack('VIOKF_LANDMARKS', data)), ('VIOKF_LANDMARKS', data))
        with self.assertRaises(ValueError):
            unpack(b'\x05ab')

    def test_republished_peer_message_is_not_sent_back(self):
        echo = EchoFilter()
        echo.remember('PGO_Sync_Data', b'peer')
        self.assertTrue(echo.is_echo('PGO_Sync_Data', b'peer'))   # our own republication
        self.assertFalse(echo.is_echo('PGO_Sync_Data', b'peer'))  # a later genuine local message
        self.assertFalse(echo.is_echo('SYNC_SIGNAL', b'other'))

    def test_local_sensor_wire_round_trip(self):
        a, b = socket.socketpair()
        try:
            send(a, {'t': .128, 'imu': [0., 0., 0., 9.81], 'image_stamp': .096, 'images': ['l', 'r']})
            value = receive(b)
            self.assertEqual(value['image_stamp'], .096)
        finally:
            a.close()
            b.close()

    def test_missing_docker_is_explicit_and_never_a_python_fallback(self):
        with patch('docker_runtime.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Docker is required'):
                check_docker()
        self.assertEqual(build_identity(), build_identity())


class OutputTests(unittest.TestCase):
    def state(self, **values):
        state = {'frontend': 1., 'forwarded': True, 'backend': 1., 'loop_queue': 0, 'loop_busy': 0}
        state.update(values)
        return state

    def test_frame_waits_for_frontend_backend_and_loop_detector(self):
        self.assertFalse(frame_done(None, 1.))
        self.assertFalse(frame_done(self.state(frontend=.904), 1.))
        self.assertFalse(frame_done(self.state(backend=.904), 1.))
        self.assertTrue(frame_done(self.state(backend=.904, forwarded=False), 1.))
        self.assertFalse(frame_done(self.state(loop_queue=1), 1.))
        self.assertFalse(frame_done(self.state(loop_busy=1), 1.))
        self.assertTrue(frame_done(self.state(), 1.))

    def edge(self, drone_a, ts_a, drone_b, ts_b, rel):
        return {'drone_a': drone_a, 'ts_a': ts_a, 'drone_b': drone_b, 'ts_b': ts_b,
                'relative': [rel[0], rel[1], 0.]+quaternion(rel[2])}

    def test_loop_reports_current_observation_in_matched_frame(self):
        rel = (1., 2., .3)  # frame b in frame a
        current, peer, matched, relative = loop_measurement(self.edge(3, 10., 1, 50., rel), 1)
        self.assertEqual((current, peer, matched), (50., 3, 10.))
        np.testing.assert_allclose(relative, rel, atol=1e-12)
        current, peer, matched, relative = loop_measurement(self.edge(1, 50., 3, 10., rel), 1)
        self.assertEqual((current, peer, matched), (50., 3, 10.))
        np.testing.assert_allclose(compose(rel, relative), [0, 0, 0], atol=1e-12)
        # Intra-robot loop: the newer observation is the current one.
        current, peer, matched, relative = loop_measurement(self.edge(2, 80., 2, 20., rel), 2)
        self.assertEqual((current, peer, matched), (80., 2, 20.))
        self.assertIsNone(loop_measurement(self.edge(4, 1., 5, 2., rel), 1))

    def test_pgo_correction_carries_to_later_odometry(self):
        correction = PoseCorrection()
        correction.add_vio(1., [1., 0., 0.])
        self.assertEqual(correction.apply([2., 0., 0.]), [2., 0., 0.])
        self.assertTrue(correction.set_pgo(1., [1., 1., math.pi/2]))
        np.testing.assert_allclose(correction.apply([2., 0., 0.]), [1., 2., math.pi/2], atol=1e-12)
        self.assertFalse(correction.set_pgo(5., [0., 0., 0.]))  # unknown stamp: keep the last correction
        self.assertEqual(stamp_key(0.0959999), stamp_key(.096))

    def test_planar_yaw_from_quaternion(self):
        np.testing.assert_allclose(planar([1, 2, 3], quaternion(-2.)), [1, 2, -2.])

    def test_map_is_rebuilt_when_keyframes_are_corrected(self):
        st = {'fx': 277.1273, 'fy': 277.1273, 'cx': 160., 'cy': 180., 'baseline_m': .025,
              'left_position_m': [.13, .0125], 'height_above_floor_m': .063}
        mapper = StereoMapper(st, {'map_resolution_m': .1, 'map_size_m': 4, 'max_stereo_depth_m': 1.6})
        mapper.keyframes[stamp_key(.096)] = [(0, 0, 1, 0, 1)]
        original = mapper.rebuild({stamp_key(.096): [0, 0, 0]}).copy()
        corrected = mapper.rebuild({stamp_key(.096): [0, .5, 0]})
        self.assertEqual(int((original == 1).sum()), 1)
        self.assertEqual(int((corrected == 1).sum()), 1)
        self.assertFalse(np.any((original == 1) & (corrected == 1)))


if __name__ == '__main__':
    unittest.main()
