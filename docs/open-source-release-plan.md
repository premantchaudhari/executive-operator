# Full repository open-source release plan

**Decision:** prepare the existing `executive-operator` repository for a public, MIT-licensed source release, preserving its meaningful history if it passes an exhaustive scan. This replaces the earlier preference for publishing only the detached Core demo.

The software is a **development/research release**, not a certified production multi-tenant system. The local owner-only demonstration remains side-effect free by default. Foundation components, integration contracts, and live-provider support have separately documented verification gaps.

## Changes in release candidate

- Update the portfolio README and historical-document scope notes.
- Prepare the MIT license for original maintainers' code (third-party licenses remain applicable).
- Fix the foundation Docker image to include shared `operator_app` imports.
- Add CI tests for the pilot, PostgreSQL foundation and Docker build/import smoke check.
- Add a history secret scan gate and document release criteria.

## Required before changing visibility

1. Full Git history scan, including **every branch and tag**, using Gitleaks (or equivalent). Review false positives and rotate any genuine leaked credentials before publication.
2. Review provenance and redistribution rights of each source file, third-party snippet, images and other bundled assets. The MIT license does not override third-party restrictions.
3. Verify clean pilot tests, PostgreSQL foundation tests with migrations, Docker image build, and deployment import smoke check.
4. Verify that the default demo is side-effect free and localhost bound, and that real provider credentials are never included in fixtures.
5. Inspect the final release diff and license implications; public MIT licensing permits commercial reuse.
6. Update `main` only after checks have passed; change GitHub visibility separately through the repository settings.

## Security and historical notes

Previous targeted source/commit-diff checks found no recognizable live-key patterns, but this does **not** establish a full history clearance. Historical plans must be explicitly marked as snapshots; see [progress](progress.md).

**Status:** release candidate prepared on a private branch; not declared cleared for publication.
