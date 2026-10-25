# Shared native boundary

Reusable radio fragmentation, local socket framing, ROS routes, camera/body
frames, backend correction state and native lifecycle modules. These implement
transport and output adapters; upstream estimators remain external.

The generator `create_packages.py` was excluded because package creation is not
a runtime dependency and would recreate old documentation. Native source tests
that require external snapshots must be run only after explicit restoration.
Transport/geometry unit tests can run independently. See the
[validation report](../../../docs/validation-report.md).
