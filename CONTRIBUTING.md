# Contributing

Thank you for your interest in Executive Operator.

**Current status:** the full-source release candidate carries an [MIT license](LICENSE). GitHub repository visibility is still private until the release gates pass. Contributions should target the release branch only until it is merged.

## Development principles

1. Preserve explicit approval before every external write and never silently retry an uncertain provider result.
2. Keep demo behavior deterministic and side-effect free by default.
3. Treat model output, browser pages and provider responses as untrusted input. Validate structure and enforce server-side policies.
4. Prefer narrow, testable changes with real failure-mode coverage over unsupported capability claims.
5. Avoid committing secrets, OAuth tokens, real email addresses, private customer content, database snapshots or live-provider transcripts.

## Local checks

For the owner-only demo:

```bash
python -m unittest discover -s tests -v
python -m compileall -q operator_app
```

For the independent foundation, follow [the documented setup](docs/phase-1-foundation.md), including its lockfile and PostgreSQL requirements, then run the matching CI workflow checks. Tests requiring live provider credentials should be opt-in and clearly identified.

## Change submissions

Explain the intended behavior, failure modes, tested commands, and whether a provider side effect is possible. Add regression tests for approval expiry, idempotency, multi-user isolation, uncertain writes and input validation when relevant. Don't claim a live integration is supported merely because the adapter compiles.

Report security issues privately as described in [SECURITY.md](SECURITY.md).
