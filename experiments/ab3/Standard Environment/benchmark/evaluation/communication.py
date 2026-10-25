"""Communication and multi-robot coordination: bandwidth, traffic, latency, packet loss, overhead,
inter-robot pose estimation error and map-merging time.

Messages are matched across robots by the payload hash benchlog records on send and receive.
Expected receivers of a message are the other robots within comm_range_m of the sender at the time
(ground truth), so loss is not inflated by robots that were simply out of range. Messages sent during
a supervisor-injected radio outage are reported separately.
"""
from collections import defaultdict
import numpy as np
from .common import apply_se2, stats, wrap


def bins(times, values, width, end):
    if not len(times):
        return np.zeros(1)
    edges = np.arange(0, max(end, width)+width, width)
    hist, _ = np.histogram(times, bins=edges, weights=values)
    return hist/width


def evaluate(run, cfg, transforms, mapped_m2, distances):
    sends, recvs = {}, defaultdict(list)
    per_robot = {}
    span = max(run.sim_end, 1e-6)
    for robot in run.names:
        rec = run.robots.get(robot, {})
        s, r = rec.get('send', []), rec.get('recv', [])
        tx = np.array([m['bytes'] for m in s], float)
        rx = np.array([m['bytes'] for m in r], float)
        bw = bins(np.array([m['t'] for m in s]), tx, cfg['bandwidth_bin_s'], span)
        per_robot[robot] = {'tx_bytes': int(tx.sum()), 'rx_bytes': int(rx.sum()),
                            'tx_messages': len(s), 'rx_messages': len(r),
                            'tx_bandwidth_mean_Bps': float(tx.sum()/span), 'tx_bandwidth_peak_Bps': float(bw.max()),
                            'messages_per_s': float((len(s)+len(r))/span)}
        for m in s:
            # Identical payloads can be sent more than once (retransmissions): keep every send.
            sends.setdefault(m['id'], []).append((robot, m['t'], m['bytes']))
        for m in r:
            recvs[m['id']].append((robot, m['t']))
    outages = [(e['t'], e['robot'], e['state']) for e in run.supervisor if e.get('type') == 'comm_outage']

    def in_outage(robot, t):
        state = False
        for te, r, s in outages:
            if te > t:
                break
            if r == robot:
                state = s == 'start'
        return state
    latencies, expected, delivered, exp_out, del_out = [], 0, 0, 0, 0
    for mid, copies in sends.items():
        sender, t, _ = copies[0]
        send_times = np.sort([c[1] for c in copies])
        got = {}
        for r, tr in recvs.get(mid, []):
            if r == sender:
                continue
            got.setdefault(r, tr)
            # Latency against the latest send of this payload at or before the reception.
            k = np.searchsorted(send_times, tr, side='right')-1
            if k >= 0:
                latencies.append(tr-send_times[k])
        if sender not in run.gt or not run.gt_valid(sender, t)[0]:
            continue
        ps = run.gt_at(sender, t)[0, :2]
        for other in run.names:
            if other == sender or other not in run.gt or not run.gt_valid(other, t)[0]:
                continue
            if np.hypot(*(run.gt_at(other, t)[0, :2]-ps)) > cfg['comm_range_m']:
                continue
            outage = in_outage(sender, t) or in_outage(other, t)
            if outage:
                exp_out += 1
                del_out += other in got
            else:
                expected += 1
                delivered += other in got
    total_tx = sum(v['tx_bytes'] for v in per_robot.values())
    total_rx = sum(v['rx_bytes'] for v in per_robot.values())
    out = {'per_robot': per_robot,
           'total_tx_bytes': int(total_tx), 'total_rx_bytes': int(total_rx),
           'bandwidth_mean_Bps_per_robot': float(np.mean([v['tx_bandwidth_mean_Bps'] for v in per_robot.values()])) if per_robot else 0.,
           'bandwidth_peak_Bps': float(max([v['tx_bandwidth_peak_Bps'] for v in per_robot.values()] or [0])),
           'network_traffic_messages_per_s': float(sum(v['messages_per_s'] for v in per_robot.values())),
           'latency_s': stats(latencies),
           'packet_loss_rate': (1-delivered/expected) if expected else None,
           'expected_deliveries': expected,
           'packet_loss_rate_during_outages': (1-del_out/exp_out) if exp_out else None,
           'overhead_bytes_per_m2_mapped': float(total_tx/mapped_m2) if mapped_m2 else None,
           'overhead_bytes_per_m_travelled': float(total_tx/sum(distances.values())) if distances and sum(distances.values()) else None}
    out.update(inter_robot(run, cfg, transforms))
    return out


def inter_robot(run, cfg, transforms):
    errors, merges, first_merge = [], [], []
    for robot in run.names:
        rec = run.robots.get(robot, {})
        for e in rec.get('peer_pose', []):
            key = (robot, e.get('frame', 'map'))
            peer = e['peer']
            if key not in transforms or peer not in run.gt or not run.gt_valid(peer, e['t'])[0]:
                continue
            R, t = transforms[key]
            xy, yaw = apply_se2(R, t, np.array([e['p'][:2]]), np.array([e['p'][2]]))
            g = run.gt_at(peer, e['t'])[0]
            errors.append((float(np.hypot(*(xy[0]-g[:2]))), float(np.degrees(abs(wrap(yaw[0]-g[2]))))))
        merge_events = rec.get('merge', [])
        merges += [m['duration'] for m in merge_events if m.get('duration') is not None]
        # First-merge latency: first reception from a peer -> first merge of that peer's data.
        first_rx = {}
        for m in rec.get('recv', []):
            if m.get('src') is not None:
                first_rx.setdefault(str(m['src']), m['t'])
        done = set()
        for m in merge_events:
            peer = m['peer']
            if peer in first_rx and peer not in done:
                first_merge.append(m['t']-first_rx[peer])
                done.add(peer)
    out = {}
    if errors:
        out['inter_robot_pose_error_m'] = stats([e[0] for e in errors])
        out['inter_robot_heading_error_deg'] = stats([e[1] for e in errors])
    if merges:
        out['map_merging_time_s'] = stats(merges)
    if first_merge:
        out['first_merge_latency_s'] = stats(first_merge)
    return out
