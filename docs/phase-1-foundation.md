# Phase 1 foundation implementation

The new `foundation` package is separate from the existing owner-only demo. The existing demo stays runnable. This increment implements an ASGI API, PostgreSQL data model, initial migration, OIDC JWT verification, organization membership checks, durable job claims with worker leases, atomic enqueue/audit records, artifact metadata authorization and trusted CLI organization provisioning.

## Start with a staging deployment

Use a dedicated PostgreSQL database, not the demo database. Supply `.env.foundation` with DATABASE_URL (`postgresql+psycopg://...`), OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL from your chosen identity provider. Use HTTPS issuer/JWKS endpoints; accepted algorithm is RS256. Use a dedicated API audience/access-token configuration. Provider-specific token-type checks and browser authorization-code/PKCE login are not yet implemented. Never treat this as a working team-login UI.

The Compose database password is supplied as POSTGRES_PASSWORD through Compose interpolation. Its value must match DATABASE_URL in the API env file. Supply it through deployment secrets or `--env-file`; do not commit either file.

1. Build/start PostgreSQL with the separate compose.foundation.yaml project.
2. Run `docker compose -p operator-foundation -f compose.foundation.yaml run --rm api alembic upgrade head` with the required environment configured.
3. Provision an organization with `python -m foundation.admin --name 'Client name' --owner-subject '<verified OIDC subject>'` inside the API container. This trusted operation requires deployment access and has no public bootstrap route.
4. Start API. It binds to host loopback port 8090. Add authenticated HTTPS ingress/rate limits before remote use. No CORS policy is enabled for untrusted origins.
5. Submit with Bearer access token to POST /v1/organizations/{id}/jobs and Idempotency-Key header, JSON `{"instruction":"Read inbox"}`. The response is 202; this records work, not proof it ran.
6. GET the organization-scoped job to inspect state. Members with viewer role may read but cannot submit. Unknown organizations/resources return 404.
7. `python -m foundation.worker --once` safely claims one job and marks it needs_review because multi-step execution/policy integration is deferred to Phases 2/4. It never reports unimplemented work completed. Expired leases also require review, not blind re-execution.

`/health/live` reports process availability. `/health/ready` requires the supported migration revision. SQL migrations are explicit operator actions, not automatic startup changes. The initial migration contains a frozen schema snapshot; later model changes must create a new migration.

## Validation and operating limits

Local tests exercise the same services with SQLite. PostgreSQL-specific row locking, concurrent transactions and migrations require the PostgreSQL CI job. CI tests include upgrade/downgrade/upgrade; downgrade destroys foundation tables and is appropriate only for disposable test data. Never use downgrade as a production data rollback procedure.

The resolved requirements lock currently includes provider dependencies from the verified Python 3.12 environment. It pins versions but does not include wheel hashes or image digests. It needs vulnerability/image review and ARM64 build testing before use on Oracle ARM. No container build or local PostgreSQL execution was possible in this environment because those executables were absent.

Membership roles are owner/admin/operator/viewer; role/membership mutation endpoints are not implemented. Identity provider handles password/MFA/recovery; login, recovery and invitations UI remain open. The API verifies signatures, issuer, audience, expiry and required claims; cryptographic negative tests cover wrong signature, issuer/audience, expiry, missing expiry and unsigned tokens. Job claims use SKIP LOCKED on PostgreSQL, audit events share the transaction, and terminal updates require an unexpired matching lease token. No provider calls occur in API requests.

Artifact routes return authorized metadata only, never storage keys/public URLs. Uploads, signing and delivery remain Phase 6. No full storage system, budgets, team UI, production monitoring or complete Phase 1 acceptance is claimed yet.

## Remaining Phase 1 work

- Select/configure identity provider; implement PKCE browser login, recovery/invitations/session lifecycle and provider integration tests.
- Enforce database constraints/RLS and least-privilege runtime database role; add concurrent PostgreSQL isolation/lease tests beyond serial service tests.
- Implement usage reservations/admission, private object-store integration, structured redacted logging/metrics and ingress limits.
- Exercise migrations and image builds in CI, restore/upgrade tests and staging deployment.
- Integrate the foundation into the product UI after these gates pass; keep demo and live isolation tested.

## Team access and budget increment (migration 0002)

Owner-only invitation creation returns a one-time token to the authorized owner; this is not automatically emailed or sent to anyone. Store only its SHA-256 hash. It expires in 24 hours and is bound to the intended verified OIDC subject. The recipient signs in and accepts through POST /v1/invitations/accept. Wrong identities cannot consume it. Roles available through invitations are admin/operator/viewer. Only owners may change non-owner roles; ownership transfer/demotion is explicitly blocked pending its own verified flow. Browser login, invitation delivery UI and self-service provisioning remain open.

Jobs now require a configured budget and reserve USD 0.10 (100,000 microUSD) atomically alongside enqueue/audit within the organization row lock. Duplicate submissions reuse the reservation. Missing or insufficient budget fails closed with 402. This fixed reservation is admission scaffolding, not a verified provider cost estimate or actual spending cap: workers in this increment still do not execute providers. Provider execution must enforce remaining allocation per step before being enabled. Reservations remain held for uncertain/review work; settlement, release and billing reconciliation are pending. Provision new organizations with --budget-microusd; default zero blocks execution admission until explicitly funded. No money is charged by this ledger.
