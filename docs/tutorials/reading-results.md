# Reading trajectories, occupancy maps and point clouds

## Trajectories

Check time units and clock origin first. The planar evaluator expects body x/y
in metres and yaw in radians; optical camera axes and inverted pose matrices
require an explicit conversion. Inspect `associated.csv` to see which poses
were used. Plot full data and tracking gaps before interpreting a small RMSE.
The standalone PNG uses equal spatial axes and labels the experiment kind.

## Occupancy maps

An occupancy grid assigns a cell a free, occupied or unknown state. Unknown is
not free. Check resolution, origin, orientation and whether rows increase with
world +y or image-down direction before overlaying two grids. The imported AB3
ground-truth NPZ describes the simulated layout and is evaluation-only. It must
never be fed to an estimator or mislabeled as a reconstructed map.

For the imported grids, inspect key names without allowing object deserialization:

```sh
python -B -c "import numpy as np; p=np.load('experiments/ab3/Standard Environment/ground_truth/ab3_gt_map.npz', allow_pickle=False); print({k:p[k].shape for k in p.files})"
```

Map overlap needs a defined frame/alignment, occupancy threshold, observation
mask and treatment of furniture/dynamic objects. A sparse map may appear precise
while covering little area, so report precision and completeness together.

## 3D maps and point clouds

A point cloud is a set of 3D samples; a mesh also connects surfaces with faces.
Color or semantic labels are additional attributes, not proof of geometry
accuracy. Declare metres versus millimetres, sensor/body/world frame, estimated
versus ground-truth identity and the reconstruction settings. Use an appropriate
viewer such as the upstream system's ROS visualization or standalone mapping
tool after checking its format. SLAMLab does not currently ship a validated 3D
reconstruction example or fabricate one from the occupancy ground truth.

See [visualization outputs](../../visualizations/README.md) and
[metric assumptions](../benchmarking/metrics.md).
