"""Apply the documented CPU, timing and read-only telemetry adapters to a BUILD COPY.

Never modify algorithm/D2SLAM. No change to D2VINS estimation, the feature
tracker, loop detection, PCM or D2PGO mathematics. Every replacement asserts its
exact upstream context (SOURCE_AND_ADAPTERS.md lists each one and why).
"""
import argparse
from pathlib import Path


def replace(path, before, after, count=1):
    # Byte-exact (LF) on every host: text mode would write CRLF on Windows.
    text = path.read_bytes().decode('utf-8')
    if text.count(before) != count:
        raise RuntimeError('Unexpected upstream context: %s (%r, found %d, expected %d)'
                           % (path, before[:70], text.count(before), count))
    path.write_bytes(text.replace(before, after).encode('utf-8'))


# Read-only telemetry for the benchmark bridge: which local frame the native
# pipeline has finished, so the simulation waits for it instead of letting
# the host CPU speed decide which frames are dropped.
TELEMETRY_CALLBACK = '''  void benchTimerCallback(const ros::WallTimerEvent &) {
    int loop_queue_size = 0, loop_busy = 0;
    {
      std::lock_guard<std::mutex> guard(loop_lock);
      loop_queue_size = loop_queue.size();
      loop_busy = bench_loop_busy_;
    }
    std::ostringstream out;
    out.precision(17);
    {
      std::lock_guard<std::mutex> guard(bench_lock_);
      out << "{\\"frontend\\":" << bench_frontend_stamp_
          << ",\\"forwarded\\":" << (bench_frontend_forwarded_ ? "true" : "false")
          << ",\\"backend\\":" << bench_backend_stamp_
          << ",\\"keyframe\\":" << (bench_backend_keyframe_ ? "true" : "false")
          << ",\\"frame_id\\":" << bench_backend_frame_id_
          << ",\\"accepted\\":" << (bench_backend_ret_ ? "true" : "false");
    }
    out << ",\\"initialized\\":" << (estimator->isInitialized() ? "true" : "false")
        << ",\\"loop_queue\\":" << loop_queue_size
        << ",\\"loop_busy\\":" << loop_busy << "}";
    std_msgs::String msg;
    msg.data = out.str();
    bench_pub_.publish(msg);
  }

'''


