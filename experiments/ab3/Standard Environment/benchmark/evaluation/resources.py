"""Compute, memory, latency/throughput, real-time factor, energy, collisions, failures and stability."""
import numpy as np
from .common import path_length, stats


def processing(run):
    per_robot = {}
    for robot in run.names:
        rec = run.robots.get(robot, {})
        res = rec.get('resource', [])
        cpu = [r['cpu_pct'] for r in res if r.get('cpu_pct') is not None]
        rss = [r['rss'] for r in res if r.get('rss')]
        cpu_s = [r['cpu_seconds'] for r in res if r.get('cpu_seconds') is not None]
        frames = rec.get('frame', [])
        opt = rec.get('optimization', [])
        r = {}
        if cpu:
            r['cpu_mean_pct'] = float(np.mean(cpu))
            r['cpu_peak_pct'] = float(np.max(cpu))
        if rss:
            r['memory_mean_mb'] = float(np.mean(rss)/2**20)
            r['memory_peak_mb'] = float(np.max(rss)/2**20)
            # Growth after start-up: memory the algorithm accumulates while it maps.
            r['memory_overhead_mb'] = float((np.max(rss)-np.median(rss[:5]))/2**20)
        if len(cpu_s) > 1:
            r['cpu_seconds'] = float(cpu_s[-1]-cpu_s[0])
        if frames:
            lat = [f['latency'] for f in frames]
            r['processing_latency_ms'] = {k: v*1000 if k not in ('n',) else v for k, v in stats(lat).items()}
            wall = frames[-1]['wall']-frames[0]['wall']
            sim = frames[-1]['t']-frames[0]['t']
            r['throughput_fps_wall'] = float(len(frames)/wall) if wall > 0 else None
            r['throughput_fps_sim'] = float(len(frames)/sim) if sim > 0 else None
        if opt:
            durations = [o['duration'] for o in opt]
            r['optimization_time_s'] = stats(durations)
            r['optimization_total_s'] = float(np.sum(durations))
        per_robot[robot] = r
    return per_robot


def real_time(run):
    rtf = [e['rtf'] for e in run.supervisor if e.get('type') == 'rtf' and e.get('rtf') is not None]
    start = run.meta.get('start_wall')
    walls = [e['wall'] for e in run.supervisor if 'wall' in e]
    out = {'sim_duration_s': run.sim_end}
    if start and walls:
        out['wall_duration_s'] = float(max(walls)-start)
        out['real_time_factor'] = float(run.sim_end/max(out['wall_duration_s'], 1e-6))
    if rtf:
        out['rtf_samples'] = {'mean': float(np.mean(rtf)), 'min': float(np.min(rtf)),
                              'cv': float(np.std(rtf)/max(np.mean(rtf), 1e-9))}
    procs = {}
    for e in run.supervisor:
        if e.get('type') == 'process':
            procs.setdefault(e['name'], []).append(e)
    out['processes'] = {name: {'cpu_mean_pct': float(np.mean([e['cpu_pct'] for e in v])),
                               'cpu_peak_pct': float(np.max([e['cpu_pct'] for e in v])),
                               'memory_peak_mb': float(np.max([e['rss'] for e in v])/2**20)}
                        for name, v in procs.items()}
    system = [e for e in run.supervisor if e.get('type') == 'system']
    if system:
        out['system_cpu_mean_pct'] = float(np.mean([e['cpu_pct'] for e in system]))
        out['system_memory_peak_mb'] = float(np.max([e['mem_used'] for e in system])/2**20)
    return out


def energy(run, cfg, cpu_seconds):
    """Measured energy if the algorithm reports it; otherwise a model: compute (CPU-seconds x W per
    core) + motion (rolling resistance and acceleration, from ground truth) + idle electronics."""
    e = cfg['energy']
    per_robot = {}
    for robot in run.names:
        measured = run.robots.get(robot, {}).get('energy', [])
        if measured:
            per_robot[robot] = {'joules': float(measured[-1]['joules']), 'kind': 'measured'}
            continue
        g = run.gt.get(robot)
        motion = 0.
        if g is not None and len(g['t']) > 2:
            d = np.diff(path_length(g['xy']))
            v = d/np.maximum(np.diff(g['t']), 1e-6)
            kinetic = .5*e['robot_mass_kg']*v**2
            motion = (e['robot_mass_kg']*9.81*e['rolling_resistance']*d.sum()
                      + np.clip(np.diff(kinetic), 0, None).sum())/e['drive_efficiency']
        compute = cpu_seconds.get(robot, 0.)*e['compute_watts_per_core']
        idle = e['idle_watts']*run.sim_end
        per_robot[robot] = {'joules': float(motion+compute+idle), 'motion_j': float(motion),
                            'compute_j': float(compute), 'idle_j': float(idle), 'kind': 'model'}
    total = sum(v['joules'] for v in per_robot.values())
    return {'per_robot': per_robot, 'total_joules': float(total),
            'mean_joules_per_robot': float(total/len(per_robot)) if per_robot else None}


