# Landmark EKF-SLAM

Estimate a robot trajectory and an initially unknown landmark map from wheel
motion and relative range/bearing observations. This original educational
implementation runs on ordinary Python/NumPy development machines and Webots
R2025a. It introduces no ROS or Docker dependency.

## Run

From the repository root, after installing `requirements.txt`:

```sh
python -B tools/slam.py info ekf-slam
python -B tools/slam.py run ekf-slam --config examples/landmark-slam/config.json --output outputs/my-landmark-run
python -B tools/slam.py evaluate outputs/my-landmark-run --output outputs/my-landmark-evaluation
python -B tools/slam.py visualize outputs/my-landmark-run --output outputs/my-landmark-replay.json
```

Use a new output path on each run. `--robots 2` selects two independent
estimators with distinct identifiers. Both use declared known starting poses;
this experiment does not implement collaborative communication. The browser
multi-robot lesson separately teaches alignment and sharing.

## Estimator

The joint state is `mu = [x, y, theta, m1x, m1y, ...]`. Prediction integrates
wheel travel with a midpoint planar motion model and propagates the complete
covariance, including robot–landmark cross-correlation. New landmarks are
initialized using the inverse range/bearing model and its state/noise Jacobians.
Existing observations use the forward model
`h(mu) = [sqrt(dx² + dy²), atan2(dy, dx) - theta]`.

Updates wrap angular residuals, apply a Mahalanobis innovation gate, and use
Joseph covariance updates for numerical stability. Reobserving a landmark
corrects both the robot and map through their joint covariance. The estimator
has no world-map input or Supervisor API. The initial pose anchors the gauge.

## Sensor contract

Webots front/rear cameras produce simulated recognition observations of labeled
markers. Their camera-relative planar positions become range and bearing, with
seeded Gaussian measurement noise. Marker model strings provide known identity;
their global positions are never supplied to the estimator. This controlled
sensor is not an image-feature detector or a general visual SLAM frontend.
See the [R2025a camera recognition reference](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/camera.md#camera-recognition-object).

Wheel encoders include a fixed scale bias and seeded noise. Robot frames are
x-forward, y-left, z-up; the rear camera's planar rotation is explicitly applied.
A separate supervisor records evaluation truth and stops the bounded experiment.

## Outputs and reproducibility

The [example guide](../../examples/landmark-slam/README.md) defines the output
layout, JSON replay format, recorded sensor replay, and actual execution evidence.
CPU and step times are measured controller values and vary by machine. No
network or whole-simulator memory metric is synthesized.

The assumptions are static uniquely identified landmarks, planar motion,
approximately Gaussian local errors, and a sufficiently accurate linearization.
Known identities simplify association; the gate cannot recover arbitrary wrong
identities. Dense covariance scales quadratically with landmark count, so this
implementation deliberately targets small teaching environments.

The formulation follows standard EKF-SLAM material described in
[Probabilistic Robotics](https://mitpress.mit.edu/9780262201629/probabilistic-robotics/), by Sebastian
Thrun, Wolfram Burgard and Dieter Fox. The code here is an original SLAMLab
implementation, not copied from the book or a research algorithm repository.
