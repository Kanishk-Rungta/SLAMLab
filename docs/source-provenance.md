# Source provenance and publication boundary

## Immutable source

Source repository: Final-Year-Project; inspected local HEAD
`7425aec9f58fccb609b5cb788785851a4dc3a682`. Initial Git status was clean.
A private temporary SHA-256 baseline covers 1858 source files,
excluding Git internals. No source commands that write outputs are authorized.
The final safety report records a complete before/after comparison.

The owner explicitly confirmed in this session that team-written code and AB3
simulation assets may be redistributed under MIT, including team/university
rights. This grant does not extend to external research code, CNN weights,
third-party textures or recordings with separate terms. Existing author and
license notices take precedence over the root license.

## Import policy

Only reviewed software/simulation files are eligible. Each transferred file is
recorded by relative source path, destination and SHA-256 in the import manifest
when imported. Changed copies retain an import digest and are listed separately.
No nested Git directories, credentials, raw recordings, historical benchmark
results, physical-board code or university documents are imported.

The preserved AB3 workspace layout is a compatibility boundary. Its simulated
robot class has a historical platform name; it contains Webots device access,
not board drivers. Public tutorials use simulator terminology.

## Attribution

Research algorithms belong to their upstream authors. SLAMLab contributes
integration, simulation organization, evaluation and education. Repository
ownership is not authorship of an upstream algorithm. Kanishk Rungta is verified
as the repository owner and configured Git contributor; no additional project
authors or affiliations are inferred.

No Final-Year-Project Git history is copied or rewritten. SLAMLab was an existing
empty repository with an origin pointing to Kanishk-Rungta/SLAMLab, an unborn
`main` and no remote refs. A first real foundation commit on the foundation
branch must seed `main` before GitHub can compare subsequent feature PRs.

## Completed transfer and safety verification

The reviewed import contains **430 files (7,505,601 bytes before Git line-ending
normalization)**: 238 shared standard files, 39 DOOR adapter files, 40 D? adapter
files, 53 Kimera files, 25 Swarm files and 35 shared-boundary modules/tests.
The [manifest](import-manifest.json) retains original raw SHA-256 and the
normalized repository SHA-256 used by CI. Copied runtime sources are unchanged;
new navigation/setup documentation is written separately. Two obsolete archive
profile generators were excluded. Original model/source ZIPs are not tracked.

Private ignored dependency storage holds the 399-file D?SLAM and 1,345-file
DOOR snapshots used for local preparation, verified against their original
archive and every file hash. These are upstream components, not team-original
code. The D? default sparse Git restoration independently reproduced its locked
archive and retained no nested Git history.

The [source integrity receipt](source-integrity.json) confirms all **1,858**
non-Git source files match the initial baseline, with no added/removed/modified
files or symlinks/junctions, unchanged HEAD and unchanged clean status. Direct
writes were restricted to SLAMLab and isolated temporary test/helper paths.
