# Developing SLAMLab

Use a feature branch and a pull request for each coherent change. Run the
affected checks before pushing, then merge after required CI succeeds.

## Repository and estimator checks

```sh
python -m pip install -r requirements.txt
python -B tools/validation/run_checks.py
```

Checks cover repository structure, JSON, Markdown links, Python syntax, provenance,
the standard-world fingerprint, mathematical evaluation, sensor transport and
native output contracts. They do not replace a native runtime experiment.

For the NumPy estimator, test covariance symmetry and positive semidefiniteness,
new landmark initialization, joint cross-covariance, angle wrapping, innovation
gating and actual correction of accumulated motion error.

## Experiment contract

An experiment records configuration, seed, software versions, real sensor inputs,
estimated trajectory/map, separately recorded reference data and evaluation.
Never feed reference poses or global landmark coordinates into the estimator.
Configured initial priors and simulated recognition identities must be declared.
Use `tools/replay_landmark_slam.py` to replay estimation from measured sensor
increments independently of the reference recorder.

`tools/export_experiment.py` packages real output for static visualization. It
copies computed metrics and decimates display trajectories/checkpoints only.
Preserve the final checkpoint and publish reproduction metadata with shared
samples. Native stacks must export initialized, backend-corrected poses and
identify any local odometry output separately.

## Website and curriculum

See [website development](../website/README.md). Lesson source lives under
`docs/learning`, `docs/fundamentals` and the relevant technical guide directories.
Only the allowlist in `website/scripts/content.mjs` becomes website content.
Add new routes to the static packaging script and test direct refresh.

Tests for models should assess mathematical behavior: reproducibility,
measurement residual reduction, frame recovery, geometric intersections and
input bounds. Browser checks should verify the user can operate the controls,
understand displayed results, and use the site on a small screen and keyboard.

## Native research systems

Keep ROS and model dependencies isolated per algorithm. Record upstream commit,
license, sensor contract, calibration, exact build command and native output.
Current build/execution work is tracked in the
[native research milestone](https://github.com/Kanishk-Rungta/SLAMLab/milestone/1).
Do not present source preparation, transport receipts or a trajectory fixture as
a completed native SLAM run.

## Release gate

Require clean repository checks, website build/lint/unit/browser checks, a
verified Pages deployment, runnable measured examples, current installation
instructions, attribution and release notes matching actual functionality.
Use a semantic version and a normal GitHub release targeting the tested main
commit. Preserve the original source repository and import provenance.
