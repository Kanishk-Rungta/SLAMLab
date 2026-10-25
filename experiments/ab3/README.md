# Preserved AB3 integration workspace

The shared `Standard Environment` and native algorithm folders remain siblings
so their established Python imports, Docker build contexts and calibration
paths keep working. This is a compatibility layout inside the monorepo, not an
embedded Git repository. Navigation belongs in the root algorithm and simulation
indexes; code is not duplicated there.

Start with the [simulation index](../../simulations/webots/README.md),
[scenario guide](../../docs/simulations/ab3.md) and
[source inventory](../../docs/implementation-inventory.md).
Generated controllers, dependency snapshots, native builds and runs are ignored.
Use the active interpreter after installing [requirements](../../requirements.txt).
Native builds require separately installed Docker with Linux containers.
