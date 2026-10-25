# Multi-robot frames, communication and map merging

Robots can observe the same scene while using different map origins and headings.
Shared identities or verified correspondences constrain the relative transform.
Sharing coordinates without their frames does not create a coherent map.

## Rigid alignment

For matched planar points $p_i,q_i$, fit rotation and translation with fixed scale:

$$
\min_{R\in SO(2),t}\sum_i\|Rp_i+t-q_i\|^2.
$$

The Playground centers both sets and recovers rotation from dot/cross sums.
At least two distinct shared points are needed in this known-correspondence
model. Noise and observation count change the fit. The corrected map comes from
the estimated transform, not a snap to a reference path.

Actual merging also needs association checks, uncertainty, overlap management and
consistent graph updates. Known initial docking priors already supply shared
frame information and should be disclosed in experiments.

## Communication

Centralized servers, shared ROS masters and isolated peers make different
assumptions. Count descriptors, keyframes, retries and protocol bytes; test delay,
loss and queues. All peer routes must pass through the simulated radio for a
communication-limited comparison.

The browser lesson is an alignment model. The two-robot EKF Webots example runs
independent maps in declared starting frames. Research collaboration is developed
through [DOOR-SLAM](../../algorithms/door-slam/README.md),
[D²SLAM](../../algorithms/d2slam/README.md) and [Swarm-SLAM](../../algorithms/swarm-slam/README.md).
