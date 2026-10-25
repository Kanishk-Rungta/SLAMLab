"""Recompute EKF state from recorded relative sensors only, without Webots or truth."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'algorithms/ekf-slam'))
from ekf import EKFSLAM, Noise


def replay(experiment, robot):
    config = json.loads((experiment / 'config.json').read_text())
    if not 1 <= robot <= config['robots']:
        raise ValueError('Robot is not present in this experiment')
    state = EKFSLAM(config['initial_poses'][robot - 1], Noise(**config['noise']))
    with (experiment / ('robot-%d' % robot) / 'sensors.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            state.predict(row['distance_m'], row['turn_rad'])
            for observation in row['observations']:
                state.observe(observation['id'], observation['range_m'], observation['bearing_rad'])
    return state.snapshot()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    parser.add_argument('--robot', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.experiment, args.robot)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print('Replayed relative sensor stream:', args.output)
