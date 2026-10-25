"""Map metrics against a ground-truth occupancy grid.

Ground-truth map (npz): occupied (bool, structure that must be mapped), floor (bool, where robots can
be), optional ignore (bool, e.g. furniture: neither rewarded nor penalised), resolution (m),
origin (x, y of the lower-left corner of cell [0, 0]); rows along +y.
"""
import os
import numpy as np
from .common import apply_se2, stats

try:
    import cv2
except ImportError:      # pragma: no cover
    cv2 = None


def distance_to(mask, res):
    """Distance (m) from every cell to the nearest True cell of mask."""
    if cv2 is not None:
        return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5)*res
    from scipy.ndimage import distance_transform_edt
    return distance_transform_edt(~mask)*res


class GroundTruthMap(object):
    def __init__(self, path):
        d = np.load(path)
        self.occupied = d['occupied'].astype(bool)
        self.floor = d['floor'].astype(bool)
        self.ignore = d['ignore'].astype(bool) if 'ignore' in d else np.zeros_like(self.occupied)
        self.res = float(d['resolution'])
        self.origin = np.asarray(d['origin'], float)
        self.shape = self.occupied.shape
        self.dist_occ = distance_to(self.occupied, self.res)
        self.dist_ign = distance_to(self.ignore, self.res) if self.ignore.any() else np.full(self.shape, np.inf)
        # Visible structure: occupied cells that border floor (inside of thick walls cannot be seen).
        border = np.zeros_like(self.floor)
        border[1:, :] |= self.floor[:-1, :]; border[:-1, :] |= self.floor[1:, :]
        border[:, 1:] |= self.floor[:, :-1]; border[:, :-1] |= self.floor[:, 1:]
        self.walls = self.occupied & border
        self.floor_m2 = float(self.floor.sum()*self.res**2)

    def cells(self, xy):
        c = np.floor((xy[:, 0]-self.origin[0])/self.res).astype(int)
        r = np.floor((xy[:, 1]-self.origin[1])/self.res).astype(int)
        ok = (r >= 0) & (r < self.shape[0]) & (c >= 0) & (c < self.shape[1])
        return r, c, ok


def load_snapshot(run, robot, record):
    path = os.path.join(run.dir, 'robots', robot, record['file'])
    if not os.path.exists(path):
        return None
    d = np.load(path)
    return d['cells'], float(d['resolution']), np.asarray(d['origin'], float)


def to_ground_truth_grid(snapshot, transform, gt):
    """Rasterise an estimated map (in its own frame) into the ground-truth grid: (known, occupied)."""
    cells, res, origin = snapshot
    R, t = transform
    rows, cols = np.nonzero(cells >= 0)
    xy = np.c_[origin[0]+(cols+.5)*res, origin[1]+(rows+.5)*res]
    world = apply_se2(R, t, xy)
    r, c, ok = gt.cells(world)
    known = np.zeros(gt.shape, bool)
    occ = np.zeros(gt.shape, bool)
    known[r[ok], c[ok]] = True
    is_occ = cells[rows, cols] == 1
    occ[r[ok & is_occ], c[ok & is_occ]] = True
    return known, occ


