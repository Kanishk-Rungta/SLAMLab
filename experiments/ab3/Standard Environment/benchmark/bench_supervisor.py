"""Benchmark supervisor for Webots: measures everything that does not need the algorithm's cooperation.

Add one Robot with `supervisor TRUE` and this as its controller (tools/install.py writes the wrapper
controller into a Webots project). It records, into $SLAM_BENCH_RUN_DIR:
  run_meta.json      robots found, world, scenario, machine, configuration
  ground_truth.jsonl {"t": sim s, "p": {robot: [x, y, z, yaw]}} at gt_period
  supervisor.jsonl   real-time factor, process CPU/RAM (Webots + configured external processes),
                     collisions, and scenario events (dynamic obstacles, radio outages)
Scenarios (robustness tests) come from the JSON file in $SLAM_BENCH_SCENARIO:
  {"name": "...", "noise_scale": 2.0,                 # applied by the algorithm's adapter (benchlog.scenario())
   "dynamic_obstacles": {"count": 5, "speed": 0.6, "radius": 0.25, "seed": 1},
   "comm_outages": [{"start": 300, "end": 420, "robots": "all"}], "comm_field": "radioRange"}
Ground truth is never sent to the algorithms.
"""
from __future__ import division, print_function
import json
import math
import os
import platform
import random
import sys
import time

from controller import Supervisor

DEFAULTS = {
    'gt_period': 0.1,             # s, ground-truth sampling
    'resource_period': 1.0,       # s of wall time, process sampling
    'robot_names': None,          # list; default: every robot except this supervisor and the excluded
    'exclude_robot_names': ['gt_logger'],   # helper robots that are not running SLAM
    'process_patterns': [],       # extra process names to monitor (e.g. ROS nodes), substring match
    'collision_min_height': 0.015,# m above the floor: contacts above this are collisions, not wheels
    'collision_debounce': 1.0,    # s
    'gt_map': None,               # npz with floor/occupied grids (for obstacle placement)
    'max_sim_seconds': 0,         # 0 = until the simulation ends
    'quit_grace_seconds': 120,    # sim s after STOP / max_sim_seconds before the supervisor closes Webots
}


def load_json(path):
    if path and os.path.exists(path):
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    return {}


