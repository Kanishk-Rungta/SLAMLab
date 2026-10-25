#!/usr/bin/env python3
"""AB3 output node for the original Kimera-Multi (added file; reads published estimates only).

Kimera-VIO publishes the robot's keyframe poses (odometry frame) and Kimera-Distributed/DPGO the
optimised keyframe poses in the shared world frame (anchored to robot 0). This node reports:
  /ab3/native_pose  the latest Kimera-VIO odometry pose, carried into the DPGO world frame with the
                    correction of the newest keyframe that both have: T = T_world(kf) T_odom(kf)^-1
  /ab3/events       graph3: the optimised keyframes (world) - or, before the first DPGO solution, the
                    VIO keyframes (odometry frame). Keys are keyframe timestamps (ns), so the
                    occupancy adapter keeps its keyframes across the frame change.
Poses are body (IMU = robot body) poses. Nothing is published to Kimera-Multi.
"""
import json
import numpy as np
import rospy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from pose_graph_tools_msgs.msg import PoseGraph
from std_msgs.msg import String


def matrix(pose):
    q = np.array([pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w])
    x, y, z, w = q / np.linalg.norm(q)
    T = np.eye(4)
    T[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                 [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                 [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    T[:3, 3] = [pose.position.x, pose.position.y, pose.position.z]
    return T


def quaternion(R):
    w = np.sqrt(max(0., 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = np.sqrt(max(0., 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2
    y = np.sqrt(max(0., 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2
    z = np.sqrt(max(0., 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2
    x, y, z = np.copysign(x, R[2, 1] - R[1, 2]), np.copysign(y, R[0, 2] - R[2, 0]), np.copysign(z, R[1, 0] - R[0, 1])
    return [float(x), float(y), float(z), float(w)]


class Output:
    def __init__(self):
        self.name, self.id = rospy.get_param('~robot_name'), int(rospy.get_param('~robot_id'))
        self.odom_frame, self.world_frame = 'kimera_%s_odom' % self.name, 'kimera_world'
        self.vio, self.optimised, self.correction = {}, {}, None
        self.pose_pub = rospy.Publisher('/ab3/native_pose', PoseStamped, queue_size=100)
        self.events = rospy.Publisher('/ab3/events', String, queue_size=100)
        rospy.Subscriber('/%s/kimera_vio_ros/pose_graph_incremental' % self.name, PoseGraph, self.on_vio_graph, queue_size=100)
        rospy.Subscriber('/%s/kimera_distributed/optimized_nodes' % self.name, PoseGraph, self.on_optimised, queue_size=10)
        rospy.Subscriber('/%s/kimera_vio_ros/odometry' % self.name, Odometry, self.on_odometry, queue_size=100)
        rospy.Timer(rospy.Duration(2.), self.publish_graph)

    def on_vio_graph(self, msg):
        for node in msg.nodes:
            if node.robot_id == self.id:
                self.vio[node.header.stamp.to_nsec()] = matrix(node.pose)

    def on_optimised(self, msg):
        self.optimised = {n.header.stamp.to_nsec(): matrix(n.pose) for n in msg.nodes if n.robot_id == self.id}
        common = sorted(set(self.optimised) & set(self.vio))
        if common:
            k = common[-1]
            self.correction = self.optimised[k] @ np.linalg.inv(self.vio[k])
        self.publish_graph()

    def on_odometry(self, msg):
        T, frame = matrix(msg.pose.pose), self.odom_frame
        if self.correction is not None:
            T, frame = self.correction @ T, self.world_frame
        out = PoseStamped()
        out.header.stamp, out.header.frame_id = msg.header.stamp, frame
        out.pose.position.x, out.pose.position.y, out.pose.position.z = T[:3, 3]
        q = quaternion(T[:3, :3])
        out.pose.orientation.x, out.pose.orientation.y, out.pose.orientation.z, out.pose.orientation.w = q
        self.pose_pub.publish(out)

    def publish_graph(self, _event=None):
        nodes, frame = (self.optimised, self.world_frame) if self.optimised else (self.vio, self.odom_frame)
        if not nodes:
            return
        now = rospy.Time.now().to_sec()
        event = {'kind': 'graph3', 't': now, 'frame': frame, 'axes': 'body',
                 'nodes': [{'key': str(k), 't': k * 1e-9, 'position': T[:3, 3].tolist(), 'quaternion': quaternion(T[:3, :3])}
                           for k, T in sorted(nodes.items()) if k * 1e-9 <= now]}
        self.events.publish(String(json.dumps(event)))


if __name__ == '__main__':
    rospy.init_node('ab3_kimera_output')
    Output()
    rospy.spin()
