# Your first complete SLAM experiment

Follow [installation](../getting-started/installation.md). The landmark lab uses
Python/NumPy and Webots R2025a without a native ROS stack.

```sh
python -B tools/slam.py list
python -B tools/slam.py info ekf-slam
python -B tools/slam.py run ekf-slam --config examples/landmark-slam/config.json --output outputs/first-slam
```

The robot drives a bounded arc, reads encoders and observes labeled markers
through front/rear simulated cameras. It starts with no landmark coordinates.
Repeated relative observations jointly correct trajectory and map. A separate
supervisor records reference poses.

## Inspect and replay

Open `evaluation/robot-1/map.png` and `metrics.json` within your output directory.
`robot-1/map.json` contains estimated landmarks and covariance; `sensors.jsonl`
stores measured wheel increments and range/bearing observations.

```sh
python -B tools/replay_landmark_slam.py outputs/first-slam --output outputs/replayed-map.json
python -B tools/slam.py evaluate outputs/first-slam --output outputs/first-slam-evaluation
python -B tools/slam.py visualize outputs/first-slam --output outputs/first-slam-viewer.json
```

Open the exported JSON in **Visualization Studio** for trajectories, headings,
map checkpoints and Python-computed metrics. Files stay in your browser.

Try `--robots 2` with a new output directory. The estimators have separate sensor
streams and maps, with known configured starting poses. They do not communicate;
the **Multi-robot alignment** lesson introduces sharing and relative frames.