class Collector(object):
    def __init__(self):
        self.sup = Supervisor()
        self.step = int(self.sup.getBasicTimeStep())
        self.run_dir = os.environ.get('SLAM_BENCH_RUN_DIR')
        if not self.run_dir:
            raise RuntimeError('Set $SLAM_BENCH_RUN_DIR for the benchmark supervisor')
        os.makedirs(self.run_dir, exist_ok=True)
        self.cfg = dict(DEFAULTS)
        self.cfg.update(load_json(os.environ.get('SLAM_BENCH_CONFIG')))
        self.scenario = load_json(os.environ.get('SLAM_BENCH_SCENARIO'))
        self.log = open(os.path.join(self.run_dir, 'supervisor.jsonl'), 'a')
        self.gt = open(os.path.join(self.run_dir, 'ground_truth.jsonl'), 'a')
        self.robots = self.find_robots()
        self.contacts = {name: -1e9 for name in self.robots}
        self.contact_tracking = self.enable_contacts()
        self.obstacles = []
        self.outage_state = {}
        self.random = random.Random(self.scenario.get('dynamic_obstacles', {}).get('seed', 1))
        self.write_meta()
        self.processes = {}
        self.psutil = None
        try:
            import psutil
            self.psutil = psutil
        except ImportError:
            self.event(0., 'warning', message='psutil not installed: no supervisor-side process sampling')

    # ---- setup ------------------------------------------------------------------------------
    def find_robots(self):
        root = self.sup.getRoot().getField('children')
        me = self.sup.getSelf()
        robots = {}
        for i in range(root.getCount()):
            node = root.getMFNode(i)
            try:
                base = node.getBaseTypeName()
            except Exception:
                continue
            if base != 'Robot' or node.getId() == me.getId():
                continue
            name_field = node.getField('name')
            name = name_field.getSFString() if name_field else 'robot_%d' % i
            if self.cfg['robot_names'] and name not in self.cfg['robot_names']:
                continue
            if name in self.cfg['exclude_robot_names'] or name.startswith('bench_'):
                continue
            robots[name] = node
        return robots

    def enable_contacts(self):
        ok = True
        for node in self.robots.values():
            try:
                node.enableContactPointsTracking(self.step, True)
            except Exception:
                ok = False
        return ok

    def write_meta(self):
        meta = {'world': self.sup.getWorldPath(), 'basic_time_step_ms': self.step,
                'robots': sorted(self.robots), 'scenario': self.scenario, 'config': self.cfg,
                'start_wall': time.time(), 'python': sys.version, 'platform': platform.platform(),
                'processor': platform.processor(), 'cpu_count': os.cpu_count(),
                'contact_tracking': self.contact_tracking}
        try:
            import psutil
            meta['memory_total'] = psutil.virtual_memory().total
        except ImportError:
            pass
        with open(os.path.join(self.run_dir, 'run_meta.json'), 'w') as f:
            json.dump(meta, f, indent=1)

    def event(self, t, kind, **data):
        record = {'type': kind, 't': round(t, 4), 'wall': time.time()}
        record.update(data)
        self.log.write(json.dumps(record, separators=(',', ':'))+'\n')

    # ---- ground truth and collisions --------------------------------------------------------
    def record_ground_truth(self, t):
        poses = {}
        for name, node in self.robots.items():
            p, R = node.getPosition(), node.getOrientation()
            poses[name] = [round(p[0], 5), round(p[1], 5), round(p[2], 5), round(math.atan2(R[3], R[0]), 6)]
        self.gt.write(json.dumps({'t': round(t, 4), 'p': poses}, separators=(',', ':'))+'\n')

    def check_collisions(self, t):
        if not self.contact_tracking:
            return
        for name, node in self.robots.items():
            try:
                points = node.getContactPoints(True)
            except Exception:
                return
            for cp in points:
                point = cp.getPoint() if hasattr(cp, 'getPoint') else cp.point
                if point[2] > self.cfg['collision_min_height']:
                    if t-self.contacts[name] >= self.cfg['collision_debounce']:
                        self.event(t, 'collision', robot=name, point=[round(v, 3) for v in point])
                    self.contacts[name] = t
                    break

    # ---- resources --------------------------------------------------------------------------
    def sample_processes(self, t):
        if self.psutil is None:
            return
        patterns = ['webots']+list(self.cfg['process_patterns'])
        seen = set()
        for proc in self.psutil.process_iter(['pid', 'name']):
            name = (proc.info.get('name') or '').lower()
            if not any(p.lower() in name for p in patterns):
                continue
            seen.add(proc.pid)
            if proc.pid not in self.processes:
                self.processes[proc.pid] = proc
                try:
                    proc.cpu_percent(None)
                except Exception:
                    pass
                continue
            try:
                with proc.oneshot():
                    self.event(t, 'process', pid=proc.pid, name=name, cpu_pct=proc.cpu_percent(None),
                               rss=proc.memory_info().rss)
            except Exception:
                pass
        for pid in list(self.processes):
            if pid not in seen:
                del self.processes[pid]
        vm = self.psutil.virtual_memory()
        self.event(t, 'system', cpu_pct=self.psutil.cpu_percent(None), mem_used=vm.used, mem_pct=vm.percent)

    # ---- scenarios --------------------------------------------------------------------------
    def spawn_obstacles(self):
        spec = self.scenario.get('dynamic_obstacles')
        if not spec or not spec.get('count'):
            return
        floor = None
        if self.cfg.get('gt_map'):
            import numpy as np
            m = np.load(self.cfg['gt_map'])
            floor = (m['floor'] & ~m['occupied'], float(m['resolution']), m['origin'])
        root = self.sup.getRoot().getField('children')
        radius = float(spec.get('radius', .25))
        for k in range(int(spec['count'])):
            x, y = self.free_point(floor)
            root.importMFNodeFromString(-1, (
                'DEF BENCH_OBSTACLE_%d Solid { translation %.3f %.3f 0.85 name "bench_obstacle_%d" children [ Shape { '
                'appearance PBRAppearance { baseColor 0.8 0.3 0.3 roughness 1 metalness 0 } geometry Cylinder { '
                'radius %.3f height 1.7 } } ] boundingObject Cylinder { radius %.3f height 1.7 } }') % (k, x, y, k, radius, radius))
            node = self.sup.getFromDef('BENCH_OBSTACLE_%d' % k)
            self.obstacles.append({'node': node, 'pos': [x, y], 'goal': self.free_point(floor, (x, y)), 'floor': floor})
        self.event(0., 'scenario', what='dynamic_obstacles', count=len(self.obstacles), speed=spec.get('speed', .6))

    def free_point(self, floor, near=None):
        if floor is None:
            names = sorted(self.robots)
            base = self.robots[self.random.choice(names)].getPosition()
            return base[0]+self.random.uniform(-4, 4), base[1]+self.random.uniform(-4, 4)
        free, res, origin = floor
        for _ in range(500):
            if near is None:
                r, c = self.random.randrange(free.shape[0]), self.random.randrange(free.shape[1])
            else:
                r = int((near[1]-origin[1])/res)+self.random.randint(-60, 60)
                c = int((near[0]-origin[0])/res)+self.random.randint(-60, 60)
            if 0 <= r < free.shape[0] and 0 <= c < free.shape[1] and free[max(0, r-8):r+9, max(0, c-8):c+9].all():
                point = (origin[0]+(c+.5)*res, origin[1]+(r+.5)*res)
                if near is None or self.clear_line(free, res, origin, near, point):
                    return point
        return near if near is not None else (0., 0.)

    @staticmethod
    def clear_line(free, res, origin, a, b):
        n = int(math.hypot(b[0]-a[0], b[1]-a[1])/res)+1
        for i in range(n+1):
            x, y = a[0]+(b[0]-a[0])*i/n, a[1]+(b[1]-a[1])*i/n
            r, c = int((y-origin[1])/res), int((x-origin[0])/res)
            if not (0 <= r < free.shape[0] and 0 <= c < free.shape[1]) or not free[r, c]:
                return False
        return True

    def move_obstacles(self, dt):
        speed = float(self.scenario.get('dynamic_obstacles', {}).get('speed', .6))
        for ob in self.obstacles:
            dx, dy = ob['goal'][0]-ob['pos'][0], ob['goal'][1]-ob['pos'][1]
            dist = math.hypot(dx, dy)
            if dist < speed*dt:
                ob['goal'] = self.free_point(ob['floor'], ob['goal'])
                continue
            ob['pos'][0] += dx/dist*speed*dt
            ob['pos'][1] += dy/dist*speed*dt
            ob['node'].getField('translation').setSFVec3f([ob['pos'][0], ob['pos'][1], .85])

    def apply_outages(self, t):
        windows = self.scenario.get('comm_outages') or []
        field_name = self.scenario.get('comm_field', 'radioRange')
        for i, w in enumerate(windows):
            active = w['start'] <= t < w['end']
            targets = sorted(self.robots) if w.get('robots', 'all') == 'all' else w['robots']
            for name in targets:
                key = (i, name)
                field = self.robots[name].getField(field_name) if name in self.robots else None
                if field is None:
                    continue
                if active and key not in self.outage_state:
                    self.outage_state[key] = field.getSFFloat()
                    field.setSFFloat(0.)
                    self.event(t, 'comm_outage', robot=name, state='start')
                elif not active and key in self.outage_state:
                    field.setSFFloat(self.outage_state.pop(key))
                    self.event(t, 'comm_outage', robot=name, state='end')

    # ---- main loop --------------------------------------------------------------------------
    def run(self):
        self.spawn_obstacles()
        dt = self.step/1000.
        last_gt = -1e9
        last_res_wall = 0.
        rtf_sim, rtf_wall = 0., time.time()
        stop_file = os.path.join(self.run_dir, 'STOP')
        stop_at = None
        while self.sup.step(self.step) != -1:
            t = self.sup.getTime()
            if t-last_gt >= self.cfg['gt_period']-1e-9:
                self.record_ground_truth(t)
                last_gt = t
            self.check_collisions(t)
            if self.obstacles:
                self.move_obstacles(dt)
            self.apply_outages(t)
            wall = time.time()
            if wall-last_res_wall >= self.cfg['resource_period']:
                self.event(t, 'rtf', rtf=(t-rtf_sim)/max(wall-rtf_wall, 1e-6), sim=t)
                rtf_sim, rtf_wall = t, wall
                self.sample_processes(t)
                last_res_wall = wall
                self.gt.flush()
                self.log.flush()
            if stop_at is None and ((self.cfg['max_sim_seconds'] and t >= self.cfg['max_sim_seconds']) or os.path.exists(stop_file)):
                # Recording continues while the robots save their final outputs; algorithms that do not
                # end the simulation themselves are stopped after the grace period.
                stop_at = t
                self.event(t, 'stop_requested')
            if stop_at is not None and t-stop_at >= self.cfg['quit_grace_seconds']:
                break
        self.event(self.sup.getTime(), 'end')
        self.gt.close()
        self.log.close()
        if stop_at is not None:
            self.sup.simulationQuit(0)


if __name__ == '__main__':
    Collector().run()
