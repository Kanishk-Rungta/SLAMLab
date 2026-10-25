# Implementation inventory

Audit date: 2026-10-25 (Asia/Kolkata). Source HEAD: `7425aec9f58fccb609b5cb788785851a4dc3a682`.

## Audit method and evidence

Inspected the complete non-Git file tree (1858 files), root/archive layouts, README and setup/validation updates, locks, package manifests, CMake and Docker recipes, worlds/PROTOs, controllers, evaluation code/tests and result filenames. No source tests were executed. Git status was clean. Missing extracted native trees are distinguished from lock metadata that describes them. No symlinks were followed.

| Component | Source path (relative to source root) | Purpose/language | Dependencies / ROS | Classification | Evidence and integration action |
| --- | --- | --- | --- | --- | --- |
| DOOR-SLAM | `Benchmark/Door Slam` | Native SLAM integration; Python/C++/shell | ROS Melodic; TensorFlow 1; GTSAM; Buzz | Implemented but not verified | Adapters and source archive exist; no native build/run established. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| Kimera-Multi | `Benchmark/Kimera Multi` | Native SLAM integration; Python/C++/shell | ROS Noetic; Kimera-VIO/DPGO/PGMO workspace | Implemented but not verified | Later implementation update supersedes older missing-adapter table; native validation absent. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| D?SLAM | `Benchmark/D2 Slam` | Native SLAM integration; Python/C++/shell | ROS Noetic; ONNX Runtime; Ceres; LCM; libtorch | Implemented but not verified | Preparation tests reported; no native runtime verification. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| Swarm-SLAM | `Benchmark/Swarm Slam` | Native SLAM integration; Python/C++/shell | ROS 2 Humble; RTAB-Map VO; GTSAM; descriptor model | Implemented but not verified | Native graph/transport adapters exist; build and runtime pending. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| CCM-SLAM | `Benchmark/CCM Slam` | Native SLAM integration; Python/C++/shell | ROS 1; ORB/DBoW2/g2o | Integration-only | Source reports one-robot smoke but no initialized native poses. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| COVINS-G | `Benchmark/COVINS G` | Native SLAM integration; Python/C++/shell | ROS 1; ORB-SLAM3; backend workspace | Integration-only | Later reference reports describe bounded replay; no full collaborative validation. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| DVM-SLAM | `Benchmark/DVM Slam` | Native SLAM integration; Python/C++/shell | ROS 2 Humble; ORB-SLAM3; Pangolin | Integration-only | Adapted stereo and original monocular paths differ; short replay diagnostics are not rankings. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| Custom SLAM | `Benchmark/Custom Slam` | Native SLAM integration; Python | NumPy; OpenCV; Webots | Implemented but not verified | Team simulation implementation; excluded from this first four-algorithm integration batch. Retain layout under `experiments/ab3`; only four requested candidates enter the first adapter batch. |
| ORB-SLAM2 | References in `Benchmark/Live Integrations/live_runner.py` and CCM settings | Configuration/reference; Python/YAML | ORB-family settings; no independent package | Documentation/reference only | No standalone source, build or executable found. Add upstream guide, not a claimed port. |
| RTAB-Map | `Benchmark/Swarm Slam/Dockerfile`, `Benchmark/Door Slam/Dockerfile`, `Benchmark/Standard Environment/benchmark/adapters/ros2_bridge.py` | Dependency and ROS bridge; Python/C++ dependencies | Historical ROS Melodic fork and ROS 2 Humble packages | Integration-only | Present as VO/dependency/bridge; no standalone complete Webots port found. |
| Standard AB3 environment | `Benchmark/Standard Environment` | Worlds, PROTOs, stereo/IMU/encoder/radio simulation; Python/VRML/JSON/YAML | Webots R2025a, Python 3.10+, NumPy/OpenCV/SciPy | Implemented but not verified | 10 initial robot poses; 32 ms step, 96 ms cameras; keep shared layout and fingerprint. Destination `experiments/ab3/Standard Environment`. |
| Shared native boundary | `Benchmark/Live Integrations` | ROS transport, frames, correction output; Python/shell | ROS-specific containers; standard radio | Implemented but not verified | Preserve runtime modules and unit tests; omit package generator and unpublished historical reports. |
| Benchmark recorder/evaluator | `Benchmark/Standard Environment/benchmark` | ATE/RPE/maps/loops/resources/network; Python | NumPy, optional OpenCV/SciPy; Matplotlib for plots | Implemented but not verified | Existing tests available. Audit metric assumptions; provide a focused validated trajectory CLI. |
| Reference evaluation | `Benchmark/Reference Benchmarks/evaluate_smoke.py`, `test_evaluation.py` | 3D alignment and rigid RPE; Python | NumPy plus tightly coupled replay/evidence helpers | Documentation/reference only | Useful math reviewed; not copied wholesale because imports depend on private recordings/artifacts. |
| Results and recordings | `Benchmark/results`, archive experiment tools/reports | Historical outputs; CSV/PNG/HTML/SQLite | Specific trial inputs and provenance | Documentation/reference only | No complete native trajectories/recordings in this checkout for the four candidates. Do not republish rankings. |
| Archived simulations | `archive/AB3_Webots`, `archive/custom slam`, `archive/final bstem slam` | Earlier generators/controllers/experiments | Webots and project-specific Python | Documentation/reference only | Superseded active workspace; avoid duplicates and hardware-coupled assets. |
| Board and hardware assets | `Bstem`, `archive/AB3_Robot_Specs.zip` | Physical deployment, vendor bundles | Board-specific dependencies | Unsuitable for redistribution | Outside software/simulation scope; rights to vendor materials not established. |
| Existing project website | `website` | Reviewed public overview and selected media | Node.js and vendored marked | Documentation/reference only | Separate disclosure rules; do not migrate private generated content or build a speculative frontend. |

## Build/run evidence and destinations

The first four native folders provide Python prepare/run commands plus shell,
Windows and macOS launchers. Docker recipes isolate Melodic, Noetic and Humble;
these environments must not be combined. Source command names are
`run_door_slam_original.py --prepare-only`, `run_d2slam.py --prepare-only`,
`run_kimera_multi.py --prepare-only`, `run_swarm_slam.py --prepare-only`.
These commands may fetch weights/sources and create outputs; they were not run
inside the immutable source. The new algorithm navigation pages document the
reviewed SLAMLab interface and exact remaining gates.

Team attribution is established by source history and owner's MIT confirmation;
individual authorship of every file is not inferred. Upstream locks record
commits/hashes, but do not replace licenses. Original archives are excluded from
publication. Models stay external. Texture generator/provenance is checked
before import; uncertain media are excluded.

Sample-data availability: simulation ground-truth occupancy grids and layout
JSON exist; these describe the world, not measured SLAM accuracy. Most run/raw
recording directories are absent from the clean checkout. Test fixtures may be
synthetic and must stay explicitly labeled. No component is marked Verified
runnable until an actual local check establishes the stated scope.
