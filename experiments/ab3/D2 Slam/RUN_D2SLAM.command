#!/bin/bash
set -e
cd "$(dirname "$0")"
D2_BENCH_PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
"$D2_BENCH_PY" run_d2slam.py "$@"
