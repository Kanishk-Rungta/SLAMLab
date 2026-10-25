#!/usr/bin/env python3
"""Container supervisor: one isolated ROS master, one original native robot."""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import urllib.request


def main():
    config = json.loads(Path('/config/native_config.json').read_text())
    rid = int(os.environ['DOOR_ROBOT_ID'])
    peer = (rid+1) % config['robots']
    scripts = Path('/tmp/door_scripts')
    shutil.copytree('/opt/source/tx2-setup/robust_pose_graph_optimization/scripts', str(scripts))
    parameters = scripts / 'config/ros/slam_parameters.bzz'
    text = parameters.read_text()
    text, count = re.subn(r'NUMBER_OF_ROBOTS=\d+', 'NUMBER_OF_ROBOTS=%d' % config['robots'], text)
    if count != 1:
        raise RuntimeError('Upstream robot-count parameter changed')
    text = text.replace('/root/rdpgo_ws/src/robust_distributed_slam_module/scripts/log/datasets/', '/output/')
    parameters.write_text(text)
    subprocess.check_call(['bzzc', 'ros_slam.bzz'], cwd=str(scripts))
    env = dict(os.environ, ROS_MASTER_URI='http://127.0.0.1:11311', ROS_IP='127.0.0.1')
    children = []
    try:
        children.append(subprocess.Popen(['roscore'], env=env))
        for _ in range(150):
            try:
                urllib.request.urlopen('http://127.0.0.1:11311', timeout=.5)
                break
            except urllib.error.HTTPError:
                break  # XMLRPC server is listening; GET is not an XMLRPC call.
            except OSError:
                if children[0].poll() is not None:
                    raise RuntimeError('ROS master exited')
                time.sleep(.1)
        else:
            raise RuntimeError('ROS master did not start')
        subprocess.check_call(['rosparam', 'set', '/use_sim_time', 'true'], env=env)
        children.append(subprocess.Popen(['roslaunch', '/opt/benchmark/native/robot.launch',
                                          'robot_id:=%d' % rid, 'peer_id:=%d' % peer,
                                          'robots:=%d' % config['robots']], env=env))
        gateway_env = dict(env, ROS_NAMESPACE='/robot_%d' % rid)
        gateway = subprocess.Popen(['/usr/bin/python2', '/opt/benchmark/native/gateway.py'], env=gateway_env)
        children.append(gateway)
        while gateway.poll() is None:
            if any(p.poll() is not None for p in children[:-1]):
                raise RuntimeError('A required native ROS process exited; see native.log')
            time.sleep(.2)
        if gateway.returncode:
            raise RuntimeError('Native gateway failed (%d)' % gateway.returncode)
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
        for process in children:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == '__main__':
    main()
