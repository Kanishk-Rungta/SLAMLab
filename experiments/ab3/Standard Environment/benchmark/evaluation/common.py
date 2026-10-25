"""Run loading and shared geometry for the evaluator."""
import json
import math
import os
from collections import defaultdict
import numpy as np


def wrap(a):
    return (np.asarray(a)+np.pi) % (2*np.pi)-np.pi


def read_jsonl(path):
    records = []
    if not os.path.exists(path):
        return records
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                pass            # a truncated last line after a crash
    return records


class Run(object):
    """Everything recorded for one benchmark run."""

    def __init__(self, run_dir):
        self.dir = run_dir
        meta_path = os.path.join(run_dir, 'run_meta.json')
        self.meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
        self.supervisor = read_jsonl(os.path.join(run_dir, 'supervisor.jsonl'))
        self.gt = self._load_gt(os.path.join(run_dir, 'ground_truth.jsonl'))
        self.robots = {}
        robots_dir = os.path.join(run_dir, 'robots')
        if os.path.isdir(robots_dir):
            for name in sorted(os.listdir(robots_dir)):
                records = read_jsonl(os.path.join(robots_dir, name, 'bench.jsonl'))
                by_type = defaultdict(list)
                for r in records:
                    by_type[r.get('type')].append(r)
                self.robots[name] = by_type
        self.names = sorted(set(self.robots) | set(self.gt))
        algorithms = sorted({r['algorithm'] for v in self.robots.values() for r in v.get('meta', [])})
        self.algorithm = ', '.join(algorithms) or 'unknown'
        times = [r['t'] for r in self.supervisor if 't' in r]+[g['t'][-1] for g in self.gt.values() if len(g['t'])]
        self.sim_end = max(times) if times else 0.
        stops = [r['t'] for r in self.supervisor if r.get('type') == 'stop_requested']
        if stops:   # the supervisor keeps recording while robots shut down; the run ends at the stop
            self.sim_end = min(self.sim_end, stops[0])

    @staticmethod
    def _load_gt(path):
        series = defaultdict(list)
        for rec in read_jsonl(path):
            for name, p in rec['p'].items():
                series[name].append([rec['t']]+p)
        gt = {}
        for name, rows in series.items():
            a = np.array(rows, float)
            gt[name] = {'t': a[:, 0], 'xy': a[:, 1:3], 'z': a[:, 3], 'yaw': np.unwrap(a[:, 4])}
        return gt

    def frame_of(self, robot):
        meta = self.robots.get(robot, {}).get('meta', [])
        return meta[0].get('frame', 'map') if meta else 'map'

    def gt_at(self, robot, t):
        """Ground-truth (x, y, yaw) of `robot` at times t (linear interpolation, yaw unwrapped)."""
        g = self.gt[robot]
        t = np.atleast_1d(np.asarray(t, float))
        x = np.interp(t, g['t'], g['xy'][:, 0])
        y = np.interp(t, g['t'], g['xy'][:, 1])
        yaw = wrap(np.interp(t, g['t'], g['yaw']))
        return np.c_[x, y, yaw]

    def gt_valid(self, robot, t):
        g = self.gt.get(robot)
        if g is None or not len(g['t']):
            return np.zeros(len(np.atleast_1d(t)), bool)
        t = np.atleast_1d(t)
        return (t >= g['t'][0]) & (t <= g['t'][-1])


def align_se2(source, target):
    """Rigid 2-D transform (R, t) minimising |R source + t - target| (Umeyama without scale)."""
    source, target = np.asarray(source, float), np.asarray(target, float)
    if len(source) < 2:
        return np.eye(2), (target.mean(0)-source.mean(0)) if len(source) else np.zeros(2)
    ms, mt = source.mean(0), target.mean(0)
    H = (source-ms).T.dot(target-mt)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T.dot(U.T)
    if np.linalg.det(R) < 0:
        Vt[1] *= -1
        R = Vt.T.dot(U.T)
    return R, mt-R.dot(ms)


def apply_se2(R, t, xy, yaw=None):
    out = np.asarray(xy, float).dot(R.T)+t
    if yaw is None:
        return out
    return out, wrap(np.asarray(yaw)+math.atan2(R[1, 0], R[0, 0]))


def between(a, b):
    """Pose b expressed in the frame of pose a (arrays of (x, y, yaw))."""
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    c, s = np.cos(a[:, 2]), np.sin(a[:, 2])
    dx, dy = b[:, 0]-a[:, 0], b[:, 1]-a[:, 1]
    return np.c_[c*dx+s*dy, -s*dx+c*dy, wrap(b[:, 2]-a[:, 2])]


def stats(values, prefix=''):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], float)
    if not len(v):
        return {prefix+'n': 0}
    return {prefix+'n': int(len(v)), prefix+'mean': float(v.mean()), prefix+'median': float(np.median(v)),
            prefix+'rmse': float(np.sqrt(np.mean(v**2))), prefix+'std': float(v.std()),
            prefix+'p95': float(np.percentile(v, 95)), prefix+'max': float(v.max()), prefix+'min': float(v.min())}


def path_length(xy):
    xy = np.asarray(xy, float)
    if len(xy) < 2:
        return np.zeros(len(xy))
    return np.r_[0., np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
