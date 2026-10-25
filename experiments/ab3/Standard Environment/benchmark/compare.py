"""Compare evaluated runs across algorithms, scenarios and robot counts.

    python compare.py RUN_DIR [RUN_DIR ...] --out comparison/ [--baseline baseline]

Each RUN_DIR must contain metrics.json (from evaluate.py). Runs with the same (algorithm, scenario,
robots) are averaged (± standard deviation). Writes to --out:
  comparison.md / .csv / .html   headline metrics per algorithm and robot count, with ranks
  robustness.md / .csv           each scenario relative to the same algorithm's baseline
  scalability.md / .csv          metrics vs robot count, with the fitted growth exponent (y ~ N^b)
  charts/*.png                   if matplotlib is installed
"""
import argparse
import csv
import glob
import json
import os
from collections import defaultdict
import numpy as np

# Direction of "better" for ranking: +1 higher is better, -1 lower is better.
DIRECTION = {
    'ate_rmse_m': -1, 'rpe_1m_trans_pct': -1, 'rpe_1m_rot_deg_per_m': -1, 'translational_error_mean_m': -1,
    'rotational_error_mean_deg': -1, 'trajectory_drift_pct_of_distance': -1,
    'localization_accuracy_within_0.5m': 1, 'localization_success_rate': 1, 'improvement_over_odometry_x': 1,
    'map_accuracy_f1': 1, 'map_occupied_precision': 1, 'map_completeness_wall_recall': 1, 'map_coverage_m2': 1,
    'map_coverage_pct': 1, 'map_consistency_temporal': 1, 'map_ghost_wall_ratio': -1,
    'map_reconstruction_error_chamfer_m': -1, 'map_update_frequency_per_min': 1, 'map_generation_time_90pct_s': -1,
    'map_size_bytes': -1, 'exploration_efficiency_m2_per_m': 1, 'map_merging_accuracy_f1': 1,
    'map_merging_time_s': -1, 'first_merge_latency_s': -1, 'inter_robot_pose_error_m': -1,
    'map_overlap_consistency': 1, 'global_map_convergence_time_s': -1, 'loop_detection_accuracy': 1,
    'loop_precision': 1, 'loop_recall': 1, 'loop_correction_error_after_m': -1, 'loop_correction_gain_m': 1,
    'cpu_mean_pct': -1, 'cpu_peak_pct': -1, 'memory_mean_mb': -1, 'memory_peak_mb': -1,
    'memory_overhead_mb': -1, 'computational_overhead_cores_per_robot': -1, 'processing_latency_mean_ms': -1,
    'throughput_fps': 1, 'optimization_time_mean_s': -1, 'initialization_time_s': -1, 'real_time_factor': 1,
    'execution_time_wall_s': -1, 'bandwidth_mean_Bps_per_robot': -1, 'total_tx_bytes': -1,
    'total_rx_bytes': -1, 'communication_overhead_bytes_per_m2': -1, 'communication_latency_ms': -1,
    'network_traffic_messages_per_s': -1, 'packet_loss_rate': -1, 'tracking_loss_per_min': -1,
    'tracking_recovery_time_s': -1, 'relocalization_time_s': -1, 'slam_failure_rate': -1,
    'collisions_per_robot_hour': -1, 'stability_index': 1, 'energy_j_per_robot': -1,
}
ROBUSTNESS_KEYS = ['ate_rmse_m', 'localization_success_rate', 'map_accuracy_f1', 'map_coverage_pct',
                   'loop_precision', 'packet_loss_rate', 'slam_failure_rate', 'tracking_loss_per_min',
                   'inter_robot_pose_error_m', 'stability_index']
SCALING_KEYS = ['real_time_factor', 'cpu_mean_pct', 'memory_peak_mb', 'bandwidth_mean_Bps_per_robot',
                'network_traffic_messages_per_s', 'ate_rmse_m', 'map_coverage_pct',
                'global_map_convergence_time_s', 'optimization_time_mean_s', 'packet_loss_rate']


def load(paths):
    runs = []
    for p in paths:
        for path in glob.glob(p):
            f = path if path.endswith('.json') else os.path.join(path, 'metrics.json')
            if os.path.exists(f):
                runs.append(json.load(open(f)))
    return runs


def group(runs):
    groups = defaultdict(list)
    for m in runs:
        s = m['summary']
        groups[(s['algorithm'], s['scenario'], s['robots'])].append(s)
    table = {}
    for key, items in groups.items():
        row = {'runs': len(items)}
        for metric in DIRECTION:
            vals = [i.get(metric) for i in items if isinstance(i.get(metric), (int, float))]
            if vals:
                row[metric] = float(np.mean(vals))
                row[metric+'_std'] = float(np.std(vals)) if len(vals) > 1 else None
        table[key] = row
    return table


def fmt(v, std=None):
    if v is None:
        return 'n/a'
    s = '%.4g' % v
    return s+(' ± %.2g' % std if std else '')


def ranks(columns, table):
    """Rank of each column for each metric (1 = best) and the mean rank."""
    out = {c: {} for c in columns}
    for metric, d in DIRECTION.items():
        vals = [(table[c].get(metric), c) for c in columns if table[c].get(metric) is not None]
        if len(vals) < 2:
            continue
        vals.sort(key=lambda x: -d*x[0])
        for r, (_, c) in enumerate(vals, 1):
            out[c][metric] = r
    mean = {c: (float(np.mean(list(v.values()))) if v else None) for c, v in out.items()}
    return out, mean


