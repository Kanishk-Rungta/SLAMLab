"""BstemSensors bridge to the official D2SLAM native stack (D2VINS + D2PGO).

No simulator positions, RangeFinder, lidar, shared peer files or Python pose
estimation substitute. D2VINS odometry with D2PGO's correction is the only
source of the reported SLAM estimate.
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
from radio_packets import sender_of
from radio_outbox import RadioOutbox
from mapping import StereoMapper, compose
from d2_outputs import PoseCorrection, loop_measurement, stamp_key

PROTOCOL = 'd2slam-original-v1'


def write_json(path, value):
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=1, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


def tum(stream, stamp, pose):
    stream.write('%.6f %.6f %.6f 0 0 0 %.8f %.8f\n' % (stamp, pose[0], pose[1], math.sin(pose[2]/2), math.cos(pose[2]/2)))


def main():
    from controller import Robot
    robot = Robot()
    sensors = BstemSensors(robot, load_spec())
    config = json.loads(Path(os.environ['D2SLAM_RUN_CONFIG']).read_text(encoding='utf-8-sig'))
    profile = config['profile']
    run = Path(config['output_dir'])
    out = run / ('robot_%d' % sensors.number)
    (out / 'map_history').mkdir(parents=True, exist_ok=True)
    number = sensors.number
    # Each robot starts D2SLAM in an independent local map. These frames must
    # not be jointly aligned unless a verified peer-map merge is reported.
    frame = '%s_robot_%d' % (profile['frame'], number)
    log = BenchLog(robot.getName(), profile['algorithm'], frame=frame, resource_period=0,
                   meta={'known_docks': False, 'upstream_commit': config['upstream_commit'],
                         'pose_source': 'native D2VINS odometry with the native D2PGO correction',
                         'occupancy': 'local stereo output adapter; no merged occupancy output',
                         'cnn_backend': 'ONNX Runtime CPU', 'motion_policy': profile['motion_policy'],
                         'lidar': False, 'imu': 'standard 3-axis gyro (BstemSensors.imu()) and raw accelerometer',
                         'odometry_baseline': 'saved separately in each robot-local frame; not a shared-frame benchmark baseline',
                         'transport': 'standard radio carrying unchanged native LCM bytes',
                         'validation': 'native stack requires target-machine validation'})
    mapper = StereoMapper(sensors.spec['stereo'], profile)
    outbox = RadioOutbox(sensors.spec['radio']['bandwidth_limit_Bps'])
    correction = PoseCorrection()
    self_process = psutil.Process()
    self_process.cpu_percent(None)
    native = None
    now = 0.
    pose = np.zeros(3)
    wheels_pose = np.zeros(3)
    rays_by_stamp = {}
    keyframe_vio = {}
    graph = {}
    pending_images = None
    latest_rays = []
    clearance = (None, None, None)
    last_depth = -1e9
    last_pose_time = last_snapshot = last_status = -1e9
    last_live = -1e9
    seen_loops = set()
    merged_peers = set()
    last_peer_log = -1e9
    bias_sum = bias_n = 0
    tracking = 'initializing'
    initialized = False
    idle_since = None
    wall_start = time.perf_counter()
    reason = 'simulation_ended'
    log.tracking(0, tracking)
    trajectory = (out / 'estimate_tum.txt').open('w', encoding='utf-8')
    odometry_trajectory = (out / 'odometry_tum.txt').open('w', encoding='utf-8')
    odometry_trajectory.write('# wheel/gyro baseline in this robot-local start frame; not d2_map\n')
    write_json(out / 'config_used.json', config)

    def keyframe_poses():
        # D2PGO's optimized keyframes; newer keyframes not yet optimized use
        # D2VINS odometry with the latest D2PGO correction.
        poses = {key: correction.apply(vio) for key, vio in keyframe_vio.items()}
        poses.update(graph)
        return poses

    def snapshot():
        grid = mapper.rebuild(keyframe_poses())
        log.map(now, grid, mapper.resolution, mapper.origin, kind='local', frame=frame,
                memory_bytes=mapper.grid.nbytes)
        np.savez_compressed(out / 'final_map.npz', grid=grid, resolution=mapper.resolution,
                            origin=mapper.origin, frame=frame)

    try:
        native = socket.create_connection((config['native_host'], config['native_ports'][number-1]), timeout=30)
        native.settimeout(profile['frame_wait_wall_seconds']+60)
        send(native, {'protocol': PROTOCOL})
        if receive(native) != {'ready': True, 'protocol': PROTOCOL}:
            raise RuntimeError('Native handshake failed')
        while robot.step(sensors.step_ms) != -1:
            now = robot.getTime()
            wheels, gyro, accel = sensors.read()
            gyro_xyz, accel = sensors.imu()
            if now < profile['settle_seconds']:
                bias_sum += gyro
                bias_n += 1
            else:
                angle = (gyro-bias_sum/max(1, bias_n))*sensors.dt
                distance = float(np.mean(wheels))
                wheels_pose = compose(wheels_pose, [distance*math.cos(angle/2), distance*math.sin(angle/2), angle])
            packets = sensors.receive()
            for raw in packets:
                sender = sender_of(raw)
                log.recv(now, raw, source=None if sender is None else 'bstem%d' % sender)
            request = {'t': now, 'imu': [float(v) for v in gyro_xyz] + [float(v) for v in accel],
                       'radio': [encode_bytes(raw) for raw in packets]}
            if pending_images is not None:
                # One step late: D2VINS needs an IMU sample newer than the frame.
                request['image_stamp'], request['images'] = pending_images
                pending_images = None
            images = sensors.images()
            if images is not None:
                latest_rays, clearance = mapper.rays(*images)
                rays_by_stamp[stamp_key(now)] = latest_rays
                last_depth = now
                encoded = []
                for image in images:
                    ok, data = cv2.imencode('.png', image)
                    if not ok:
                        raise RuntimeError('Lossless stereo encoding failed')
                    encoded.append(encode_bytes(data.tobytes()))
                pending_images = (now, encoded)
            send(native, request)
            response = receive(native)
            logical_messages = response.get('radio_messages')
            if logical_messages is None:
                logical_messages = [[raw] for raw in response.get('radio', [])]
            for encoded_message in logical_messages:
                if not outbox.enqueue_message([decode_bytes(raw) for raw in encoded_message]):
                    log.event(now, 'radio_queue_drop', reason='native outbox full')
            for packet in outbox.offer(now):
                log.send(now, packet)
                sensors.send(packet)
            latest_vio = None
            for event in response['events']:
                kind = event['kind']
                if kind == 'error':
                    raise RuntimeError(event['message'])
                if kind in ('radio_drop', 'radio_reject'):
                    log.event(now, kind, **{k: v for k, v in event.items() if k not in ('kind', 't')})
                elif kind == 'odometry':
                    correction.add_vio(event['t'], event['pose'])
                    if latest_vio is None or event['t'] >= latest_vio[0]:
                        latest_vio = (event['t'], event['pose'])
                elif kind == 'frame':
                    stamp = event['t']
                    log.frame(stamp, event['latency_s'])
                    rays = rays_by_stamp.pop(stamp_key(stamp), None)
                    if event['keyframe']:
                        vio = correction.vio_at(stamp)
                        if vio is not None and rays is not None:
                            keyframe_vio[stamp_key(stamp)] = vio
                            mapper.keyframes[stamp_key(stamp)] = rays
                            log.keyframe(stamp, len(mapper.keyframes))
                            log.map_update(stamp)
                elif kind == 'pgo_pose':
                    correction.set_pgo(event['t'], event['pose'])
                elif kind == 'pgo_traj':
                    graph = {stamp_key(s): p for s, p in zip(event['stamps'], event['poses'])}
                elif kind == 'solve':
                    if event['success']:
                        log.optimization(event['t'], event['duration'], kind='d2pgo_distributed', nodes=len(graph))
                elif kind == 'loop':
                    measurement = loop_measurement(event, number)
                    if measurement is not None and event['id'] not in seen_loops:
                        seen_loops.add(event['id'])
                        current_time, peer, matched_time, relative = measurement
                        log.loop(current_time, True, 'bstem%d' % peer, matched_time, relative=relative,
                                 score=event['inliers'], reason='D2SLAM front-end geometric verification')
                elif kind == 'fused':
                    for peer in event['peers']:
                        if peer not in merged_peers:
                            merged_peers.add(peer)
                            log.merge(now, 'bstem%s' % peer)
                    if now-last_peer_log >= 1.:
                        for peer, (x, y, yaw) in event['peers'].items():
                            log.peer_pose(now, 'bstem%s' % peer, x, y, yaw)
                        last_peer_log = now
            # Drop rays of frames the native side never reported (camera dropouts excluded).
            for key in [k for k in rays_by_stamp if k < stamp_key(now-5.)]:
                del rays_by_stamp[key]
            if latest_vio is not None:
                stamp, vio = latest_vio
                pose = np.asarray(correction.apply(vio))
                if not initialized:
                    log.initialized(stamp)
                    initialized = True
                    tracking = 'ok'
                    log.tracking(stamp, tracking)
                if stamp-last_pose_time >= .2:
                    # Wheel dead reckoning starts in a DIFFERENT local frame for
                    # every robot. Do not pass it as shared-frame odometry.
                    log.pose(stamp, *pose)
                    tum(trajectory, stamp, pose)
                    tum(odometry_trajectory, stamp, wheels_pose)
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
            can_move = initialized and now >= profile['settle_seconds'] and now-last_depth < .5
            if can_move:
                sign = 1 if (left or 0) > (right or 0) else -1
                if front is None or front < .35:
                    angular = sign*profile['turn_rad_s']
                elif now % 40 < 2*math.pi/profile['turn_rad_s']:
                    angular = profile['turn_rad_s']*(1 if number % 2 else -1)
                else:
                    linear = min(profile['speed_m_s'], max(0., (front-.35)*.3))
            sensors.drive(linear, angular)
            wall = time.perf_counter()-wall_start
            if now-last_snapshot >= 60:
                snapshot()
                last_snapshot = now
            if wall-last_live >= config['live_map_wall_seconds']:
                snapshot()
                mapper.render(out / 'live_map.png', pose, '%s | native D2SLAM | local occupancy adapter' % robot.getName())
                shutil.copyfile(out / 'live_map.png', out / 'map_history' / ('map_%05dmin_%d.png' % (int(wall/60), time.time_ns())))
                last_live = wall
            if now-last_status >= 5:
                write_json(out / 'status.json', {'time': now, 'pose': [float(v) for v in pose], 'frame': frame,
                           'tracking': tracking, 'keyframes': len(mapper.keyframes), 'loops': len(seen_loops),
                           'pgo_correction': correction.has_pgo, 'peers_merged': sorted(merged_peers)})
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
            if not initialized or front is None:
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
            mapper.render(out / 'final_map.png', pose, '%s | final native D2SLAM local map' % robot.getName())
            shutil.copyfile(out / 'final_map.png', out / 'live_map.png')
            write_json(out / 'summary.json', {'reason': reason, 'time': now, 'pose': [float(v) for v in pose],
                       'algorithm': profile['algorithm'], 'frame': frame, 'keyframes': len(mapper.keyframes),
                       'loops': len(seen_loops), 'peers_merged': sorted(merged_peers)})
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
