#!/bin/bash
# PID 1 of a ROS 1 robot container (Noetic or Melodic). CATKIN_WS: the algorithm workspace (default /opt/ws).
set -eo pipefail
for setup in /opt/ros/noetic/setup.bash /opt/ros/melodic/setup.bash; do
    if [ -f "$setup" ]; then source "$setup"; break; fi
done
WS="${CATKIN_WS:-/opt/ws}"
if [ -f "$WS/devel/setup.bash" ]; then source "$WS/devel/setup.bash"; fi
if [ -f "$WS/install/setup.bash" ]; then source "$WS/install/setup.bash"; fi
# Melodic's rospy is pure Python and also runs under Python 3 (the gateway is Python 3).
if [ -d /opt/ros/melodic/lib/python2.7/dist-packages ]; then
    export PYTHONPATH="${PYTHONPATH:-}:/opt/ros/melodic/lib/python2.7/dist-packages:$WS/devel/lib/python2.7/dist-packages"
fi
export PYTHONPATH="/opt/ab3:${PYTHONPATH:-}"
export ROS_MASTER_URI="${ROS_MASTER_URI:-http://localhost:11311}" ROS_HOSTNAME="${ROS_HOSTNAME:-localhost}"
exec python3 /opt/ab3/native_supervisor.py
