# Recorded example exports

These bundles come from actual Webots R2025a landmark EKF-SLAM runs on 2026-10-25:
one robot and two independent robots, each for 30 simulated seconds. Each
`manifest.json` records source-run identity, configuration, estimator/controller
digests, original export hash and reproduction command.

Visualization coordinates/checkpoints are rounded to six decimals. Python metric
summaries remain unrounded. Display decimation retains recorded timestamps and
does not synthesize measurements.

Starting body poses are configured priors. Landmark coordinates begin unknown.
A separate supervisor records reference poses/landmarks. The controlled sensor
uses camera-recognition identities plus range/bearing noise; it is distinct from
feature-based research implementations.

Website builds copy these reviewed bundles into static assets. Educational
Playground models are labeled separately from the measured recordings.
