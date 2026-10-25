# Visualizations

The trajectory evaluator exports `trajectory.png` as a standalone Matplotlib
figure with metre axes and experiment-kind labeling. Associated poses are saved
as CSV so researchers can build custom plots without rerunning SLAM. See the
[example](../examples/trajectory-evaluation/README.md).

Occupancy grids require a declared cell resolution, origin, frame, row-axis
convention and unknown/free/occupied encoding. The imported ground-truth NPZ is
evaluation input; it is not an estimated map. Point clouds require declared
units/frame and a real source reconstruction. No fabricated map or point-cloud
result is included. See the [output-reading tutorial](../docs/tutorials/reading-results.md).
