# D²SLAM

**Status: implemented adapter, native execution not verified in SLAMLab.**
The source project records preparation-level checks; no native benchmark result
for this adapter is imported or inferred. This is an integration of the
[upstream research system](https://github.com/HKUST-Aerial-Robotics/D2SLAM), not a new SLAMLab algorithm.

## Algorithm and attribution

Collaborative visual-inertial estimation (D2VINS), visual loop detection and distributed graph optimization (D2PGO); learned descriptors aid place recognition.

Hao Xu, Peize Liu, Xinyi Chen and Shaojie Shen; D²SLAM, IEEE Transactions on Robotics 40, 3445–3464 (2024), DOI 10.1109/TRO.2024.3422003. [Primary paper](https://arxiv.org/abs/2211.01538). See upstream for the complete publication and implementation details.
A frontend processes sensor observations; the backend corrects a graph of poses.
Inter-robot loops are constraints between observations from different robots.

## Inputs and requirements

Rectified stereo and simulated three-axis IMU; explicit body/optical transforms. The [shared scenario](../../docs/simulations/ab3.md) defines rates,
calibration and seeded errors. Ground truth is available only to evaluation.

ROS 1 Noetic, Ceres, LCM, libtorch, FAISS and ONNX Runtime CPU in the prepared Docker recipe. Native stacks remain isolated. Use Python 3.10+ for host tools and Webots
R2025a. Docker with Linux containers is required for native execution. These are
x86-64 recipes; ARM emulation and resource requirements have not been measured.
Start with two robots and a 120-second trial rather than assuming ten-robot
capacity. Do not install historical native dependencies into the host Python.

## Setup and execution

Run commands from the SLAMLab root after the [Python setup](../../docs/getting-started/installation.md).
The pinned main revision is `4c33871083e4ae97b97973eb5bd88dc6735359d7`; transitive locks live beside the
[preserved integration](../../experiments/ab3/D2%20Slam/README.md).

```sh
python -B tools/slam.py doctor d2slam
python -B tools/setup/fetch_original_sources.py d2slam
python -B tools/slam.py prepare d2slam --robots 2
python -B tools/slam.py build d2slam --robots 2
python -B tools/slam.py run d2slam --robots 2 --seconds 120 --gui
```

Source restoration uses a filtered sparse Git fetch to omit unlocked model blobs.
An exact previously verified cache can be used offline with
`--local-archive PATH_TO_ORIGINAL_ZIP`. The optional `--transport archive` path
has a 64 MiB cap; a D²SLAM full-archive trial exceeded it and wrote no output.
Source restoration is an explicit network operation; inspect notices before
redistributing fetched files. Models may require additional downloads during
preparation/build. No model or native snapshot is tracked in Git. The common
interface checks source presence and Docker before launching dependent work.
Preparation may create ignored configuration/output files and download missing
transitive dependencies; it does not establish a successful native build.

## Integration boundary and outputs

The team adapter uses CPU inference, simulation-clock coordination, corrected native output and LCM messages fragmented through the shared radio. Build-copy patches are separate from estimator snapshots.

Expected outputs after a successful native run: unique `runs/` directory beneath
the preserved algorithm folder, native logs, timestamped pose/benchmark records,
world fingerprint and evaluation summaries. These are expectations, not
published measured results. Missing pose initialization, stale corrections or
bypassed radio routes are failures even when a process exits successfully.

## Validation and troubleshooting

CNN weights/PCA assets have separate terms and checksums. Native build, initialized tracking, D2PGO corrections and communication behavior are unverified here. Retain native build logs, exact dependency/image IDs, sensor contract,
run metadata and failure evidence. Test baseline tracking and actual backend
corrections before trying `--scenario comm_failure`. Validate every inter-robot
route and output timestamp. Never replace a missing backend with synthetic poses.

The local [validation report](../../docs/validation-report.md) lists checks
actually executed. The [source inventory](../../docs/implementation-inventory.md)
separates historical source evidence from SLAMLab execution.
