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
