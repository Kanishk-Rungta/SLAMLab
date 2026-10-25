# Local validation report

Environment: Windows, Python 3.11.9, installed Webots R2025a. Docker and gh are
not on PATH. Git remote operations use existing Git authentication; pull
requests use GitHub REST because gh is unavailable.

- Original standard fingerprint passes.
- Imported evaluator: 9 synthetic known-answer tests pass.
- Webots: one- and two-robot odometry demonstrations each complete 3.008 simulated
  seconds, with estimate/truth CSV and completion receipts. No native SLAM or
  mapping result is implied.
- Shared radio/wire boundary: 13 tests pass.
- Native-output suite: 10 tests run successfully, with 2 source-dependent
  subcases skipped (DVM and Swarm external sources absent).
- Shared stereo-output utility: 3 tests pass.
- Doctor commands for all four adapters report native validation false.
- Native run attempt fails explicitly before work because Docker is absent.

Final repository validation, benchmarking tests, GitHub workflow results and
source integrity receipts will be added after the corresponding work completes.

- Offline source restoration verified D?SLAM: 399 locked files; DOOR-SLAM: 1,345 locked files. Both prepare commands succeeded in SLAMLab, generating calibration and checking available build-copy adapters. Native build/run remains unverified.
- Four source-restoration integrity/path/edit-preservation unit tests pass.
- The optional D?SLAM full ZIP network fetch exceeded its 64 MiB cap and wrote no source archive; sparse Git is the default transport.
