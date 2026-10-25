"""benchlog: the client side of the SLAM benchmark.

Any SLAM algorithm (Webots controller, ROS node through the bridge, or offline importer) reports
what only it can know through this module: pose estimates, tracking state, per-frame processing
time, optimisation time, loop-closure decisions, map snapshots, peer-pose estimates, map merges and
radio messages. Everything else (ground truth, real-time factor, collisions, process resources,
scenarios) is measured outside the algorithm by the benchmark supervisor.

Python 2.7 and 3 compatible; standard library only (numpy is needed only for map snapshots, psutil
is optional for resource sampling). Times are SIMULATION seconds unless a field says "wall".

    from benchlog import BenchLog
    log = BenchLog(robot='bstem1', algorithm='Custom-SLAM')     # run dir from $SLAM_BENCH_RUN_DIR
    log.initialized(t)
    log.pose(t, x, y, yaw)                     # estimate in the algorithm's map frame
    log.tracking(t, 'ok' | 'lost' | 'relocalizing')
    log.frame(t, latency_s)                    # one sensor frame processed
    log.optimization(t, duration_s, kind='global')
    log.loop(t, accepted, matched_robot, matched_time, relative=(dx, dy, dyaw))
    log.map(t, grid, resolution, origin)       # occupancy grid: -1 unknown, 0 free, 1 (or >=50) occupied
    log.send(t, payload) / log.recv(t, payload, source)
    log.close()

File format (one JSON object per line) is documented in README.md.
"""
from __future__ import division, print_function
import hashlib
import json
import os
import threading
import time

__all__ = ['BenchLog', 'scenario']

TRACKING_STATES = ('ok', 'lost', 'relocalizing', 'initializing')


def scenario():
    """Scenario parameters for this run (e.g. noise_scale) so an algorithm's sensor adapter can apply
    them. Read from $SLAM_BENCH_SCENARIO (a JSON file written by the launcher); {} if not set."""
    path = os.environ.get('SLAM_BENCH_SCENARIO')
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def message_id(payload):
    """Stable identifier of a radio message: the same bytes give the same id on sender and receiver."""
    if not isinstance(payload, bytes):
        payload = str(payload).encode('utf8')
    return hashlib.sha1(payload).hexdigest()[:16]


