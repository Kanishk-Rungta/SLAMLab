#!/bin/bash
# prepare for Kimera Multi, with the benchmark Python environment (.venv).
set -euo pipefail
cd "$(dirname "$0")"
PY="$(bash "../Standard Environment/tools/bench_python.sh" "$(cd .. && pwd)")"
"$PY" "run_kimera_multi.py" --prepare-only "$@" || true
echo
read -r -p "Press Enter to close this window ..." || true
