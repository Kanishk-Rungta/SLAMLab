#!/bin/bash
set -eo pipefail
source /opt/ros/melodic/setup.bash
source /opt/rtab_ws/devel/setup.bash
source /opt/door_ws/devel/setup.bash
export LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH:-}"
exec python3 /opt/benchmark/native/start_robot.py