def score(known, occ, gt, cfg):
    tol = cfg['map_tolerance_m']
    free = known & ~occ
    res2 = gt.res**2
    out = {'known_m2': float(known.sum()*res2), 'occupied_m2': float(occ.sum()*res2)}
    covered = free & gt.floor
    out['coverage_m2'] = float(covered.sum()*res2)
    out['coverage_pct'] = float(100*covered.sum()/max(gt.floor.sum(), 1))
    out['completeness_floor_known_pct'] = float(100*(known & gt.floor).sum()/max(gt.floor.sum(), 1))
    # Obstacle accuracy (ignoring cells near "ignore" structure such as furniture).
    scored_occ = occ & (gt.dist_ign > tol)
    d_est = gt.dist_occ[scored_occ]
    precision = float(np.mean(d_est <= tol)) if len(d_est) else None
    explored = distance_to(free, gt.res) <= cfg['explored_radius_m'] if free.any() else np.zeros(gt.shape, bool)
    dist_est = distance_to(occ, gt.res) if occ.any() else np.full(gt.shape, np.inf)
    walls_seen = gt.walls & explored
    recall_explored = float(np.mean(dist_est[walls_seen] <= tol)) if walls_seen.any() else None
    recall_global = float(np.mean(dist_est[gt.walls] <= tol)) if gt.walls.any() else None
    f1 = (2*precision*recall_explored/(precision+recall_explored)
          if precision and recall_explored else None)
    out.update({'occupied_precision': precision, 'wall_recall_explored': recall_explored,
                'wall_recall_global': recall_global, 'occupied_f1': f1,
                'free_accuracy': float(np.mean(~gt.occupied[free] & (gt.floor[free] | gt.ignore[free]))) if free.any() else None,
                'ghost_wall_ratio': float(np.mean(d_est > 2*tol)) if len(d_est) else None})
    # Reconstruction error (Chamfer, both directions).
    if len(d_est) and walls_seen.any():
        d_gt = dist_est[walls_seen]
        d_gt = d_gt[np.isfinite(d_gt)]
        out['reconstruction_error_m'] = {'est_to_gt': stats(d_est), 'gt_to_est_mean': float(d_gt.mean()) if len(d_gt) else None,
                                         'chamfer_m': float((d_est.mean()+d_gt.mean())/2) if len(d_gt) else None,
                                         'hausdorff95_m': float(max(np.percentile(d_est, 95), np.percentile(d_gt, 95))) if len(d_gt) else None}
    return out


def robot_snapshots(run, robot, kind):
    return sorted([r for r in run.robots.get(robot, {}).get('map', []) if r.get('kind', 'local') == kind],
                  key=lambda r: r['t'])


def temporal_consistency(run, robot, records, cfg):
    """Fraction of cells known in two consecutive snapshots whose state did not flip."""
    flips, total = 0, 0
    prev = None
    for rec in records[-cfg['consistency_snapshots']:]:
        snap = load_snapshot(run, robot, rec)
        if snap is None:
            continue
        if prev is not None and prev[0].shape == snap[0].shape and np.allclose(prev[2], snap[2]):
            both = (prev[0] >= 0) & (snap[0] >= 0)
            flips += int(np.sum(prev[0][both] != snap[0][both]))
            total += int(both.sum())
        prev = snap
    return 1-flips/total if total else None


