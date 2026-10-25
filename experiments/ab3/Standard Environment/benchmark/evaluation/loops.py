"""Loop closure: detection accuracy, precision, recall and correction error, checked against ground truth.

A reported loop is a true positive when ground truth confirms it: with a claimed relative pose, the
claim must match the true relative pose of the two observations within (loop_tp_trans_m,
loop_tp_rot_deg); without one, the two places must be within loop_place_radius_m.
Recall uses true revisit episodes: a robot comes within revisit_radius_m of a place it visited at
least revisit_min_gap_m of travel earlier (intra-robot), or that another robot visited earlier
(inter-robot). An episode is detected when a true-positive accepted loop by that robot falls inside it.
"""
import numpy as np
from .common import between, path_length, stats, wrap


def classify(run, robot, loop, cfg):
    other = loop.get('matched_robot') or robot
    tq, tm = loop['t'], loop.get('matched_time')
    if tm is None or robot not in run.gt or other not in run.gt:
        return None, None
    if not (run.gt_valid(robot, tq)[0] and run.gt_valid(other, tm)[0]):
        return None, None
    pq, pm = run.gt_at(robot, tq)[0], run.gt_at(other, tm)[0]
    true_rel = between(pm, pq)[0]
    if loop.get('relative') is not None:
        rel = np.asarray(loop['relative'], float)
        dt = float(np.hypot(*(rel[:2]-true_rel[:2])))
        dr = float(np.degrees(abs(wrap(rel[2]-true_rel[2]))))
        return (dt <= cfg['loop_tp_trans_m'] and dr <= cfg['loop_tp_rot_deg']), (dt, dr)
    return float(np.hypot(*(pq[:2]-pm[:2]))) <= cfg['loop_place_radius_m'], None


def revisit_episodes(run, cfg):
    """{robot: [(t_start, t_end, kind)]} from ground truth, sampled every 0.5 m of travel."""
    samples = {}
    for robot, g in run.gt.items():
        d = path_length(g['xy'])
        idx = np.searchsorted(d, np.arange(0, d[-1], .5)) if len(d) else []
        samples[robot] = (g['t'][idx], g['xy'][idx], d[idx])
    episodes = {}
    for robot, (t, xy, d) in samples.items():
        flags = []
        for i in range(len(t)):
            kind = None
            early = d <= d[i]-cfg['revisit_min_gap_m']
            if early.any() and np.min(np.hypot(*(xy[early]-xy[i]).T)) <= cfg['revisit_radius_m']:
                kind = 'intra'
            else:
                for other, (to, xo, _) in samples.items():
                    if other == robot:
                        continue
                    before = to < t[i]
                    if before.any() and np.min(np.hypot(*(xo[before]-xy[i]).T)) <= cfg['revisit_radius_m']:
                        kind = 'inter'
                        break
            flags.append(kind)
        eps, start = [], None
        for i, kind in enumerate(flags+[None]):
            if kind and start is None:
                start, start_kind = i, kind
            elif not kind and start is not None:
                eps.append((t[start], t[i-1], start_kind))
                start = None
        episodes[robot] = eps
    return episodes


def correction_error(run, robot, loop, transforms):
    """Pose error just before and just after an accepted loop (aligned estimate vs ground truth)."""
    poses = run.robots[robot].get('pose', [])
    if loop.get('pose_before') is not None and loop.get('pose_after') is not None:
        before, after = loop['pose_before'], loop['pose_after']
        t_before = t_after = loop['t']
        frame = poses[0].get('frame', 'map') if poses else 'map'
    else:
        tb = [p for p in poses if loop['t']-2 <= p['t'] < loop['t']]
        ta = [p for p in poses if loop['t'] <= p['t'] <= loop['t']+2]
        if not tb or not ta:
            return None
        before, after, frame = tb[-1]['p'][:2], ta[0]['p'][:2], tb[-1].get('frame', 'map')
        t_before, t_after = tb[-1]['t'], ta[0]['t']
    if (robot, frame) not in transforms or not run.gt_valid(robot, [t_before, t_after]).all():
        return None
    R, t = transforms[(robot, frame)]
    # Each estimate is compared with ground truth at its own time.
    gb, ga = run.gt_at(robot, [t_before, t_after])[:, :2]
    eb = float(np.hypot(*(R.dot(np.asarray(before[:2], float))+t-gb)))
    ea = float(np.hypot(*(R.dot(np.asarray(after[:2], float))+t-ga)))
    return eb, ea


def evaluate(run, cfg, transforms):
    total = {'accepted': 0, 'rejected': 0, 'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'unverifiable': 0}
    rel_err, corrections, per_robot = [], [], {}
    accepted_tp_times = {}
    for robot in run.names:
        loops = run.robots.get(robot, {}).get('loop', [])
        c = {'accepted': 0, 'rejected': 0, 'tp': 0, 'fp': 0}
        for loop in loops:
            positive, err = classify(run, robot, loop, cfg)
            key = 'accepted' if loop['accepted'] else 'rejected'
            c[key] += 1
            total[key] += 1
            if positive is None:
                total['unverifiable'] += 1
                continue
            if loop['accepted']:
                total['tp' if positive else 'fp'] += 1
                c['tp' if positive else 'fp'] += 1
                if positive:
                    accepted_tp_times.setdefault(robot, []).append(loop['t'])
                if err is not None:
                    rel_err.append(err)
                ce = correction_error(run, robot, loop, transforms)
                if ce is not None:
                    corrections.append(ce)
            else:
                total['tn' if not positive else 'fn'] += 1
        c['precision'] = c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else None
        per_robot[robot] = c
    episodes = revisit_episodes(run, cfg) if run.gt else {}
    detected = {'intra': [0, 0], 'inter': [0, 0]}
    for robot, eps in episodes.items():
        times = accepted_tp_times.get(robot, [])
        for t0, t1, kind in eps:
            detected[kind][1] += 1
            if any(t0-cfg['loop_window_s'] <= t <= t1+cfg['loop_window_s'] for t in times):
                detected[kind][0] += 1
    judged = total['tp']+total['fp']+total['tn']+total['fn']
    out = {'candidates': total['accepted']+total['rejected'], 'accepted': total['accepted'],
           'true_positives': total['tp'], 'false_positives': total['fp'],
           'precision': total['tp']/(total['tp']+total['fp']) if total['tp']+total['fp'] else None,
           'detection_accuracy': (total['tp']+total['tn'])/judged if judged else None,
           'unverifiable': total['unverifiable'],
           'revisit_episodes': {k: v[1] for k, v in detected.items()},
           'recall': (sum(v[0] for v in detected.values())/sum(v[1] for v in detected.values())
                      if sum(v[1] for v in detected.values()) else None),
           'recall_intra_robot': detected['intra'][0]/detected['intra'][1] if detected['intra'][1] else None,
           'recall_inter_robot': detected['inter'][0]/detected['inter'][1] if detected['inter'][1] else None,
           'per_robot': per_robot}
    if rel_err:
        out['relative_pose_error_trans_m'] = stats([e[0] for e in rel_err])
        out['relative_pose_error_rot_deg'] = stats([e[1] for e in rel_err])
    if corrections:
        out['correction'] = {'error_before_m': float(np.mean([c[0] for c in corrections])),
                             'error_after_m': float(np.mean([c[1] for c in corrections])),
                             'mean_gain_m': float(np.mean([c[0]-c[1] for c in corrections])),
                             'n': len(corrections)}
    if out['precision'] is not None and out['recall'] is not None and out['precision']+out['recall'] > 0:
        out['f1'] = 2*out['precision']*out['recall']/(out['precision']+out['recall'])
    return out
