# Installation

Use Python 3.10–3.12. From the repository root, create an isolated environment:

```sh
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

The requirements pin direct host packages. This is not a full transitive lock;
record `python -m pip freeze` with an experiment. These packages do not install
ROS, Docker or Webots. Install Webots R2025a separately and set `WEBOTS_HOME` if
needed. Native algorithm builds require Docker with Linux containers and their
separate historical ROS stacks. The [algorithm guides](../../algorithms/README.md)
explain source restoration and remaining validation gates.

Start offline with `python -B tools/run_webots_demo.py --prepare-only`, then run
`python -B tools/run_webots_demo.py --robots 1 --seconds 10` on a simulator host.
No native SLAM dependency is required for wheel odometry.

Run all offline checks with `python -B tools/validation/run_checks.py`. CI uses
Python 3.10 and 3.12 on Ubuntu; Webots/native builds remain separate local checks.

## Complete landmark SLAM

With Webots R2025a installed, run the NumPy estimator without a ROS stack:

```sh
python -B tools/slam.py list
python -B tools/slam.py run ekf-slam --robots 1 --seconds 30 --output outputs/my-slam
```

See [your first experiment](../learning/first-slam.md) for the complete workflow.

## Interactive website

Use Node.js 24 LTS and the committed npm lockfile:

```sh
cd website
npm ci
npm run dev
```

Open the printed `/SLAMLab/` URL. Build with `npm run build`, then
`npm run preview`. Windows PowerShell users can use `npm.cmd` if script execution
policy blocks the npm PowerShell shim. Browser experiments require no Python,
Webots, server API, or uploaded data service.
