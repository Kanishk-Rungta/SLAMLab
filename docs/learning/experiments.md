# Designing reproducible experiments

Connect observations to executable software, configuration and retained output.
A persuasive plot still needs timestamps, frames and algorithm identity.

## Capture a contract

Record algorithm version, environment, robot count, sensor/calibration model,
initial priors, seed, dependency versions and launch command. Keep estimates and
truth separate. Retain tracking gaps, shutdown failures and incomplete coverage.

The [landmark example](../../examples/landmark-slam/README.md) records its contract
in `experiment.json`/`config.json` and preserves relative sensors for replay.
Its `viewer.json` carries Python-computed metric scores into the static website.

## Compare compatible work

Modality, resolution, frame rate, initial scale, exploration, compute budget and
communication routing can change the problem. A shared world filename alone
does not establish fairness. Show coverage and failure counts beside accuracy.

Use the [metric definitions](../benchmarking/metrics.md) for alignment choices.
Repeat representative trials. Controller CPU time differs from whole-system
runtime, and a sampled resource value differs from an exact peak. Keep unavailable
metrics absent rather than estimating them without input evidence.

## Share compact evidence

Publish reviewed static replays, metrics, provenance and reproduction commands.
Keep large/private recordings outside the website. Local Studio uploads are
processed in the browser and are not sent to a server.
