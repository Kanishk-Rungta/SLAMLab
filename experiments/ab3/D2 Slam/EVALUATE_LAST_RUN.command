#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f runs/LATEST.txt ]; then echo "No D2SLAM run found."; exit 1; fi
D2_LAST_RUN="$(tr -d '\r\n' < runs/LATEST.txt)"
bash RUN_D2SLAM.command --evaluate-run "$D2_LAST_RUN"
