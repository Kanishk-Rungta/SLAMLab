#!/usr/bin/env python3
"""Container supervisor: one isolated ROS master, one original D2SLAM robot."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


def main():
    config = json.loads(Path('/config/native_config.json').read_text())
    number = int(os.environ['D2_ROBOT_NUMBER'])
    profile = config['profile']
    env = dict(os.environ, ROS_MASTER_URI='http://127.0.0.1:11311', ROS_IP='127.0.0.1')
    children = []
    try:
        children.append(subprocess.Popen(['roscore'], env=env))
        for _ in range(300):
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
                                          'self_id:=%d' % number, 'config:=/config/d2slam.yaml',
                                          'models:=/opt/d2models', 'output:=/output/',
                                          'lcm_uri:=%s' % profile['lcm_url']], env=env))
        gateway = subprocess.Popen(['python3', '/opt/benchmark/native/gateway.py'], env=env)
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
