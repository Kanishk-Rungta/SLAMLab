"""Trajectory metrics: ATE, RPE, translational/rotational error, drift, localization accuracy and success."""
import math
from collections import defaultdict
import numpy as np
from .common import align_se2, apply_se2, between, path_length, stats, wrap


def estimates(run, robot):
    rows = [r for r in run.robots.get(robot, {}).get('pose', []) if all(map(np.isfinite, r['p']))]
    if not rows:
        return None
    t = np.array([r['t'] for r in rows])
    p = np.array([r['p'] for r in rows], float)
    est = {'t': t, 'xy': p[:, :2], 'yaw': p[:, 3], 'frame': np.array([r.get('frame', 'map') for r in rows]),
           'nan': sum(1 for r in run.robots[robot].get('pose', []) if not all(map(np.isfinite, r['p'])))}
    if any('odom' in r for r in rows):
        o = np.array([r.get('odom', [np.nan]*3) for r in rows], float)
        est['odom'] = o
    covs = [r.get('cov') for r in rows]
    if any(c is not None for c in covs):
        est['cov'] = covs
    return est


def alignments(run, cfg):
    """(robot, frame) -> (R, t) mapping the algorithm's frame into the world. 'world' frames are taken
    as-is; a frame shared by several robots gets one joint transform; otherwise per robot."""
    users = defaultdict(list)
    data = {}
    for robot in run.names:
        est = estimates(run, robot)
        if est is None or robot not in run.gt:
            continue
        data[robot] = est
        for frame in set(est['frame']):
            users[frame].append(robot)
    transforms = {}
    for frame, robots in users.items():
        if frame == 'world' and cfg['alignment'] == 'auto':
            for r in robots:
                transforms[(r, frame)] = (np.eye(2), np.zeros(2))
            continue
        groups = [robots] if (cfg['alignment'] in ('auto', 'joint') and len(robots) > 1) else [[r] for r in robots]
        for group in groups:
            src, dst = [], []
            for r in group:
                e = data[r]
                m = (e['frame'] == frame) & run.gt_valid(r, e['t'])
                src.append(e['xy'][m])
                dst.append(run.gt_at(r, e['t'][m])[:, :2])
            R, t = align_se2(np.concatenate(src), np.concatenate(dst))
            for r in group:
                transforms[(r, frame)] = (R, t)
    return transforms, data


def robot_metrics(run, robot, est, transforms, cfg):
    m = (np.array([(robot, f) in transforms for f in est['frame']])) & run.gt_valid(robot, est['t'])
    if m.sum() < 2:
        return None
    t = est['t'][m]
    xy = np.empty((m.sum(), 2))
    yaw = np.empty(m.sum())
    for frame in set(est['frame'][m]):
        k = est['frame'][m] == frame
        R, tr = transforms[(robot, frame)]
        xy[k], yaw[k] = apply_se2(R, tr, est['xy'][m][k], est['yaw'][m][k])
    gt = run.gt_at(robot, t)
    err = np.hypot(*(xy-gt[:, :2]).T)
    herr = np.degrees(np.abs(wrap(yaw-gt[:, 2])))
    dist = path_length(gt[:, :2])
    total = float(dist[-1])
    out = {'poses': int(m.sum()), 'nan_poses': int(est['nan']), 'distance_m': total,
           'duration_s': float(t[-1]-t[0])}
    out['ate_m'] = stats(err)
    out['rotation_error_deg'] = stats(herr)
    out['translation_error_m'] = {'mean': float(err.mean()), 'final': float(err[-1]), 'max': float(err.max())}
    # RPE over travelled distance and over time.
    est_pose, gt_pose = np.c_[xy, yaw], gt
    rpe = {}
    for d in cfg['rpe_distances']:
        j = np.searchsorted(dist, dist+d)
        ok = j < len(dist)
        if ok.sum() < 2:
            continue
        i, j = np.flatnonzero(ok), j[ok]
        e = between(est_pose[i], est_pose[j])-between(gt_pose[i], gt_pose[j])
        te, re = np.hypot(e[:, 0], e[:, 1]), np.degrees(np.abs(wrap(e[:, 2])))
        rpe['%gm' % d] = {'trans_rmse_m': float(np.sqrt(np.mean(te**2))), 'trans_mean_m': float(te.mean()),
                          'trans_pct': float(100*te.mean()/d), 'rot_mean_deg': float(re.mean()),
                          'rot_deg_per_m': float(re.mean()/d), 'pairs': int(len(te))}
    for d in cfg['rpe_seconds']:
        j = np.searchsorted(t, t+d)
        ok = j < len(t)
        if ok.sum() < 2:
            continue
        i, j = np.flatnonzero(ok), j[ok]
        e = between(est_pose[i], est_pose[j])-between(gt_pose[i], gt_pose[j])
        te, re = np.hypot(e[:, 0], e[:, 1]), np.degrees(np.abs(wrap(e[:, 2])))
        rpe['%gs' % d] = {'trans_rmse_m': float(np.sqrt(np.mean(te**2))), 'rot_mean_deg': float(re.mean()),
                          'pairs': int(len(te))}
    out['rpe'] = rpe
    # Drift: error growth with distance and time.
    out['drift'] = {
        'final_error_pct_of_distance': float(100*err[-1]/total) if total > 1 else None,
        'error_growth_m_per_100m': float(100*np.polyfit(dist, err, 1)[0]) if total > 5 else None,
        'heading_drift_deg_per_min': float(np.polyfit(t/60., herr, 1)[0]) if t[-1]-t[0] > 60 else None}
    # Localization accuracy at thresholds.
    out['localization_accuracy'] = {'within_%gm' % th: float(np.mean(err < th)) for th in cfg['accuracy_thresholds_m']}
    out['localization_accuracy'].update({'heading_within_%gdeg' % th: float(np.mean(herr < th))
                                          for th in cfg['accuracy_thresholds_deg']})
    # Dead-reckoning baseline, when the algorithm reports its odometry.
    if 'odom' in est:
        o = est['odom'][m]
        good = np.all(np.isfinite(o), 1)
        if good.sum() > 1:
            frames = est['frame'][m][good]
            oxy = np.empty((good.sum(), 2))
            for frame in set(frames):
                k = frames == frame
                R, tr = transforms[(robot, frame)]
                oxy[k] = apply_se2(R, tr, o[good][k, :2])
            oerr = np.hypot(*(oxy-gt[good][:, :2]).T)
            out['odometry_ate_rmse_m'] = float(np.sqrt(np.mean(oerr**2)))
            out['improvement_over_odometry'] = float(out['odometry_ate_rmse_m']/max(out['ate_m']['rmse'], 1e-9))
    # Covariance consistency (NEES), when covariances are reported.
    if 'cov' in est:
        covs = [c for c, keep in zip(est['cov'], m) if keep]
        nees = []
        for k, c in enumerate(covs):
            if c is None:
                continue
            e = np.r_[xy[k]-gt[k, :2], wrap(yaw[k]-gt[k, 2])]
            try:
                nees.append(float(e.dot(np.linalg.solve(np.asarray(c, float), e))))
            except np.linalg.LinAlgError:
                pass
        if nees:
            out['nees'] = {'mean': float(np.mean(nees)), 'expected': 3.0}
    # Pose jumps: estimate moves much more than the robot did between consecutive outputs.
    step_est = np.hypot(*np.diff(xy, axis=0).T)
    step_gt = np.hypot(*np.diff(gt[:, :2], axis=0).T)
    out['pose_jumps'] = int(np.sum(step_est > np.maximum(cfg['jump_min_m'], 3*step_gt+.3)))
    out['_series'] = {'t': t, 'err': err, 'herr': herr, 'xy': xy, 'yaw': yaw, 'dist': dist}
    return out


