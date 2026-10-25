#!/bin/bash
# prepare for Swarm Slam, with the benchmark Python environment (.venv).
set -euo pipefail
cd "$(dirname "$0")"
PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
exec "$PY" "run_swarm_slam.py" --prepare-only "$@"
