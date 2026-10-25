"""Tracking: initialization time, tracking-loss frequency, recovery and relocalization time."""
import numpy as np
from .common import stats


def timeline(run, robot, cfg):
    """[(t, state)] for a robot. Without reported tracking states, gaps in pose output longer than
    pose_timeout_s count as 'lost' (marked as inferred)."""
    events = run.robots.get(robot, {}).get('tracking', [])
    if events:
        return [(e['t'], e['state']) for e in sorted(events, key=lambda e: e['t'])], False
    poses = sorted(r['t'] for r in run.robots.get(robot, {}).get('pose', []))
    states = []
    for a, b in zip(poses, poses[1:]):
        if b-a > cfg['pose_timeout_s']:
            states += [(a+cfg['pose_timeout_s'], 'lost'), (b, 'ok')]
    if poses:
        states.insert(0, (poses[0], 'ok'))
        end = run.sim_end
        if end-poses[-1] > cfg['pose_timeout_s']:
            states.append((poses[-1]+cfg['pose_timeout_s'], 'lost'))
    return states, True


def ok_function(states):
    times = np.array([t for t, _ in states], float)
    ok = np.array([s == 'ok' for _, s in states], bool)

    def tracking_ok(ts):
        if not len(times):
            return np.zeros(len(ts), bool)
        k = np.searchsorted(times, ts, side='right')-1
        return np.where(k >= 0, ok[np.clip(k, 0, None)], False)
    return tracking_ok


def robot_metrics(run, robot, states, inferred, distance_m):
    rec = run.robots.get(robot, {})
    init = rec.get('init', [])
    poses = rec.get('pose', [])
    out = {'inferred_from_pose_gaps': inferred,
           'initialization_time_s': init[0]['t'] if init else (min(r['t'] for r in poses) if poses else None)}
    losses, recoveries, relocalizations = [], [], []
    lost_since = reloc_since = None
    lost_time = 0.
    for t, s in states:
        if s == 'lost' and lost_since is None:
            lost_since = t
            losses.append(t)
        elif s == 'relocalizing' and reloc_since is None:
            reloc_since = t
            if lost_since is None:
                lost_since = t
                losses.append(t)
        elif s == 'ok' and lost_since is not None:
            recoveries.append(t-lost_since)
            lost_time += t-lost_since
            if reloc_since is not None:
                relocalizations.append(t-reloc_since)
            lost_since = reloc_since = None
    if lost_since is not None:
        lost_time += max(0., run.sim_end-lost_since)
    span = max(run.sim_end-(out['initialization_time_s'] or 0.), 1e-6)
    out.update({'tracking_losses': len(losses),
                'tracking_loss_per_min': len(losses)/(span/60.),
                'tracking_loss_per_100m': (100.*len(losses)/distance_m) if distance_m and distance_m > 1 else None,
                'lost_fraction': lost_time/span,
                'unrecovered_at_end': lost_since is not None,
                'recovery_time_s': stats(recoveries),
                'relocalization_time_s': stats(relocalizations)})
    return out


def evaluate(run, cfg, distances):
    per_robot, ok_for = {}, {}
    for robot in run.names:
        states, inferred = timeline(run, robot, cfg)
        ok_for[robot] = ok_function(states)
        per_robot[robot] = robot_metrics(run, robot, states, inferred, distances.get(robot))
    vals = list(per_robot.values())
    swarm = {}
    if vals:
        inits = [v['initialization_time_s'] for v in vals if v['initialization_time_s'] is not None]
        rec = [v['recovery_time_s'].get('mean') for v in vals if v['recovery_time_s'].get('n')]
        rel = [v['relocalization_time_s'].get('mean') for v in vals if v['relocalization_time_s'].get('n')]
        swarm = {'initialization_time_s': float(np.mean(inits)) if inits else None,
                 'tracking_losses': int(sum(v['tracking_losses'] for v in vals)),
                 'tracking_loss_per_min': float(np.mean([v['tracking_loss_per_min'] for v in vals])),
                 'lost_fraction': float(np.mean([v['lost_fraction'] for v in vals])),
                 'recovery_time_mean_s': float(np.mean(rec)) if rec else None,
                 'relocalization_time_mean_s': float(np.mean(rel)) if rel else None}
    return {'per_robot': per_robot, 'swarm': swarm}, ok_for
