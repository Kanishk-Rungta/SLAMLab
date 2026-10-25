"""Cross-platform lifecycle for the implemented additional native AB3 ports."""
import html
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'Standard Environment/tools'))
import launcher_common as lc
from live_runtime import build, Runtime


def calibration(root, profile):
    files = {}
    if profile['id'] == 'dvm_slam':
        content = (root / 'build/native_config/camera.yaml').read_text()
        content = content.replace('Camera.type: "PinHole"', 'Camera.type: "Rectified"')
        spec = json.loads((lc.SE / 'robot/robot_spec.json').read_text())
        content += 'Stereo.b: %.9f\nStereo.ThDepth: 40.0\n' % spec['stereo']['baseline_m']
        files['camera.yaml'] = content
    elif profile['id'] == 'swarm_slam':
        params = {
            'use_sim_time': True,
            'frontend.left_image_topic': '/ab3/left/image',
            'frontend.right_image_topic': '/ab3/right/image',
            'frontend.left_camera_info_topic': '/ab3/left/camera_info',
            'frontend.right_camera_info_topic': '/ab3/right/camera_info',
            'frontend.odom_topic': 'odom', 'frontend.sensor_base_frame_id': 'base_link',
            'frontend.sensor_type': 'stereo', 'frontend.max_queue_size': 20,
            'frontend.pnp_min_inliers': 20, 'frontend.inter_robot_loop_closure_budget': 1,
            'frontend.inter_robot_detection_period_sec': 5, 'frontend.similarity_threshold': .8,
            'frontend.global_descriptors_topic': 'global_descriptors',
            'frontend.inter_robot_matches_topic': 'inter_robot_matches',
            'frontend.image_crop_size': 320, 'frontend.intra_loop_min_inbetween_keyframes': 20,
            'frontend.detection_publication_period_sec': 1.,
            'frontend.detection_publication_max_elems_per_msg': 10,
            'frontend.enable_intra_robot_loop_closures': True,
            'frontend.keyframe_generation_ratio_threshold': 1.,
            'frontend.use_vertex_cover_selection': True,
            'frontend.map_manager_process_period_ms': 100,
            'frontend.enable_sparsification': True, 'frontend.global_descriptor_technique': 'cosplace',
            'frontend.nn_checkpoint': 'models/resnet18_64.pth',
            'frontend.cosplace.backbone': 'resnet18', 'frontend.cosplace.descriptor_dim': 64,
            'neighbor_management.enable_neighbor_monitoring': True,
            'neighbor_management.max_heartbeat_delay_sec': 5., 'neighbor_management.init_delay_sec': 5.,
            'neighbor_management.heartbeat_period_sec': 1.,
            'backend.pose_graph_optimization_start_period_ms': 10000,
            'backend.pose_graph_optimization_loop_period_ms': 100,
            'backend.max_waiting_time_sec': 60, 'backend.enable_broadcast_tf_frames': True,
            'evaluation.enable_logs': False, 'evaluation.enable_gps_recording': False,
            'evaluation.enable_simulated_rendezvous': False, 'evaluation.enable_pose_timestamps_recording': False,
            'visualization.enable': False,
        }
        # JSON is a YAML subset accepted by the ROS parameter-file parser.
        files['swarm.yaml'] = json.dumps({'/**': {'ros__parameters': params}}, indent=2) + '\n'
    elif profile['id'] == 'ccm_slam':
        # Monocular pinhole camera (left), ORB-SLAM2 settings layout, from the standard calibration.
        files['camera.yaml'] = (root / 'build/native_config/camera.yaml').read_text()
    elif profile['id'] in NATIVE_CALIBRATION:
        files.update(NATIVE_CALIBRATION[profile['id']](root, profile))
    else:
        raise RuntimeError('Native calibration generator is missing for ' + profile['id'])
    return files


def covins_calibration(root, profile):
    """ORB-SLAM3 (COVINS-modified, v0.3 settings layout) stereo settings from the standard calibration.
    Images are already rectified (no LEFT/RIGHT rectification block). ORB/threshold values: upstream
    Examples/Stereo/EuRoC.yaml defaults."""
    spec = json.loads((lc.SE / 'robot/robot_spec.json').read_text(encoding='utf-8-sig'))
    st = spec['stereo']
    lines = ['%YAML:1.0', 'Camera.type: "PinHole"']
    lines += ['Camera.%s: %.9f' % (k, st[k]) for k in ('fx', 'fy', 'cx', 'cy')]
    lines += ['Camera.%s: 0.0' % k for k in ('k1', 'k2', 'p1', 'p2')]
    lines += ['Camera.bFishEye: 0', 'Camera.width: %d' % st['width'], 'Camera.height: %d' % st['height'],
              'Camera.fps: %.6f' % (1000. / spec['timing']['camera_period_ms']),
              'Camera.bf: %.9f' % (st['fx'] * st['baseline_m']), 'Camera.RGB: 0', 'ThDepth: 35.0',
              'ORBextractor.nFeatures: 1200', 'ORBextractor.scaleFactor: 1.2', 'ORBextractor.nLevels: 8',
              'ORBextractor.iniThFAST: 20', 'ORBextractor.minThFAST: 7',
              'Viewer.KeyFrameSize: 0.05', 'Viewer.KeyFrameLineWidth: 1', 'Viewer.GraphLineWidth: 0.9',
              'Viewer.PointSize: 2', 'Viewer.CameraSize: 0.08', 'Viewer.CameraLineWidth: 3',
              'Viewer.ViewpointX: 0', 'Viewer.ViewpointY: -0.7', 'Viewer.ViewpointZ: -1.8', 'Viewer.ViewpointF: 500']
    return {'covins_stereo.yaml': '\n'.join(lines) + '\n'}