def success_rate(run, robot, series, tracking_ok, cfg):
    """Fraction of time (1 Hz samples over the robot's ground-truth span) with a recent pose, tracking
    reported OK, and the error under both success thresholds."""
    g = run.gt[robot]
    ts = np.arange(g['t'][0], g['t'][-1], 1.)
    if not len(ts) or series is None:
        return 0.
    idx = np.searchsorted(series['t'], ts, side='right')-1
    fresh = (idx >= 0) & (ts-series['t'][np.clip(idx, 0, None)] <= cfg['pose_timeout_s'])
    ok = fresh & tracking_ok(ts)
    k = np.clip(idx, 0, None)
    ok &= (series['err'][k] < cfg['success_trans_m']) & (series['herr'][k] < cfg['success_rot_deg'])
    return float(np.mean(ok))


def evaluate(run, cfg, tracking_ok_for):
    transforms, data = alignments(run, cfg)
    per_robot, errs, herrs = {}, [], []
    for robot, est in data.items():
        r = robot_metrics(run, robot, est, transforms, cfg)
        if r is None:
            continue
        r['localization_success_rate'] = success_rate(run, robot, r['_series'], tracking_ok_for(robot), cfg)
        per_robot[robot] = r
        errs.append(r['_series']['err'])
        herrs.append(r['_series']['herr'])
    swarm = {}
    if errs:
        e, h = np.concatenate(errs), np.concatenate(herrs)
        swarm = {'ate_m': stats(e), 'rotation_error_deg': stats(h),
                 'ate_rmse_mean_of_robots_m': float(np.mean([r['ate_m']['rmse'] for r in per_robot.values()])),
                 'localization_success_rate': float(np.mean([r['localization_success_rate'] for r in per_robot.values()])),
                 'distance_m': float(sum(r['distance_m'] for r in per_robot.values()))}
        for key in ('within_0.25m', 'within_0.5m'):
            vals = [r['localization_accuracy'].get(key) for r in per_robot.values() if key in r['localization_accuracy']]
            if vals:
                swarm['localization_accuracy_'+key] = float(np.mean(vals))
        rpe = [r['rpe'].get('1m', {}).get('trans_pct') for r in per_robot.values()]
        rpe = [v for v in rpe if v is not None]
        if rpe:
            swarm['rpe_1m_trans_pct'] = float(np.mean(rpe))
        rot = [r['rpe'].get('1m', {}).get('rot_deg_per_m') for r in per_robot.values()]
        rot = [v for v in rot if v is not None]
        if rot:
            swarm['rpe_1m_rot_deg_per_m'] = float(np.mean(rot))
        drift = [r['drift']['final_error_pct_of_distance'] for r in per_robot.values() if r['drift']['final_error_pct_of_distance'] is not None]
        if drift:
            swarm['drift_final_pct_of_distance'] = float(np.mean(drift))
        odo = [r['improvement_over_odometry'] for r in per_robot.values() if 'improvement_over_odometry' in r]
        if odo:
            swarm['improvement_over_odometry'] = float(np.mean(odo))
    return {'per_robot': per_robot, 'swarm': swarm}, transforms
