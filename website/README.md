# AlgoWorlds project page

This Astro site is the standalone project page for AlgoWorlds. Its visible
copy follows the current paper terminology, uses `Weixin AI` as the only
organization identity, and links the code and dataset as one GitHub resource.
The paper button points to arXiv and does not expose a local PDF download.

## Develop and test

```bash
npm ci
npm run dev
npm run test:all
```

The production build is static and is published by the repository's Pages
workflow.

## Results data

`src/data/results.v1.json` contains only the aggregate values rendered by the
page and the current paper PDF digest. It omits unpublished manifests, commits,
snapshots, trajectories, raw runs, and the internal result exporter.

## Visual assets

Asset provenance, checksums, modification status, and the 2026-08-28 project
lead approval are recorded in `docs/assets/ASSETS.json`. This review metadata
is source documentation and is not copied into the static site output.
