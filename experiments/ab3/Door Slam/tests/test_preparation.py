import json
from pathlib import Path
import shutil
import socket
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'bridge')]
import numpy as np
from scipy.spatial.transform import Rotation
from calibration import generate
from upstream_source import verify
from patch_runtime import patch as patch_native
from radio_packets import fragments, Reassembler, HEADER, MAX_PACKET
from radio_outbox import RadioOutbox
from buzz_transport import compact, expand
from mapping import StereoMapper, corrected_pose
from wire import send, receive
from docker_runtime import check_docker, build_identity


class PreparationTests(unittest.TestCase):
    def test_all_original_source_blobs_unchanged(self):
        manifest = verify()
        self.assertEqual(manifest['repositories'][0]['commit'], '92fa342d62f80ee343d3db7e0b93c719f0c2054a')
        self.assertGreater(len(manifest['files']), 1000)

    def test_portable_archive_rehydrates_fresh_copy_and_preserves_edits(self):
        lock = json.loads((ROOT/'source_lock.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            (fresh/'algorithm').mkdir()
            shutil.copyfile(ROOT/'source_lock.json', fresh/'source_lock.json')
            shutil.copyfile(ROOT/lock['archive_file'], fresh/lock['archive_file'])
            verify(fresh)
            license_file = fresh/'algorithm/DOOR-SLAM/LICENSE'
            self.assertEqual(license_file.read_bytes(), (ROOT/'algorithm/DOOR-SLAM/LICENSE').read_bytes())
            license_file.write_bytes(b'user edit preserved')
            with self.assertRaisesRegex(RuntimeError, 'snapshot changed'):
                verify(fresh)
            self.assertEqual(license_file.read_bytes(), b'user edit preserved')

    def test_calibration_projection_and_optical_transform(self):
        value = generate()
        left, right = value['left'], value['right']
        self.assertEqual([left['width'], left['height']], [320, 360])
        self.assertAlmostEqual(-right['P'][3]/right['P'][0], .025)
        self.assertEqual(left['P'][3], 0)
        transform = np.asarray(value['left_T_BS']['data']).reshape(4, 4)
        np.testing.assert_allclose(Rotation.from_quat(value['optical_to_body_quaternion_xyzw']).as_matrix(), transform[:3, :3])
        self.assertTrue(value['use_sim_time'])

    def test_radio_reassembles_reordered_bytes_and_filters_other_robot(self):
        data = bytes(range(256))*400
        packets = fragments(0, 1, 'service_request', b'x'*16, data)
        self.assertGreater(len(packets), 1)
        self.assertTrue(all(len(p) <= MAX_PACKET < 50000 for p in packets))
        receiver = Reassembler(1)
        result = None
        for packet in reversed(packets):
            result = receiver.accept(packet, .1) or result
        self.assertEqual(result['payload'], data)
        self.assertIsNone(receiver.accept(packets[-1], .2))
        self.assertTrue(all(Reassembler(2).accept(p, .1) is None for p in packets))

    def test_missing_radio_fragment_expires_in_simulation_time(self):
        packets = fragments(0, -1, 'service_request', b'y'*16, b'z'*30000)
        receiver = Reassembler(1, timeout=1)
        self.assertIsNone(receiver.accept(packets[0], 0))
        for packet in packets[1:]:
            self.assertIsNone(receiver.accept(packet, 2))

    def test_corrupted_radio_payload_is_rejected(self):
        packet = fragments(0, 1, 'buzz', b'z'*16, b'abcdef')[0]
        with self.assertRaises(ValueError):
            Reassembler(1).accept(packet[:-1]+b'x', 0)

    def test_large_rpc_is_paced_across_steps_without_fragment_starvation(self):
        packets = fragments(0, 1, 'service_response', b'o'*16, bytes(range(256))*400)
        outbox = RadioOutbox(50000)
        for packet in packets:
            self.assertTrue(outbox.enqueue(packet))
            self.assertTrue(outbox.enqueue(packet))  # retry already pending
        first = outbox.offer(0)
        self.assertLessEqual(sum(map(len, first)), 50000)
        self.assertLess(len(first), len(packets))
        delivered = first
        for stamp in (1., 2., 3.):
            delivered += outbox.offer(stamp)
        self.assertEqual(delivered, packets)
        self.assertFalse(outbox.pending)

    def test_buzz_compaction_preserves_zero_bytes_inside_messages(self):
        original = struct.pack('<HH', 0, 5)+b'a\0b\0c'+b'\0'*(10000-9)
        packet = compact(original)
        self.assertLess(len(packet), len(original))
        self.assertEqual(expand(packet, 10000), original)

    def test_local_sensor_wire_round_trip(self):
        a, b = socket.socketpair()
        try:
            send(a, {'t': .096, 'radio': ['AA=='], 'images': ['lossless-left', 'lossless-right']})
            value = receive(b)
            self.assertEqual(value['t'], .096)
            self.assertEqual(len(value['images']), 2)
        finally:
            a.close()
            b.close()

    def test_optimized_anchor_propagates_native_visual_motion(self):
        result = corrected_pose([2, 3, 0], [1, 0, np.pi/2], [1, 1, np.pi/2])
        np.testing.assert_allclose(result, [3, 3, 0], atol=1e-10)

    def test_map_is_rebuilt_when_native_graph_corrects_a_keyframe(self):
        value = generate()
        st = {'fx': value['left']['K'][0], 'fy': value['left']['K'][4], 'cx': value['left']['K'][2],
              'cy': value['left']['K'][5], 'baseline_m': .025, 'left_position_m': [.13, .0125],
              'height_above_floor_m': .063}
        mapper = StereoMapper(st, {'map_resolution_m': .1, 'map_size_m': 4, 'max_stereo_depth_m': 1.6})
        mapper.keyframes[1] = [(0, 0, 1, 0, 1)]
        original = mapper.rebuild({1: [0, 0, 0]}).copy()
        corrected = mapper.rebuild({1: [0, .5, 0]})
        self.assertEqual(int((original == 1).sum()), 1)
        self.assertEqual(int((corrected == 1).sum()), 1)
        self.assertFalse(np.any((original == 1) & (corrected == 1)))

    def test_runtime_patches_apply_only_to_build_copy(self):
        original = ROOT/'algorithm/DOOR-SLAM'
        names = [
            'tx2-setup/robust_pose_graph_optimization/buzz_slam/src/generic_robot/utils/buzz_utils.h',
            'tx2-setup/robust_pose_graph_optimization/buzz_slam/src/slam/buzz_slam.h',
            'tx2-setup/robust_pose_graph_optimization/buzz_slam/src/generic_robot/buzz_generic_robot_slam_ros.cpp',
            'tx2-setup/slam_front_end/ros_ws/src/multi_robot_separators/src/stereoCamGeometricTools.cpp']
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory)
            for relative in names:
                (copy/relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original/relative, copy/relative)
            patch_native(copy)
            header = (copy/names[1]).read_text()
            self.assertIn('poses_initial_guess_->at<gtsam::Pose3>', header)
            self.assertIn('BenchmarkState() const', header)
            self.assertIn('ros::Rate(10).sleep()', (copy/names[0]).read_text())
            self.assertNotIn('BenchmarkState() const', (original/names[1]).read_text())

    def test_launch_selects_stereo_and_original_backend(self):
        launch = ET.parse(ROOT/'native/robot.launch')
        nodes = launch.findall('.//node')
        types = {node.attrib['type'] for node in nodes}
        self.assertIn('stereo_odometry', types)
        self.assertIn('generic_robot_buzz_slam_node', types)
        self.assertFalse(types & {'communication', 'rgbd_odometry', 'icp_odometry'})
        self.assertTrue(all('lidar' not in kind and 'laser' not in kind for kind in types))

    def test_missing_docker_is_explicit_and_never_a_python_fallback(self):
        with patch('docker_runtime.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Docker is required'):
                check_docker()
        self.assertEqual(build_identity(), build_identity())


if __name__ == '__main__':
    unittest.main()
