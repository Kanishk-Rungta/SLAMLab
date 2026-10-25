"""Strict planar trajectory evaluation using the imported AB3 geometry utilities."""
import argparse
import bisect
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/ab3/Standard Environment/benchmark'))
from evaluation.common import align_se2, apply_se2, between, path_length, stats, wrap


def nanoseconds(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('Timestamp must be finite')
        result = int((number * 1_000_000_000).to_integral_value(rounding=ROUND_HALF_EVEN))
        if abs(result) >= 2 ** 63:
            raise ValueError('Timestamp outside signed nanosecond range')
        return result
    except (InvalidOperation, OverflowError) as error:
        raise ValueError('Invalid timestamp') from error


def load_csv(path):
    times, poses = [], []
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['timestamp', 'x', 'y', 'yaw']:
            raise ValueError('CSV header must be timestamp,x,y,yaw (seconds, metres, radians)')
        for line, row in enumerate(reader, 2):
            if set(row) != {'timestamp', 'x', 'y', 'yaw'} or None in row.values():
                raise ValueError('Malformed CSV row %d' % line)
            stamp = nanoseconds(row['timestamp'])
            pose = [float(row[key]) for key in ('x', 'y', 'yaw')]
            if not np.isfinite(pose).all():
                raise ValueError('Nonfinite pose at row %d' % line)
            if times and stamp <= times[-1]:
                raise ValueError('Timestamps must be strictly increasing and unique')
            times.append(stamp)
            poses.append(pose)
    if len(times) < 2:
        raise ValueError('At least two poses are required')
    return np.asarray(times, dtype=np.int64), np.asarray(poses, dtype=float)


def associate(estimated_times, reference_times, tolerance_ns):
    """Chronological greedy nearest match, monotone and one-to-one; no interpolation."""
    if tolerance_ns < 0:
        raise ValueError('Association tolerance must be nonnegative')
    pairs, previous = [], -1
    for i, stamp in enumerate(estimated_times):
        index = bisect.bisect_left(reference_times, stamp, lo=previous + 1)
        choices = [j for j in (index - 1, index) if previous < j < len(reference_times)]
        if not choices:
            continue
        j = min(choices, key=lambda k: (abs(int(reference_times[k]) - int(stamp)), k))
        if abs(int(reference_times[j]) - int(stamp)) <= tolerance_ns:
            pairs.append((i, j))
            previous = j
    if len(pairs) < 2:
        raise ValueError('Fewer than two timestamp associations; check clock units and tolerance')
    return np.asarray(pairs, dtype=int)


def relative_pairs(times, delta_ns, tolerance_ns):
    if delta_ns <= 0 or tolerance_ns < 0:
        raise ValueError('RPE delta must be positive and tolerance nonnegative')
    pairs = []
    for i, stamp in enumerate(times):
        target = int(stamp) + delta_ns
        j = bisect.bisect_left(times, target, lo=i + 1)
        candidates = [k for k in (j - 1, j) if i < k < len(times)]
        if candidates:
            k = min(candidates, key=lambda k: (abs(int(times[k]) - target), k))
            if abs(int(times[k]) - target) <= tolerance_ns:
                pairs.append((i, k))
    return pairs


def evaluate(estimated_times, estimated, reference_times, reference, *,
             alignment='none', association_ns=20_000_000,
             rpe_delta_ns=1_000_000_000, rpe_tolerance_ns=50_000_000):
    for times, poses in ((estimated_times, estimated), (reference_times, reference)):
        if (np.shape(poses) != (len(times), 3) or len(times) < 2 or
                not np.isfinite(poses).all() or any(int(b) <= int(a) for a, b in zip(times, times[1:]))):
            raise ValueError('Expected finite Nx3 poses and strictly increasing integer nanosecond times')
    matches = associate(estimated_times, reference_times, association_ns)
    times = estimated_times[matches[:, 0]]
    est, ref = estimated[matches[:, 0]].copy(), reference[matches[:, 1]].copy()
    rotation, shift = np.eye(2), np.zeros(2)
    if alignment == 'se2':
        if np.sum((est[:, :2] - est[:, :2].mean(axis=0)) ** 2) < 1e-16:
            raise ValueError('Stationary trajectory cannot determine a positional alignment')
        rotation, shift = align_se2(est[:, :2], ref[:, :2])
        est[:, :2], est[:, 2] = apply_se2(rotation, shift, est[:, :2], est[:, 2])
    elif alignment != 'none':
        raise ValueError('Alignment must be none or se2; metric scale is never fitted')
    translation = np.linalg.norm(est[:, :2] - ref[:, :2], axis=1)
    angles = np.abs(np.degrees(wrap(est[:, 2] - ref[:, 2])))
    pairs = relative_pairs(times, rpe_delta_ns, rpe_tolerance_ns)
    rpe = None
    if pairs:
        i, j = np.asarray(pairs).T
        relative_est, relative_ref = between(est[i], est[j]), between(ref[i], ref[j])
        # Norm of the translation of inv(reference_delta) @ estimate_delta.
        position_error = np.linalg.norm(relative_est[:, :2] - relative_ref[:, :2], axis=1)
        rotation_error = np.abs(np.degrees(wrap(relative_est[:, 2] - relative_ref[:, 2])))
        rpe = {'pairs': len(pairs), 'translation_m': stats(position_error),
               'rotation_deg': stats(rotation_error)}
    distance = float(path_length(ref[:, :2])[-1])
    report = {
        'alignment': {'mode': alignment, 'rotation': rotation.tolist(), 'translation_m': shift.tolist(), 'scale': 1.0},
        'association': {'policy': 'chronological greedy nearest, monotone one-to-one, no interpolation',
                        'tolerance_s': association_ns / 1e9, 'matched': len(matches),
                        'estimated_total': len(estimated), 'reference_total': len(reference),
                        'estimated_fraction': len(matches) / len(estimated),
                        'reference_fraction': len(matches) / len(reference),
                        'max_offset_s': max(abs(int(estimated_times[i]) - int(reference_times[j])) for i, j in matches) / 1e9},
        'duration_s': (int(times[-1]) - int(times[0])) / 1e9,
        'ate_m': stats(translation), 'orientation_error_deg': stats(angles),
        'rpe': rpe, 'rpe_delta_s': rpe_delta_ns / 1e9, 'rpe_tolerance_s': rpe_tolerance_ns / 1e9,
        'matched_reference_distance_m': distance,
        'endpoint_error_percent_of_distance': float(100 * translation[-1] / distance) if distance > 0 else None,
        'unavailable_metrics': ['mapping accuracy', 'loop closure statistics', 'CPU/memory', 'network usage', 'scalability'],
    }
    return report, times, est, ref


def convert_tum(source, destination):
    """Convert strictly planar TUM poses; reject roll/pitch or height variation."""
    rows, height = [], None
    with Path(source).open(encoding='utf-8-sig') as stream:
        for line in stream:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            fields = line.split()
            if len(fields) != 8:
                raise ValueError('TUM rows require timestamp tx ty tz qx qy qz qw')
            stamp = nanoseconds(fields[0])
            x, y, z, qx, qy, qz, qw = map(float, fields[1:])
            if not np.isfinite([x, y, z, qx, qy, qz, qw]).all():
                raise ValueError('TUM pose must be finite')
            norm = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if abs(norm - 1) > 0.001 or abs(qx) > 1e-6 or abs(qy) > 1e-6:
                raise ValueError('Expected unit planar yaw quaternion; use a 3D evaluator for nonplanar poses')
            if height is not None and abs(z - height) > 1e-5:
                raise ValueError('Changing height is not a planar trajectory')
            height = z
            yaw = 2 * math.atan2(qz, qw)
            if rows and stamp <= rows[-1][0]:
                raise ValueError('TUM timestamps must be strictly increasing')
            rows.append((stamp, x, y, float(wrap(yaw))))
    if len(rows) < 2:
        raise ValueError('At least two TUM poses required')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['timestamp', 'x', 'y', 'yaw'])
        for stamp, x, y, yaw in rows:
            writer.writerow([format(Decimal(stamp) / Decimal(1_000_000_000), '.9f'), x, y, yaw])


