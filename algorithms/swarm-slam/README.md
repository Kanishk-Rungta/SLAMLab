# Swarm-SLAM

**Status: implemented adapter, native execution not verified in SLAMLab.**
The source project records preparation-level checks; no native benchmark result
for this adapter is imported or inferred. This is an integration of the
[upstream research system](https://github.com/MISTLab/Swarm-SLAM), not a new SLAMLab algorithm.

## Algorithm and attribution

Sparse decentralized collaboration with prioritized inter-robot loop detection and pose-graph optimization; upstream supports stereo, RGB-D and lidar.

Pierre-Yves Lajoie and Giovanni Beltrame; RA-L 2024, DOI 10.1109/LRA.2023.3333742. See upstream for the complete publication and implementation details.
A frontend processes sensor observations; the backend corrects a graph of poses.
Inter-robot loops are constraints between observations from different robots.

## Inputs and requirements

This adapter selects stereo imagery, calibration and native odometry; other upstream modalities are not supplied. The [shared scenario](../../docs/simulations/ab3.md) defines rates,
calibration and seeded errors. Ground truth is available only to evaluation.

ROS 2 Humble, RTAB-Map stereo visual odometry, GTSAM, cslam/interfaces/experiments and a descriptor model. Native stacks remain isolated. Use Python 3.10+ for host tools and Webots
R2025a. Docker with Linux containers is required for native execution. These are
x86-64 recipes; ARM emulation and resource requirements have not been measured.
Start with two robots and a 120-second trial rather than assuming ten-robot
capacity. Do not install historical native dependencies into the host Python.

## Setup and execution

Run commands from the SLAMLab root after the [Python setup](../../docs/getting-started/installation.md).
The pinned main revision is `af17c4b71432f750571ea699a0beccfbe9004872`; transitive locks live beside the
[preserved integration](../../experiments/ab3/Swarm%20Slam/README.md).

```sh
python -B tools/slam.py doctor swarm-slam
python -B "experiments/ab3/Live Integrations/restore_sources.py" "experiments/ab3/Swarm Slam"
python -B tools/slam.py prepare swarm-slam --robots 2
python -B tools/slam.py build swarm-slam --robots 2
python -B tools/slam.py run swarm-slam --robots 2 --seconds 120 --gui
```

Source restoration is an explicit network operation; inspect notices before
redistributing fetched files. Models may require additional downloads during
preparation/build. No model or native snapshot is tracked in Git. The common
interface checks source presence and Docker before launching dependent work.
Preparation may create ignored configuration/output files and download missing
transitive dependencies; it does not establish a successful native build.

## Integration boundary and outputs

The team adapter composes backend graph corrections with native VO and forwards native inter-robot messages through the standard radio. Raw RTAB-Map odometry is not labeled corrected Swarm output.

Expected outputs after a successful native run: unique `runs/` directory beneath
the preserved algorithm folder, native logs, timestamped pose/benchmark records,
world fingerprint and evaluation summaries. These are expectations, not
published measured results. Missing pose initialization, stale corrections or
bypassed radio routes are failures even when a process exits successfully.

## Validation and troubleshooting

Descriptor weights, ROS 2 route coverage, graph correction and real two-robot map behavior need native validation. Retain native build logs, exact dependency/image IDs, sensor contract,
run metadata and failure evidence. Test baseline tracking and actual backend
corrections before trying `--scenario comm_failure`. Validate every inter-robot
route and output timestamp. Never replace a missing backend with synthetic poses.

The local [validation report](../../docs/validation-report.md) lists checks
actually executed. The [source inventory](../../docs/implementation-inventory.md)
separates historical source evidence from SLAMLab execution.
