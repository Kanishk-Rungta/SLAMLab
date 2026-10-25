#!/bin/bash
# stop for Kimera Multi, with the benchmark Python environment (.venv).
set -euo pipefail
cd "$(dirname "$0")"
PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
"$PY" "run_kimera_multi.py" --stop "$@" || true
