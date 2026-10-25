# Contributing

Start from updated `main`, create a descriptive feature branch, and open a pull
request with a Conventional Commit title. Keep commits coherent and retain
source attribution. Do not commit generated runs, models, private datasets or
credentials. Explain failing experiments as carefully as successful ones.

Python utilities use Python 3.10+ and standard `unittest` tests. Keep native ROS
stacks isolated. Never install system packages as an automatic validation step.

For an algorithm integration, include upstream commit, license, publication,
sensor/calibration contract, native build and run commands, output convention,
transport assumptions, and separate preparation/build/runtime validation states.
Report backend-corrected poses separately from raw visual odometry.

For a Webots scenario, specify R2025a, world and controller paths, robot count,
sensors, seed, launch command, output paths and termination behavior. Keep ground
truth in the evaluation supervisor; estimation must not consume it.

For a benchmark, define units, timestamps, pose frames, association policy,
alignment and failure/coverage exclusions. Preserve configuration and dataset
provenance. Synthetic fixtures belong in tests and must be labeled synthetic.

Before a PR, run the documented repository checks and affected utility tests.
Update linked documentation and the changelog. Bug reports should include the
exact command, versions and a minimal sanitized reproduction.
