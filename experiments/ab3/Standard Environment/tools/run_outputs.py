"""Run outputs for ANY algorithm, built only from the benchmark recordings (evaluation/visualisation only).

The custom SLAM draws its own overview and keeps its own histories. Other algorithms only log to the
benchmark (benchlog + bench_supervisor), so this module gives every run the same set of outputs:

  during the run (every live-map period, called from launcher_common.run_webots):
    overview.png + overview_history/overview_NNNNNmin.png   all robots' latest maps over the true AB3
                                                             layout, estimated paths (aligned to the world
                                                             like the evaluator does), true positions,
                                                             coverage of the floor
    coverage_history.jsonl                                   covered m2 / % per refresh, sim + wall time
    robot_N/map_history/map_NNNNNmin.png                     copy of robot_N/live_map.png (if the algorithm
                                                             did not save one for that minute itself)
  at the end (finalize, before evaluation):
    final_overview.png, robot_N/ground_truth_tum.txt, robot_N/metrics.jsonl (5 s error series)
  after evaluation (write_run_summary):
    run_summary.json + RUN_SUMMARY.md                        everything about the run in one place

Files an algorithm writes itself are never overwritten (except the generic overview, which is only
drawn when the algorithm does not draw its own, see `owns_overview`). Nothing here is ever given to
an algorithm.

    python run_outputs.py refresh  RUN [--wall-seconds S]
    python run_outputs.py finalize RUN
    python run_outputs.py summary  RUN
"""
import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SE / 'benchmark'))
from evaluation.common import align_se2, apply_se2, wrap   # noqa: E402  (same alignment as the report)

LAYOUT = SE / 'ground_truth' / 'ab3_layout.npz'
MARKER = 'overview_source.txt'       # present when the overview below is the one in the run folder
COLOURS = [(230, 120, 30), (40, 160, 40), (40, 40, 220), (200, 60, 200), (0, 170, 220),
           (120, 80, 20), (90, 90, 230), (0, 120, 120), (180, 140, 0), (100, 40, 140)]   # BGR, as overview.py


# ---- reading the recordings (tolerant of files that are still being written) -----------------------
def _records(path, types):
    """Records of the given types from a JSONL file; cheap substring filter before parsing."""
    out = []
    keys = ['"type":"%s"' % t for t in types] + ['"type": "%s"' % t for t in types]
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            for line in f:
                if any(k in line for k in keys):
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def _ground_truth(run):
    series = {}
    try:
        with open(run / 'benchmark' / 'ground_truth.jsonl', encoding='utf-8-sig') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                for name, p in rec['p'].items():
                    series.setdefault(name, []).append([rec['t'], p[0], p[1], p[3]])
    except OSError:
        pass
    return {k: np.array(v, float) for k, v in series.items()}


def _gt_at(gt, t):
    t = np.atleast_1d(np.asarray(t, float))
    yaw = np.unwrap(gt[:, 3])
    return np.c_[np.interp(t, gt[:, 0], gt[:, 1]), np.interp(t, gt[:, 0], gt[:, 2]),
                 wrap(np.interp(t, gt[:, 0], yaw))]


def robot_names(run):
    names = [p.name for p in (run / 'benchmark' / 'robots').glob('*') if p.is_dir()]
    return sorted(names, key=lambda n: int(''.join(c for c in n if c.isdigit()) or 0))


def robot_data(run, gt):
    """Per robot: poses, map snapshots, frame alignment (R, t) per frame, aligned positions."""
    data = {}
    for name in robot_names(run):
        bench = run / 'benchmark' / 'robots' / name / 'bench.jsonl'
        recs = _records(bench, ('pose', 'map', 'meta', 'tracking'))
        poses = [r for r in recs if r['type'] == 'pose' and all(map(math.isfinite, r['p']))]
        d = {'poses': poses, 'maps': [r for r in recs if r['type'] == 'map'],
             'tracking': [r for r in recs if r['type'] == 'tracking'],
             'algorithm': next((r.get('algorithm') for r in recs if r['type'] == 'meta'), None),
             'transforms': {}}
        g = gt.get(name)
        for frame in sorted({p.get('frame', 'map') for p in poses}):
            if frame == 'world':
                d['transforms'][frame] = (np.eye(2), np.zeros(2))
            elif g is not None and len(g):
                rows = [p for p in poses if p.get('frame', 'map') == frame and g[0, 0] <= p['t'] <= g[-1, 0]]
                if len(rows) >= 2:
                    xy = np.array([p['p'][:2] for p in rows])
                    d['transforms'][frame] = align_se2(xy, _gt_at(g, [p['t'] for p in rows])[:, :2])
        data[name] = d
    return data


