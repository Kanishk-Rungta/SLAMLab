#!/bin/bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source /opt/ws/install/setup.bash
export PYTHONPATH="/opt/ab3:${PYTHONPATH:-}"
exec python3 /opt/ab3/native_supervisor.py
