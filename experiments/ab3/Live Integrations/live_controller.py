"""Shared Webots sensor/radio/benchmark boundary for the additional native ports.

The only SLAM estimates consumed here are timestamped native poses/graphs.
Stereo occupancy is an output adapter and a reactive motion sensor, not a SLAM
replacement. No simulator geometry or evaluation ground truth is read.
"""
from collections import OrderedDict
import json
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import time

HERE = Path(__file__).resolve().parent
STANDARD = Path(os.environ.get('STANDARD_ENV', str(HERE.parent / 'Standard Environment')))
sys.path[:0] = [str(HERE), str(STANDARD / 'sensors'), str(STANDARD / 'benchmark')]
import numpy as np
import psutil
from bstem_sensors import BstemSensors
from benchlog import BenchLog
from live_radio import RadioLink, packet_sender
from live_wire import send, receive, b64, unb64
from pose_frames import planar_pose
from stereo_output import StereoMapper
from monocular_scale import MonocularScale
from server_correction import ServerCorrection
from initialization_scan import scan_command
from reactive_drive import ReactiveDrive


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def main():
    from controller import Robot
    robot = Robot()
    sensors = BstemSensors(robot)
    config = json.loads(Path(os.environ['AB3_LIVE_CONFIG']).read_text(encoding='utf-8-sig'))
    profile, number = config['profile'], sensors.number
    run = Path(config['output_dir'])
    out = run / ('robot_%d' % number)
    (out / 'map_history').mkdir(parents=True, exist_ok=True)
    log = BenchLog(robot.getName(), profile.get('result_label', profile['algorithm']),
                   frame='native_pending', resource_period=0, meta={
                       'upstream_commit': config['upstream_commit'], 'known_docks': False,
                       'input_mode': profile['input_mode'], 'native_validation': 'unvalidated',
                       'transport': 'isolated native runtime; all peer traffic via BstemSensors',
                       'occupancy': 'local standard stereo output rasterized with native corrected keyframes',
                       'motion_policy': ('standard-stereo reactive motion with committed obstacle turns and slow pre-initialization scan; no world or ground truth'
                                         if profile['id'] == 'dvm_slam' else
                                         'standard-stereo reactive motion; no world or ground truth'),
                       'unsupported_telemetry': profile.get('unsupported_telemetry', [])})
    radio = RadioLink(number, sensors.spec['radio']['bandwidth_limit_Bps'],
                      recoverable=profile['id'] == 'dvm_slam')
    mono = MonocularScale()
    correction = ServerCorrection(run, number) if profile.get('server_output') == 'covins' else None
    mapper = StereoMapper(sensors.spec['stereo'], {
        'map_resolution_m': .05, 'map_size_m': 160.})   # depth limit derived (stereo_output.py)
    rays = OrderedDict()
    graph, frame = {}, 'native_pending'
    pose = [0., 0., 0.]
    tracking, initialized = 'initializing', False
    last_depth = -1e9
    clearance = (None, None, None)
    last_snapshot, last_status, last_live = -1e9, -1e9, -1e9
    last_pose, completed_frame = -1e9, -1e9
    reason, now = 'simulation_ended', 0.
    native = None
    pending_image = None
    peer_rpc_failures = radio_transport_failures = 0
    motion_mode, last_motion_mode = 'waiting_for_stereo', None
    reactive_drive = ReactiveDrive(number) if profile['id'] == 'dvm_slam' else None
    linear = angular = 0.
    reported_keyframes = set()
    self_process = psutil.Process()
    self_process.cpu_percent(None)
    trajectory = (out / 'estimate_tum.txt').open('w', encoding='utf-8')
    log.tracking(now, tracking)

    def snapshot(final=False):
        if initialized and graph:
            grid = mapper.rebuild(graph)
            log.map(now, grid, mapper.resolution, mapper.origin, kind='local', frame=frame)
            mapper.render(out / ('final_map.png' if final else 'live_map.png'), pose,
                          '%s | %s | native corrected local occupancy' % (robot.getName(), profile['algorithm']))
            if final:
                shutil.copyfile(out / 'final_map.png', out / 'live_map.png')

    def consume(response):
        nonlocal frame, graph, pose, initialized, tracking, completed_frame, last_pose, peer_rpc_failures
        if 'error' in response:
            raise RuntimeError(response['error'])
        if response.get('protocol') != 'ab3-live-v1':
            raise RuntimeError('Unexpected native runtime protocol')
        for outgoing in response.get('radio', []):
            payload = unb64(outgoing['data'])
            try:
                record = json.loads(payload)
            except (ValueError, UnicodeError):
                record = {}
            if not isinstance(record, dict):
                record = {}
            metadata = {key: record[key] for key in ('kind', 'id', 'name', 'topic') if key in record}
            radio.enqueue(outgoing['destination'], payload, now,
                          reliable=outgoing.get('reliable', False), metadata=metadata)
        events = response.get('events', [])
        if correction is not None:
            events = correction.process(events, now)     # centralized back-ends (server_correction.py)
        for event in events:
            kind, stamp = event['kind'], float(event['t'])
            if kind == 'peer_rpc_failed':
                peer_rpc_failures += 1
            if stamp > now + 1e-6:
                raise RuntimeError('Native event is ahead of the simulation clock')
            if kind in ('pose3', 'graph3') and not event.get('metric', True):
                # Monocular output: scale it with the robot's own wheel odometry (output only;
                # see monocular_scale.py). Keyframes feed the estimate before anything is logged.
                if kind == 'graph3':
                    previous = mono.scale
                    if mono.update(event['nodes']) is not None and (previous is None or abs(mono.scale / previous - 1) > .02):
                        log.event(now, 'native_scale', scale=mono.scale, source='wheel path / native keyframe translation')
                if mono.scale is None:
                    continue
                event = mono.apply(event) if kind == 'pose3' else dict(event, nodes=[mono.apply(n) for n in event['nodes']])
            if kind == 'pose3':
                if not event.get('metric', True):
                    raise RuntimeError('Cannot log arbitrary-scale native coordinates as metric benchmark poses')
                pose, z = planar_pose(event, sensors.spec['stereo'])
                native_frame = event['frame']
                if native_frame != frame:
                    frame = native_frame
                    graph = {}      # keyframe rays are kept: the next graph re-places them by key
                    log.event(now, 'native_frame_change', frame=frame)
                if not initialized:
                    log.initialized(stamp)
                    initialized = True
                if tracking != 'ok':
                    tracking = 'ok'
                    log.tracking(stamp, tracking)
                log.pose(stamp, *pose, z=z, frame=frame)
                trajectory.write('%.9f %.9f %.9f %.9f 0 0 %.9f %.9f\n' %
                    (stamp, pose[0], pose[1], z, math.sin(pose[2] / 2), math.cos(pose[2] / 2)))
                last_pose = stamp
            elif kind == 'graph3':
                if event['frame'] != frame:
                    continue
                updated = {}
                for node in event['nodes']:
                    key = str(node['key'])
                    identity = (frame, key)
                    if identity not in reported_keyframes:
                        log.event(node['t'], 'native_keyframe', key=key, frame=frame)
                        reported_keyframes.add(identity)
                    node_pose, _ = planar_pose(dict(node, axes=event['axes']), sensors.spec['stereo'])
                    updated[key] = node_pose
                    if key not in mapper.keyframes:
                        captured = rays.get(int(round(node['t'] * 1e9)))
                        if captured is not None:
                            mapper.keyframes[key] = captured
                            log.keyframe(node['t'], len(mapper.keyframes))
                            log.map_update(now)
                graph = updated
            elif kind == 'frame_done':
                completed_frame = max(completed_frame, stamp)
                latency = event.get('latency_s')
                if latency is None and pending_image is not None:
                    latency = time.monotonic() - pending_image[1]
                if latency is not None:
                    log.frame(stamp, latency)
                state = event.get('tracking', tracking)
                if not initialized and state == 'lost':
                    state = 'initializing'
                if state != tracking:
                    tracking = state
                    log.tracking(stamp, tracking)
            elif kind == 'merge':
                log.merge(stamp, 'bstem%d' % event['peer'])
            elif kind == 'loop':
                log._write({'type': 'loop', 't': stamp, 'accepted': event['accepted'],
                    'matched_robot': event.get('matched_robot'), 'matched_time': event.get('matched_time'),
                    'relative': event.get('relative'), 'reason': event.get('reason'),
                    'current_keyframe': event.get('current_keyframe'), 'matched_keyframe': event.get('matched_keyframe')})
            elif kind == 'keyframe':
                key = str(event['key'])
                identity = (frame, key)
                if identity not in reported_keyframes:
                    log.event(stamp, 'native_keyframe', key=key, frame=frame)
                    reported_keyframes.add(identity)
            elif kind == 'optimization':
                log.optimization(stamp, event['duration_s'], kind=event.get('solver', 'native'))
            else:
                log.event(stamp, 'native_' + kind, **{k: v for k, v in event.items() if k not in ('kind', 't')})
        if response.get('resources'):
            resource = response['resources']
            resource['cpu_pct'] += self_process.cpu_percent(None)
            resource['cpu_seconds'] += sum(self_process.cpu_times()[:2])
            resource['rss'] += self_process.memory_info().rss
            resource['threads'] += self_process.num_threads()
            log.event(now, 'native_and_bridge_resources', type='resource', **resource)

    def transport_failures():
        nonlocal radio_transport_failures
        failures = radio.take_failures()
        radio_transport_failures += len(failures)
        for failure in failures:
            metadata = failure['metadata']
            log.event(now, 'peer_transport_failure', peer=failure['destination'],
                      reason=failure['reason'], record_kind=metadata.get('kind'),
                      request_id=metadata.get('id'), service=metadata.get('name'), topic=metadata.get('topic'))
        return failures

    try:
        native = socket.create_connection(('127.0.0.1', config['ports'][number - 1]), timeout=60.)
        native.settimeout(120.)
        greeting = receive(native)
        if greeting != {'protocol': 'ab3-live-v1', 'number': number}:
            raise RuntimeError('Native runtime identity does not match this robot')
        while robot.step(sensors.step_ms) != -1:
            now = robot.getTime()
            wheels, gyro, accel = sensors.read()
            gyro_xyz, accel = sensors.imu()
            mono.wheels(now, wheels)
            incoming = []
            for packet in sensors.receive():
                sender = packet_sender(packet)
                if sender is None:
                    raise RuntimeError('Unexpected peer protocol in the algorithm world')
                log.recv(now, packet, 'bstem%d' % sender)
                value = radio.accept(packet, now)
                if value:
                    incoming.append({'sender': value['sender'], 'data': b64(value['payload'])})
            images = sensors.images()
            request = {'t': now, 'gyro': [float(v) for v in gyro_xyz], 'accel': accel.tolist(), 'radio': incoming,
                       'transport_failures': transport_failures()}
            if images is not None:
                left, right = images
                current_rays, clearance = mapper.rays(left, right)
                rays[int(round(now * 1e9))] = current_rays
                while len(rays) > 2048:
                    rays.popitem(last=False)
                last_depth = now
                request['images'] = {'left': b64(left.tobytes()), 'right': b64(right.tobytes())}
                pending_image = (now, time.monotonic())
            send(native, request)
            consume(receive(native))
            if pending_image is not None and profile.get('frame_ack') == 'none':
                # The native front-end acknowledges keyframes only (Kimera-VIO): frames stream at the
                # simulation pace like a real camera; latency is not reported per frame.
                pending_image = None
            if pending_image is not None:
                # Backpressure only on native visual processing; peer service
                # callbacks run asynchronously and never gate a visual frame.
                deadline = pending_image[1] + config.get('frame_timeout_wall_s', 120.)
                while completed_frame + 1e-7 < pending_image[0]:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Native visual frontend did not finish its camera frame')
                    time.sleep(.002)
                    send(native, {'t': now, 'poll': True, 'radio': [],
                                  'transport_failures': transport_failures()})
                    consume(receive(native))
                pending_image = None
            def attempt(packet):
                accepted = sensors.send(packet)
                if accepted:
                    log.send(now, packet)
                return accepted
            radio.drain(attempt, now)
            front, left_clear, right_clear = clearance
            linear = angular = 0.
            motion_mode = 'waiting_for_stereo'
            if reactive_drive is None and now >= 2. and now - last_depth < .5:
                motion_mode = 'reactive'
                sign = 1 if (left_clear or 0.) >= (right_clear or 0.) else -1
                if front is None or front < .35:
                    angular = .45 * sign
                else:
                    linear = min(.15, max(0., (front - .35) * .3))
                    if now % 60 < 4:
                        linear, angular = 0., .45 * (1 if number % 2 else -1)
            if profile['id'] == 'dvm_slam':
                scan = scan_command(now, number, initialized, now - last_depth)
                if scan is not None:
                    reactive_drive.reset()
                    linear, angular = scan
                    motion_mode = 'initialization_scan'
                else:
                    linear, angular, motion_mode = reactive_drive.command(now, clearance, now - last_depth)
                if motion_mode != last_motion_mode:
                    log.event(now, 'motion_mode', mode=motion_mode, initialized=initialized,
                              linear_m_s=linear, angular_rad_s=angular,
                              clearance_m=list(clearance), turn_sign=reactive_drive.turn_sign)
                    last_motion_mode = motion_mode
            sensors.drive(linear, angular)
            if now - last_pose > 2. and initialized and tracking == 'ok':
                tracking = 'lost'
                log.tracking(now, tracking, reason='native pose timeout')
            if now - last_snapshot >= 60:
                snapshot()
                last_snapshot = now
            if time.monotonic() - last_live >= config['live_map_wall_seconds']:
                snapshot()
                last_live = time.monotonic()
            if now - last_status >= 5.:
                write_json(out / 'status.json', {'time': now, 'tracking': tracking,
                           'frame': frame, 'pose': pose, 'keyframes': len(mapper.keyframes),
                           'motion_mode': motion_mode,
                           'last_command': {'linear_m_s': linear, 'angular_rad_s': angular},
                           'clearance_m': list(clearance),
                           'peer_rpc_failures': peer_rpc_failures, 'radio_transport_failures': radio_transport_failures})
                log.flush()
                trajectory.flush()
                last_status = now
            if (run / 'STOP').exists() or (run / 'benchmark/STOP').exists():
                reason = 'stop_requested'
                break
            if config['max_seconds'] and now >= config['max_seconds']:
                reason = 'time_limit'
                break
    except Exception as error:
        reason = 'controller_error'
        log.error(now, str(error))
        (run / 'benchmark/STOP').touch()
        raise
    finally:
        sensors.drive(0., 0.)
        try:
            snapshot(final=True)
            write_json(out / 'summary.json', {'reason': reason, 'time': now, 'frame': frame,
                       'algorithm': profile.get('result_label', profile['algorithm']),
                       'tracking': tracking, 'pose': pose, 'keyframes': len(mapper.keyframes),
                       'motion_mode': motion_mode,
                       'last_command': {'linear_m_s': linear, 'angular_rad_s': angular},
                       'clearance_m': list(clearance),
                       'peer_rpc_failures': peer_rpc_failures, 'radio_transport_failures': radio_transport_failures})
        finally:
            trajectory.close()
            log.close()
            if native is not None:
                try:
                    send(native, {'stop': True})
                except (OSError, EOFError):
                    pass
                native.close()
    if number == 1:
        while robot.step(sensors.step_ms) != -1:
            if all((run / ('robot_%d' % n) / 'summary.json').exists() for n in range(1, config['robots'] + 1)):
                (run / 'benchmark/STOP').touch()
                break
    while robot.step(sensors.step_ms) != -1:
        pass


if __name__ == '__main__':
    main()
