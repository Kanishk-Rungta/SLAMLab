"""Apply documented clock, calibration-API and read-only telemetry adapters to a BUILD COPY.

Never modify algorithm/DOOR-SLAM. No PCM, optimizer, feature matcher, NetVLAD or
geometric verification changes. Every replacement asserts its upstream context.
"""
import argparse
from pathlib import Path


def replace(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise RuntimeError('Unexpected upstream context: %s (%r)' % (path, before[:70]))
    path.write_text(text.replace(before, after))


def patch(root):
    source = root / 'tx2-setup'
    buzz = source / 'robust_pose_graph_optimization/buzz_slam/src'
    utils = buzz / 'generic_robot/utils/buzz_utils.h'
    replace(utils, '#include <pthread.h>', '#include <pthread.h>\n#include <ros/ros.h>')
    replace(utils, 'usleep(100000);', 'ros::Rate(10).sleep(); // adapter: simulation clock, original 10 Hz')
    geom = source / 'slam_front_end/ros_ws/src/multi_robot_separators/src/stereoCamGeometricTools.cpp'
    replace(geom, 'listener.waitForTransform("frame_id",', 'listener.waitForTransform(frame_id,')
    header = buzz / 'slam/buzz_slam.h'
    replace(header, '#include <list>', '#include <list>\n#include <sstream>')
    # Read the OPTIMIZED initial-guess store, not robot_local_map_, which retains
    # raw odometry for PCM. This hook does not write to any estimator state.
    telemetry = '''
   std::string BenchmarkState() const {
      std::ostringstream out;
      out.precision(17);
      out << "{\\"state\\":" << static_cast<int>(optimizer_state_)
          << ",\\"keyframes\\":" << number_of_poses_ << ",\\"graph\\":[";
      bool first = true;
      for (const auto& item : *poses_initial_guess_) {
         gtsam::Symbol symbol(item.key);
         if (symbol.chr() != robot_id_char_) continue;
         auto p = poses_initial_guess_->at<gtsam::Pose3>(item.key);
         if (!first) out << ",";
         first = false;
         out << "[" << symbol.index() << "," << p.x() << "," << p.y() << "," << p.rotation().yaw() << "]";
      }
      out << "],\\"loops\\":[";
      first = true;
      for (const auto& factor : *local_pose_graph_no_filtering_) {
         auto between = boost::dynamic_pointer_cast<gtsam::BetweenFactor<gtsam::Pose3> >(factor);
         if (!between) continue;
         gtsam::Symbol a(between->key1()), b(between->key2());
         if (a.chr() == b.chr()) continue;
         auto pair = std::make_pair(between->key1(), between->key2());
         auto reverse_pair = std::make_pair(between->key2(), between->key1());
         bool accepted = accepted_keys_.count(pair) != 0 || accepted_keys_.count(reverse_pair) != 0;
         bool rejected = rejected_keys_.count(pair) != 0 || rejected_keys_.count(reverse_pair) != 0;
         if (!accepted && !rejected) continue;
         if (!first) out << ",";
         first = false;
         auto p = between->measured();
         out << "[" << static_cast<int>(a.chr()-97) << "," << a.index() << ","
             << static_cast<int>(b.chr()-97) << "," << b.index() << ","
             << (accepted ? "true" : "false") << "," << p.x() << "," << p.y() << "," << p.rotation().yaw() << "]";
      }
      out << "]}";
      return out.str();
   }
'''
    replace(header, '   int GetNumberOfPoses();', '   int GetNumberOfPoses();\n'+telemetry)
    main = buzz / 'generic_robot/buzz_generic_robot_slam_ros.cpp'
    replace(main, '#include <std_srvs/Empty.h>', '#include <std_srvs/Empty.h>\n#include <std_msgs/String.h>')
    replace(main, '      /* Main loop */', '''      ros::Publisher bench_pub = nh_.advertise<std_msgs::String>("benchmark_state", 1);
      /* Main loop */''')
    replace(main, '         ros::spinOnce();', '''         ros::spinOnce();
         std_msgs::String telemetry;
         telemetry.data = buzz_slam::BuzzSLAMSingleton::GetInstance().GetBuzzSLAM<buzz_slam::BuzzSLAMRos>(VM->robot)->BenchmarkState();
         bench_pub.publish(telemetry);''')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('build_copy', type=Path)
    args = parser.parse_args()
    patch(args.build_copy)