class BenchLog(object):
    def __init__(self, robot, algorithm, run_dir=None, frame='map', resource_period=1.0, meta=None):
        """robot: the Webots robot name (must match the world, used to find ground truth).
        algorithm: a short name shown in comparisons. frame: name of the frame poses are expressed
        in ('world' if the algorithm is given true start poses; anything else is aligned to ground
        truth by the evaluator)."""
        run_dir = run_dir or os.environ.get('SLAM_BENCH_RUN_DIR')
        if not run_dir:
            raise RuntimeError('No run directory: set $SLAM_BENCH_RUN_DIR or pass run_dir')
        self.robot, self.algorithm, self.pose_frame = str(robot), str(algorithm), str(frame)
        self.dir = os.path.join(run_dir, 'robots', self.robot)
        self.map_dir = os.path.join(self.dir, 'maps')
        for d in (self.dir, self.map_dir):
            if not os.path.isdir(d):
                os.makedirs(d)
        self._file = open(os.path.join(self.dir, 'bench.jsonl'), 'a')
        self._lock = threading.Lock()
        self._last_t = 0.
        self._closed = False
        self._write({'type': 'meta', 't': 0., 'robot': self.robot, 'algorithm': self.algorithm,
                     'frame': self.pose_frame, 'pid': os.getpid(), 'wall': time.time(), 'meta': meta or {}})
        self._sampler = None
        if resource_period:
            self._sampler = threading.Thread(target=self._sample_resources, args=(resource_period,))
            self._sampler.daemon = True
            self._sampler.start()

    # ---- core -----------------------------------------------------------------------------
    def _write(self, record):
        if self._closed:
            return
        record.setdefault('wall', time.time())
        line = json.dumps(record, separators=(',', ':'))
        with self._lock:
            self._file.write(line+'\n')

    def _t(self, t):
        t = float(t)
        self._last_t = max(self._last_t, t)
        return t

    def flush(self):
        with self._lock:
            self._file.flush()

    def close(self):
        if not self._closed:
            self._write({'type': 'end', 't': self._last_t})
            self._closed = True
            with self._lock:
                self._file.close()

    # ---- localization ---------------------------------------------------------------------
    def initialized(self, t):
        """The algorithm has produced its first valid pose (initialization time)."""
        self._write({'type': 'init', 't': self._t(t)})

    def pose(self, t, x, y, yaw, z=0., covariance=None, frame=None, odometry=None):
        """Pose estimate. covariance: optional 3x3 (x, y, yaw) as nested lists, for NEES.
        odometry: optional (x, y, yaw) dead-reckoning pose in the same frame, to measure how much the
        SLAM improves on odometry alone."""
        r = {'type': 'pose', 't': self._t(t), 'p': [float(x), float(y), float(z), float(yaw)],
             'frame': frame or self.pose_frame}
        if covariance is not None:
            r['cov'] = [[float(v) for v in row] for row in covariance]
        if odometry is not None:
            r['odom'] = [float(v) for v in odometry]
        self._write(r)

    def tracking(self, t, state, reason=None):
        state = str(state).lower()
        if state not in TRACKING_STATES:
            raise ValueError('tracking state must be one of %s' % (TRACKING_STATES,))
        self._write({'type': 'tracking', 't': self._t(t), 'state': state, 'reason': reason})

    # ---- processing -----------------------------------------------------------------------
    def frame(self, t, latency_s, kind='camera'):
        """One sensor frame processed; latency_s is wall-clock processing time for it."""
        self._write({'type': 'frame', 't': self._t(t), 'latency': float(latency_s), 'kind': kind})

    def optimization(self, t, duration_s, kind='global', nodes=None, edges=None):
        self._write({'type': 'optimization', 't': self._t(t), 'duration': float(duration_s), 'kind': kind,
                     'nodes': nodes, 'edges': edges})

    def keyframe(self, t, count=None):
        self._write({'type': 'keyframe', 't': self._t(t), 'count': count})

    # ---- loop closure ---------------------------------------------------------------------
    def loop(self, t, accepted, matched_robot=None, matched_time=None, relative=None, score=None,
             pose_before=None, pose_after=None, reason=None):
        """A loop-closure candidate and the algorithm's decision.
        matched_robot/matched_time: the robot and time of the earlier observation it matched (own
        robot for intra-robot loops). relative: the claimed pose of the current observation in the
        matched one's frame (dx, dy, dyaw), used to check the loop against ground truth.
        pose_before/pose_after: the robot's pose estimate just before and after the correction."""
        r = {'type': 'loop', 't': self._t(t), 'accepted': bool(accepted),
             'matched_robot': str(matched_robot) if matched_robot is not None else self.robot,
             'matched_time': None if matched_time is None else float(matched_time), 'score': score,
             'reason': reason}
        if relative is not None:
            r['relative'] = [float(v) for v in relative]
        if pose_before is not None:
            r['pose_before'] = [float(v) for v in pose_before]
        if pose_after is not None:
            r['pose_after'] = [float(v) for v in pose_after]
        self._write(r)

    # ---- mapping and multi-robot ----------------------------------------------------------
    def map_update(self, t, duration_s=None):
        """A (cheap) record that the map was updated, for update frequency and map generation time."""
        self._write({'type': 'map_update', 't': self._t(t), 'duration': duration_s})

    def map(self, t, grid, resolution, origin, kind='local', frame=None, memory_bytes=None):
        """Occupancy-grid snapshot. grid: 2-D array, rows along +y, columns along +x; -1 unknown,
        0 free, 1 occupied (ROS 0..100 probabilities are also accepted). origin: (x, y) of the
        lower-left corner of cell [0, 0] in `frame`. kind: 'local' (this robot's own map) or
        'merged' (this robot's view of the shared map)."""
        import numpy as np
        g = np.asarray(grid)
        if g.ndim != 2:
            raise ValueError('map grid must be 2-D')
        if g.dtype.kind == 'f' or g.max() > 1:
            occ = (g >= 50) if g.max() > 1 else (g > .5)
            free = (g >= 0) & ~occ
        else:
            occ, free = g == 1, g == 0
        cells = np.full(g.shape, -1, np.int8)
        cells[free] = 0
        cells[occ] = 1
        name = '%s_%010.2f.npz' % (kind, float(t))
        path = os.path.join(self.map_dir, name)
        np.savez_compressed(path, cells=cells, resolution=float(resolution), origin=np.asarray(origin, float))
        self._write({'type': 'map', 't': self._t(t), 'kind': kind, 'file': 'maps/'+name, 'frame': frame or self.pose_frame,
                     'resolution': float(resolution), 'known_cells': int((cells >= 0).sum()),
                     'occupied_cells': int(occ.sum()), 'bytes_raw': int(g.nbytes),
                     'bytes_file': os.path.getsize(path), 'memory_bytes': memory_bytes})

    def peer_pose(self, t, peer, x, y, yaw, frame=None):
        """This robot's estimate of another robot's pose (inter-robot pose estimation)."""
        self._write({'type': 'peer_pose', 't': self._t(t), 'peer': str(peer),
                     'p': [float(x), float(y), float(yaw)], 'frame': frame or self.pose_frame})

    def merge(self, t, peer, duration_s=None):
        """Data from `peer` was merged into this robot's map."""
        self._write({'type': 'merge', 't': self._t(t), 'peer': str(peer), 'duration': duration_s})

    # ---- communication --------------------------------------------------------------------
    def send(self, t, payload, destination=None, size=None):
        """A radio message sent. payload: the exact bytes (hashed to match receptions)."""
        self._write({'type': 'send', 't': self._t(t), 'id': message_id(payload),
                     'bytes': int(size if size is not None else len(payload)), 'dst': destination})

    def recv(self, t, payload, source=None, size=None):
        self._write({'type': 'recv', 't': self._t(t), 'id': message_id(payload),
                     'bytes': int(size if size is not None else len(payload)), 'src': source})

    # ---- free-form ------------------------------------------------------------------------
    def event(self, t, name, **data):
        r = {'type': 'event', 't': self._t(t), 'name': str(name)}
        r.update(data)
        self._write(r)

    def energy(self, t, joules, kind='measured'):
        self._write({'type': 'energy', 't': self._t(t), 'joules': float(joules), 'kind': kind})

    def error(self, t, message):
        """A fault inside the algorithm (counted for stability and failure rate)."""
        self._write({'type': 'error', 't': self._t(t), 'message': str(message)[:2000]})

    # ---- resources ------------------------------------------------------------------------
    def _sample_resources(self, period):
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            proc.cpu_percent(None)
        except Exception:
            proc = None
        cpu_prev, wall_prev = time.process_time() if hasattr(time, 'process_time') else time.clock(), time.time()
        while not self._closed:
            time.sleep(period)
            wall = time.time()
            try:
                if proc is not None:
                    with proc.oneshot():
                        cpu = proc.cpu_percent(None)
                        rss = proc.memory_info().rss
                        threads = proc.num_threads()
                    cpu_s = sum(proc.cpu_times()[:2])
                else:
                    now = time.process_time() if hasattr(time, 'process_time') else time.clock()
                    cpu = 100.*(now-cpu_prev)/max(wall-wall_prev, 1e-6)
                    cpu_prev, rss, threads, cpu_s = now, None, None, now
                wall_prev = wall
                self._write({'type': 'resource', 't': self._last_t, 'cpu_pct': cpu, 'rss': rss,
                             'threads': threads, 'cpu_seconds': cpu_s})
            except Exception:
                pass
