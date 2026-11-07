# Production release gate · owner-only deployment

This branch is hardened development code, not a certified production release. It does not implement the entire original autonomous-operator scope. Read-only browser inspection, bounded tools and explicit write approvals remain the supported scope.

## Implemented controls

- One operating-system lock per SQLite database; a second server refuses startup.
- WAL, full synchronous writes, busy timeout and owner/date index.
- Persisted request digest and interpreted plan before execution; identical retries avoid repeated planner calls, changed requests using the same key fail.
- Interrupted running/queued tasks require manual review. No automatic external write retries.
- Bounded HTTP connection concurrency (16), 15-second socket timeout, 64 KiB body cap; transfer encoding rejected.
- Example token rejected, mode-specific deployment, no host mounts for sandbox code, non-root containers.
- Network-only PWA and in-memory access token, explicit approvals and fictional demo outputs.
- Consistent SQLite backup helper with integrity verification and private file permissions.

## Mandatory before real clients

1. Resolve and lock SDK dependencies; build both images and scan them. Current live requirements are not pinned. Do not call this reproducible until a tested lock exists.
2. Test LangGraph and every selected Composio tool/version with controlled accounts. Test OAuth revocation, expired links, send ambiguity and account selection. Existing unit tests do not prove live SDK compatibility.
3. Confirm provider-enforced E2B memory allocation and timeout behavior. Test Browserbase redirect/private-network protections and cleanup with live sessions.
4. Configure dedicated HTTPS reverse proxy, connection and authentication rate limits, and provider spending caps. The built-in server is bounded but remains a pilot HTTP server, not a replacement for a production application server/gateway.
5. Deploy demo and live with separate secrets, volumes and hostnames. Do not use client data in demonstration mode.
6. Encrypt data/backup storage, set retention, and perform an actual restore drill. Schedule backups outside the request process. Backups contain sensitive plans and outputs.
7. Add alerting for failed health probes and `needs_review` tasks. Audit events are local and not tamper-proof. Telegram response delivery has no durable outbox yet.
8. Run a paid pilot acceptance test: read a real mailbox, draft an exact email, reject once, approve once to a controlled address, retry the request, and verify exactly one delivery.

No multi-tenant isolation, team RBAC, monetary metering, arbitrary browser writes, file delivery bucket, complete agent loops or SLA is claimed. A single owner/token per deployment is the supported operating model. The exclusive database lock protects server startup; embedded code must not instantiate competing engines against the same database.

## Backup and recovery

Run `python scripts/backup.py data/operator.db /secure-backups/operator-YYYYMMDD.db` from a trusted shell. Use a new destination per backup. Keep backups off the application host with encryption and access restrictions. For restore, stop the application, restore to a new database path, verify integrity, then start with that path. Review uncertain external writes before resubmission. Database rollback cannot undo provider-side emails or calendar changes.
