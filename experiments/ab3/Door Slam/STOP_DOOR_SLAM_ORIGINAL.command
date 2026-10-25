#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f runs/LATEST.txt ]; then echo "No original DOOR-SLAM run found."; exit 1; fi
DOOR_LAST_RUN="$(tr -d '\r\n' < runs/LATEST.txt)"
if [ ! -d "$DOOR_LAST_RUN/benchmark" ]; then echo "Latest run folder is missing."; exit 1; fi
touch "$DOOR_LAST_RUN/STOP" "$DOOR_LAST_RUN/benchmark/STOP"
echo "Stop requested for $DOOR_LAST_RUN"
