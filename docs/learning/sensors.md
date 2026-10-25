# Sensors, odometry and uncertainty

Encoders measure wheel rotation. Inertial sensors measure acceleration and
angular rate. Cameras provide image observations; stereo/RGB-D adds depth under
a calibration model. No sensor directly provides an infallible global pose.

Noise, bias and missing data differ. Independent zero-mean noise may average
down; fixed scale bias accumulates systematically. Time offsets and wrong
extrinsics can mimic estimator failure even when matching works.

## Propagating a belief

For a locally Gaussian belief with covariance $P$ and motion Jacobian $F$,

$$
P^- = FPF^T + GQG^T.
$$

$Q$ describes process uncertainty; $G$ maps it into the state. This equation does
not guarantee that covariance matches physical error: model assumptions,
linearization and calibration still matter.

The [reference EKF](../../algorithms/ekf-slam/ekf.py) uses explicit standard
deviations in metres and radians. Its Webots input combines noisy wheel travel
with relative range/bearing marker observations. Known camera-recognition IDs
isolate estimation from arbitrary-identity data association.

Try the same seed at several noise levels in **Odometry drift**. Reset replays
the same model, distinguishing a parameter change from a new random realization.
An experimental performance distribution still requires repeated trials and
representative data.
