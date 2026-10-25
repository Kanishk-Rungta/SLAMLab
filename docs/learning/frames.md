# Coordinate frames and robot motion

A pose describes position and orientation relative to a frame. Camera measurements
are local to the camera; map landmarks use a map frame. Adding these coordinates
directly mixes different geometric meanings.

For a robot at $(x,y,\theta)$, a local point $(u,v)$ becomes

$$
\begin{bmatrix}X\\Y\end{bmatrix} =
\begin{bmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{bmatrix}
\begin{bmatrix}u\\v\end{bmatrix} + \begin{bmatrix}x\\y\end{bmatrix}.
$$

Rotation and translation have an order. A rear-facing sensor needs its rotation
relative to the body; the [controller](../../simulations/webots/controllers/landmark_slam.py)
applies that rotation before using its marker bearing.

## Integrating motion

For left/right wheel travel $d_l,d_r$ and wheel separation $b$,
$d=(d_l+d_r)/2$ and $\Delta\theta=(d_r-d_l)/b$. A midpoint update is

$$
x' = x+d\cos(\theta+\Delta\theta/2),\quad
y' = y+d\sin(\theta+\Delta\theta/2).
$$

This discrete approximation is most accurate for short steps. Wrap angles
consistently. Wheel radius and separation are calibration parameters, not values
to recover from simulator truth during estimation.

In **Odometry drift**, set both noise controls to zero, then increase rotation
noise. A heading error changes the direction of later translation, so position
error can grow even if wheel distance is accurate. Continue with
[sensors and uncertainty](sensors.md) and [your first experiment](first-slam.md).
