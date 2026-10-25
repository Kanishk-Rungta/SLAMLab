# Pose graphs, factors and bundle adjustment

A pose graph connects pose variables with relative-motion constraints. Factor
graphs generalize this view: variables can include landmarks, calibration and
biases; factors encode measurement, motion and prior likelihoods.

## Optimize constraints

For poses $T_i,T_j$ and measured transform $Z_{ij}$, a residual derives from
$Z_{ij}^{-1}T_i^{-1}T_j$. A weighted objective is

$$
\min_{\{T_i\}}\sum_{(i,j)} e_{ij}^T\Omega_{ij}e_{ij}.
$$

Fix one pose to remove the global gauge. Odometry edges connect nearby states;
loop edges connect revisits. The browser module uses damped Gauss–Newton updates
and a line search on planar residuals. Its solver receives measured edges and
initial poses, not the reference path.

Enable loop closure and optimize. Corrections spread through the connected
graph. Wrong loops can also corrupt it, motivating robust losses and geometric
outlier checks. Read the displayed objective rather than expecting a path to
snap to reference coordinates.

## Bundle adjustment

Bundle adjustment refines camera poses and scene points using image reprojection
residuals. Pose graphs commonly optimize coarser relative-pose constraints. Both
are graph problems, but they retain different information.

Inspect the [interactive solver](../../website/src/lab/models.ts) and compare the
teaching model with the [research collection](../../algorithms/README.md).
