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

The final integrity receipt and GitHub operations are recorded in the implementation report.

- Offline source restoration verified D?SLAM: 399 locked files; DOOR-SLAM: 1,345 locked files. Both prepare commands succeeded in SLAMLab, generating calibration and checking available build-copy adapters. Native build/run remains unverified.
- Four source-restoration integrity/path/edit-preservation unit tests pass.
- The optional D?SLAM full ZIP network fetch exceeded its 64 MiB cap and wrote no source archive; sparse Git is the default transport.

- Default sparse D?SLAM Git restoration succeeded and reproduced the exact 399-file locked archive; no model weights were fetched.
- Twelve analytic trajectory/format/rejection tests pass. Synthetic CLI: 5 matches, ATE RMSE 0.10000000000000003 m (known 0.1 m offset).
- Actual short two-robot Webots recording, robot 1: 94 matches, position ATE RMSE 0.0013542252933906292 m without alignment. This only checks the wheel-odometry/evaluation pipeline over 3 seconds; it is not a research SLAM benchmark.
- Both CLI runs exported JSON, CSV and PNG successfully to ignored output directories.

## Automated validation scope

The common runner executes 18 standalone tests, 9 imported evaluator tests,
13 transport tests, the 10-test native-output suite (2 missing-source subcases
skipped), 3 stereo-output tests and the original environment fingerprint. It
also checks repository structure, Python syntax, JSON/XML/YAML configuration,
internal Markdown links, per-file import digests, high-confidence secret
patterns, generated/oversized files and shell syntax when bash is available.
Legacy evaluator tests emit ResourceWarning messages about existing open-file
patterns; assertions pass. No scientific native SLAM claim follows from them.

GitHub Actions uses pinned official checkout/setup-python commits, read-only
contents permission, unprivileged pull_request events, 15-minute jobs and
Python 3.10/3.12. It runs no simulator GUI, native ROS build, model download or
specialized accelerator workload. Host package pins cover direct dependencies,
not a complete transitive lock. External URLs are reviewed primary references;
CI validates internal links without making network requests.

## Remote CI evidence

[GitHub Actions run 40183475057](https://github.com/Kanishk-Rungta/SLAMLab/actions/runs/40183475057)
completed successfully for implementation commit
`6e381b2760e725195247436a8eeb5a71d1c7cb28`: both Ubuntu Python 3.10 and 3.12 jobs
passed using the pinned requirements, including the synthetic CLI smoke.
The local Windows interpreter used NumPy 2.4.3, SciPy 1.15.2, Matplotlib 3.10.0,
psutil 7.0.0 and PyYAML 6.0.2; its existing OpenCV distributions were 4.11.0.86
and headless 4.13.0.92. No host package installation was performed. Remote CI
therefore separately establishes the pinned direct-package configuration on
Ubuntu; the current Windows environment is not misrepresented as that lock.
