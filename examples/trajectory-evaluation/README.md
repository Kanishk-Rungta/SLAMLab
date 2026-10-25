# Synthetic trajectory evaluation

These five-pose unit-square trajectories are hand-authored mathematical fixtures.
They are not a sensor recording or a SLAM result. Estimate x is offset by 0.1 m.
Without alignment, expected ATE RMSE is 0.1 m and consecutive-step translation
RPE is zero. With SE(2) alignment, the constant offset is removed.

From the repository root:

```sh
python -B benchmarks/evaluation/trajectory.py evaluate --estimate examples/trajectory-evaluation/estimate.csv --reference examples/trajectory-evaluation/reference.csv --metadata examples/trajectory-evaluation/metadata.json --output outputs/fixture-evaluation
```

Use a new output directory for each invocation. Inspect `metrics.json`,
`summary.csv`, `associated.csv` and `trajectory.png`. The plot title and metadata
retain the synthetic identity. See the [metric definitions](../../docs/benchmarking/metrics.md).
