# Imported benchmark recorder and evaluator

`benchlog.py` records per-robot events. `bench_supervisor.py` records simulator
ground truth and process/scenario observations. `evaluate.py` reads a saved
benchmark directory with `run_meta.json`, `ground_truth.jsonl`, supervisor events
and `robots/<name>/bench.jsonl`. Missing metrics must remain unavailable.

```sh
python -B "experiments/ab3/Standard Environment/benchmark/evaluate.py" PATH_TO_BENCHMARK --gt-map "experiments/ab3/Standard Environment/ground_truth/ab3_gt_map.npz"
```

This writes reports into the supplied benchmark directory; only use a writable
SLAMLab output or isolated copy. Existing modules include planar trajectory,
tracking, loop correctness, occupancy, resources and communication evaluation.
Inspect each module's assumptions before publication. In particular, energy is
an estimate based on a configured model and not a measured power metric.

`tests/test_evaluator.py` contains explicitly synthetic known-answer fixtures.
The focused trajectory CLI is the recommended small-input path; it records
input hashes, association/alignment choices and limitations. No historical
algorithm performance outputs were imported.
