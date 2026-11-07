# Deployment

## Local and container demo

The standard-library HTTP server is a pilot server, not an internet-facing production application server. It binds to loopback by default. Never expose it directly without HTTPS, request/connection timeouts and rate limits at a reverse proxy.

Create `.env` with a random API token, then run `docker compose up -d --build`. Docker publishes only 127.0.0.1:8080. The container is non-root, drops capabilities and has a read-only root filesystem; the SQLite volume is writable. Do not mount the Docker socket or host home directory.

For your Oracle VM, keep this service separate from ShaadiMint's PM2 processes. The demo has modest resource limits in compose.yaml. No deployment or modification to your existing live VM has been performed.

For live SDKs, create a separate reviewed image that installs resolved, locked dependencies. The default image deliberately supports demo only.

## Operating boundaries

- Exactly one server process and one owner per SQLite database. No multi-worker or horizontal deployment: the execution lock is process-local.
- Back up the data volume securely. Task plans may contain personal information and code; encryption at rest, access policy and retention deletion need deployment-level implementation.
- Use a dedicated origin and HTTPS reverse proxy. Rotate the API token on suspected exposure.
- Add reverse-proxy rate limiting, request/idle timeouts and body limits; application body limit is 64 KiB.
- External write timeout means uncertainty, not proven failure. Inspect provider state before creating a new request. Do not automatically retry `needs_review` tasks.
- Rolling task cap controls task count, not money. It does not cover failed planning calls or authorize unlimited usage. Provider-level spending caps are required before a paid pilot.
- One token grants owner access. There is no team login, RBAC, billing, per-user spend ledger or client self-service provisioning.
- Health endpoint discloses only readiness and mode. Audit events reside in the local SQLite audit table; no tamper-proof audit guarantee.

## Cost worksheet

Treat the blueprint's dollar amounts as hypotheses, not verified COGS. Track hosting allocation, input/output tokens, browser minutes, E2B seconds, integration operations, channel charges and human maintenance. Quote a bounded pilot with task limits and a maintenance scope until measured invoices establish margin. No current vendor pricing is embedded in this version.
