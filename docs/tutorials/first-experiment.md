# First reproducible experiment

## 1. Install and inspect

Follow [installation](../getting-started/installation.md), then run
`python -B tools/slam.py doctor d2slam` to see the difference between available
adapter code, local sources and native execution dependencies. A false native
validation flag is expected until that exact stack has been exercised.

## 2. Prepare the environment

From the repository root:

```sh
python -B tools/run_webots_demo.py --prepare-only --robots 1
```

This derives a world from the fixed AB3 standard and installs ignored local
controller wrappers using the current Python interpreter. It does not launch a
native SLAM system or modify the standard world. The run world changes robot
count/controller only. The original fingerprint can be checked with:

```sh
python -B "experiments/ab3/Standard Environment/tools/standard_manifest.py"
```

## 3. Run and examine wheel odometry

```sh
python -B tools/run_webots_demo.py --robots 1 --seconds 10
```

With Webots R2025a installed, the simulated robot drives a short arc. A separate
supervisor records its true pose and ends the run. Locate the printed
`outputs/webots-demo-*/` directory. Read its log, completion receipt,
`bstem1_estimate.csv` and `bstem1_groundtruth.csv`. This is odometry, not mapping.
A second robot can be added with `--robots 2`; this example does not share maps.

## 4. Understand trajectory evaluation

Run the [five-pose analytic example](../../examples/trajectory-evaluation/README.md).
Its metadata explicitly identifies it as synthetic and its known x-offset is
0.1 m. Inspect the plot axes, retained pose count and JSON alignment setting.
Repeat with a new output path and `--alignment se2`; the rigid fit can remove
the constant offset. That is why aligned ATE and absolute world-frame accuracy
answer different questions.

For your real CSV recording, copy the sample metadata into your ignored output
folder, replace every field with actual algorithm/version/environment/input
provenance and use `kind: simulation_measurement`. Record the known-dock prior,
robot count, selected robot and settings. Supply your estimate/reference paths
to the same evaluator. Never relabel a fixture as a recording.

## 5. Prepare a native research system

Choose a [supported adapter](../../algorithms/README.md), restore its pinned
sources explicitly and run its prepare command. DOOR-SLAM and D?SLAM preparation
have been exercised locally; native builds have not. Build inside the documented
container environment on a Docker host. Start with two robots for 120 seconds,
check native initialization and graph-corrected output, then exercise radio
loss/outage scenarios. Preserve failures and shutdown evidence.

A successful source preparation, Docker build or nonempty CSV does not by itself
establish correct native mapping. Compare only compatible experiments, retaining
sensor settings, alignment, coverage and failure counts.
