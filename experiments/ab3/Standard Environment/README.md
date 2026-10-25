# Shared simulation standard

The world, robot/calibration, seeded sensor/radio model, occupancy ground truth
and original benchmark recorder/evaluator are retained from the source project.
Their original standard fingerprint must pass:

```sh
python -B "experiments/ab3/Standard Environment/tools/standard_manifest.py"
python -B -m unittest discover -s "experiments/ab3/Standard Environment/benchmark/tests" -v
```

Run from the repository root. The nine synthetic regression tests establish
only their stated evaluator checks. They do not validate a research SLAM system.
See the [scenario guide](../../../docs/simulations/ab3.md) for assumptions.
