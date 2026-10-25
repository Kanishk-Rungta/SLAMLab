"""Separate evaluation process: record truth and end the bounded demonstration."""
import json
import math
import os
from pathlib import Path

from controller import Supervisor


def main():
    robot = Supervisor()
    step = int(robot.getBasicTimeStep())
    seconds = float(os.environ['SLAMLAB_DEMO_SECONDS'])
    output = Path(os.environ['SLAMLAB_DEMO_OUTPUT'])
    count = int(os.environ['SLAMLAB_DEMO_ROBOTS'])
    nodes = [robot.getFromDef('BSTEM%d' % i) for i in range(1, count + 1)]
    if any(node is None for node in nodes):
        raise RuntimeError('Missing expected robot DEF')
    streams = [(output / ('bstem%d_groundtruth.csv' % i)).open('x', encoding='utf-8')
               for i in range(1, count + 1)]
    try:
        for stream in streams:
            stream.write('timestamp,x,y,yaw\n')
        while robot.step(step) != -1:
            now = robot.getTime()
            for node, stream in zip(nodes, streams):
                position, orientation = node.getPosition(), node.getOrientation()
                stream.write('%.9f,%.9f,%.9f,%.9f\n' % (
                    now, position[0], position[1], math.atan2(orientation[3], orientation[0])))
            if now >= seconds:
                break
    finally:
        for stream in streams:
            stream.close()
    (output / 'simulation_complete.json').write_text(json.dumps({
        'simulated_seconds': robot.getTime(), 'robots': count,
        'scope': 'Wheel odometry demonstration; no SLAM or mapping validation.'
    }, indent=2) + '\n', encoding='utf-8')
    robot.simulationQuit(0)


if __name__ == '__main__':
    main()