def check_covins(root):
    up = root / 'algorithm/upstream'
    require_text(up / 'covins_backend/include/covins/covins_backend/backend.hpp', 'ManagerPtr                  mapmanager_;', 'protected:')
    require_text(up / 'covins_backend/include/covins/covins_backend/map_be.hpp',
                 'auto CheckoutMap(int map_id, int& check_num)', 'auto ReturnMap(int map_id, int& check_num)')
    require_text(up / 'covins_backend/include/covins/covins_base/keyframe_base.hpp',
                 'virtual auto GetPoseTws()', 'virtual auto GetPoseTws_vio()', 'double                      timestamp_;')
    require_text(up / 'covins_backend/include/covins/covins_base/map_base.hpp', 'std::set<size_t>            associated_clients_;')
    require_text(up / 'covins_backend/src/covins_backend/backend.cpp', 'new AgentPackage(agent_next_id_++')
    require_text(up / 'orb_slam3/include/System.h', 'cv::Mat TrackStereo(', 'int GetTrackingState();')
    require_text(up / 'covins_backend/config/config_backend.yaml', "placerec.type: 'COVINS_G'")
    for name in ('CMakeLists.txt', 'package.xml', 'src/ab3_covins_agent.cpp', 'src/ab3_covins_backend.cpp'):
        if not (root / 'native/ab3_covins_adapter' / name).exists():
            raise RuntimeError('COVINS-G adapter file missing: ' + name)


def kimera_calibration(root, profile):
    """Kimera-VIO sensor files: the standard stereo calibration (already in the Kimera/EuRoC layout,
    robot/stereo_*.yaml) and upstream params/D455/ImuParams.yaml with the standard IMU rate."""
    import re
    spec = json.loads((lc.SE / 'robot/robot_spec.json').read_text(encoding='utf-8-sig'))
    imu = (root / 'algorithm/upstream/params/D455/ImuParams.yaml').read_text()
    imu, n = re.subn(r'^rate_hz:.*$', 'rate_hz: %.6f  # AB3 standard control rate' % (1000. / spec['timing']['control_step_ms']),
                     imu, flags=re.M)
    if n != 1:
        raise RuntimeError('Upstream ImuParams.yaml changed: rate_hz not found')
    return {'kimera_left.yaml': (lc.SE / 'robot/stereo_left.yaml').read_text(encoding='utf-8-sig'),
            'kimera_right.yaml': (lc.SE / 'robot/stereo_right.yaml').read_text(encoding='utf-8-sig'),
            'kimera_imu.yaml': imu}


def check_kimera(root):
    up, ws = root / 'algorithm/upstream', root / 'algorithm/workspace'
    for name in ('BackendParams.yaml', 'FrontendParams.yaml', 'PipelineParams.yaml', 'LcdParams.yaml',
                 'ImuParams.yaml', 'LeftCameraParams.yaml', 'RightCameraParams.yaml'):
        if not (up / 'params/D455' / name).exists():
            raise RuntimeError('Upstream params/D455 file missing: ' + name)
    require_text(up / 'launch/kimera_vio_jackal.launch', '$(find kimera_vio_ros)/launch/kimera_vio_ros.launch')
    require_text(ws / 'kimera_distributed/src/DistributedLoopClosureRos.cpp',
                 '"/kimera_distributed/vlc_requests"', '"/kimera_distributed/bow_requests"', '"/kimera_distributed/loop_closures"',
                 '"/kimera_distributed/vlc_responses"', '"/kimera_distributed/loop_ack"', '"/kimera_vio_ros/bow_query"',
                 '"/kimera_distributed/pose_corrector"', '"/kimera_distributed/optimized_nodes"', '"/connected_peer_ids"',
                 'node_msg.header.stamp.fromNSec(keyframe->stamp());')
    require_text(ws / 'dpgo_ros/src/PGOAgentROS.cpp', '"/dpgo_ros_node/"', '"lifting_matrix"', '"public_measurements"',
                 '"measurement_weights"', '"/connected_peer_ids"')
    require_text(ws / 'kimera_ros/src/RosVisualizer.cpp', '"odometry"')
    require_text(ws / 'kimera_ros/src/RosDataProviderInterface.cpp', 'image_encodings::BGR8')
    if not (ws / 'kimera_distributed/params/Jackal.yaml').exists() and not list((ws / 'kimera_distributed/params').glob('*Jackal*')):
        raise RuntimeError('kimera_distributed has no Jackal dataset parameters')
    for name in ('CMakeLists.txt', 'package.xml', 'launch/ab3_kimera_vio.launch', 'scripts/ab3_kimera_output.py'):
        if not (root / 'native/ab3_kimera_adapter' / name).exists():
            raise RuntimeError('Kimera-Multi adapter file missing: ' + name)


