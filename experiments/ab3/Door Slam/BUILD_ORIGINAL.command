#!/bin/bash
set -e
cd "$(dirname "$0")"
bash RUN_DOOR_SLAM_ORIGINAL.command --build-only "$@"