def patch(root):
    frontend = root / 'd2frontend'
    # A. CPU CNN adapter: build upstream's own ONNX SuperPoint/MobileNetVLAD
    # classes (TensorRT/CUDA otherwise required) on the ONNX Runtime CPU provider.
    cmake = frontend / 'CMakeLists.txt'
    replace(cmake, 'if (NOT USE_CUDA)\n  # This is because TORCH',
            'if (D2_CPU_CNN)\n  # Benchmark adapter: CPU libtorch for upstream SuperPointONNX descriptors.\n'
            '  add_definitions(-DD2_CPU_CNN)\nelseif (NOT USE_CUDA)\n  # This is because TORCH')
    replace(cmake, '  target_link_libraries(loop_cnn\n    opencv_dnn\n    opengv\n    onnxruntime\n  )',
            '  target_link_libraries(loop_cnn\n    opencv_dnn\n    opengv\n    onnxruntime\n    ${TORCH_LIBRARIES}\n  )')
    onnx = frontend / 'include/d2frontend/CNN/onnx_generic.h'
    replace(onnx, '        OrtCUDAProviderOptions options;',
            '#ifdef USE_CUDA  // adapter: the CPU package has no CUDA provider\n        OrtCUDAProviderOptions options;')
    replace(onnx, '        session_options.AppendExecutionProvider_CUDA(options);\n',
            '        session_options.AppendExecutionProvider_CUDA(options);\n#endif\n')
    cpu_guard = '#if defined(USE_CUDA) || defined(D2_CPU_CNN)'
    replace(frontend / 'src/CNN/superpoint_common.cpp', '#ifdef USE_CUDA\n  TicToc tic;\n  cv::Mat kpt_mat',
            cpu_guard + '\n  TicToc tic;\n  cv::Mat kpt_mat')
    replace(frontend / 'src/CNN/superpoint_onnx.cpp', '#ifdef USE_CUDA\n  TicToc tic;\n  cv::Mat _input;',
            cpu_guard + '\n  TicToc tic;\n  cv::Mat _input;')
    # Upstream's commented-out ONNX construction, enabled verbatim for the CPU build.
    replace(frontend / 'src/loop_cam.cpp', '#else\n    // netvlad_onnx = new MobileNetVLADONNX(\n',
            '#elif defined(D2_CPU_CNN)\n'
            '    // Benchmark adapter: upstream\'s commented ONNX construction, CPU provider.\n'
            '    netvlad_onnx = new MobileNetVLADONNX(\n'
            '        config.netvlad_model, img_width, img_height, config.cnn_enable_tensorrt,\n'
            '        config.cnn_enable_tensorrt_fp16, config.cnn_enable_tensorrt_int8,\n'
            '        config.netvlad_int8_calib_table_name);\n'
            '    superpoint_ptr = new SuperPointONNX(\n'
            '        config.superpoint_model, ((int)(params->feature_min_dist / 2)),\n'
            '        config.pca_comp, config.pca_mean, img_width, img_height,\n'
            '        config.superpoint_thres, config.superpoint_max_num,\n'
            '        config.cnn_enable_tensorrt, config.cnn_enable_tensorrt_fp16,\n'
            '        config.cnn_enable_tensorrt_int8,\n'
            '        config.superpoint_int8_calib_table_name);\n'
            '#else\n    // netvlad_onnx = new MobileNetVLADONNX(\n')
    # The ROS parameters those constructors read (commented out upstream).
    params = frontend / 'src/d2frontend_params.cpp'
    replace(params,
            '  // nh.param<double>("superpoint_thres", loopcamconfig->superpoint_thres, 0.012);\n'
            '  // nh.param<std::string>("pca_comp_path", loopcamconfig->pca_comp, "");\n'
            '  // nh.param<std::string>("pca_mean_path", loopcamconfig->pca_mean, "");\n'
            '  // nh.param<std::string>("pca_netvlad", pca_netvlad, "");\n'
            '  // nh.param<std::string>("superpoint_model_path",\n'
            '  //                       loopcamconfig->superpoint_model, "");\n',
            '  // Benchmark adapter: upstream lines re-enabled for the CPU ONNX classes.\n'
            '  nh.param<double>("superpoint_thres", loopcamconfig->superpoint_thres, 0.012);\n'
            '  nh.param<std::string>("pca_comp_path", loopcamconfig->pca_comp, "");\n'
            '  nh.param<std::string>("pca_mean_path", loopcamconfig->pca_mean, "");\n'
            '  nh.param<std::string>("pca_netvlad", pca_netvlad, "");\n'
            '  nh.param<std::string>("superpoint_model_path",\n'
            '                        loopcamconfig->superpoint_model, "");\n')

    # B. Timing adapters. Thread pacing uses wall time (identical to sim time on
    # a robot), so it keeps running while the bridge holds the simulation for a
    # frame; and a frame the bridge waits for is queued instead of discarded.
    header = frontend / 'include/d2frontend/d2frontend.h'
    replace(header, 'std::unique_ptr<ros::Rate>', 'std::unique_ptr<ros::WallRate>', count=3)
    source = frontend / 'src/d2frontend.cpp'
    replace(source, 'std::make_unique<ros::Rate>(', 'std::make_unique<ros::WallRate>(', count=3)
    replace(source,
            '  if (stereo_frame_buffer_lock_.try_lock()) {\n'
            '    stereo_frame_q_.push(std::make_shared<StereoFrame>(_l->header.stamp, _l->image, _r->image,',
            '  stereo_frame_buffer_lock_.lock();  // adapter: queue, never drop, a held frame\n'
            '  {\n'
            '    stereo_frame_q_.push(std::make_shared<StereoFrame>(_l->header.stamp, _l->image, _r->image,')
    node = root / 'd2vins/src/d2vins_node.cpp'
    replace(node, 'std::unique_ptr<ros::Rate>', 'std::unique_ptr<ros::WallRate>', count=3)
    replace(node, 'std::make_unique<ros::Rate>(', 'std::make_unique<ros::WallRate>(', count=3)

    # The upstream consensus solver takes ownership of residual callbacks on
    # its final internal Ceres step, then deletes them again on the next reset.
    # Keep ownership with the shared residual objects used by D2SLAM.
    consensus = root / 'd2common/src/solver/ConsensusSolver.cpp'
    replace(consensus,
            '    if (i != config.max_steps - 1) {\n'
            '      problem_options.cost_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '      problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '      problem_options.local_parameterization_ownership =\n'
            '          ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '      problem_options.manifold_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '    }\n',
            '    problem_options.cost_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '    problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '    problem_options.local_parameterization_ownership =\n'
            '        ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '    problem_options.manifold_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n')

    arock = root / 'd2common/src/solver/ARock.cpp'
    replace(arock,
            '  if (!final_iter) {\n'
            '    problem_options.cost_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '    problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '  }\n',
            '  problem_options.cost_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '  problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '  problem_options.local_parameterization_ownership =\n'
            '      ceres::DO_NOT_TAKE_OWNERSHIP;\n'
            '  problem_options.manifold_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;\n')

    # A truncated or reordered radio fragment must not turn a remote descriptor
    # header's advertised length into an out-of-bounds read.
    frontend_types = root / 'd2common/include/d2common/d2frontend_types.h'
    replace(frontend_types,
            '            for (int i = 0; i < desc.landmark_num; i++) {\n'
            '                desc0.segment(i * 32, 32).normalize();\n'
            '            }\n'
            '        } else {\n'
            '            landmark_descriptor = desc.landmark_descriptor;\n'
            '        }\n'
            '        if (desc.header.image_desc_size_int8 > 0) {\n'
            '            image_desc.resize(desc.header.image_desc_size_int8);\n'
            '            Eigen::Map<VectorXf> gdesc(image_desc.data(), image_desc.size());\n',
            '            const int complete_landmarks =\n'
            '                desc.landmark_descriptor_int8.size() / 32;\n'
            '            for (int i = 0; i < desc.landmark_num &&\n'
            '                        i < complete_landmarks; i++) {\n'
            '                desc0.segment(i * 32, 32).normalize();\n'
            '            }\n'
            '        } else {\n'
            '            landmark_descriptor = desc.landmark_descriptor;\n'
            '        }\n'
            '        if (desc.header.image_desc_size_int8 > 0) {\n'
            '            const size_t image_desc_size =\n'
            '                desc.header.image_desc_size_int8 <\n'
            '                        desc.header.image_desc_int8.size()\n'
            '                    ? desc.header.image_desc_size_int8\n'
            '                    : desc.header.image_desc_int8.size();\n'
            '            if (image_desc_size != desc.header.image_desc_size_int8) {\n'
            '                SPDLOG_WARN("[D2SLAM] Truncated image descriptor: header {} bytes, received {} bytes",\n'
            '                             desc.header.image_desc_size_int8,\n'
            '                             desc.header.image_desc_int8.size());\n'
            '            }\n'
            '            image_desc.resize(image_desc_size);\n'
            '            Eigen::Map<VectorXf> gdesc(image_desc.data(), image_desc.size());\n')

    # C. Read-only telemetry: stamps of finished local frames and the loop queue.
    replace(header, '    int32_t visual_frame_size_ = 2;\n',
            '    int32_t visual_frame_size_ = 2;\n'
            '    // Benchmark telemetry (read-only).\n'
            '    std::mutex bench_lock_;\n'
            '    double bench_frontend_stamp_ = -1;\n'
            '    bool bench_frontend_forwarded_ = false;\n'
            '    int bench_loop_busy_ = 0;\n')
    replace(source, '  if (vframearry.send_to_backend) {\n    backendFrameCallback(vframearry);\n  }\n}\n',
            '  if (vframearry.send_to_backend) {\n    backendFrameCallback(vframearry);\n  }\n'
            '  {\n    lock_guard bench_guard(bench_lock_);\n'
            '    bench_frontend_forwarded_ = vframearry.send_to_backend;\n'
            '    bench_frontend_stamp_ = vframearry.stamp;\n  }\n}\n')
    replace(source, '        loop_queue.pop();\n      }\n',
            '        loop_queue.pop();\n        bench_loop_busy_ = 1;\n      }\n')
    replace(source, '      loop_detector->processImageArray(vframearry);\n',
            '      loop_detector->processImageArray(vframearry);\n'
            '      {\n        lock_guard guard(loop_lock);\n        bench_loop_busy_ = 0;\n      }\n')
    replace(node, '#include "sensor_msgs/Imu.h"\n',
            '#include "sensor_msgs/Imu.h"\n#include <std_msgs/String.h>\n#include <sstream>\n')
    replace(node, '  std::map<int, std::pair<int, Swarm::Pose>> vins_poses;\n',
            '  std::map<int, std::pair<int, Swarm::Pose>> vins_poses;\n'
            '  // Benchmark telemetry (read-only).\n'
            '  double bench_backend_stamp_ = -1;\n'
            '  bool bench_backend_keyframe_ = false;\n'
            '  bool bench_backend_ret_ = false;\n'
            '  int64_t bench_backend_frame_id_ = -1;\n'
            '  ros::Publisher bench_pub_;\n'
            '  ros::WallTimer bench_timer_;\n')
    replace(node, '          updateOutModuleSldWinAndLandmarkDB();\n          need_solve = true;\n',
            '          updateOutModuleSldWinAndLandmarkDB();\n          need_solve = true;\n'
            '          {\n'
            '            std::lock_guard<std::mutex> bench_guard(bench_lock_);\n'
            '            bench_backend_keyframe_ = viokf.is_keyframe;\n'
            '            bench_backend_ret_ = ret;\n'
            '            bench_backend_frame_id_ = viokf.frame_id;\n'
            '            bench_backend_stamp_ = viokf.stamp;\n'
            '          }\n')
    replace(node, '  void Init(ros::NodeHandle &nh) {\n', TELEMETRY_CALLBACK + '  void Init(ros::NodeHandle &nh) {\n')
    replace(node,
            '        nh.advertise<swarm_msgs::ImageArrayDescriptor>("image_array_desc", 1);\n',
            '        nh.advertise<swarm_msgs::ImageArrayDescriptor>("image_array_desc", 1);\n'
            '    bench_pub_ = nh.advertise<std_msgs::String>("benchmark_state", 10);\n'
            '    bench_timer_ = nh.createWallTimer(ros::WallDuration(0.005),\n'
            '                                      &D2VINSNode::benchTimerCallback, this);\n')
    # Duration of each D2PGO solve (the optimisation-time metric).
    pgo = root / 'd2pgo/src/d2pgo_node.cpp'
    replace(pgo, '#include "swarm_msgs/swarm_fused.h"\n',
            '#include "swarm_msgs/swarm_fused.h"\n#include <std_msgs/String.h>\n#include <chrono>\n#include <sstream>\n')
    replace(pgo, '  ros::Publisher drone_traj_pub, swarm_fused_pub;\n',
            '  ros::Publisher drone_traj_pub, swarm_fused_pub;\n  ros::Publisher bench_pub_;  // benchmark telemetry\n')
    replace(pgo,
            '    bool succ;\n    if (multi) {\n',
            '    auto bench_start = std::chrono::steady_clock::now();\n    bool succ;\n    if (multi) {\n')
    replace(pgo,
            '      succ = pgo->solve_single();\n    }\n    if (succ) {\n',
            '      succ = pgo->solve_single();\n    }\n'
            '    {\n'
            '      std::ostringstream out;\n'
            '      out.precision(17);\n'
            '      out << "{\\"duration\\":" << std::chrono::duration<double>(\n'
            '                 std::chrono::steady_clock::now() - bench_start).count()\n'
            '          << ",\\"success\\":" << (succ ? "true" : "false")\n'
            '          << ",\\"t\\":" << ros::Time::now().toSec() << "}";\n'
            '      std_msgs::String bench_msg;\n'
            '      bench_msg.data = out.str();\n'
            '      bench_pub_.publish(bench_msg);\n'
            '    }\n'
            '    if (succ) {\n')
    replace(pgo,
            '        _nh->advertise<swarm_msgs::swarm_fused>("swarm_fused", 1000);\n',
            '        _nh->advertise<swarm_msgs::swarm_fused>("swarm_fused", 1000);\n'
            '    bench_pub_ = _nh->advertise<std_msgs::String>("benchmark_solve", 100);\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('build_copy', type=Path)
    args = parser.parse_args()
    patch(args.build_copy)
    print('Applied the documented D2SLAM benchmark adapters to', args.build_copy)
