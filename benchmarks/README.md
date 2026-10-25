# Benchmarking foundation

Start with the [metric definitions](../docs/benchmarking/metrics.md) and
[synthetic example](../examples/trajectory-evaluation/README.md). The standalone
planar trajectory CLI supports strict CSV, planar TUM conversion, one-to-one
timestamp association, rigid alignment, ATE/RPE, comparison tables and PNG plots.

The preserved AB3 benchmark recorder/evaluator is under
[Standard Environment](../experiments/ab3/Standard%20Environment/benchmark/README.md).
It is kept in place for native adapter compatibility. No code is duplicated in
this navigation directory. Do not commit raw maps/databases or recordings;
publish compact reviewed reports with complete provenance only after validation.
