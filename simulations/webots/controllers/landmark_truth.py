"""Evaluation-only truth collector. Estimators cannot read its output while running."""
import csv
import json
import math
import os
from pathlib import Path

from controller import Supervisor


def main():
    supervisor = Supervisor()
    config = json.loads(Path(os.environ['SLAMLAB_CONFIG']).read_text(encoding='utf-8'))
    output = Path(os.environ['SLAMLAB_OUTPUT'])
    streams, nodes = [], []
    for i in range(1, config['robots'] + 1):
        streams.append((output / ('robot-%d-reference.csv' % i)).open('x', newline=''))
        nodes.append(supervisor.getFromDef('ROBOT%d' % i))
    writers = [csv.writer(stream) for stream in streams]
    for writer in writers:
        writer.writerow(['timestamp', 'x', 'y', 'yaw'])
    markers = []
    children = supervisor.getRoot().getField('children')
    for i in range(children.getCount()):
        node = children.getMFNode(i)
        field = node.getField('model')
        if field and field.getSFString().startswith('marker-'):
            position = node.getPosition()
            markers.append({'id': field.getSFString(), 'x': position[0], 'y': position[1]})
    try:
        while supervisor.step(int(supervisor.getBasicTimeStep())) != -1:
            now = supervisor.getTime()
            for node, writer in zip(nodes, writers):
                p, rotation = node.getPosition(), node.getOrientation()
                writer.writerow([format(now, '.9f'), p[0], p[1], math.atan2(rotation[3], rotation[0])])
            if now >= config['seconds'] + .32:
                break
    finally:
        for stream in streams:
            stream.close()
    (output / 'reference_landmarks.json').write_text(json.dumps(markers, indent=2), encoding='utf-8')
    (output / 'simulation_complete.json').write_text(json.dumps({'time_s': supervisor.getTime()}), encoding='utf-8')
    supervisor.simulationQuit(0)


if __name__ == '__main__':
    main()
