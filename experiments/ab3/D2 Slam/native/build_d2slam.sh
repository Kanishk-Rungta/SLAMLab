#!/bin/bash
# Build the patched copy of the pinned D2SLAM sources (CPU, no CUDA/TensorRT).
set -eo pipefail
JOBS="${1:-2}"
source /opt/ros/noetic/setup.bash
mkdir -p /root/swarm_ws/src
cd /root/swarm_ws/src
python3 /opt/benchmark/native/fetch_pinned.py swarm_msgs swarm_msgs
python3 /opt/benchmark/native/fetch_pinned.py vision_opencv vision_opencv
# The original stays in /opt/source-original; only this build copy is adapted.
cp -a /opt/source-original /root/swarm_ws/src/D2SLAM
python3 /opt/benchmark/tools/patch_runtime.py /root/swarm_ws/src/D2SLAM
cd /root/swarm_ws
catkin config --extend /opt/ros/noetic \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DUSE_CUDA=OFF -DD2_CPU_CNN=ON
catkin build --no-status -p 1 -j "$JOBS" d2vins d2pgo d2comm
