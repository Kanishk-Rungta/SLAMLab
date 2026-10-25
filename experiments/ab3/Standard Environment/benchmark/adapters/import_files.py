"""Import an algorithm's saved outputs into a benchmark run (for algorithms that cannot call benchlog).

    python adapters/import_files.py RUN_DIR --robot bstem1 --algorithm ORB-SLAM3 \
        --tum estimate.txt [--frame map] [--map map.yaml | --map map.npz --map-time 600] \
        [--loops loops.csv]

RUN_DIR is the directory the benchmark supervisor recorded ground truth into, so the imported
estimate is evaluated against the same run. TUM timestamps must be simulation seconds.
Maps: ROS map_server .yaml (+ .pgm) or an .npz with cells/resolution/origin.
loops.csv columns: t, accepted (0/1), matched_robot, matched_time[, dx, dy, dyaw].
"""
import argparse
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchlog import BenchLog


def read_tum(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            v = [float(x) for x in line.split()]
            t, x, y, z, qx, qy, qz, qw = v[:8]
            yaw = math.atan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))
            rows.append((t, x, y, z, yaw))
    return rows


def read_ros_map(yaml_path):
    import yaml
    meta = yaml.safe_load(open(yaml_path))
    image_path = os.path.join(os.path.dirname(yaml_path), meta['image'])
    try:
        import cv2
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    except ImportError:
        from PIL import Image
        img = np.array(Image.open(image_path).convert('L'))
    img = np.flipud(img)                          # image rows go down; grid rows go up (+y)
    p = (255-img)/255. if not meta.get('negate', 0) else img/255.
    cells = np.full(img.shape, -1, np.int8)
    cells[p > meta.get('occupied_thresh', .65)] = 1
    cells[p < meta.get('free_thresh', .196)] = 0
    return cells, float(meta['resolution']), meta['origin'][:2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dir')
    ap.add_argument('--robot', required=True)
    ap.add_argument('--algorithm', required=True)
    ap.add_argument('--tum', required=True)
    ap.add_argument('--frame', default='map')
    ap.add_argument('--map', default=None)
    ap.add_argument('--map-time', type=float, default=None)
    ap.add_argument('--loops', default=None)
    args = ap.parse_args()
    log = BenchLog(args.robot, args.algorithm, run_dir=args.run_dir, frame=args.frame, resource_period=0,
                   meta={'imported': True})
    rows = read_tum(args.tum)
    if rows:
        log.initialized(rows[0][0])
    for t, x, y, z, yaw in rows:
        log.pose(t, x, y, yaw, z=z)
    if args.map:
        if args.map.endswith('.yaml'):
            cells, res, origin = read_ros_map(args.map)
        else:
            d = np.load(args.map)
            cells, res, origin = d['cells'], float(d['resolution']), d['origin']
        log.map(args.map_time if args.map_time is not None else (rows[-1][0] if rows else 0.), cells, res, origin)
    if args.loops:
        with open(args.loops) as f:
            for r in csv.DictReader(f):
                rel = [float(r[k]) for k in ('dx', 'dy', 'dyaw')] if r.get('dx') not in (None, '') else None
                log.loop(float(r['t']), bool(int(r['accepted'])), r.get('matched_robot') or args.robot,
                         float(r['matched_time']), relative=rel)
    log.close()
    print('imported %d poses for %s into %s' % (len(rows), args.robot, args.run_dir))


if __name__ == '__main__':
    main()
