# Webots landmark SLAM experiment

This self-contained marker laboratory connects actual Webots wheel/camera
observations to a joint robot/landmark EKF. It creates an estimated trajectory,
landmark map, recorded sensor stream, evaluation reports and a browser replay.
The original AB3 worlds and native research recipes remain separate examples.

## Requirements and configuration

Use Python 3.10–3.12 with the repository requirements and Webots R2025a.
[config.json](config.json) defines seed, duration, one/two robots, initial poses,
wheel geometry, motion and observation noise in SI units. The marker coordinates
exist only in the generated world and evaluation recorder, not estimator inputs.

```sh
python -B tools/run_reference_slam.py --config examples/landmark-slam/config.json --output outputs/landmark-example
python -B tools/run_webots_demo.py --example landmark-slam --world landmark-lab --robots 2 --seconds 30 --output outputs/two-landmark-robots
```

Nondefault simulator installations can use `--webots-home`. A wall timeout stops
only the process tree launched for this experiment. `--prepare-only` creates a
portable local Webots project without starting it.

## Recorded results

One-robot 8-second and two-robot 30-second R2025a runs completed during platform
development. Each robot discovered 12 landmarks and repeatedly corrected its
joint pose/map state. These are controlled educational marker experiments;
research system comparisons require their own matched sensor/data protocols.

## Result layout

```text
experiment.json                identity, settings, versions and reproduction
config.json                    exact run configuration
robot-1/estimate.csv            EKF body trajectory: seconds, metres, radians
robot-1/odometry.csv            wheel-only baseline using the same input
robot-1/sensors.jsonl           relative observations and measured wheel deltas
robot-1/states.jsonl            map/pose checkpoints for playback
robot-1/map.json                estimated landmarks, covariance and measured timing
robot-1-reference.csv           separate supervisor ground truth
reference_landmarks.json        evaluation-only landmark positions
evaluation/robot-1/             metrics.json, summary.csv, trajectory.png, map.png
viewer.json                    compact static viewer bundle
execution.log                  simulator stdout/stderr
```

Robot 2 has the same namespaced outputs when selected. The result exporter
copies Python-computed metric summaries into static JSON; the website does not
recalculate benchmark scores. Local trajectory/map uploads stay in the browser.

## Replay without the simulator

```sh
python -B tools/replay_landmark_slam.py outputs/landmark-example --robot 1 --output outputs/replayed-map.json
```

Replay consumes only configuration, wheel deltas and relative observations.
For the recorded first smoke run it reproduced the live pose/landmark state
exactly, without reading either reference file.
