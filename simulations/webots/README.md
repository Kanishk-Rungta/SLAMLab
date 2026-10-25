# Webots simulation index

Target simulator: **Webots R2025a**. Python 3.10+ runs the launch and evaluation
tools. Install Python dependencies in a repository-local virtual environment.

| Scenario | World | Robots | Controller | Status |
| --- | --- | --- | --- | --- |
| AB3 static standard | [ab3_standard.wbt](../../experiments/ab3/Standard%20Environment/webots/worlds/ab3_standard.wbt) | 10 fixed initial poses | None until an adapter is selected | Imported, fingerprint verified; native SLAM validation pending |
| AB3 odometry teaching demo | Derived from the standard at preparation time | 1 or 2 | [odometry_demo.py](controllers/odometry_demo.py) and separate [demo_supervisor.py](controllers/demo_supervisor.py) | Bounded wheel odometry; see validation report for actual runtime result |

The paths above are relative to the repository root via this index; see the
[AB3 guide](../../docs/simulations/ab3.md) for the execution contract.
Historical platform names in PROTO/device interfaces describe a simulated robot.
No board integration, hardware deployment or vendor driver is included.

From the repository root:

```sh
python -B tools/run_webots_demo.py --prepare-only --robots 2
python -B tools/run_webots_demo.py --robots 1 --seconds 10
```

Set `WEBOTS_HOME` or use `--webots-home` for a nondefault installation. Run output
is a unique ignored `outputs/webots-demo-*/` folder containing per-robot estimate
and ground-truth CSV, a simulator log and completion receipt. The simulation
supervisor stops after the requested 1?60 simulated seconds. Wall-time timeout
is 120 seconds by default. A failure, missing trajectory or controller exception
returns a nonzero exit status.

Wheel odometry integrates noisy encoder travel; it neither detects loop closures
nor creates a map. Ground truth comes only from the separate supervisor. The
initial dock is a declared known prior. Two robots do not collaborate in this
example. Native adapters use their own radio transport and require separate
acceptance tests.

Capture future demonstrations by running the short example, verifying its
receipt/logs, then using Webots' screenshot/movie tools. Record version, world
fingerprint, command and scope beside the media. No fabricated screenshot or
algorithm result is published.
