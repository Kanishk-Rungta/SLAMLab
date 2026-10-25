"""Explicit native peer channels; sensor/debug/visualization data stays local."""
import re

DVM_CHANNELS = ('new_key_frame_bows', 'new_key_frames', 'loop_closure_triggers',
                'is_lost_from_base_map', 'change_coordinate_frame', 'map_to_attempt_merge')
SWARM_GLOBAL = ('global_descriptors', 'inter_robot_matches', 'inter_robot_loop_closure', 'pose_graph', 'local_descriptors')
SWARM_TARGET = ('local_descriptors_request', 'optimized_estimates', 'get_pose_graph')


def peer_address(stack, topic, robots):
    """None = local-only; 0 = broadcast; 1..10 = robot destination."""
    if stack == 'dvm_slam':
        if topic == '/successfully_merged':
            return 0
        match = re.fullmatch(r'/robot(\d+)/(' + '|'.join(DVM_CHANNELS) + ')', topic)
        if match and 1 <= int(match[1]) <= robots:
            return int(match[1])
    elif stack == 'swarm_slam':
        if topic in ('/cslam/' + name for name in SWARM_GLOBAL):
            return 0
        match = re.fullmatch(r'/r(\d+)/cslam/(' + '|'.join(SWARM_TARGET + ('heartbeat',)) + ')', topic)
        if match and 0 <= int(match[1]) < robots:
            return 0 if match[2] == 'heartbeat' else int(match[1]) + 1
    return None


def service_routes(stack, local, robots):
    if stack != 'dvm_slam':
        return []
    return [{'name': '/robot%d/%s' % (robot, name), 'target': robot,
             'type': 'interfaces/srv/' + kind}
            for robot in range(1, robots + 1)
            for name, kind in [('get_current_map', 'GetCurrentMap'), ('get_map_points', 'GetMapPoints')]]


KIMERA_DISTRIBUTED = ('vlc_requests', 'bow_requests', 'loop_closures', 'vlc_responses', 'loop_ack')
DPGO = ('lifting_matrix', 'status', 'command', 'anchor', 'public_poses', 'public_measurements', 'measurement_weights')


def ros1_routes(stack, number, robots):
    """Inter-robot ROS 1 topics: what robot `number` forwards (and to whom), and what it accepts.

    ROS 1 carries topics over TCP, so unicast routes use the radio link's reliable mode (ACKs and
    retransmissions, all within the standard radio budget)."""
    outgoing, incoming = [], []
    if stack == 'ccm_slam':
        # CCM-SLAM server is hosted on robot 1; clients are robots 1..N (client id = robot - 1).
        if number == 1:
            for peer in range(2, robots + 1):
                outgoing.append({'topic': '/ccmslam/MapOutServer%d' % (peer - 1), 'destination': peer, 'reliable': True})
                incoming.append({'topic': '/ccmslam/MapOutClient%d' % (peer - 1), 'sources': [peer]})
        else:
            outgoing.append({'topic': '/ccmslam/MapOutClient%d' % (number - 1), 'destination': 1, 'reliable': True})
            incoming.append({'topic': '/ccmslam/MapOutServer%d' % (number - 1), 'sources': [1]})
    elif stack == 'covins_g':
        pass        # COVINS-G uses its own TCP protocol only, carried by the gateway's radio tunnel
    elif stack == 'kimera_multi':
        # Kimera-Distributed and DPGO peer topics (named by the publishing robot, read by all others).
        # The radio is a broadcast medium; Kimera-Distributed has its own request/ack retries.
        for peer in range(1, robots + 1):
            names = ['/bstem%d/kimera_distributed/%s' % (peer, t) for t in KIMERA_DISTRIBUTED]
            names += ['/bstem%d/kimera_vio_ros/bow_query' % peer]
            names += ['/bstem%d/dpgo_ros_node/%s' % (peer, t) for t in DPGO]
            if peer == 1:
                names.append('/bstem1/kimera_distributed/pose_corrector')
            for topic in names:
                if peer == number:
                    outgoing.append({'topic': topic, 'destination': 0})
                else:
                    incoming.append({'topic': topic, 'sources': [peer]})
    else:
        raise ValueError('No ROS 1 peer routes for ' + stack)
    return {'outgoing': outgoing, 'incoming': incoming}
