# Security policy

Executive Operator is experimental developer software. It must not be treated as a production-safe autonomous agent.

## Responsible use

- Keep the pilot bound to loopback. Use demo mode first and use dedicated test accounts for controlled live trials.
- External writes require explicit approval of the exact persisted action; do not weaken authorization or retry uncertain writes automatically.
- Never commit `.env` files, API tokens, OAuth grants, provider output, authentication cookies, local databases, screenshots from private accounts, customer records, or captured browser state.
- Review network and tool allowlists. Never authorize automated financial transfers, browser security bypasses or operations against accounts you do not control.
- Enable per-provider spend caps and review permissions before experiments.

## Report a vulnerability

Use private GitHub security reporting when available. Otherwise contact the maintainer through a trusted private channel; do not post credentials, sensitive exploit instructions or personal data in a public issue.

## Public-release record and ongoing security review

The repository became public under MIT on November 19, 2026. The release PR checks passed: demo tests, PostgreSQL foundation tests, Docker image builds, and a Gitleaks scan of reachable Git history using `--all`. See [release history](docs/open-source-release-plan.md). These results are not a comprehensive security certification.

Ongoing requirements:

- Rotate and revoke any credentials discovered in the future; deleting a secret in a new commit does not erase earlier Git objects.
- Continue examining fixtures, docs, configuration, integrations and repository history for personal or confidential data.
- Verify redistributability of third-party code and assets; the MIT license only covers code the maintainer has the right to license.
- Re-run automated tests, Docker builds, and history secret scanning for material changes.
- Review authorization, account scoping, sandbox and SSRF defenses before any live deployment with client data.
- Confirm that the demo remains fictional and performs no external side effects by default.

Passing a pattern search or unit tests alone is **not** proof that a repository is safe to publish.