# Further stacks register their calibration generators here (see their native/ folders).
NATIVE_CALIBRATION = {'covins_g': covins_calibration, 'kimera_multi': kimera_calibration}
ADAPTER_CHECKS = {'covins_g': check_covins, 'kimera_multi': check_kimera}


def require_text(path, *needles):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    missing = [n for n in needles if n not in text]
    if missing:
        raise RuntimeError('Pinned upstream changed; the AB3 adapter expects %s in %s' % (missing, path))


def check_ccm(root):
    up = root / 'algorithm/upstream/cslam'
    require_text(up / 'include/cslam/ClientHandler.h', 'trackptr GetTrackPtr()', 'void InitializeThreads()')
    require_text(up / 'include/cslam/Tracking.h', 'frameptr mCurrentFrame;', 'eTrackingState mLastProcessedState;')
    require_text(up / 'include/cslam/Map.h', 'vector<kfptr> GetAllKeyFrames();')
    require_text(up / 'include/cslam/KeyFrame.h', 'cv::Mat GetPoseInverse();', 'bool isBad()')
    require_text(up / 'src/client/ClientSystem.cpp', 'new ClientHandler(mNh,mNhPrivate,mpVoc,mpKFDB,mpMap,mClientId,mpUID,eSystemState::CLIENT,strCamFile,nullptr)')
    require_text(up / 'include/cslam/Optimizer.h', '#define MAXAGENTS 4')
    for name in ('CMakeLists.txt', 'package.xml', 'src/ab3_ccm_client.cpp'):
        if not (root / 'native/ab3_ccm_adapter' / name).exists():
            raise RuntimeError('CCM-SLAM output adapter file missing: ' + name)


