# Third-party notices

The root MIT license covers original SLAMLab files and team-owned files whose
redistribution was confirmed by the owner. It does not relicense dependencies.

| Component | Relationship | License handling |
| --- | --- | --- |
| DOOR-SLAM and its separate frontend/Buzz/mapper repositories | External pinned source | The archived DOOR root license is MIT (Pierre-Yves Lajoie, 2019); distributed mapper has Georgia Tech BSD conditions. Other subrepositories need their own review. No archive is vendored. |
| D?SLAM | External pinned source | Upstream README identifies LGPL-3; models and dependencies require separate checks. No code or weights are vendored. |
| Kimera-Multi workspace | External pinned source | Index and each native workspace repository retain separate notices. Native adapter package already declares BSD; that declaration is preserved. |
| Swarm-SLAM, RTAB-Map and descriptor models | External dependencies | Review each pinned repository and model license before redistribution. Model hashes do not grant rights. |
| ORB-SLAM2 | External reference | GPLv3 upstream; no independent implementation copied from the source project. |
| Webots | Simulator dependency | Installed separately; bundled Cyberbotics PROTOs resolve via `webots://`. They are not relicensed by SLAMLab. |
| Contributor Covenant 2.1 | Community policy reference | Linked as the established behavioral standard; the full text is not reproduced. |

Upstream links and pins are recorded with the algorithm guides. Downloaded
sources, archives and weights remain ignored local dependencies. A public URL
or source hash does not by itself establish redistribution permission.
