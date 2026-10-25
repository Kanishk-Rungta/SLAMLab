# Metric boundaries

The imported AB3 evaluator includes planar trajectories, tracking, maps, loop
records, resources and communication. Its original synthetic tests pass; this
is not a blanket scientific validation of every metric.

Only compute metrics supported by actual inputs. Keep timestamps, units, body
versus camera frame, initial priors, alignment and startup/coverage exclusions
explicit. Global alignment uses ground truth only offline. A corrected global
trajectory is different from raw odometry. CPU time is not wall runtime, process
RSS is not whole-container peak memory, and configured energy models are not
physical power measurements.

The focused trajectory utility will document its narrower supported format,
validated formulas and output provenance here when implemented. No synthetic
fixture is a measured research benchmark.
