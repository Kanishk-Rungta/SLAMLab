# Visual odometry, stereo and RGB-D SLAM

Visual odometry estimates camera motion from images. Visual SLAM also maintains
a map and uses revisits to correct drift. Backend correction can change earlier
poses, making output timestamps and pose provenance important.

## Depth and scale

Rectified stereo uses focal length $f$, baseline $b$ and disparity $d$ to recover
$Z=fb/d$. Small disparity makes far-object depth sensitive to pixel error. RGB-D
supplies a depth channel with its own unit scale, missing values and calibration.

Monocular image motion generally leaves scale ambiguous. Inertial measurements,
known geometry or explicit priors can change observability. Fitting scale offline
is an evaluation decision, distinct from providing metric information online.

## Tracking and correction

Tracking associates observations across frames. Triangulation initializes 3D
landmarks. Local optimization refines poses/points; place recognition proposes
loops; geometric checks and backend optimization reconcile revisits. Low texture,
repetition, dynamics and poor synchronization can break different stages.

Explore [ORB-SLAM2](../../algorithms/orb-slam2/README.md),
[RTAB-Map](../../algorithms/rtabmap/README.md) and
[Kimera-Multi](../../algorithms/kimera-multi/README.md). Their sensor contracts and
dependency environments differ. The algorithm explorer links to their native
setup guides and original research.
