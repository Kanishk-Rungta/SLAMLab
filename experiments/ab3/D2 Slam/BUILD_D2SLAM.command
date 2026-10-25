#!/bin/bash
set -e
cd "$(dirname "$0")"
bash RUN_D2SLAM.command --build-only "$@"