def stability(run, cfg, trajectory, tracking):
    collisions = {}
    for e in run.supervisor:
        if e.get('type') == 'collision':
            collisions[e['robot']] = collisions.get(e['robot'], 0)+1
    hours = max(run.sim_end/3600., 1e-6)
    per_robot, failed = {}, 0
    for robot in run.names:
        rec = run.robots.get(robot, {})
        times = [r['t'] for typ in ('pose', 'frame', 'resource') for r in rec.get(typ, [])]
        last = max(times) if times else 0.
        crashed = bool(rec) and not rec.get('end') and last < run.sim_end-cfg['crash_grace_s']
        tr = trajectory['per_robot'].get(robot)
        tk = tracking['per_robot'].get(robot, {})
        reasons = []
        if not rec.get('pose'):
            reasons.append('no_pose_output')
        if crashed:
            reasons.append('crashed_or_stopped_early')
        if tr and tr['ate_m'].get('rmse', 0) > cfg['fail_ate_m']:
            reasons.append('ate_above_%gm' % cfg['fail_ate_m'])
        if tk.get('lost_fraction', 0) > cfg['fail_lost_fraction']:
            reasons.append('lost_too_long')
        errors = len(rec.get('error', []))
        jumps = tr['pose_jumps'] if tr else 0
        penalty = min(1., float(crashed) + errors/hours/10 + jumps/hours/10 + tk.get('lost_fraction', 0))
        per_robot[robot] = {'failed': bool(reasons), 'failure_reasons': reasons, 'errors': errors,
                            'pose_jumps': jumps, 'collisions': collisions.get(robot, 0),
                            'collisions_per_hour': collisions.get(robot, 0)/hours, 'stability': 1-penalty}
        failed += bool(reasons)
    n = max(len(per_robot), 1)
    return {'per_robot': per_robot, 'slam_failure_rate': failed/n if per_robot else None,
            'collisions_total': int(sum(collisions.values())),
            'stability_index': float(np.mean([v['stability'] for v in per_robot.values()])) if per_robot else None}


def summarize(run, cfg, per_robot_proc, trajectory, mapped_m2):
    vals = [v for v in per_robot_proc.values() if v]
    out = {}
    if vals:
        for key, agg in (('cpu_mean_pct', np.mean), ('cpu_peak_pct', np.max), ('memory_mean_mb', np.mean),
                         ('memory_peak_mb', np.max), ('memory_overhead_mb', np.mean)):
            xs = [v[key] for v in vals if key in v]
            if xs:
                out[key] = float(agg(xs))
        cpu_s = sum(v.get('cpu_seconds', 0.) for v in vals)
        out['cpu_seconds_total'] = cpu_s
        out['computational_overhead'] = {
            'cpu_cores_per_robot': cpu_s/max(run.sim_end, 1e-6)/len(vals),
            'cpu_seconds_per_m': cpu_s/trajectory['swarm']['distance_m'] if trajectory['swarm'].get('distance_m') else None,
            'cpu_seconds_per_m2_mapped': cpu_s/mapped_m2 if mapped_m2 else None}
        lat = [v['processing_latency_ms']['mean'] for v in vals if 'processing_latency_ms' in v]
        if lat:
            out['processing_latency_mean_ms'] = float(np.mean(lat))
            out['processing_latency_p95_ms'] = float(np.mean([v['processing_latency_ms']['p95'] for v in vals if 'processing_latency_ms' in v]))
        fps = [v['throughput_fps_wall'] for v in vals if v.get('throughput_fps_wall')]
        if fps:
            out['throughput_fps_wall'] = float(np.mean(fps))
        fps_s = [v['throughput_fps_sim'] for v in vals if v.get('throughput_fps_sim')]
        if fps_s:
            out['throughput_fps_sim'] = float(np.mean(fps_s))
        opt = [v['optimization_time_s']['mean'] for v in vals if 'optimization_time_s' in v]
        if opt:
            out['optimization_time_mean_s'] = float(np.mean(opt))
            out['optimization_time_max_s'] = float(np.max([v['optimization_time_s']['max'] for v in vals if 'optimization_time_s' in v]))
    return out
