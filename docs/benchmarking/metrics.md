# Trajectory metric definitions and reproducibility

The [focused evaluator](../../benchmarks/evaluation/trajectory.py) reuses the
imported AB3 SE(2) alignment, relative-transform and statistics utilities.
It evaluates **planar body poses**. It does not silently project arbitrary 3D
trajectories. Use a 3D tool such as [evo](https://github.com/MichaelGrupp/evo) when
roll, pitch, variable height or Sim(3) alignment is required.

## Inputs and association

CSV header must be `timestamp,x,y,yaw`: decimal seconds, metres and radians.
Timestamps are parsed to integer nanoseconds, strictly increasing and unique.
Poses must be finite and use compatible frames, clock and body reference point.
Camera trajectories must first be converted with the actual extrinsic transform.
The TUM converter accepts eight-column unit-quaternion poses only when roll/pitch
are zero and height is constant. It discards that constant height explicitly.

Association is chronological greedy nearest, monotone and one-to-one, within
`--max-difference` (default 0.02 s). It does not interpolate or optimize the total
matching count. Both estimated and reference retained fractions and maximum time
offset are exported. Sparse coverage and startup exclusions can bias accuracy.

## Metrics

| Metric | Definition | Units and limitations |
| --- | --- | --- |
| Position ATE | Euclidean distance between associated estimated/reference x,y; RMSE = sqrt(mean(error?)) | metres; reports matched interval only |
| Orientation error | Absolute wrapped estimated minus reference yaw | degrees; separate from position ATE |
| Translation RPE | Translation norm of `inverse(reference_delta) * estimate_delta` | metres over approximately `--rpe-delta` seconds |
| Rotation RPE | Absolute wrapped angular residual of those relative transforms | degrees over the selected interval |
| Reference distance | Sum of distances between associated reference positions | metres; omits unassociated path detail |
| Endpoint error / distance | Last associated ATE divided by associated reference path length ?100 | percent; unavailable for zero distance; not a general drift-rate estimate |

RPE uses the nearest later associated estimated timestamp to the requested
interval, within `--rpe-tolerance` (default 0.05 s). Windows may overlap; report
pair count and actual evaluation settings. No valid RPE pair means `null`, not
zero error. Reference time differences can differ by association offsets.

Alignment `none` preserves the supplied world frames. Optional `se2` fits one
rigid planar rotation/translation over the associated path and rotates yaw
consistently. Scale is always 1. Stationary position alignment is rejected.
An offline fit uses future information and can remove a constant offset; it is
not online localization accuracy. Monocular arbitrary-scale output requires a
separately defined evaluation policy rather than pretending it is metric.

## Execution and outputs

Run the [synthetic tutorial](../../examples/trajectory-evaluation/README.md).
For your recording, provide experiment metadata: algorithm/version, environment,
robot count, dataset provenance, experiment date (null if unknown), dependencies,
configuration and kind (`synthetic_fixture`, `simulation_measurement` or
`recorded_measurement`). A unique output directory contains `metrics.json`,
`summary.csv`, `associated.csv` and a standalone `trajectory.png`. JSON records
SHA-256 hashes of both inputs and metadata, evaluator versions and all settings.

Compare reports with:

```sh
python -B benchmarks/evaluation/compare_reports.py outputs/trial-a/metrics.json outputs/trial-b/metrics.json --output outputs/comparison
```

The comparison rejects differing dataset/reference hashes, environment, robot
count, configuration, kind, association/RPE settings or alignment. It exposes
coverage differences and does not infer a ranking. Also review estimator inputs,
compute budgets, trajectory duration, failure cases and independent repetitions;
matching metadata alone cannot prove a fair experiment.

## Wider legacy evaluator

The imported recorder/evaluator also includes map/loop/tracking/resource/network
modules with nine passing synthetic regression tests. This does not establish
scientific validity for every reported field. Missing raw maps/events/resources
must remain unavailable. Its configured energy model is not measured electrical
power. Peak sampled process RSS is not complete container memory. The focused
CLI calculates none of these wider metrics and lists them as unavailable.

No historical SLAM rankings or raw recordings are published. The committed
sample is a mathematical fixture; actual short Webots odometry outputs stay
in ignored local storage and are not native SLAM measurements.
