#!/bin/bash
set -Eeo pipefail
trap 'status=$?; printf "Native build failed at line %s (exit %s): %s\n" "$LINENO" "$status" "$BASH_COMMAND" >&2; exit "$status"' ERR
BUILD_JOBS="${BUILD_JOBS:-1}"
if ! [[ "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo 'BUILD_JOBS must be a positive integer' >&2
    exit 1
fi

# Ensure CMake 3.10 knows about Boost::timer imported target
if ! grep -q "Boost::timer" /usr/share/cmake-3.10/Modules/FindBoost.cmake 2>/dev/null; then
cat << 'EOF' >> /usr/share/cmake-3.10/Modules/FindBoost.cmake
if(NOT TARGET Boost::timer)
  find_file(BOOST_TIMER_SO libboost_timer.so PATHS /usr/lib/x86_64-linux-gnu /usr/lib)
  if(BOOST_TIMER_SO)
    add_library(Boost::timer UNKNOWN IMPORTED)
    set_target_properties(Boost::timer PROPERTIES
      IMPORTED_LINK_INTERFACE_LANGUAGES "CXX"
      IMPORTED_LOCATION "${BOOST_TIMER_SO}")
  endif()
endif()
EOF
fi

build_library() {
    local source_dir="$1"
    local build_dir="$2"
    shift 2
    echo "Building $source_dir with $BUILD_JOBS job(s)"
    mkdir -p "$build_dir"
    (cd "$build_dir"; cmake "$source_dir" -DCMAKE_BUILD_TYPE=Release "$@")
    cmake --build "$build_dir" -- -j"$BUILD_JOBS"
    cmake --build "$build_dir" --target install -- -j"$BUILD_JOBS"
    ldconfig
}

build_library /opt/deps/gtsam /opt/deps/gtsam/build \
    -DGTSAM_BUILD_TESTS=OFF -DGTSAM_BUILD_EXAMPLES_ALWAYS=OFF \
    -DGTSAM_BUILD_WITH_MARCH_NATIVE=OFF -DGTSAM_USE_SYSTEM_EIGEN=ON -DGTSAM_BUILD_UNSTABLE=ON

sed -i -E '/testing/d' /opt/deps/buzz/src/CMakeLists.txt 2>/dev/null || true
sed -i -E '/testing/d' /opt/deps/buzz/CMakeLists.txt 2>/dev/null || true
rm -rf /opt/deps/buzz/src/testing /opt/deps/buzz/testing
mkdir -p /opt/deps/buzz/build
(cd /opt/deps/buzz/build; cmake /opt/deps/buzz/src -DCMAKE_BUILD_TYPE=Release)
cmake --build /opt/deps/buzz/build -- -j"$BUILD_JOBS"
cmake --build /opt/deps/buzz/build --target install -- -j"$BUILD_JOBS"
ldconfig

build_library /opt/deps/rtabmap /opt/deps/rtabmap/build \
    -DWITH_GTSAM=OFF \
    -DWITH_OPENNI=OFF -DWITH_OPENNI2=OFF -DWITH_FREENECT=OFF \
    -DWITH_FREENECT2=OFF -DWITH_REALSENSE=OFF -DWITH_REALSENSE2=OFF

source /opt/ros/melodic/setup.bash
DOOR_RTAB_CONFIG="$(find /usr/local -name RTABMapConfig.cmake -print -quit)"
if [ -z "$DOOR_RTAB_CONFIG" ]; then echo 'Pinned RTAB-Map CMake config missing'; exit 1; fi
DOOR_RTAB_DIR="$(dirname "$DOOR_RTAB_CONFIG")"

mkdir -p /opt/rtab_ws/src
ln -s /opt/deps/rtabmap_ros /opt/rtab_ws/src/rtabmap_ros
(cd /opt/rtab_ws; catkin_make -j"$BUILD_JOBS" -l"$BUILD_JOBS" -DCATKIN_ENABLE_TESTING=OFF -DRTABMap_DIR="$DOOR_RTAB_DIR")

# Remove tests and unneeded GtsamTesting includes from robust_distributed_mapper
sed -i -E '/add_subdirectory\(tests\)/d' \
    /opt/source/tx2-setup/robust_pose_graph_optimization/buzz_slam/robust_distributed_mapper/cpp/CMakeLists.txt 2>/dev/null || true
sed -i -E '/GtsamTesting/d' \
    /opt/source/tx2-setup/robust_pose_graph_optimization/buzz_slam/robust_distributed_mapper/cpp/CMakeLists.txt 2>/dev/null || true
sed -i -E '/GtsamTesting/d' \
    /opt/source/tx2-setup/robust_pose_graph_optimization/buzz_slam/src/CMakeLists.txt 2>/dev/null || true
find /usr/local -name "GtsamTesting.cmake" -exec sed -i '1i macro(gtsam_apply_build_flags)\nendmacro()' {} + 2>/dev/null || true

build_library /opt/source/tx2-setup/robust_pose_graph_optimization/buzz_slam/robust_distributed_mapper/cpp /opt/mapper_build

sed -i 's|HINTS /root/multi_robot_SLAM_separators/ros_ws/devel/lib|HINTS /opt/door_ws/devel/lib /root/multi_robot_SLAM_separators/ros_ws/devel/lib|' \
    /opt/source/tx2-setup/robust_pose_graph_optimization/buzz_slam/src/CMakeLists.txt 2>/dev/null || true

# Strip roslaunch test checks which fail when testing is disabled or catkin_run_tests_target is undefined
find /opt/source -name CMakeLists.txt -exec sed -i -E '/roslaunch_add_file_check/d' {} + 2>/dev/null || true

mkdir -p /opt/door_ws/src
ln -s /opt/source/tx2-setup/slam_front_end/ros_ws/src/multi_robot_separators /opt/door_ws/src/multi_robot_separators
ln -s /opt/deps/netvlad /opt/door_ws/src/multi_robot_separators/scripts/netvlad_tf_open
source /opt/rtab_ws/devel/setup.bash
(cd /opt/door_ws; catkin_make -j"$BUILD_JOBS" -l"$BUILD_JOBS" -DCATKIN_ENABLE_TESTING=OFF -DRTABMap_DIR="$DOOR_RTAB_DIR")

mkdir -p /root/multi_robot_SLAM_separators/ros_ws
ln -s /opt/door_ws/devel /root/multi_robot_SLAM_separators/ros_ws/devel
ln -s /opt/source/tx2-setup/robust_pose_graph_optimization /opt/door_ws/src/robust_distributed_slam_module
(cd /opt/door_ws; catkin_make -j"$BUILD_JOBS" -l"$BUILD_JOBS" -DCATKIN_ENABLE_TESTING=OFF -DRTABMap_DIR="$DOOR_RTAB_DIR")

mkdir -p /opt/door_ws/devel/lib/robust_distributed_slam_module
NODE_BIN="$(find /opt/door_ws /usr/local -name generic_robot_buzz_slam_node -type f -print -quit 2>/dev/null || true)"
if [ -n "$NODE_BIN" ] && [ ! -f /opt/door_ws/devel/lib/robust_distributed_slam_module/generic_robot_buzz_slam_node ]; then
    cp "$NODE_BIN" /opt/door_ws/devel/lib/robust_distributed_slam_module/generic_robot_buzz_slam_node
fi
test -x /opt/door_ws/devel/lib/robust_distributed_slam_module/generic_robot_buzz_slam_node

chmod +x /opt/door_ws/src/multi_robot_separators/scripts/find_separators.py