def check_adapters(root, profile):
    """Fail against changed upstream before spending time on a container build."""
    if profile['id'] in ('dvm_slam', 'swarm_slam'):
        import shutil
        import tempfile
        file = root / 'native/patch_build.py'
        spec = importlib.util.spec_from_file_location('ab3_' + profile['id'] + '_build_adapter', file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            if profile['id'] == 'dvm_slam':
                for name in ['src/slam_system/src/orb_slam3_wrapper.cpp',
                             'src/slam_system/include/orb_slam3_wrapper.h',
                             'src/slam_system/orb_slam3/src/Settings.cc',
                             'src/slam_system/CMakeLists.txt']:
                    target = stage / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(root / 'algorithm/upstream' / name, target)
                module.patch(stage, root / 'native/ab3_stereo.cpp')
            else:
                shutil.copytree(root / 'algorithm/workspace/cslam', stage / 'cslam')
                module.patch(stage / 'cslam')
    elif profile['id'] == 'ccm_slam':
        check_ccm(root)
    elif profile['id'] in ADAPTER_CHECKS:
        ADAPTER_CHECKS[profile['id']](root)
    else:
        raise RuntimeError('Native build adapter check is missing for ' + profile['id'])


def validate_run_paths(root):
    root = root.resolve()
    for name in ('runs', 'backup_runs', 'build'):
        path = root / name
        if path.exists() and path.resolve().parent != root:
            raise ValueError('Algorithm output directory escapes its folder: ' + str(path))
    runs = root / 'runs'
    if runs.exists():
        for path in runs.iterdir():
            if path.is_dir() and path.resolve().parent != runs.resolve():
                raise ValueError('Previous run resolves outside the runs directory')


def latest(root):
    marker = root / 'runs/LATEST.txt'
    if not marker.exists():
        raise RuntimeError('No previous run exists for this algorithm')
    run = Path(marker.read_text(encoding='utf-8-sig').strip()).resolve()
    if not run.is_dir() or run.parent != (root / 'runs').resolve():
        raise ValueError('LATEST.txt does not identify a run inside this algorithm')
    return run


def run(root, args, profile):
    root = Path(root)
    check_adapters(root, profile)
    native_calibration = calibration(root, profile)
    for name, content in native_calibration.items():
        (root / 'build/native_config' / name).write_text(content)
    if args.prepare_only:
        print('Native build-copy adapters match the pinned source; generated native calibration.')
        print('Docker compilation and actual native/Webots execution remain unvalidated.')
        return
    if not args.build_only:
        webots_home, webots_exe = lc.find_webots()
    image, image_id, fingerprint = build(root, profile, rebuild=args.rebuild_image)
    if args.build_only:
        print('Native image built:', image, image_id)
        return
    validate_run_paths(root)
    lc.backup_previous_runs(root)
    output = lc.new_run_dir(root, args.scenario, args.robots)
    lc.check_standard(output)
    manifest = json.loads((output / 'standard_environment.json').read_text())
    if not manifest['matches_standard']:
        raise RuntimeError('The standard environment changed; refusing an incomparable run')
    controller = 'ab3_' + profile['id']
    for command in [
        [sys.executable, lc.SE / 'tools/make_algorithm_world.py', '--controller', controller, '--robots', args.robots],
        [sys.executable, lc.SE / 'tools/install_controller.py', '--name', controller,
         '--source', HERE / 'live_controller.py', '--python', sys.executable],
        [sys.executable, lc.SE / 'tools/install_controller.py', '--name', 'bench_supervisor',
         '--source', lc.SE / 'benchmark/bench_supervisor.py', '--python', sys.executable],
    ]:
        if lc.run_quiet(command):
            raise RuntimeError('Standard world/controller preparation failed')
    contract = json.loads((root / 'build/native_config/sensor_contract.json').read_text())
    source = json.loads((root / 'source_lock.json').read_text())
    runtime = Runtime(image, output, args.robots,
        {'robots': args.robots, 'profile': profile, 'contract': contract}, native_calibration,
        first_port=profile.get('first_port', 48200))
    config = {'output_dir': str(output), 'profile': profile, 'robots': args.robots,
              'max_seconds': args.seconds, 'ports': runtime.ports,
              'upstream_commit': source['commit'], 'live_map_wall_seconds': args.live_map_seconds,
              'frame_timeout_wall_s': 120.}
    lc.write_json(output / 'run_config.json', config)
    lc.write_json(output / 'bench_config.json', {'gt_map': str(lc.GT_MAP), 'max_sim_seconds': args.seconds})
    lc.write_json(output / 'native_build.json', {'image': image, 'image_id': image_id,
        'fingerprint': fingerprint, 'upstream_commit': source['commit'],
        'result_label': profile.get('result_label', profile['algorithm']),
        'input_mode': profile['input_mode'], 'validation': 'target-machine validation required'})
    cells = ''.join('<figure><figcaption>Robot %d</figcaption><img src="robot_%d/live_map.png"></figure>' % (n, n)
                    for n in range(1, args.robots + 1))
    title = html.escape(profile.get('result_label', profile['algorithm']))
    page = ('<!doctype html><html><meta charset="utf-8"><title>' + title +
            '</title><style>body{font:16px system-ui;background:#eee}main{display:flex;flex-wrap:wrap}'
            'figure{margin:8px}img{max-width:620px;width:100%}</style><h1>' + title +
            '</h1><p>Native local map frames; occupancy output adapter. Ground-truth alignment is evaluation only.</p>'
            '<figure><figcaption>Swarm overview over the AB3 layout (from the benchmark recordings; '
            'refreshed every live-map period)</figcaption><img src="overview.png" style="max-width:1280px"></figure>'
            '<main>' + cells + '</main><script>setInterval(()=>document.querySelectorAll("img").forEach('
            'i=>i.src=i.src.split("?")[0]+"?t="+Date.now()),10000)</script></html>')
    (output / 'live_view.html').write_text(page, encoding='utf-8')
    env = lc.bench_environment(output, lc.SE / 'benchmark/scenarios' / (args.scenario + '.json'),
                               webots_home, {'AB3_LIVE_CONFIG': str(output / 'run_config.json')})
    started = False
    try:
        runtime.start()
        if not args.no_browser:
            lc.open_live_view(output / 'live_view.html')
        print('Run folder:', output, flush=True)
        started = True
        world = lc.SE / 'webots/worlds' / ('ab3_standard__' + controller + '.wbt')
        lc.run_webots(webots_exe, world, env, output, gui=args.gui, live_seconds=args.live_map_seconds)
    finally:
        try:
            runtime.close()
        finally:
            if started and (output / 'benchmark/run_meta.json').exists():
                from finalize_native import finalize
                finalize(output)
                lc.evaluate(output, open_folder=not args.no_browser)
    if (output / 'controller_errors.txt').exists():
        raise RuntimeError('A Webots controller failed; see ' + str(output / 'controller_errors.txt'))
