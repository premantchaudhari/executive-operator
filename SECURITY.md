# Security policy and publication gates

Executive Operator is experimental developer software. It must not be treated as a production-safe autonomous agent.

## Responsible use

- Keep the pilot bound to loopback. Use demo mode first and use dedicated test accounts for controlled live trials.
- External writes require explicit approval of the exact persisted action; do not weaken authorization or retry uncertain writes automatically.
- Never commit `.env` files, API tokens, OAuth grants, provider output, authentication cookies, local databases, screenshots from private accounts, customer records, or captured browser state.
- Review network and tool allowlists. Never authorize automated financial transfers, browser security bypasses or operations against accounts you do not control.
- Enable per-provider spend caps and review permissions before experiments.

## Report a vulnerability

Use private GitHub security reporting when available. Otherwise contact the maintainer through a trusted private channel; do not post credentials, sensitive exploit instructions or personal data in a public issue.

## Publication checklist (not yet certified)

- [ ] Confirm whether the distribution will be a limited public demo/core or the entire codebase.
- [ ] Run a full repository and **all reachable Git history** scan using Gitleaks or equivalent, across all branches/tags.
- [ ] Rotate credentials found anywhere in history before rewriting or exporting code; deleting only the latest occurrence does not remove past exposure.
- [ ] Audit sample fixtures, docs, configuration, migrations and logs for personal/business data.
- [ ] Review third-party source, assets, and SDK licenses before adding an open-source license.
- [ ] Verify no internal deployment URLs, real customer identifiers, private integration mappings or personal emails are present.
- [ ] Run the pilot unit tests, foundation tests and CI from a fresh checkout. Document any skipped tests.
- [ ] Test demo behavior and validate that zero external side effects occur with default settings.
- [ ] Audit production-facing auth, scopes, sandbox and SSRF protections before permitting live accounts.
- [ ] Review the README to ensure every implementation claim matches evidence.
- [ ] Explicitly approve the exact branch/commit and license before switching visibility.

Passing a pattern search or unit tests alone is **not** proof that a repository is safe to publish.
