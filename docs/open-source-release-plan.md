# Open-source release record

The original `executive-operator` repository was made **public** on November 19, 2026 under the [MIT License](../LICENSE). This supersedes the earlier proposal to publish only the detached Executive Operator Core demo.

## What was published

The original repository includes the owner-only SQLite demo, PostgreSQL foundation, migrations, tests, example integration configurations and historical engineering notes. It demonstrates approval-first automation, task state persistence, bounded workflows and verification contracts. It is **development/research software**, not a production-certified agent service.

## Release preparation

[PR #1](https://github.com/premantchaudhari/executive-operator/pull/1), merged as `3b8875fe76ca74caa4a58d64585a2eba41122713`, completed the following:

- Rewrote the portfolio README and marked initial design plans as historical.
- Added MIT licensing for original code authored and owned by the maintainer.
- Fixed missing shared modules and user/group conflicts in Docker packaging.
- Added a GitHub Actions release workflow covering owner-only tests, PostgreSQL foundation tests, foundation and live Docker builds, and Gitleaks history scanning.

The release workflow passed on commit `dc475a0f2ae7b841c2f28e0fb6266d473b7d852d` before PR merge. These results do not validate the production behavior of external APIs.

## Ongoing responsibilities

- Keep secrets, OAuth credentials and customer data out of the repository; rotate exposed credentials immediately.
- Continue third-party license, code-provenance, dependency and asset-rights review. Public availability and passing CI are not proof of redistribution clearance.
- Preserve the distinction between the fictional local demo and the unfinished/unverified production foundation.
- Run Git history scanning, tests and Docker builds after consequential changes.
- Review [security policy](../SECURITY.md) and [implementation progress](progress.md) before deployment.

**Current publication status:** public, MIT-licensed source project. Production readiness is **not established**.
