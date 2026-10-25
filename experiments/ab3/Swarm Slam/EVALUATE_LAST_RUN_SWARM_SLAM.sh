#!/bin/bash
# evaluate last run for Swarm Slam, with the benchmark Python environment (.venv).
set -euo pipefail
cd "$(dirname "$0")"
PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
exec "$PY" "run_swarm_slam.py" --evaluate-last-run "$@"