def _aligned(d):
    """World-frame (t, x, y, yaw) of the poses whose frame has an alignment."""
    out = []
    for p in d['poses']:
        tr = d['transforms'].get(p.get('frame', 'map'))
        if tr is None:
            continue
        xy, yaw = apply_se2(tr[0], tr[1], [p['p'][:2]], [p['p'][3]])
        out.append([p['t'], xy[0, 0], xy[0, 1], float(np.atleast_1d(yaw)[0])])
    return np.array(out, float).reshape(-1, 4)


# ---- the overview -----------------------------------------------------------------------------------
def owns_overview(run):
    """True when the algorithm draws its own overview.png (e.g. the custom SLAM's robot 1)."""
    return (run / 'overview.png').exists() and not (run / MARKER).exists()


def render_overview(run, path, wall_seconds=None):
    import cv2
    layout = np.load(str(LAYOUT))
    res = float(layout['resolution'])
    floor_full = layout['floor']
    # The layout stores its CENTRE; cell [0, 0] lower-left corner is:
    origin = layout['origin'] - np.array([floor_full.shape[1] // 2, floor_full.shape[0] // 2]) * res
    step = 2                                     # draw at 0.1 m per pixel
    floor = floor_full[::step, ::step]
    px = res * step
    img = np.full(floor.shape + (3,), 225, np.uint8)
    img[floor] = 250
    img[layout['furniture'][::step, ::step]] = 215
    img[layout['walls'][::step, ::step]] = 150
    h, w = floor.shape
    covered = np.zeros(floor.shape, bool)
    first = np.full(floor.shape, -1, np.int16)
    gt = _ground_truth(run)
    data = robot_data(run, gt)
    labels, occupied = [], []
    for index, (name, d) in enumerate(data.items()):
        colour = COLOURS[index % len(COLOURS)]
        snaps = [m for m in d['maps'] if m.get('kind') == 'local'] or d['maps']
        for m in reversed(snaps):                       # newest snapshot that can be placed and read
            tr = d['transforms'].get(m.get('frame', 'map'))
            if tr is None:
                continue
            try:
                snap = np.load(str(run / 'benchmark' / 'robots' / name / m['file']))
                cells, mres, morg = snap['cells'], float(snap['resolution']), snap['origin']
            except Exception:
                continue
            ys, xs = np.nonzero(cells >= 0)
            local = np.c_[morg[0] + (xs + .5) * mres, morg[1] + (ys + .5) * mres]
            world = apply_se2(tr[0], tr[1], local)
            gx = np.floor((world[:, 0] - origin[0]) / px).astype(int)
            gy = np.floor((world[:, 1] - origin[1]) / px).astype(int)
            ok = (gx >= 0) & (gx < w) & (gy >= 0) & (gy < h)
            free = (cells[ys, xs] == 0) & ok
            new = free.copy()
            new[free] = first[gy[free], gx[free]] < 0
            first[gy[new], gx[new]] = index
            covered[gy[free], gx[free]] = True
            occ = (cells[ys, xs] == 1) & ok
            occupied.append((gy[occ], gx[occ]))
            break
        a = _aligned(d)
        g = gt.get(name)
        err = None
        if len(a) and g is not None and len(g):
            m = (a[:, 0] >= g[0, 0]) & (a[:, 0] <= g[-1, 0])
            if m.any():
                e = a[m, 1:3] - _gt_at(g, a[m, 0])[:, :2]
                err = float(np.sqrt(np.mean(np.sum(e * e, 1))))
        labels.append((name, colour, err, a, g))
    for index in range(len(data)):
        tint = (np.array(COLOURS[index % len(COLOURS)], float) * .35 + 255 * .65).astype(np.uint8)
        img[first == index] = tint
    for gy_, gx_ in occupied:
        img[gy_, gx_] = 0
    for name, colour, err, a, g in labels:
        if len(a) > 1:
            pts = np.c_[(a[:, 1] - origin[0]) / px, (a[:, 2] - origin[1]) / px].astype(np.int32)
            cv2.polylines(img, [pts[::max(1, len(pts) // 4000)].reshape(-1, 1, 2)], False, colour, 1, cv2.LINE_AA)
            cv2.circle(img, (int(pts[-1, 0]), int(pts[-1, 1])), 4, colour, -1, cv2.LINE_AA)
        if g is not None and len(g):
            c = (int((g[-1, 1] - origin[0]) / px), int((g[-1, 2] - origin[1]) / px))
            cv2.circle(img, c, 6, (0, 0, 0), 1, cv2.LINE_AA)
    img = np.flipud(img).copy()                          # world +y up
    for name, colour, err, a, g in labels:               # robot numbers next to their true positions
        if g is not None and len(g):
            c = (int((g[-1, 1] - origin[0]) / px) + 7, h - int((g[-1, 2] - origin[1]) / px) - 7)
            cv2.putText(img, ''.join(ch for ch in name if ch.isdigit()), c, cv2.FONT_HERSHEY_SIMPLEX, .4, colour, 1, cv2.LINE_AA)
    floor_m2 = float(floor.sum() * px * px)
    covered_m2 = float((covered & floor).sum() * px * px)
    sim = max([p['t'] for d in data.values() for p in d['poses'][-1:]] or [0.])
    algos = sorted({d['algorithm'] for d in data.values() if d['algorithm']}) or ['unknown algorithm']
    lines = ['%s | %d robots | AB3 first floor | sim %.0f min%s' % (', '.join(algos), len(data), sim / 60,
             '' if wall_seconds is None else ' | wall %.0f min' % (wall_seconds / 60)),
             'Covered together: %.0f of %.0f m2 floor (%.1f%%) | tint = first robot to cover, black = mapped obstacles, '
             'ring = true position' % (covered_m2, floor_m2, 100 * covered_m2 / max(floor_m2, 1e-9)),
             'Position RMSE (each robot aligned to ground truth, evaluation only): ' + '  '.join(
                 '%s %s' % (n.replace('bstem', 'R'), '%.2fm' % e if e is not None else '-') for n, _, e, _, _ in labels)]
    header = np.full((96, w, 3), 255, np.uint8)
    for k, line in enumerate(lines):
        cv2.putText(header, line[:200], (8, 22 + 26 * k), cv2.FONT_HERSHEY_SIMPLEX, .45, (20, 20, 20), 1, cv2.LINE_AA)
    out = np.concatenate((header, img))
    tmp = Path(str(path) + '.tmp.png')
    cv2.imwrite(str(tmp), out)
    os.replace(str(tmp), str(path))
    return {'covered_m2': round(covered_m2, 1), 'floor_m2': round(floor_m2, 1),
            'covered_pct': round(100 * covered_m2 / max(floor_m2, 1e-9), 2), 'sim_seconds': round(sim, 1)}


# ---- public steps -----------------------------------------------------------------------------------
def save_map_histories(run, wall_seconds):
    """Copy robot_N/live_map.png into map_history/ for algorithms that keep no history themselves.

    The copies made here are listed in map_history/.generic_copies; as soon as the folder holds any
    other image, the algorithm keeps its own history and no more copies are made (no duplicates)."""
    minute = int((wall_seconds or 0) / 60)
    for live in run.glob('robot_*/live_map.png'):
        history = live.parent / 'map_history'
        history.mkdir(exist_ok=True)
        ledger = history / '.generic_copies'
        ours = set(ledger.read_text().split()) if ledger.exists() else set()
        if any(p.name not in ours for p in history.glob('*.png')):
            continue                                      # the algorithm saves its own history
        name = 'map_%05dmin.png' % minute
        if name not in ours:
            shutil.copyfile(str(live), str(history / name))
            with open(ledger, 'a') as f:
                f.write(name + '\n')


def refresh(run, wall_seconds=None, final=False):
    """One live-view refresh: robot map histories and, unless the algorithm draws its own, the overview."""
    run = Path(run).resolve()
    if not final:
        save_map_histories(run, wall_seconds)
    if owns_overview(run):
        return None
    (run / MARKER).write_text('benchmark-generic: Standard Environment/tools/run_outputs.py\n')
    result = render_overview(run, run / ('final_overview.png' if final else 'overview.png'), wall_seconds)
    if final:
        shutil.copyfile(str(run / 'final_overview.png'), str(run / 'overview.png'))
    else:
        (run / 'overview_history').mkdir(exist_ok=True)
        shutil.copyfile(str(run / 'overview.png'),
                        str(run / 'overview_history' / ('overview_%05dmin.png' % int((wall_seconds or 0) / 60))))
    if wall_seconds is not None:
        result['wall_seconds'] = round(float(wall_seconds), 1)
    if final:
        result['final'] = True
    with open(run / 'coverage_history.jsonl', 'a') as f:
        f.write(json.dumps(result) + '\n')
    return result


def finalize(run):
    """End-of-run files that only need the recordings; never overwrites the algorithm's own files."""
    run = Path(run)
    if not (run / 'benchmark' / 'run_meta.json').exists():
        return
    generic = (run / MARKER).exists()
    nothing_drawn = not (run / 'overview.png').exists() and not (run / 'final_overview.png').exists()
    if generic or nothing_drawn:
        try:
            refresh(run, final=True)
        except Exception as error:      # a drawing problem must never block the evaluation
            with open(run / 'render_errors.txt', 'a') as f:
                f.write('final overview: %r\n' % (error,))
    gt = _ground_truth(run)
    data = robot_data(run, gt)
    for name, d in data.items():
        number = ''.join(c for c in name if c.isdigit())
        out = run / ('robot_%s' % number)
        out.mkdir(exist_ok=True)
        g = gt.get(name)
        if g is not None and len(g) and not (out / 'ground_truth_tum.txt').exists():
            with open(out / 'ground_truth_tum.txt', 'w') as f:
                f.write('# timestamp x y z qx qy qz qw (world frame; evaluation only, from the benchmark supervisor)\n')
                dt = float(np.median(np.diff(g[:, 0]))) if len(g) > 1 else .1
                stride = max(1, int(round(.25 / max(dt, 1e-3))))          # 4 Hz, like the custom SLAM's files
                for t, x, y, yaw in g[::stride]:
                    f.write('%.3f %.4f %.4f 0 0 0 %.6f %.6f\n' % (t, x, y, math.sin(yaw / 2), math.cos(yaw / 2)))
        if not (out / 'metrics.jsonl').exists() and d['poses']:
            a = {round(r[0], 3): r for r in _aligned(d)}
            states = sorted((r['t'], r.get('state')) for r in d['tracking'])
            with open(out / 'metrics.jsonl', 'w') as f:
                last = -1e9
                for p in d['poses']:
                    if p['t'] - last < 5.:
                        continue
                    last = p['t']
                    rec = {'time': round(p['t'], 2), 'frame': p.get('frame', 'map'),
                           'pose': [round(v, 4) for v in (p['p'][0], p['p'][1], p['p'][3])],
                           'tracking': next((s for t, s in reversed(states) if t <= p['t']), None)}
                    w_ = a.get(round(p['t'], 3))
                    if w_ is not None:
                        rec['pose_world_aligned'] = [round(float(v), 4) for v in w_[1:]]
                        if g is not None and len(g) and g[0, 0] <= p['t'] <= g[-1, 0]:
                            t_ = _gt_at(g, p['t'])[0]
                            rec['ground_truth'] = [round(float(v), 4) for v in t_]
                            rec['position_error_m'] = round(float(np.hypot(*(w_[1:3] - t_[:2]))), 4)
                            rec['heading_error_deg'] = round(math.degrees(float(wrap(w_[3] - t_[2]))), 3)
                    f.write(json.dumps(rec) + '\n')


def _git_commit():
    try:
        out = subprocess.run(['git', '-C', str(SE.parent), 'rev-parse', 'HEAD'], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=10)
        dirty = subprocess.run(['git', '-C', str(SE.parent), 'status', '--porcelain'], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, universal_newlines=True, timeout=30)
        return {'commit': out.stdout.strip() or None, 'uncommitted_changes': bool(dirty.stdout.strip())}
    except Exception:
        return {'commit': None}


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except Exception:
        return None


def write_run_summary(run):
    """run_summary.json + RUN_SUMMARY.md: the whole run in one place (after evaluation)."""
    run = Path(run).resolve()
    meta = _load(run / 'benchmark' / 'run_meta.json') or {}
    metrics = _load(run / 'benchmark_metrics.json') or _load(run / 'benchmark' / 'metrics.json') or {}
    std = _load(run / 'standard_environment.json') or {}
    robots = {}
    for d in sorted(run.glob('robot_*'), key=lambda p: int(p.name.split('_')[-1]) if p.name.split('_')[-1].isdigit() else 0):
        s = _load(d / 'summary.json') or {}
        robots[d.name] = {'end_reason': s.get('end_reason', s.get('reason')),
                          'live_map_history_images': len(list((d / 'map_history').glob('*.png'))),
                          'files': sorted(p.name for p in d.iterdir() if p.is_file())}
    errors = [n for n in ('controller_errors.txt', 'controller_error.txt', 'render_errors.txt') if (run / n).exists()]
    summary = {
        'run': run.name, 'folder': str(run),
        'algorithm': (metrics.get('summary') or {}).get('algorithm') or (metrics.get('run') or {}).get('algorithm'),
        'scenario': (meta.get('scenario') or {}).get('name'), 'robots': meta.get('robots'),
        'world': meta.get('world'),
        'started_wall': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(meta['start_wall'])) if meta.get('start_wall') else None,
        'summary_written': time.strftime('%Y-%m-%d %H:%M:%S'),
        'durations': metrics.get('real_time') and {k: metrics['real_time'].get(k) for k in
                                                   ('sim_duration_s', 'wall_duration_s', 'real_time_factor')},
        'standard_environment_matches': std.get('matches_standard'),
        'launcher_options': _load(run / 'run_config.json'),
        'benchmark_supervisor_config': _load(run / 'bench_config.json'),
        'native_build': _load(run / 'native_build.json'),
        'machine': {k: meta.get(k) for k in ('platform', 'processor', 'cpu_count', 'memory_total', 'python')},
        'launcher_machine': {'platform': platform.platform(), 'python': sys.version.split()[0]},
        'repository': _git_commit(),
        'headline_metrics': metrics.get('summary'),
        'robots_outputs': robots,
        'overview': {'source': 'algorithm' if not (run / MARKER).exists() else 'benchmark-generic (run_outputs.py)',
                     'history_images': len(list((run / 'overview_history').glob('*.png'))),
                     'final_overview': (run / 'final_overview.png').exists()},
        'problems': errors,
        'files': sorted(p.name for p in run.iterdir() if p.is_file()),
    }
    (run / 'run_summary.json').write_text(json.dumps(summary, indent=1, default=str) + '\n', encoding='utf-8')
    h = summary.get('headline_metrics') or {}

    def num(v, digits=3):
        return ('%.*f' % (digits, v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
    dur = summary['durations'] or {}
    md = ['# Run summary: %s' % run.name, '',
          '| Item | Value |', '|---|---|',
          '| Algorithm | %s |' % summary['algorithm'], '| Scenario | %s |' % summary['scenario'],
          '| Robots | %s |' % (len(summary['robots']) if isinstance(summary['robots'], list) else summary['robots']),
          '| Started | %s |' % summary['started_wall'],
          '| Simulated / wall time | %s s / %s s |' % (num(dur.get('sim_duration_s'), 0), num(dur.get('wall_duration_s'), 0)),
          '| Standard environment unchanged | %s |' % summary['standard_environment_matches'],
          '| Repository commit | %s%s |' % (summary['repository'].get('commit'),
                                           ' (+ uncommitted changes)' if summary['repository'].get('uncommitted_changes') else ''),
          '| ATE RMSE | %s m |' % num(h.get('ate_rmse_m')), '| Map accuracy F1 | %s |' % num(h.get('map_accuracy_f1')),
          '| Coverage | %s m2 |' % num(h.get('map_coverage_m2'), 1), '| Loop precision | %s |' % num(h.get('loop_precision')),
          '| Overview images | %d (%s) |' % (summary['overview']['history_images'], summary['overview']['source']),
          '| Problems | %s |' % (', '.join(errors) or 'none'), '',
          'Full metrics: `benchmark_report.md` / `benchmark_metrics.json`. Everything above: `run_summary.json`.', '']
    (run / 'RUN_SUMMARY.md').write_text('\n'.join(md), encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['refresh', 'finalize', 'summary'])
    ap.add_argument('run', type=Path)
    ap.add_argument('--wall-seconds', type=float, default=None)
    args = ap.parse_args()
    if args.step == 'refresh':
        refresh(args.run, args.wall_seconds)
    elif args.step == 'finalize':
        finalize(args.run)
    else:
        write_run_summary(args.run)


if __name__ == '__main__':
    main()
