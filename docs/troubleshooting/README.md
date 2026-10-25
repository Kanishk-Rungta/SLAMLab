# Troubleshooting

| Symptom | Check and next action |
| --- | --- |
| Webots not found | Install R2025a; set `WEBOTS_HOME` or `--webots-home`. Use the intended Python environment. |
| Demo times out | Read its printed `webots.log` and controller error file. Verify GUI/OpenGL availability. The timeout kills only the started process tree. |
| Missing native sources | Use the explicit restoration command in the algorithm guide. Preserve edited snapshots; verification refuses mismatches. |
| Full upstream archive exceeds cap | Prefer default sparse Git restoration or an exact previously verified `--local-archive`; do not download large model bundles merely for source preparation. |
| Docker unavailable | Native build/run requires a Linux container engine. Doctor and independent evaluator checks do not install one. |
| Kimera workspace dependency missing | Source records an unavailable historical opengv fork; the imported recipe pins a replacement. Check every workspace lock and actual native build rather than trusting an older status table. |
| No initialized native poses | Inspect sensor timestamps, baseline/extrinsics and frontend/native logs. A frame acknowledgement is not tracking. |
| Fingerprint mismatch | Stop the comparison; review changed standard inputs. Do not silently rewrite the manifest to make it pass. |
| Timestamp association fails | Check seconds versus nanoseconds, unique ordered timestamps, shared clocks and declared tolerance. No interpolation is performed. |
| CSV/TUM rejected | Supply finite poses; the converter accepts planar motion only. Use a 3D evaluator for varying height/roll/pitch. |
| Output directory already exists | Choose a new directory; previous evidence is deliberately preserved. |
| Small error but partial output | Read both coverage fractions, initialization exclusions and RPE pair counts before interpreting accuracy. |

Sanitize logs before posting them. Include exact commands, dependency/image
versions and whether the failure occurred during preparation, build, native
startup, tracking, collaboration or evaluation.
