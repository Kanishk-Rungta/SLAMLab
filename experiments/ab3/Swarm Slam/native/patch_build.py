"""Build-copy clock, validity and telemetry adapters for pinned Swarm-SLAM."""
from pathlib import Path
import sys


def replace(path, old, new, expected=1):
    data = path.read_text()
    if data.count(old) != expected:
        raise RuntimeError('Pinned Swarm source differs from its adapter: ' + str(path))
    path.write_text(data.replace(old, new))


def patch(root):
    root = Path(root)
    for name in ['src/front_end/map_manager.cpp', 'src/back_end/decentralized_pgo.cpp']:
        path = root / name
        text = path.read_text()
        if 'node_->create_wall_timer(' not in text:
            raise RuntimeError('Expected native timer sites were not found')
        text = '#include <rclcpp/create_timer.hpp>\n#include <sstream>\n' + text
        text = text.replace('node_->create_wall_timer(',
            'rclcpp::create_timer(node_->get_node_base_interface(), node_->get_node_timers_interface(), node_->get_clock(),')
        path.write_text(text)
    replace(root / 'cslam/loop_closure_detection_node.py', 'clock=Clock()', 'clock=self.get_clock()')
    replace(root / 'cslam/global_descriptor_loop_closure_detection.py', 'clock=Clock()', 'clock=self.node.get_clock()', 2)
    # Full pretrained CosPlace state is loaded immediately afterwards. Avoid a
    # redundant ImageNet download inside an isolated runtime container.
    network = root / 'cslam/vpr/cosplace_utils/network.py'
    data = network.read_text()
    if data.count('pretrained=True') != 5:
        raise RuntimeError('Unexpected native CosPlace backbone initialization')
    network.write_text(data.replace('pretrained=True', 'pretrained=False'))
    header = root / 'include/cslam/back_end/decentralized_pgo.h'
    replace(header, '        gtsam::LabeledSymbol latest_local_symbol_;',
        '        gtsam::LabeledSymbol latest_local_symbol_;\n'
        '        builtin_interfaces::msg::Time ab3_latest_keyframe_stamp_;\n'
        '        rclcpp::Publisher<std_msgs::msg::String>::SharedPtr ab3_events_;')
    cpp = root / 'src/back_end/decentralized_pgo.cpp'
    replace(cpp, '  node_->get_parameter("robot_id", robot_id_);',
        '  node_->get_parameter("robot_id", robot_id_);\n'
        '  origin_robot_id_ = robot_id_;\n'
        '  ab3_events_ = node_->create_publisher<std_msgs::msg::String>("/ab3/events", 100);')
    replace(cpp, '  latest_local_pose_ = current_estimate;',
        '  ab3_latest_keyframe_stamp_ = msg->odom.header.stamp;\n  latest_local_pose_ = current_estimate;')
    replace(cpp, 'void DecentralizedPGO::broadcast_tf_callback()\n{',
        'void DecentralizedPGO::broadcast_tf_callback()\n{\n  if (odometry_pose_estimates_->empty()) return;')
    replace(cpp, '  pose_msg.header.stamp = now;', '  pose_msg.header.stamp = ab3_latest_keyframe_stamp_;')
    data = cpp.read_text()
    begin = data.index('DecentralizedPGO::optimize(')
    end = data.index('void DecentralizedPGO::start_optimization()', begin)
    method = data[begin:end]
    method = method.replace('  gtsam::Values result;',
        '  const auto ab3_started = std::chrono::steady_clock::now();\n  gtsam::Values result;', 1)
    if method.count('  return result;') != 1:
        raise RuntimeError('Unexpected native optimizer return structure')
    method = method.replace('  return result;', '''  const double ab3_duration = std::chrono::duration<double>(std::chrono::steady_clock::now() - ab3_started).count();
  std::ostringstream ab3_json; ab3_json.precision(16);
  ab3_json << "{\\\"kind\\\":\\\"optimization\\\",\\\"t\\\":" << node_->get_clock()->now().seconds()
           << ",\\\"duration_s\\\":" << ab3_duration << ",\\\"solver\\\":\\\"native_swarm_gnc\\\"}";
  std_msgs::msg::String ab3_message; ab3_message.data = ab3_json.str(); ab3_events_->publish(ab3_message);
  return result;''')
    cpp.write_text(data[:begin] + method + data[end:])
    # These targets consume external interfaces; a target must not depend on itself.
    cmake = root / 'CMakeLists.txt'
    data = cmake.read_text()
    for name in ('map_manager', 'pose_graph_manager'):
        begin = data.index('add_dependencies(' + name)
        end = data.index(')', begin) + 1
        data = data[:begin] + data[end:]
    cmake.write_text(data)


if __name__ == '__main__':
    patch(sys.argv[1])
