# Website activity verification

Audit date: 2026-10-25. Starting revision: `91d9ede`. This review checked the
instructions against model behaviour, browser interactions and actual local
Webots executions. The fixes below are included with this report.

## Playground

| Activity | Verified behaviour |
| --- | --- |
| Odometry drift | Zero translation/rotation noise gives zero position error. Seeded errors repeat, nonzero noise changes the estimate, and playback resets to its first sample. |
| Occupancy mapping | Geometric rays update free/occupied evidence; unknown cells have a distinct colour. A 0.1 m grid exports 80 × 80 valid cells and opens as a map layer in Studio. |
| Feature matching | Noiseless descriptors produce 15 correct matches and no wrong matches with a tight threshold. Synthetic noisy descriptors can produce wrong matches. |
| Pose graph | Optimization reduces the measurement objective while retaining the first pose as an anchor. Removing the loop leaves a chain that already fits its own measurements. |
| Multi-robot alignment | Fewer than two shared pairs or disabled communication prevents fitting. Noiseless pairs recover the generated rigid map transform. This activity does not perform collaborative exploration or task allocation. |

Model tests and browser tests check outcomes, not only whether controls can be
clicked. Glossaries and equation panels also pass the existing accessibility
checks. Changing the seed currently restarts an activity with default controls;
the help text now states this explicitly.

## Simulation Lab

All six combinations offered on the page completed in local Webots R2025a:

| Robots | Requested seconds | Recorded completion seconds | Poses per robot | Landmarks per robot |
| --- | --- | --- | --- | --- |
| 1 | 15 | 15.008 | 469 | 12 |
| 2 | 15 | 15.008 | 469 | 12 |
| 1 | 30 | 30.016 | 938 | 12 |
| 2 | 30 | 30.016 | 938 | 12 |
| 1 | 60 | 60.000 | 1,875 | 12 |
| 2 | 60 | 60.000 | 1,875 | 12 |

The small completion-time differences follow the simulator's 32 ms time step.
All runs produced completion receipts, trajectories, sensor records, maps,
evaluation outputs and replay JSON. Sensor-only replay exactly reproduced the
saved poses, pose/landmark covariance, landmarks and observation counts for all
nine robot sessions. These are independent EKF sessions with configured initial
poses and camera-recognition marker identities.

The page prepares commands for a local computer; it does not launch Webots in
the browser. The displayed run command now uses one shell line, suitable for
PowerShell as well as POSIX shells, and its scrollable area is keyboard-accessible.
The page reminds visitors to choose a fresh output directory.

Generated reproduction instructions now reference each run's saved configuration,
including robot count and duration, instead of always referencing the default.
The two-robot configuration reference was checked against the saved settings.

Local raw evidence remains in ignored `outputs/activity-audit-*` directories.
No recordings or existing published benchmark bundles were replaced.

## Studio, exports and measured results

- Imported the fresh two-robot Webots export into Studio, selected the final
  playback step, and checked both robot sessions and all twelve final landmarks.
- Checked every fresh replay with the browser parser and 5 MiB file limit.
- Re-evaluated all three 30-second robot trajectories through the documented CLI;
  ATE and RPE matched their original evaluator outputs exactly.
- Checked that CLI visualization exports retained the evaluator's metric objects
  and final measured map checkpoints.
- Recalculated ATE and landmark-map RMSE from both published replay bundles.
  Differences from their supplied metrics were below 0.000002 m, consistent with
  rounding display coordinates to six decimals. Published metrics were unchanged.
- Checked JSON replay downloads, occupancy export/import, documented CSV/TUM
  parsing, malformed input rejection and oversized-file rejection.

The audit exposed and corrected these defects:

1. Playback selected a future pose between timestamps. It now holds the last
   recorded pose until the next sample is reached.
2. Hiding one robot reassigned the remaining robot's colour. Colours now retain
   their original robot indices, and legends identify the actual robot IDs.
3. View bounds omitted reference and odometry trajectories. Those layers now fit
   within the initial view and its reset.
4. Replay parsing discarded landmark covariance and version metadata. Valid
   supplied values now survive import and download.
5. Invalid primary metrics and unordered map checkpoints could be accepted.
   Validation now rejects them, duplicate robot IDs and checkpoint histories over
   200 entries, with an explicit downsampling message instead of silent truncation.
6. Occupancy unknown cells and feature-panel borders referenced undefined theme
   colours. Both now use defined colours.
7. Generic/local replay labels assumed EKF or Python evaluation. Labels now
   identify the supplied data and explain that local metrics are not independently
   recalculated or verified in-browser.

## Validation and limits

The production build, lint, formatting, 14 model/parser tests and eight browser
tests pass after corrections. Python repository/estimator/evaluator/transport
checks and the preserved standard-environment fingerprint pass. Two native-source
subcases remain skipped because their external sources are absent; this audit
does not turn those integrations into validated native systems.

The extra browser audit can open a fresh run when `SLAMLAB_ACTIVITY_REPLAY` points
to its replay JSON. Normal CI still tests local-file behaviour with a small
explicit synthetic fixture and the published measured examples.

These results establish the stated browser activities and bounded educational
simulation workflow on this Windows host. They do not establish physical robot
performance, native research-system rankings, reliable collaborative mapping,
autonomous task coordination or correctness under every possible input and
environment. The 60-second options were executed once each, not as a repeatability
or performance study.
