# Kimera-Multi

**Status: implemented adapter, native execution not verified in SLAMLab.**
The source project records preparation-level checks; no native benchmark result
for this adapter is imported or inferred. This is an integration of the
[upstream research system](https://github.com/MIT-SPARK/Kimera-Multi), not a new SLAMLab algorithm.

## Algorithm and attribution

Visual-inertial local estimation and metric-semantic mapping; distributed place recognition, robust pose-graph optimization and local mesh correction.

Yun Chang, Yulun Tian, Jonathan P. How and Luca Carlone; ICRA 2021, DOI 10.1109/ICRA48506.2021.9561090. See upstream for the complete publication and implementation details.
A frontend processes sensor observations; the backend corrects a graph of poses.
Inter-robot loops are constraints between observations from different robots.

## Inputs and requirements

Rectified stereo images plus three-axis simulated IMU and their extrinsics/timestamps. The [shared scenario](../../docs/simulations/ab3.md) defines rates,
calibration and seeded errors. Ground truth is available only to evaluation.

ROS 1 Noetic on Ubuntu 20.04, Kimera-VIO, Kimera-Distributed, DPGO/PGMO, GTSAM and catkin workspace dependencies. Native stacks remain isolated. Use Python 3.10+ for host tools and Webots
R2025a. Docker with Linux containers is required for native execution. These are
x86-64 recipes; ARM emulation and resource requirements have not been measured.
Start with two robots and a 120-second trial rather than assuming ten-robot
capacity. Do not install historical native dependencies into the host Python.

## Setup and execution

Run commands from the SLAMLab root after the [Python setup](../../docs/getting-started/installation.md).
The pinned main revision is `814bfe279b5e7b86be2650af49f122502b84b738`; transitive locks live beside the
[preserved integration](../../experiments/ab3/Kimera%20Multi/README.md).

```sh
python -B tools/slam.py doctor kimera-multi
python -B "experiments/ab3/Live Integrations/restore_sources.py" "experiments/ab3/Kimera Multi"
python -B tools/slam.py prepare kimera-multi --robots 2
python -B tools/slam.py build kimera-multi --robots 2
python -B tools/slam.py run kimera-multi --robots 2 --seconds 120 --gui
```

Source restoration is an explicit network operation; inspect notices before
redistributing fetched files. Models may require additional downloads during
preparation/build. No model or native snapshot is tracked in Git. The common
interface checks source presence and Docker before launching dependent work.
Preparation may create ignored configuration/output files and download missing
transitive dependencies; it does not establish a successful native build.

## Integration boundary and outputs

The team adapter supplies AB3 camera/IMU configuration, native output translation and isolated radio forwarding. Semantic inputs are not provided by this scenario; no semantic reconstruction claim is made.

Expected outputs after a successful native run: unique `runs/` directory beneath
the preserved algorithm folder, native logs, timestamped pose/benchmark records,
world fingerprint and evaluation summaries. These are expectations, not
published measured results. Missing pose initialization, stale corrections or
bypassed radio routes are failures even when a process exits successfully.

## Validation and troubleshooting

Upstream single-master examples do not establish intermittent-radio operation. Transitive native dependencies, low simulated sensor rates, backend output and peer isolation require validation. Retain native build logs, exact dependency/image IDs, sensor contract,
run metadata and failure evidence. Test baseline tracking and actual backend
corrections before trying `--scenario comm_failure`. Validate every inter-robot
route and output timestamp. Never replace a missing backend with synthetic poses.

The local [validation report](../../docs/validation-report.md) lists checks
actually executed. The [source inventory](../../docs/implementation-inventory.md)
separates historical source evidence from SLAMLab execution.
