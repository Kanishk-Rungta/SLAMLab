"""Export measured experiment data for static browser visualization; no metric recomputation."""
import argparse
import csv
import json
import math
from pathlib import Path


def safe_file(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Experiment path is missing or outside its directory: ' + relative)
    return path


def poses(path, maximum=1500):
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Trajectory input exceeds 20 MiB; select or downsample the recording first')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = [[float(row[key]) for key in ('timestamp', 'x', 'y', 'yaw')] for row in csv.DictReader(stream)]
    if not rows or any(not all(math.isfinite(v) for v in row) for row in rows):
        raise ValueError('Trajectory must contain finite poses')
    if any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
        raise ValueError('Trajectory timestamps must be strictly increasing')
    step = max(1, (len(rows) + maximum - 1) // maximum)
    selected = rows[::step]
    if rows and selected[-1] != rows[-1]:
        selected.append(rows[-1])
    return selected


def export_experiment(root, destination):
    root, destination = Path(root), Path(destination)
    experiment = json.loads((root / 'experiment.json').read_text(encoding='utf-8'))
    result = {key: experiment[key] for key in ('schema_version', 'id', 'algorithm', 'kind', 'world', 'robot_count', 'created_utc', 'versions', 'sensor_model', 'initial_prior')}
    result['configuration'] = experiment['configuration']
    result['robots'] = []
    for robot in experiment['robots']:
        state = json.loads(safe_file(root, robot['map']).read_text())
        history = safe_file(root, robot['id'] + '/states.jsonl')
        frames = [json.loads(line) for line in history.read_text().splitlines()] if history.exists() else []
        # Preserve real timestamps and final state; decimate only display checkpoints.
        step = max(1, (len(frames) + 79) // 80)
        checkpoints = frames[::step]
        if frames and checkpoints[-1] != frames[-1]:
            checkpoints.append(frames[-1])
        result['robots'].append({'id': robot['id'], 'estimate': poses(safe_file(root, robot['estimate'])),
            'reference': poses(safe_file(root, robot['reference'])),
            'odometry': poses(safe_file(root, robot['id'] + '/odometry.csv')),
            'landmarks': state['landmarks'], 'frames': checkpoints,
            'metrics': json.loads(safe_file(root, robot['metrics']).read_text())})
    truth = root / 'reference_landmarks.json'
    result['reference_landmarks'] = json.loads(truth.read_text()) if truth.exists() else []
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, separators=(',', ':'), allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        export_experiment(args.experiment, args.output)
        print(args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + '\n')