def write_outputs(output, report, times, estimated, reference):
    # A unique directory avoids overwriting previous experiment evidence.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    with (output / 'summary.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['algorithm', 'version', 'kind', 'alignment', 'matched', 'ate_rmse_m', 'rpe_translation_rmse_m', 'rpe_rotation_rmse_deg'])
        rpe = report['rpe']
        writer.writerow([report['experiment']['algorithm'], report['experiment']['version'], report['experiment']['kind'],
                         report['alignment']['mode'], len(times), report['ate_m']['rmse'],
                         rpe['translation_m']['rmse'] if rpe else '', rpe['rotation_deg']['rmse'] if rpe else ''])
    with (output / 'associated.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['timestamp_ns', 'estimated_x_m', 'estimated_y_m', 'estimated_yaw_rad',
                         'reference_x_m', 'reference_y_m', 'reference_yaw_rad'])
        for stamp, estimate, truth in zip(times, estimated, reference):
            writer.writerow([int(stamp), *estimate.tolist(), *truth.tolist()])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(reference[:, 0], reference[:, 1], label='Reference')
    ax.plot(estimated[:, 0], estimated[:, 1], label='Estimate (evaluated frame)')
    ax.set(xlabel='x [m]', ylabel='y [m]', title=report['experiment']['kind'] + ': ' + report['experiment']['algorithm'])
    ax.set_aspect('equal', adjustable='datalim')
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'trajectory.png', dpi=160)
    plt.close(fig)


