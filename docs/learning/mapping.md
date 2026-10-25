# Occupancy grids and particle beliefs

An occupancy grid assigns cells a probability of occupancy. Unknown is different
from free. Under a pose and sensor model, beam cells before a hit support free
space, while the hit endpoint supports occupancy.

## Log odds

Writing $l=\log(p/(1-p))$ makes inverse sensor evidence additive:

$$
l_t=l_{t-1}+\log\frac{p(m\mid z_t,x_t)}{1-p(m\mid z_t,x_t)}-l_0.
$$

The Playground begins at $l_0=0$, traverses cells using a grid-line algorithm,
adds free/hit evidence, and clamps odds. Range, noise and resolution change the
incremental result. This mapping lesson conditions on a supplied pose; a full
grid-SLAM pipeline must also estimate the robot pose from measurements.

## Particle filters

Particles represent alternate pose hypotheses with weights. Motion spreads them;
observation likelihoods update weights; resampling concentrates effort. Too few
particles or an inadequate proposal can lose the correct mode. Rao–Blackwellized
approaches can carry maps per particle while analytically handling other state.

Resolution trades spatial detail for memory and computation. Studio map files
declare origin, resolution and row direction, using `-1` unknown, `0` free and
`1` occupied. Inspect [output conventions](../tutorials/reading-results.md) before
overlaying two maps.
