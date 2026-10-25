"""ROS 2 -> benchmark bridge (UNTESTED: no ROS 2 on the development machine).

Logs a ROS-based SLAM's outputs live, for algorithms such as RTAB-Map, ORB-SLAM3, Kimera or
slam_toolbox running against the Webots simulation (webots_ros2) with use_sim_time:=true.

    ros2 run --prefix 'python3' ... or simply:
    SLAM_BENCH_RUN_DIR=/path/run python3 adapters/ros2_bridge.py --robot bstem1 --algorithm RTAB-Map \
        --pose-topic /rtabmap/odom --pose-type odometry --map-topic /map --map-period 30

Pose types: odometry (nav_msgs/Odometry), pose (geometry_msgs/PoseStamped),
pose_cov (geometry_msgs/PoseWithCovarianceStamped). The map is an OccupancyGrid saved every
--map-period seconds of simulation time. Message timestamps (simulation time) are used.
CPU/RAM of the SLAM processes: add their names to the supervisor's `process_patterns`.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from benchlog import BenchLog

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy


def yaw_of(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


def stamp(msg):
    return msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9


class Bridge(Node):
    def __init__(self, args):
        super().__init__('slam_bench_bridge_%s' % args.robot)
        self.args = args
        self.log = BenchLog(args.robot, args.algorithm, frame=args.frame, resource_period=0)
        self.initialized = False
        self.last_map = -1e9
        if args.pose_type == 'odometry':
            from nav_msgs.msg import Odometry as PoseMsg
        elif args.pose_type == 'pose':
            from geometry_msgs.msg import PoseStamped as PoseMsg
        else:
            from geometry_msgs.msg import PoseWithCovarianceStamped as PoseMsg
        self.create_subscription(PoseMsg, args.pose_topic, self.on_pose, 50)
        if args.map_topic:
            from nav_msgs.msg import OccupancyGrid
            qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
            self.create_subscription(OccupancyGrid, args.map_topic, self.on_map, qos)

    def on_pose(self, msg):
        t = stamp(msg)
        pose = msg.pose.pose if hasattr(msg.pose, 'pose') else msg.pose
        cov = None
        if hasattr(msg.pose, 'covariance'):
            c = np.array(msg.pose.covariance).reshape(6, 6)
            cov = c[np.ix_([0, 1, 5], [0, 1, 5])].tolist()
        if not self.initialized:
            self.log.initialized(t)
            self.initialized = True
        self.log.pose(t, pose.position.x, pose.position.y, yaw_of(pose.orientation), z=pose.position.z, covariance=cov)

    def on_map(self, msg):
        t = stamp(msg)
        self.log.map_update(t)
        if t-self.last_map < self.args.map_period:
            return
        self.last_map = t
        info = msg.info
        grid = np.array(msg.data, np.int16).reshape(info.height, info.width)
        if abs(yaw_of(info.origin.orientation)) > 1e-3:
            self.get_logger().warn('rotated map origins are not supported; map skipped')
            return
        self.log.map(t, grid, info.resolution, (info.origin.position.x, info.origin.position.y), kind=self.args.map_kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--robot', required=True)
    ap.add_argument('--algorithm', required=True)
    ap.add_argument('--frame', default='map')
    ap.add_argument('--pose-topic', required=True)
    ap.add_argument('--pose-type', choices=['odometry', 'pose', 'pose_cov'], default='odometry')
    ap.add_argument('--map-topic', default=None)
    ap.add_argument('--map-period', type=float, default=30.)
    ap.add_argument('--map-kind', default='local', choices=['local', 'merged'])
    args, ros_args = ap.parse_known_args()
    rclpy.init(args=ros_args)
    node = Bridge(args)
    try:
        rclpy.spin(node)
    finally:
        node.log.close()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