def write_table(path_base, header, rows):
    with open(path_base+'.md', 'w', encoding='utf-8') as f:
        f.write('| '+' | '.join(header)+' |\n|'+'---|'*len(header)+'\n')
        for row in rows:
            f.write('| '+' | '.join(str(c) for c in row)+' |\n')
    with open(path_base+'.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main_table(table, baseline, out):
    columns = sorted(k for k in table if k[1] == baseline) or sorted(table)
    rk, mean_rank = ranks(columns, table)
    header = ['Metric (better)']+['%s, %d robots (%s)' % (a, n, s) for a, s, n in columns]
    rows = []
    for metric, d in DIRECTION.items():
        if all(table[c].get(metric) is None for c in columns):
            continue
        rows.append(['%s (%s)' % (metric, 'higher' if d > 0 else 'lower')] +
                    ['%s%s' % (fmt(table[c].get(metric), table[c].get(metric+'_std')),
                               (' [#%d]' % rk[c][metric]) if metric in rk[c] else '') for c in columns])
    rows.append(['**mean rank (lower is better)**']+[fmt(mean_rank[c]) for c in columns])
    rows.append(['runs averaged']+[table[c]['runs'] for c in columns])
    write_table(os.path.join(out, 'comparison'), header, rows)
    with open(os.path.join(out, 'comparison.html'), 'w', encoding='utf-8') as f:
        f.write('<!doctype html><meta charset="utf-8"><title>SLAM comparison</title><style>body{font-family:sans-serif}'
                'table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px;font-size:13px}'
                'tr:nth-child(even){background:#f6f6f6}</style><h2>SLAM benchmark comparison</h2><table><tr>')
        f.write(''.join('<th>%s</th>' % h for h in header)+'</tr>')
        for row in rows:
            f.write('<tr>'+''.join('<td>%s</td>' % c for c in row)+'</tr>')
        f.write('</table>')
    return columns


def robustness(table, baseline, out):
    header = ['Algorithm', 'Robots', 'Scenario']+['%s (scenario/baseline)' % k for k in ROBUSTNESS_KEYS]
    rows = []
    for (alg, scen, n), row in sorted(table.items()):
        base = table.get((alg, baseline, n))
        if scen == baseline or base is None:
            continue
        cells = []
        for k in ROBUSTNESS_KEYS:
            a, b = row.get(k), base.get(k)
            cells.append('n/a' if a is None or b is None else ('%.3g (%.3g/%.3g)' % (a/b if b else float('inf'), a, b)))
        rows.append([alg, n, scen]+cells)
    write_table(os.path.join(out, 'robustness'), header, rows)


def scalability(table, baseline, out):
    header = ['Algorithm', 'Metric']+['N=%d' % n for n in sorted({k[2] for k in table})]+['growth exponent b (y~N^b)']
    counts = sorted({k[2] for k in table})
    rows = []
    for alg in sorted({k[0] for k in table}):
        for metric in SCALING_KEYS:
            pts = [(n, table[(alg, baseline, n)].get(metric)) for n in counts if (alg, baseline, n) in table]
            pts = [(n, v) for n, v in pts if v is not None]
            if len(pts) < 1:
                continue
            b = None
            good = [(n, v) for n, v in pts if v > 0]
            if len(good) >= 2:
                b = float(np.polyfit(np.log([p[0] for p in good]), np.log([p[1] for p in good]), 1)[0])
            vals = dict(pts)
            rows.append([alg, metric]+[fmt(vals.get(n)) for n in counts]+[fmt(b)])
    write_table(os.path.join(out, 'scalability'), header, rows)


def charts(table, columns, out):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return
    os.makedirs(os.path.join(out, 'charts'), exist_ok=True)
    groups = [('accuracy', ['ate_rmse_m', 'rpe_1m_trans_pct', 'rotational_error_mean_deg', 'localization_success_rate']),
              ('mapping', ['map_accuracy_f1', 'map_coverage_pct', 'map_reconstruction_error_chamfer_m', 'map_overlap_consistency']),
              ('loops', ['loop_precision', 'loop_recall', 'loop_detection_accuracy', 'loop_correction_gain_m']),
              ('compute', ['cpu_mean_pct', 'memory_peak_mb', 'processing_latency_mean_ms', 'real_time_factor']),
              ('communication', ['bandwidth_mean_Bps_per_robot', 'communication_latency_ms', 'packet_loss_rate', 'communication_overhead_bytes_per_m2'])]
    labels = ['%s\n%d robots' % (a, n) for a, s, n in columns]
    for name, metrics in groups:
        fig, axes = plt.subplots(1, len(metrics), figsize=(4*len(metrics), 3.6))
        for ax, metric in zip(axes, metrics):
            vals = [table[c].get(metric) or 0 for c in columns]
            ax.bar(range(len(columns)), vals, color='#4C78A8')
            ax.set_xticks(range(len(columns)))
            ax.set_xticklabels(labels, fontsize=7, rotation=30, ha='right')
            ax.set_title('%s (%s)' % (metric, 'higher better' if DIRECTION[metric] > 0 else 'lower better'), fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out, 'charts', name+'.png'), dpi=130)
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--out', default='comparison')
    ap.add_argument('--baseline', default='baseline', help='scenario name used as the reference')
    args = ap.parse_args()
    runs = load(args.runs)
    if not runs:
        raise SystemExit('No metrics.json found; run evaluate.py on each run first')
    os.makedirs(args.out, exist_ok=True)
    table = group(runs)
    columns = main_table(table, args.baseline, args.out)
    robustness(table, args.baseline, args.out)
    scalability(table, args.baseline, args.out)
    charts(table, columns, args.out)
    print('Compared %d runs in %d groups -> %s' % (len(runs), len(table), os.path.abspath(args.out)))


if __name__ == '__main__':
    main()
