"""Wheel odometry teaching example. This controller is not a SLAM algorithm."""
import json
import math
import os
from pathlib import Path
import sys

from controller import Robot

STANDARD = Path(os.environ['STANDARD_ENV'])
sys.path.insert(0, str(STANDARD / 'sensors'))
from bstem_sensors import BstemSensors


def main():
    robot = Robot()  # No Supervisor interface: estimation cannot query ground truth.
    sensors = BstemSensors(robot)
    name = robot.getName()
    # Known initial dock is an explicit prior, not a live ground-truth measurement.
    starts = json.loads((STANDARD / 'robot/start_poses.json').read_text())['poses']
    start = starts[name]
    x, y, yaw = start[:3]
    out = Path(os.environ['SLAMLAB_DEMO_OUTPUT']) / (name + '_estimate.csv')
    with out.open('x', encoding='utf-8') as stream:
        stream.write('timestamp,x,y,yaw\n')
        while robot.step(sensors.step_ms) != -1:
            wheels, _, _ = sensors.read()
            distance = float(sum(wheels) / 2)
            turn = float((wheels[1] - wheels[0]) / sensors.track)
            x += distance * math.cos(yaw + turn / 2)
            y += distance * math.sin(yaw + turn / 2)
            yaw = math.atan2(math.sin(yaw + turn), math.cos(yaw + turn))
            stream.write('%.9f,%.9f,%.9f,%.9f\n' % (robot.getTime(), x, y, yaw))
            # Bounded gentle arc; no autonomous exploration or map generation.
            sensors.drive(0.08, 0.08)


if __name__ == '__main__':
    main()
