"""Evaluate one benchmark run.

    python evaluate.py RUN_DIR [--gt-map ab3_gt_map.npz] [--config my_config.json] [--name LABEL]

Writes RUN_DIR/metrics.json (everything, per robot and swarm) and RUN_DIR/report.md. The
`summary` block of metrics.json holds one headline number per benchmark parameter and is what
compare.py tabulates across algorithms, scenarios and robot counts. Metric definitions: README.md.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluation.common import Run
from evaluation import trajectory, tracking, mapping, loops, communication, resources

DEFAULT_CONFIG = {
    'alignment': 'auto',                 # auto | per_robot | joint | none
    'rpe_distances': [1.0, 5.0],         # m
    'rpe_seconds': [1.0, 10.0],          # s
    'accuracy_thresholds_m': [0.1, 0.25, 0.5, 1.0],
    'accuracy_thresholds_deg': [5.0, 10.0],
    'success_trans_m': 0.5, 'success_rot_deg': 10.0,   # localization success criterion
    'pose_timeout_s': 2.0,               # no pose for this long = not localized / lost
    'jump_min_m': 0.5,
    'map_tolerance_m': 0.15,             # mapped obstacle counts as correct within this distance
    'explored_radius_m': 1.5,            # walls within this of mapped free space count as "seen"
    'consistency_snapshots': 20,
    'max_series_points': 40,
    'loop_tp_trans_m': 0.5, 'loop_tp_rot_deg': 10.0, 'loop_place_radius_m': 3.0,
    'revisit_radius_m': 2.0, 'revisit_min_gap_m': 20.0, 'loop_window_s': 15.0,
    'comm_range_m': 40.0, 'bandwidth_bin_s': 1.0,
    'fail_ate_m': 2.0, 'fail_lost_fraction': 0.5, 'crash_grace_s': 30.0,
    'energy': {'compute_watts_per_core': 3.0, 'idle_watts': 2.5, 'robot_mass_kg': 2.3,
               'rolling_resistance': 0.02, 'drive_efficiency': 0.6},
}


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items() if not str(k).startswith('_')}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def evaluate(run_dir, gt_map=None, config=None, name=None):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    run = Run(run_dir)
    distances = {}
    # Tracking first (its 'ok' timeline feeds the localization success rate); distances are filled
    # in afterwards for the per-100 m rates.
    track, ok_for = tracking.evaluate(run, cfg, {})
    traj, transforms = trajectory.evaluate(run, cfg, lambda robot: ok_for[robot])
    distances = {r: v['distance_m'] for r, v in traj['per_robot'].items()}
    track, _ = tracking.evaluate(run, cfg, distances)
    gt = mapping.GroundTruthMap(gt_map) if gt_map else None
    maps = mapping.evaluate(run, gt, transforms, cfg)
    mapped = maps['swarm'].get('coverage_m2') if maps.get('swarm') else None
    if mapped is None:
        known = [v['map_size'].get('known_m2') for v in maps['per_robot'].values() if v.get('map_size', {}).get('known_m2')]
        mapped = sum(known) if known else None
    loop = loops.evaluate(run, cfg, transforms)
    comm = communication.evaluate(run, cfg, transforms, mapped, distances)
    proc = resources.processing(run)
    rt = resources.real_time(run)
    res = resources.summarize(run, cfg, proc, traj, mapped)
    energy = resources.energy(run, cfg, {r: v.get('cpu_seconds', 0.) for r, v in proc.items()})
    stab = resources.stability(run, cfg, traj, track)
    metrics = {'run': {'dir': os.path.abspath(run_dir), 'name': name or os.path.basename(os.path.abspath(run_dir)),
                       'algorithm': run.algorithm, 'robots': len(run.names), 'robot_names': run.names,
                       'scenario': run.meta.get('scenario', {}).get('name', 'baseline'),
                       'world': run.meta.get('world'), 'config': cfg},
               'trajectory': traj, 'tracking': track, 'mapping': maps, 'loop_closure': loop,
               'communication': comm, 'processing': {'per_robot': proc, 'swarm': res},
               'real_time': rt, 'energy': energy, 'stability': stab}
    metrics['summary'] = summary(metrics)
    metrics = jsonable(metrics)
    with open(os.path.join(run_dir, 'metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=1)
    with open(os.path.join(run_dir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(report(metrics))
    return metrics


def g(d, *path):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def summary(m):
    """One headline value per benchmark parameter (units in the key)."""
    t, tk, mp, lp, cm = m['trajectory']['swarm'], m['tracking']['swarm'], m['mapping'], m['loop_closure'], m['communication']
    pr, rt, st = m['processing']['swarm'], m['real_time'], m['stability']
    sw = mp.get('swarm', {})
    per = list(mp['per_robot'].values())
    mean = lambda xs: float(np.mean(xs)) if xs else None
    s = {
        'algorithm': m['run']['algorithm'], 'scenario': m['run']['scenario'], 'robots': m['run']['robots'],
        # Localization
        'ate_rmse_m': g(t, 'ate_m', 'rmse'),
        'rpe_1m_trans_pct': t.get('rpe_1m_trans_pct'),
        'rpe_1m_rot_deg_per_m': t.get('rpe_1m_rot_deg_per_m'),
        'translational_error_mean_m': g(t, 'ate_m', 'mean'),
        'rotational_error_mean_deg': g(t, 'rotation_error_deg', 'mean'),
        'trajectory_drift_pct_of_distance': t.get('drift_final_pct_of_distance'),
        'localization_accuracy_within_0.5m': t.get('localization_accuracy_within_0.5m'),
        'localization_success_rate': t.get('localization_success_rate'),
        'improvement_over_odometry_x': t.get('improvement_over_odometry'),
        # Mapping
        'map_accuracy_f1': sw.get('occupied_f1'),
        'map_occupied_precision': sw.get('occupied_precision'),
        'map_completeness_wall_recall': sw.get('wall_recall_global'),
        'map_coverage_m2': sw.get('coverage_m2'),
        'map_coverage_pct': sw.get('coverage_pct'),
        'map_consistency_temporal': mean([v['temporal_consistency'] for v in per if v.get('temporal_consistency') is not None]),
        'map_ghost_wall_ratio': sw.get('ghost_wall_ratio'),
        'map_reconstruction_error_chamfer_m': g(sw, 'reconstruction_error_m', 'chamfer_m'),
        'map_update_frequency_per_min': mean([v['map_updates_per_min'] for v in per]),
        'map_generation_time_90pct_s': mean([v.get('time_to_90%_of_final_coverage_s') for v in per if v.get('time_to_90%_of_final_coverage_s') is not None]),
        'map_size_bytes': mean([v['map_size'].get('bytes_raw') for v in per if v.get('map_size', {}).get('bytes_raw')]),
        'exploration_efficiency_m2_per_m': (sw['coverage_m2']/t['distance_m']) if sw.get('coverage_m2') and t.get('distance_m') else None,
        # Multi-robot
        'map_merging_accuracy_f1': g(mp, 'multi_robot', 'map_merging_accuracy', 'merged_occupied_f1_mean'),
        'map_merging_time_s': g(cm, 'map_merging_time_s', 'mean'),
        'first_merge_latency_s': g(cm, 'first_merge_latency_s', 'mean'),
        'inter_robot_pose_error_m': g(cm, 'inter_robot_pose_error_m', 'mean'),
        'map_overlap_consistency': g(mp, 'multi_robot', 'map_overlap_agreement'),
        'global_map_convergence_time_s': g(mp, 'multi_robot', 'global_map_convergence_time_s'),
        # Loop closure
        'loop_detection_accuracy': lp.get('detection_accuracy'),
        'loop_precision': lp.get('precision'),
        'loop_recall': lp.get('recall'),
        'loop_accepted': lp.get('accepted'),
        'loop_correction_error_after_m': g(lp, 'correction', 'error_after_m'),
        'loop_correction_gain_m': g(lp, 'correction', 'mean_gain_m'),
        # Compute
        'cpu_mean_pct': pr.get('cpu_mean_pct'), 'cpu_peak_pct': pr.get('cpu_peak_pct'),
        'memory_mean_mb': pr.get('memory_mean_mb'), 'memory_peak_mb': pr.get('memory_peak_mb'),
        'memory_overhead_mb': pr.get('memory_overhead_mb'),
        'computational_overhead_cores_per_robot': g(pr, 'computational_overhead', 'cpu_cores_per_robot'),
        'processing_latency_mean_ms': pr.get('processing_latency_mean_ms'),
        'throughput_fps': pr.get('throughput_fps_wall'),
        'optimization_time_mean_s': pr.get('optimization_time_mean_s'),
        'initialization_time_s': tk.get('initialization_time_s'),
        'real_time_factor': rt.get('real_time_factor'),
        'execution_time_wall_s': rt.get('wall_duration_s'),
        'execution_time_sim_s': rt.get('sim_duration_s'),
        # Communication
        'bandwidth_mean_Bps_per_robot': cm.get('bandwidth_mean_Bps_per_robot'),
        'total_tx_bytes': cm.get('total_tx_bytes'), 'total_rx_bytes': cm.get('total_rx_bytes'),
        'communication_overhead_bytes_per_m2': cm.get('overhead_bytes_per_m2_mapped'),
        'communication_latency_ms': (g(cm, 'latency_s', 'mean') or 0)*1000 if g(cm, 'latency_s', 'mean') is not None else None,
        'network_traffic_messages_per_s': cm.get('network_traffic_messages_per_s'),
        'packet_loss_rate': cm.get('packet_loss_rate'),
        # Robustness, failures, stability
        'tracking_loss_per_min': tk.get('tracking_loss_per_min'),
        'tracking_recovery_time_s': tk.get('recovery_time_mean_s'),
        'relocalization_time_s': tk.get('relocalization_time_mean_s'),
        'slam_failure_rate': st.get('slam_failure_rate'),
        'collisions_per_robot_hour': mean([v['collisions_per_hour'] for v in st['per_robot'].values()]),
        'stability_index': st.get('stability_index'),
        'energy_j_per_robot': m['energy'].get('mean_joules_per_robot'),
        'distance_travelled_m': t.get('distance_m'),
    }
    return s


def report(m):
    s = m['summary']
    lines = ['# SLAM benchmark report: %s' % m['run']['name'], '',
             '- Algorithm: **%s**' % s['algorithm'], '- Scenario: %s' % s['scenario'],
             '- Robots: %s' % s['robots'], '- World: %s' % m['run'].get('world'), '',
             '| Metric | Value |', '|---|---|']
    for k, v in s.items():
        if k in ('algorithm', 'scenario', 'robots'):
            continue
        if isinstance(v, float):
            v = '%.4g' % v
        lines.append('| %s | %s |' % (k, 'n/a' if v is None else v))
    lines += ['', 'Full per-robot detail: metrics.json. Definitions: slam_benchmark/README.md.', '']
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dir')
    ap.add_argument('--gt-map', default=None)
    ap.add_argument('--config', default=None, help='JSON overriding DEFAULT_CONFIG')
    ap.add_argument('--name', default=None)
    args = ap.parse_args()
    cfg = json.load(open(args.config)) if args.config else None
    m = evaluate(args.run_dir, args.gt_map, cfg, args.name)
    print(report(m))


if __name__ == '__main__':
    main()
