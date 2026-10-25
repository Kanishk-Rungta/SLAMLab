# SLAM fundamentals

## What is SLAM?

Simultaneous localization and mapping estimates a moving sensor's trajectory
and a representation of its surroundings from observations. A robot may know
how far its wheels turned while still being uncertain about its actual position.
SLAM uses repeated observations of environmental structure to connect motion
and map estimates. A trajectory plot alone does not prove a map was built.

## Mapping versus localization

Localization estimates pose relative to a known reference. Mapping estimates
environmental structure from known or estimated poses. SLAM couples both:
incorrect motion can bend a map, while an incorrect correspondence can move an
otherwise good trajectory. The global position/orientation can remain arbitrary
unless an external reference or prior fixes it. This gauge freedom explains why
offline alignment must be disclosed when comparing trajectories.

## Odometry and uncertainty

Odometry integrates local changes from encoders, images or inertial sensors.
Small bias accumulates over time. A covariance describes uncertainty under a
particular model; it is not a guarantee that the real error stays inside it.
Wheel slip, camera calibration errors, ambiguous texture and time offsets can
violate that model. The AB3 odometry example integrates noisy wheel travel and
uses a declared initial dock. It has no map-based drift correction.

## Front ends and back ends

A frontend turns sensor observations into motion or landmark constraints:
feature tracks, stereo correspondences, relative transforms and candidate loop
closures. The backend estimates a trajectory/map satisfying those constraints
under an error model. Frontend failure can produce plausible but wrong matches;
a backend may reduce a numerical residual while reinforcing those mistakes.
Tracking, native backend corrections and complete output coverage therefore
need separate validation.

## Feature detection and matching

A feature detector finds repeatable image locations, such as textured corners.
A descriptor encodes nearby appearance. Matching compares descriptors and then
checks geometric consistency. Similar-looking doors may produce appearance
matches across different places. Geometric verification and robust rejection
reduce this perceptual aliasing; a high descriptor score is not sufficient.
Repeated texture, moving objects and little parallax can still cause failure.

## Visual, stereo and RGB-D SLAM

Monocular SLAM infers structure from motion and generally needs a scale policy.
Stereo uses a known baseline between synchronized cameras to infer depth; small
disparity produces large depth uncertainty. RGB-D supplies depth measurements
with a device-specific scale, valid range and missing values. Visual-inertial
systems combine camera constraints with inertial motion, gravity and bias
estimation. They need calibrated extrinsics and time synchronization. Changing
the sensor stack can change what is observable and invalidates naive rankings.

## Loop closure

A loop closure recognizes a previously observed place and introduces a new
constraint between distant parts of a trajectory. Correct loops can reduce
accumulated drift. False loops can seriously corrupt a map. Distinguish a
candidate descriptor match, a geometrically verified constraint, a robust-filter
acceptance and an applied backend correction. Counting only one of these stages
without naming it makes loop statistics ambiguous.

## Pose graphs and optimization

A pose graph represents robot/keyframe poses as nodes and measured relative
poses as edges. Odometry usually links nearby timestamps; loops connect revisits
or different robots. Optimization minimizes weighted constraint residuals.
Weights should reflect noise assumptions, and robust losses limit some outlier
influence. Results depend on initialization, data association and convergence.
Local optimization and global graph updates may run at different rates, so a
current raw pose and a last optimized keyframe are not interchangeable outputs.

## Multi-robot SLAM

Robots can share observations or map constraints to estimate a common frame.
A centralized server, a shared ROS master and isolated peer-to-peer runtimes
impose different communication/compute assumptions. Decentralized operation
requires discovering neighbors, identifying messages, handling delays/duplicates
and rejecting bad inter-robot constraints. Broadcast bytes and retries count
toward the network budget. Known initial docks already provide shared-frame
information and must be declared in an experiment.

The AB3 native adapters aim to route all peer traffic through the simulated
radio model. Passing transport unit tests does not establish that every actual
ROS route follows it. Validate collaboration by observing real backend
constraints/corrections and failure recovery, rather than merely running two
independent estimators in one world.

Continue with the [practical walkthrough](../tutorials/first-experiment.md),
[algorithm guides](../../algorithms/README.md) and
[research references](../references/README.md).
