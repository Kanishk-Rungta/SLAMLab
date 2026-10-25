#!/bin/bash
set -e
cd "$(dirname "$0")"
DOOR_BENCH_PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
"$DOOR_BENCH_PY" run_door_slam_original.py "$@"