def evaluate(run, gt, transforms, cfg):
    out = {'per_robot': {}, 'swarm': {}, 'multi_robot': {}}
    latest = {}
    for robot in run.names:
        rec = run.robots.get(robot, {})
        updates = rec.get('map_update', [])+rec.get('map', [])
        span = max(run.sim_end/60., 1e-6)
        r = {'map_updates_per_min': len(updates)/span}
        durations = [u.get('duration') for u in updates if u.get('duration') is not None]
        if durations:
            r['map_update_time_s'] = stats(durations)
        local = robot_snapshots(run, robot, 'local')
        if local:
            last = local[-1]
            r['map_size'] = {'known_cells': last.get('known_cells'), 'bytes_file': last.get('bytes_file'),
                             'bytes_raw': last.get('bytes_raw'), 'memory_bytes': last.get('memory_bytes')}
            frame = last.get('frame', 'map')
            if gt is not None and (robot, frame) in transforms:
                snap = load_snapshot(run, robot, last)
                if snap is not None:
                    known, occ = to_ground_truth_grid(snap, transforms[(robot, frame)], gt)
                    latest[robot] = (known, occ)
                    r.update(score(known, occ, gt, cfg))
                    r['map_size']['known_m2'] = r['known_m2']
                    # Map generation time: when coverage reached 50/90% of its final value.
                    series = []
                    for rec_k in local[::max(1, len(local)//cfg['max_series_points'])]+[last]:
                        s = load_snapshot(run, robot, rec_k)
                        if s is None:
                            continue
                        kn, oc = to_ground_truth_grid(s, transforms[(robot, rec_k.get('frame', 'map'))], gt)
                        series.append((rec_k['t'], float(((kn & ~oc) & gt.floor).sum())))
                    final = series[-1][1] if series else 0.
                    for frac in (.5, .9):
                        hit = [t for t, v in series if final and v >= frac*final]
                        r['time_to_%d%%_of_final_coverage_s' % int(frac*100)] = hit[0] if hit else None
            r['temporal_consistency'] = temporal_consistency(run, robot, local, cfg)
        merged = robot_snapshots(run, robot, 'merged')
        if merged and gt is not None:
            last = merged[-1]
            frame = last.get('frame', 'map')
            if (robot, frame) in transforms:
                snap = load_snapshot(run, robot, last)
                if snap is not None:
                    known, occ = to_ground_truth_grid(snap, transforms[(robot, frame)], gt)
                    r['merged_map'] = score(known, occ, gt, cfg)
        out['per_robot'][robot] = r
    if gt is not None and latest:
        known = np.any([k for k, _ in latest.values()], axis=0)
        occ = np.any([o for _, o in latest.values()], axis=0)
        out['swarm'] = score(known, occ, gt, cfg)
        out['swarm']['floor_m2'] = gt.floor_m2
        out['multi_robot'].update(overlap_consistency(latest))
        out['multi_robot'].update(convergence(run, gt, transforms, cfg))
    merged_scores = [v['merged_map'] for v in out['per_robot'].values() if 'merged_map' in v]
    if merged_scores:
        f1 = [m['occupied_f1'] for m in merged_scores if m.get('occupied_f1') is not None]
        ch = [m['reconstruction_error_m']['chamfer_m'] for m in merged_scores
              if m.get('reconstruction_error_m', {}).get('chamfer_m') is not None]
        out['multi_robot']['map_merging_accuracy'] = {
            'merged_occupied_f1_mean': float(np.mean(f1)) if f1 else None,
            'merged_chamfer_mean_m': float(np.mean(ch)) if ch else None,
            'merged_coverage_pct_mean': float(np.mean([m['coverage_pct'] for m in merged_scores]))}
    return out


def overlap_consistency(latest):
    """Agreement of robots' own maps where they overlap (same cell state; occupied IoU with 1-cell slack)."""
    names = sorted(latest)
    agree, iou = [], []
    for i, a in enumerate(names):
        for b in names[i+1:]:
            ka, oa = latest[a]
            kb, ob = latest[b]
            both = ka & kb
            if both.sum() < 100:
                continue
            agree.append(float(np.mean(oa[both] == ob[both])))
            if cv2 is not None:
                kernel = np.ones((3, 3), np.uint8)
                da = cv2.dilate(oa.astype(np.uint8), kernel).astype(bool) & both
                db = cv2.dilate(ob.astype(np.uint8), kernel).astype(bool) & both
                inter = np.sum(oa & both & db)+np.sum(ob & both & da)
                union = np.sum(oa & both)+np.sum(ob & both)
                if union:
                    iou.append(float(inter/union))
    out = {'overlapping_pairs': len(agree)}
    if agree:
        out['map_overlap_agreement'] = float(np.mean(agree))
    if iou:
        out['map_overlap_occupied_iou'] = float(np.mean(iou))
    return out


def convergence(run, gt, transforms, cfg):
    """Global map (union of every robot's latest local map) over time: earliest time after which
    coverage stays within 5% of its final value and occupied F1 within 0.02."""
    snaps = {robot: robot_snapshots(run, robot, 'local') for robot in run.names}
    times = sorted({r['t'] for recs in snaps.values() for r in recs})
    if len(times) < 2:
        return {}
    times = times[::max(1, len(times)//cfg['max_series_points'])]+[times[-1]]
    series = []
    for T in times:
        known = np.zeros(gt.shape, bool)
        occ = np.zeros(gt.shape, bool)
        for robot, recs in snaps.items():
            before = [r for r in recs if r['t'] <= T]
            if not before or (robot, before[-1].get('frame', 'map')) not in transforms:
                continue
            s = load_snapshot(run, robot, before[-1])
            if s is None:
                continue
            k, o = to_ground_truth_grid(s, transforms[(robot, before[-1].get('frame', 'map'))], gt)
            known |= k
            occ |= o
        sc = score(known, occ, gt, dict(cfg, explored_radius_m=cfg['explored_radius_m']))
        series.append((T, sc['coverage_pct'], sc.get('occupied_f1')))
    final_cov, final_f1 = series[-1][1], series[-1][2]
    converged = None
    for i, (T, cov, f1) in enumerate(series):
        if all(c >= .95*final_cov and (final_f1 is None or f is None or abs(f-final_f1) <= .02) for _, c, f in series[i:]):
            converged = T
            break
    return {'global_map_convergence_time_s': converged,
            'global_map_series': [{'t': T, 'coverage_pct': c, 'occupied_f1': f} for T, c, f in series]}
