# SLAMLab website

React + TypeScript + Vite, published at
[SLAMLab](https://kanishk-rungta.github.io/SLAMLab/) through GitHub Pages.
The site is static: lessons, educational models and experiment replays run
without an application server. Uploaded files remain in browser memory.

## Develop and build

Use Node.js 24 LTS and the committed npm lockfile:

```sh
npm ci
npm run dev
npm run lint
npm run format:check
npm test
npm run build
npm run preview
```

Open the printed `/SLAMLab/` URL. `scripts/content.mjs` builds an explicit
allowlist of shared Markdown lessons, renders equations with KaTeX, and copies
the catalog and measured replay bundles. Generated content, dependencies and
build artifacts are ignored by Git. Edit canonical repository docs rather
than generated HTML. Raw HTML in Markdown is escaped.

`scripts/routes.mjs` emits physical `index.html` files for every documented
route, plus a fallback, sitemap and `.nojekyll`. This supports direct links and
refreshes on GitHub Pages under the `/SLAMLab/` project base.

## Browser validation

```sh
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright starts the local preview server when required. It verifies playback,
all five playground models, theme persistence, mobile navigation, direct route
refresh, measured results, file validation, and axe accessibility checks.
Use `PLAYWRIGHT_BROWSERS_PATH` to keep browsers in an isolated cache if needed.
Reports and traces stay in ignored `test-results` and `playwright-report`.

## Architecture

- `src/lab/models.ts`: deterministic motion, geometric ray casting, log-odds
  mapping, descriptor matching, SE(2) optimization and rigid map alignment.
- `src/lab/data.ts`: finite, bounded local-file parsing and replay types.
- `src/components/ui.tsx`: plots, pan/zoom, headings, playback and controls.
- `src/pages/`: learning, explorer, simulation, benchmarks and Studio.
- `docs/project/README.md` (repository root): canonical project statement, objectives,
  methodology, Team 98, progress and resources, shared by Project and Documentation.
- `scripts/content.mjs`: canonical Markdown/catalog/result publishing.
- `scripts/routes.mjs`: refresh-safe static route packaging.

Browser models are educational simulations. Benchmark cards load Python-computed
metrics from measured Webots runs in [examples/results](../examples/results/README.md).
Studio's time-varying separation chart illustrates display samples; the Python
metrics retain the evaluator's association and alignment policy. There are no
native research-system rankings or unmeasured resource-use charts.

CSV imports require `timestamp,x,y,yaw`. Planar TUM imports require
`timestamp tx ty tz qx qy qz qw`, constant height and unit yaw quaternions.
JSON replays use schema version 1. Occupancy maps use `width`, `height`, positive
`resolution`, `[x,y]` origin and row-major cells (-1 unknown, 0 free, 1 occupied).
Rows advance along +Y. Files are limited to 5 MiB; map arrays to 65,536 cells.
No compatible 3D map is published in these runs; the Studio uses their native
planar representation.

## Deployment

The Pages workflow builds only on `main` or explicit dispatch, uploads `dist`,
and deploys through the `github-pages` environment. Pull requests receive build,
unit and browser checks without deployment permissions. Workflows pin actions
to reviewed commit hashes and npm packages to the lockfile.
