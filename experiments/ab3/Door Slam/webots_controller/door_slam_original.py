"""BstemSensors bridge to the official visual native DOOR-SLAM stack.

No simulator positions, RangeFinder, lidar, shared peer files or Python pose
estimation substitute. Native stereo odometry + the native optimized graph are
the only sources of the reported SLAM estimate.
"""
import json
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
STANDARD = Path(os.environ.get('STANDARD_ENV', str(ROOT.parent / 'Standard Environment')))
sys.path[:0] = [str(ROOT / 'bridge'), str(STANDARD / 'sensors'), str(STANDARD / 'benchmark')]
import cv2
import numpy as np
import psutil
from bstem_sensors import BstemSensors, load_spec
from benchlog import BenchLog
from wire import send, receive, encode_bytes, decode_bytes
from radio_packets import HEADER, MAGIC
from radio_outbox import RadioOutbox
from mapping import StereoMapper, compose, inverse, corrected_pose


def write_json(path, value):
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=1, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def main():
    from controller import Robot
    robot = Robot()
    sensors = BstemSensors(robot, load_spec())
    config = json.loads(Path(os.environ['DOOR_ORIGINAL_RUN_CONFIG']).read_text(encoding='utf-8-sig'))
    profile = config['profile']
    run = Path(config['output_dir'])
    out = run / ('robot_%d' % sensors.number)
    (out / 'map_history').mkdir(parents=True, exist_ok=True)
    rid = sensors.number-1
    frame = profile['frame']
    log = BenchLog(robot.getName(), 'DOOR-SLAM-Original-Stereo', frame=frame, resource_period=0,
                   meta={'known_docks': False, 'upstream_commit': config['upstream_commit'],
                         'pose_source': 'native optimized graph + native stereo odometry between keyframes',
                         'occupancy': 'local stereo output adapter; no merged occupancy output',
                         'motion_policy': profile['motion_policy'], 'lidar': False,
                         'odometry_baseline': 'saved separately in each robot-local frame; not a shared-frame benchmark baseline',
                         'transport': 'standard radio for ROS RPC and native Buzz',
                         'validation': 'native stack requires target-laptop validation'})
    mapper = StereoMapper(sensors.spec['stereo'], profile)
    outbox = RadioOutbox(sensors.spec['radio']['bandwidth_limit_Bps'])
    self_process = psutil.Process()
    self_process.cpu_percent(None)
    native = None
    now = 0.
    pose = np.zeros(3)
    wheels_pose = np.zeros(3)
    keyframe_visual = {0: np.zeros(3)}
    graph = {0: np.zeros(3)}
    times = {rid: {}}
    latest_rays = []
    clearance = (None, None, None)
    last_depth = -1e9
    last_pose_time = last_snapshot = last_status = -1e9
    last_live = -1e9
    seen_loops = set()
    bias_sum = bias_n = 0
    tracking = 'initializing'
    initialized = False
    optimization_start = None
    previous_state = 0
    idle_since = None
    wall_start = time.perf_counter()
    reason = 'simulation_ended'
    log.tracking(0, tracking)
    trajectory = (out / 'estimate_tum.txt').open('w', encoding='utf-8')
    odometry_trajectory = (out / 'odometry_tum.txt').open('w', encoding='utf-8')
    odometry_trajectory.write('# wheel/gyro baseline in this robot-local start frame; not door_map\n')
    write_json(out / 'config_used.json', config)

    def snapshot():
        grid = mapper.rebuild(graph)
        log.map(now, grid, mapper.resolution, mapper.origin, kind='local', frame=frame,
                memory_bytes=mapper.grid.nbytes)
        np.savez_compressed(out / 'final_map.npz', grid=grid, resolution=mapper.resolution,
                            origin=mapper.origin, frame=frame)

    try:
        native = socket.create_connection((config['native_host'], config['native_ports'][rid]), timeout=30)
        native.settimeout(profile['frame_wait_wall_seconds']+30)
        send(native, {'protocol': 'door-original-v1'})
        ready = receive(native)
        if ready != {'ready': True, 'protocol': 'door-original-v1'}:
            raise RuntimeError('Native handshake failed')
        while robot.step(sensors.step_ms) != -1:
            now = robot.getTime()
            wheels, gyro, accel = sensors.read()
            if now < 10:
                bias_sum += gyro
                bias_n += 1
            else:
                angle = (gyro-bias_sum/max(1, bias_n))*sensors.dt
                distance = float(np.mean(wheels))
                wheels_pose = compose(wheels_pose, [distance*math.cos(angle/2), distance*math.sin(angle/2), angle])
            packets = sensors.receive()
            for raw in packets:
                source = None
                if len(raw) >= HEADER.size:
                    envelope = HEADER.unpack(raw[:HEADER.size])
                    if envelope[0] == MAGIC:
                        source = 'bstem%d' % (envelope[1]+1)
                log.recv(now, raw, source=source)
            images = sensors.images()
            request = {'t': now, 'radio': [encode_bytes(raw) for raw in packets]}
            if images is not None:
                latest_rays, clearance = mapper.rays(*images)
                last_depth = now
                encoded = []
                for image in images:
                    ok, data = cv2.imencode('.png', image)
                    if not ok:
                        raise RuntimeError('Lossless stereo encoding failed')
                    encoded.append(encode_bytes(data.tobytes()))
                request['images'] = encoded
            send(native, request)
            response = receive(native)
            for raw in response.get('radio', []):
                if not outbox.enqueue(decode_bytes(raw)):
                    log.event(now, 'radio_queue_drop', reason='native outbox full')
            for packet in outbox.offer(now):
                log.send(now, packet)
                sensors.send(packet)
            odometry = {float(t): np.asarray(p, float) for t, p in response['odometry'].items()}
            for event in response['events']:
                kind = event['kind']
                if kind == 'error':
                    raise RuntimeError(event['message'])
                if kind == 'component_error':
                    log.error(event['t'], event['message'])
                if kind == 'peer_times':
                    times[event['robot']] = {int(k): float(t) for k, t in event['times'].items()}
                elif kind == 'frame':
                    stamp = event['t']
                    log.frame(stamp, event['latency_s'])
                    next_tracking = 'lost' if event['lost'] else 'ok'
                    if tracking != next_tracking:
                        log.tracking(stamp, next_tracking)
                        tracking = next_tracking
                    keyframe = event['keyframe']
                    if keyframe is not None:
                        times[rid][keyframe-1] = stamp
                        matching = min(odometry, key=lambda t: abs(t-stamp)) if odometry else None
                        if matching is not None and abs(matching-stamp) < 1e-4:
                            keyframe_visual[keyframe] = odometry[matching]
                        # Frames are processed synchronously by this bridge.
                        if abs(stamp-now) < 1e-4:
                            mapper.keyframes[keyframe] = latest_rays
                            log.keyframe(stamp, keyframe)
                            log.map_update(stamp)
            state = response.get('state')
            if state:
                graph = {int(p[0]): np.asarray(p[1:], float) for p in state['graph']}
                state_code = state['state']
                if previous_state == 0 and state_code != 0:
                    optimization_start = time.perf_counter()
                if previous_state != 6 and state_code == 6 and optimization_start is not None:
                    log.optimization(now, time.perf_counter()-optimization_start, kind='distributed_round', nodes=len(graph))
                    optimization_start = None
                previous_state = state_code
                for a, ka, b, kb, accepted, x, y, yaw in state['loops']:
                    identity = (a, ka, b, kb)
                    if identity in seen_loops:
                        continue
                    if rid == a:
                        current_time = times.get(a, {}).get(ka)
                        matched_time = times.get(b, {}).get(kb)
                        relative, peer = inverse([x, y, yaw]), b
                    elif rid == b:
                        current_time = times.get(b, {}).get(kb)
                        matched_time = times.get(a, {}).get(ka)
                        relative, peer = [x, y, yaw], a
                    else:
                        continue
                    if current_time is not None and matched_time is not None:
                        log.loop(current_time, accepted, 'bstem%d' % (peer+1), matched_time,
                                 relative=relative, reason='native PCM first decision')
                        seen_loops.add(identity)
            latest = response.get('latest')
            if tracking == 'ok' and latest and state:
                stamp, visual_pose = latest
                candidates = [key for key in graph if key in keyframe_visual]
                if not candidates:
                    raise RuntimeError('No native graph anchor for the visual pose')
                anchor = max(candidates)
                pose = corrected_pose(graph[anchor], keyframe_visual[anchor], visual_pose)
                if not initialized:
                    log.initialized(stamp)
                    initialized = True
                if stamp-last_pose_time >= .2:
                    # Wheel dead reckoning starts in a DIFFERENT local frame for
                    # every robot. Do not pass it as shared-frame odometry and
                    # fabricate an improvement ratio after native map alignment.
                    log.pose(stamp, *pose)
                    trajectory.write('%.6f %.6f %.6f 0 0 0 %.8f %.8f\n' %
                                     (stamp, pose[0], pose[1], math.sin(pose[2]/2), math.cos(pose[2]/2)))
                    odometry_trajectory.write('%.6f %.6f %.6f 0 0 0 %.8f %.8f\n' %
                        (stamp, wheels_pose[0], wheels_pose[1], math.sin(wheels_pose[2]/2), math.cos(wheels_pose[2]/2)))
                    last_pose_time = stamp
            if response.get('resources'):
                resources = response['resources']
                resources['cpu_pct'] += self_process.cpu_percent(None)
                resources['rss'] += self_process.memory_info().rss
                resources['cpu_seconds'] += sum(self_process.cpu_times()[:2])
                resources['threads'] += self_process.num_threads()
                log.event(now, 'native_and_bridge_resources', type='resource', **resources)
            front, left, right = clearance
            linear, angular = 0., 0.
            can_move = initialized and tracking == 'ok' and now >= 10 and now-last_depth < .5
            if can_move:
                sign = 1 if (left or 0) > (right or 0) else -1
                if front is None or front < .35:
                    angular = sign*profile['turn_rad_s']
                elif now % 40 < 2*math.pi/profile['turn_rad_s']:
                    angular = profile['turn_rad_s']*(1 if rid % 2 else -1)
                else:
                    linear = min(profile['speed_m_s'], max(0., (front-.35)*.3))
            sensors.drive(linear, angular)
            wall = time.perf_counter()-wall_start
            if now-last_snapshot >= 60:
                snapshot()
                last_snapshot = now
            if wall-last_live >= config['live_map_wall_seconds']:
                snapshot()
                mapper.render(out / 'live_map.png', pose, '%s | native DOOR-SLAM | local occupancy adapter' % robot.getName())
                shutil.copyfile(out / 'live_map.png', out / 'map_history' / ('map_%05dmin_%d.png' % (int(wall/60), time.time_ns())))
                last_live = wall
            if now-last_status >= 5:
                write_json(out / 'status.json', {'time': now, 'pose': pose.tolist(), 'frame': frame,
                           'tracking': tracking, 'keyframes': len(mapper.keyframes), 'loops': len(seen_loops)})
                log.flush()
                trajectory.flush()
                odometry_trajectory.flush()
                last_status = now
            if (run / 'STOP').exists():
                reason = 'stop_requested'
                break
            if config['max_seconds'] and now >= config['max_seconds']:
                reason = 'time_limit'
                break
            if not initialized or tracking != 'ok' or front is None:
                idle_since = now if idle_since is None else idle_since
            else:
                idle_since = None
            if config['idle_seconds'] and idle_since is not None and now-idle_since >= config['idle_seconds']:
                reason = 'no_visual_progress'
                break
    except Exception as error:
        reason = 'controller_error'
        log.error(now, str(error))
        (run / 'benchmark/STOP').touch()
        raise
    finally:
        sensors.drive(0., 0.)
        try:
            snapshot()
            mapper.render(out / 'final_map.png', pose, '%s | final native DOOR-SLAM local map' % robot.getName())
            shutil.copyfile(out / 'final_map.png', out / 'live_map.png')
            write_json(out / 'summary.json', {'reason': reason, 'time': now, 'pose': pose.tolist(),
                       'algorithm': 'DOOR-SLAM-Original-Stereo', 'frame': frame, 'keyframes': len(mapper.keyframes)})
        finally:
            trajectory.close()
            odometry_trajectory.close()
            log.close()
            if native is not None:
                try:
                    send(native, {'stop': True})
                except (OSError, EOFError):
                    pass
                native.close()
    if sensors.number == 1:
        deadline = now+120
        while robot.step(sensors.step_ms) != -1:
            if all((run / ('robot_%d' % n) / 'summary.json').exists() for n in range(1, config['robots']+1)) or robot.getTime() >= deadline:
                (run / 'benchmark/STOP').touch()
                break
    while robot.step(sensors.step_ms) != -1:
        pass


if __name__ == '__main__':
    main()
