"""PID 1 for a single isolated native robot. Never starts host or peer services."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def commands(config, number):
    stack = config['profile']['id']
    if stack == 'dvm_slam':
        return [['ros2', 'run', 'slam_system', 'ab3_stereo', '--ros-args',
                 '-p', 'agentId:=%d' % number, '-p', 'ab3_robot_count:=%d' % config['robots'],
                 '-p', 'config:=/config/camera.yaml',
                 '-p', 'vocFile:=/opt/ws/src/slam_system/orb_slam3/Vocabulary/ORBvoc.txt',
                 '-p', 'useViewer:=false', '-p', 'publishVizTopics:=false', '-p', 'use_sim_time:=true']]
    if stack == 'swarm_slam':
        robot_id = number - 1
        namespace = '/r%d' % robot_id
        commands = []
        for side in ('left', 'right'):
            position = config['contract']['camera'][side + '_position_body_m']
            commands.append(['ros2', 'run', 'tf2_ros', 'static_transform_publisher',
                '--x', str(position[0]), '--y', str(position[1]), '--z', str(position[2]),
                '--qx', '-0.5', '--qy', '0.5', '--qz', '-0.5', '--qw', '0.5',
                '--frame-id', 'base_link', '--child-frame-id', side + '_optical'])
        commands.append(['ros2', 'run', 'rtabmap_odom', 'stereo_odometry', '--ros-args',
            '-r', '__ns:=' + namespace, '-p', 'use_sim_time:=true',
            '-p', 'frame_id:=base_link', '-p', 'odom_frame_id:=odom', '-p', 'publish_tf:=true',
            '-p', 'approx_sync:=false', '-p', 'qos:=1', '-p', 'publish_null_when_lost:=true',
            '-p', 'wait_for_transform:=0.2', '-r', 'left/image_rect:=/ab3/left/image',
            '-r', 'right/image_rect:=/ab3/right/image', '-r', 'left/camera_info:=/ab3/left/camera_info',
            '-r', 'right/camera_info:=/ab3/right/camera_info'])
        for node in ('loop_closure_detection_node.py', 'map_manager', 'pose_graph_manager'):
            commands.append(['ros2', 'run', 'cslam', node, '--ros-args', '-r', '__ns:=' + namespace,
                             '--params-file', '/config/swarm.yaml', '-p', 'robot_id:=%d' % robot_id,
                             '-p', 'max_nb_robots:=%d' % config['robots']])
        return commands
    if stack == 'ccm_slam':
        return ccm_commands(config, number)
    if stack == 'covins_g':
        return covins_commands(config, number)
    if stack == 'kimera_multi':
        return kimera_commands(config, number)
    raise RuntimeError('No native process recipe for ' + stack)


CCM = '/opt/ws/src/ccm_slam/cslam'


def ccm_commands(config, number):
    """Upstream launch files (Server.launch, Client*_euroc.launch) as commands. The server runs on robot 1."""
    robots = config['robots']
    if robots > 4:
        raise RuntimeError('CCM-SLAM supports at most 4 agents (MAXAGENTS in the original code)')
    voc = CCM + '/conf/ORBvoc.txt'
    client = number - 1
    result = [['rosrun', 'tf', 'static_transform_publisher', '-100', '300', '5', '-1.571', '0', '-2',
               'world', 'odomC%d' % client, '100', '__ns:=/ccmslam', '__name:=linkC%d_broadcaster' % client],
              ['rosrun', 'ab3_ccm_adapter', 'ab3_ccm_client', voc, '/config/camera.yaml',
               '__ns:=/ccmslam', '__name:=ccmslamClientNode%d' % client,
               '_FrameId:=odomC%d' % client, '_ClientId:=%d' % client,
               # The adapter owns the image callback so frame completion is
               # emitted only after GrabImageMonocular returns.
               '_TopicNameCamSub:=/ab3/ccm_upstream_unused', '_MapInTopicName:=MapOutServer%d' % client]]
    if number == 1:
        server = ['rosrun', 'ccmslam', 'ccmslamServerNode', voc, '__ns:=/ccmslam', '__name:=ccmslamServerNode',
                  '_NumOfClients:=%d' % robots, '_LoadMap:=false']
        for i in range(robots):
            server += ['_FrameId%d:=odomS%d' % (i, i), '_MapInTopicName%d:=MapOutClient%d' % (i, i)]
            result.append(['rosrun', 'tf', 'static_transform_publisher', '0', '0', '5', '-1.571', '0', '-2',
                           'world', 'odomS%d' % i, '100', '__ns:=/ccmslam', '__name:=linkS%d_broadcaster' % i])
        result.insert(0, server)
    return result


COVINS = '/root/covins_ws/src/covins'


def covins_commands(config, number):
    """COVINS-G back-end on robot 1 (as covins_backend_node), an ORB-SLAM3 stereo agent on every robot."""
    port = int(config['profile']['tcp_tunnel']['port'])
    agent = ['rosrun', 'ab3_covins_adapter', 'ab3_covins_agent', COVINS + '/orb_slam3/Vocabulary/ORBvoc.txt',
             '/config/covins_stereo.yaml', '__name:=ORB_SLAM3_stereo%d' % (number - 1), '_frame:=covins_vio_%d' % number]
    if number == 1:
        # The agent exits if it cannot reach the back-end: start the back-end and wait for its port.
        return [['rosrun', 'ab3_covins_adapter', 'ab3_covins_backend'], ('wait_port', port), agent]
    return [agent]


KIMERA_SRC = '/root/catkin_ws/src'


def kimera_commands(config, number):
    """Upstream examples/1014-example.yaml for one robot: Kimera-VIO, Kimera-Distributed and DPGO."""
    import shutil
    name, rid, robots = 'bstem%d' % number, number - 1, config['robots']
    params = Path('/tmp/ab3_kimera_params')
    if params.exists():
        shutil.rmtree(params)
    # Algorithm parameters: upstream params/D455. Sensor calibration: generated from the standard.
    shutil.copytree(KIMERA_SRC + '/kimera_multi/params/D455', params)
    for target, source in (('LeftCameraParams.yaml', 'kimera_left.yaml'), ('RightCameraParams.yaml', 'kimera_right.yaml'),
                           ('ImuParams.yaml', 'kimera_imu.yaml')):
        shutil.copyfile('/config/' + source, params / target)
    Path(KIMERA_SRC + '/kimera_distributed/params/robot_names_ab3.yaml').write_text(
        ''.join('robot%d_name: bstem%d\n' % (i, i + 1) for i in range(10)))
    Path('/output/distributed').mkdir(parents=True, exist_ok=True)
    common = ['robot_id:=%d' % rid, 'robot_name:=' + name, 'num_robots:=%d' % robots, 'dataset_name:=Jackal',
              'robot_names_config:=robot_names_ab3', 'log_output_path:=/output/distributed/']
    return [['roslaunch', 'ab3_kimera_adapter', 'ab3_kimera_vio.launch', 'robot_name:=' + name, 'robot_id:=%d' % rid],
            ['roslaunch', 'kimera_distributed', 'kimera_distributed.launch'] + common,
            ['roslaunch', 'kimera_distributed', 'dpgo.launch', 'multi_master:=false'] + common,
            ['rosrun', 'ab3_kimera_adapter', 'ab3_kimera_output.py', '_robot_name:=' + name, '_robot_id:=%d' % rid]]


def wait_port(port, timeout=300.):
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection(('127.0.0.1', port), timeout=1).close()
            return
        except OSError:
            time.sleep(.5)
    raise RuntimeError('Native server port %d did not open' % port)


def start_ros1_master():
    """Each robot's container has its own ROS master; algorithm nodes use the simulation clock."""
    master = subprocess.Popen(['roscore', '-p', '11311'])
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if subprocess.run(['rosparam', 'list'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            subprocess.run(['rosparam', 'set', '/use_sim_time', 'true'], check=True)
            return master
        if master.poll() is not None:
            raise RuntimeError('roscore exited with status %d' % master.returncode)
        time.sleep(.5)
    raise RuntimeError('roscore did not start within 60 s')


def main():
    config = json.loads(Path('/config/native_config.json').read_text())
    number = int(os.environ['AB3_ROBOT_NUMBER'])
    processes = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    ros1 = str(config['profile'].get('ros', '')).startswith('ROS 1')
    commits = Path('/opt/ab3/dependency_commits.txt')
    if commits.exists():                 # provenance of build-time dependencies, kept with the run
        Path('/output/dependency_commits.txt').write_text(commits.read_text())
    try:
        if ros1:
            processes.append(start_ros1_master())
        for command in commands(config, number):
            if isinstance(command, tuple) and command[0] == 'wait_port':
                wait_port(command[1])
                continue
            processes.append(subprocess.Popen(command))
        gateway = subprocess.Popen([sys.executable, '/opt/ab3/native_ros1.py' if ros1 else '/opt/ab3/native_ros2.py'])
        processes.append(gateway)
        while not stopping:
            if gateway.poll() is not None:
                if gateway.returncode:
                    raise RuntimeError('Native bridge exited with status %d' % gateway.returncode)
                break
            for process in processes[:-1]:
                if process.poll() is not None:
                    raise RuntimeError('Native algorithm exited with status %d' % process.returncode)
            time.sleep(.2)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
