# RTAB-Map

**Status: documentation/reference only as a standalone SLAMLab integration.**
No independent runnable port was found in the source checkout. Related settings
or dependencies are not evidence that this system was separately benchmarked.

## Overview and authors

Graph-based mapping with appearance-based loop detection and memory management. Supports visual/depth and lidar configurations; accepted loop constraints are optimized with odometry in the map graph.

Mathieu Labbé and François Michaud; Journal of Field Robotics 2019, 36(2), 416–446. See the official project bibliography. [Official upstream](https://github.com/introlab/rtabmap).

## Requirements, installation and execution

Select an upstream version and compatible native environment before building.
Record a full commit, dependency versions and dataset license. Follow the
upstream installation and sensor-specific examples; no SLAMLab execution command
is claimed. ORB-SLAM2 requires a compatible C++11/Pangolin/OpenCV/Eigen stack and
is principally single-robot. RTAB-Map offers standalone and ROS interfaces;
multiple sessions do not automatically establish decentralized radio operation.

Inputs require synchronized imagery and calibrated camera geometry; stereo
requires baseline/extrinsics and RGB-D requires a declared depth scale. Expected
upstream outputs include camera trajectories and maps/databases, depending on
configuration. Pose frames and formats must be checked before evaluation.

## SLAMLab relationship and acceptance gates

ORB-family settings appear in CCM/other adapters. RTAB-Map is used as visual
odometry/dependency in the imported DOOR/Swarm recipes and has an unverified ROS
logging bridge. Neither relationship constitutes a standalone integration.

A future port must add pinned source restoration, a sensor/transport adapter,
calibration, native build and initialized tracking tests, corrected output,
shutdown behavior and [benchmark provenance](../../docs/benchmarking/metrics.md).
Read [third-party notices](../../THIRD_PARTY_NOTICES.md): ORB-SLAM2 uses GPLv3;
RTAB-Map's BSD terms and optional dependencies must be inspected at the selected
revision. Native builds and sample datasets are not shipped here.
