#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f runs/LATEST.txt ]; then echo "No original DOOR-SLAM run found."; exit 1; fi
DOOR_LAST_RUN="$(tr -d '\r\n' < runs/LATEST.txt)"
bash RUN_DOOR_SLAM_ORIGINAL.command --evaluate-run "$DOOR_LAST_RUN"