def validate_metadata(meta):
    required = ('algorithm', 'version', 'environment', 'robot_count', 'dataset', 'experiment_date', 'dependencies', 'configuration', 'kind')
    missing = [key for key in required if key not in meta]
    if missing:
        raise ValueError('Missing experiment metadata: ' + ', '.join(missing))
    for key in ('algorithm', 'version', 'environment', 'dataset'):
        if not isinstance(meta[key], str) or not meta[key].strip():
            raise ValueError('Metadata requires nonempty string: ' + key)
    if type(meta['robot_count']) is not int or meta['robot_count'] < 1:
        raise ValueError('robot_count must be a positive integer')
    if meta['kind'] not in ('synthetic_fixture', 'simulation_measurement', 'recorded_measurement'):
        raise ValueError('Declare kind as synthetic_fixture, simulation_measurement or recorded_measurement')
    if not isinstance(meta['dependencies'], dict) or not isinstance(meta['configuration'], dict):
        raise ValueError('dependencies and configuration must be objects')
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='action', required=True)
    convert = subparsers.add_parser('convert-tum', help='Convert strictly planar TUM poses to CSV')
    convert.add_argument('source', type=Path)
    convert.add_argument('destination', type=Path)
    compare = subparsers.add_parser('evaluate')
    compare.add_argument('--estimate', type=Path, required=True)
    compare.add_argument('--reference', type=Path, required=True)
    compare.add_argument('--metadata', type=Path, required=True)
    compare.add_argument('--output', type=Path, required=True)
    compare.add_argument('--alignment', choices=('none', 'se2'), default='none')
    compare.add_argument('--max-difference', default='0.02')
    compare.add_argument('--rpe-delta', default='1.0')
    compare.add_argument('--rpe-tolerance', default='0.05')
    args = parser.parse_args()
    try:
        if args.action == 'convert-tum':
            convert_tum(args.source, args.destination)
            return
        meta = validate_metadata(json.loads(args.metadata.read_text(encoding='utf-8')))
        et, ep = load_csv(args.estimate)
        rt, rp = load_csv(args.reference)
        report, times, est, ref = evaluate(et, ep, rt, rp, alignment=args.alignment,
            association_ns=nanoseconds(args.max_difference), rpe_delta_ns=nanoseconds(args.rpe_delta),
            rpe_tolerance_ns=nanoseconds(args.rpe_tolerance))
        report.update({'schema_version': 1, 'experiment': meta,
            'evaluated_utc': datetime.now(timezone.utc).isoformat(),
            'evaluator_versions': {'python': platform.python_version(), 'numpy': np.__version__},
            'inputs': {key: {'filename': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                       for key, path in [('estimate', args.estimate), ('reference', args.reference), ('metadata', args.metadata)]}})
        write_outputs(args.output, report, times, est, ref)
        print(json.dumps({'output': str(args.output), 'ate_rmse_m': report['ate_m']['rmse'],
                          'matched': len(times), 'kind': meta['kind']}, indent=2))
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
