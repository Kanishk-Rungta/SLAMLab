#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f runs/LATEST.txt ]; then echo "No D2SLAM run found."; exit 1; fi
D2_LAST_RUN="$(tr -d '\r\n' < runs/LATEST.txt)"
if [ ! -d "$D2_LAST_RUN/benchmark" ]; then echo "Latest run folder is missing."; exit 1; fi
touch "$D2_LAST_RUN/STOP" "$D2_LAST_RUN/benchmark/STOP"
echo "Stop requested for $D2_LAST_RUN"
