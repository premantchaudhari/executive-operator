# Phase 3 — native integration registry and gateway increment

The provider-independent registry covers seven services and 14 actions. These are semantic application contracts, not asserted Composio tool names or already-live connections.

| Service | Current contracts | Remaining full-scope actions |
|---|---|---|
| Gmail | Search/read query, exact-recipient send | Threads, draft lifecycle, attachments, reply identity |
| Calendar | Read window, create event, cancel by ID | Updates, attendee resolution, conflict detection |
| Drive | Search and read by ID | Upload, controlled sharing and downloads/artifact pipeline |
| Sheets | Read range, append JSON rows | Typed updates, concurrency and formula policies |
| Slack | Search, channel message | Channel/member permissions and targeted resource resolution |
| HubSpot | Search, create contact | Deals, notes, updates and duplicate resolution |
| QuickBooks | Conservative read-only SELECT | Reviewed bookkeeping changes and invoice workflows; no payment execution |

## Configuration and authorization

Copy config/integrations.example.json to a private deployment configuration and set INTEGRATION_CONFIG to its absolute path. Supply COMPOSIO_API_KEY through deployment secrets. Each app requires an auth config, each action an actual reviewed tool slug, dated version and complete semantic-to-provider argument mapping. Empty defaults intentionally disable execution. Nested payload mapping and provider-specific defaults need explicit adapter code; a flat mapping cannot make incompatible provider schemas compatible.

The organization identity is generated server-side as organization:<organization_id>, never taken from model output. Active-account listing is filtered and then rechecked for exact user ownership, auth config and active status. Ambiguous accounts require explicit internal selection; no arbitrary-account fallback exists. Accounts belong to an organization deployment: granting team access to these connections requires the approved role/policy model, not simply possession of an account ID.

Authenticated API routes:

- GET /v1/organizations/{org}/integrations/catalog: semantic contracts and approval flags.
- GET /v1/organizations/{org}/integrations/{app}/status: owner/admin only, returns account IDs/status, never credential state.
- POST /v1/organizations/{org}/integrations/{app}/connect: owner only, hosted authorization URL. No callback is accepted as proof of authorization.

Gateway execution is internal, not a public unrestricted tool endpoint. A workflow executor can call Gateway.execute after action/account authorization; write calls require a reviewed provider-specific verifier before dispatch and a confirmed postcondition afterward. All registered writes are included in the workflow approval set. The catalog does not itself authorize a destination or recipient.

Successful reads return bounded provider data; this verifies API retrieval, not the truth/completeness of business content. Write postcondition handlers are not yet implemented and writes deliberately remain blocked at the gateway without one. Missing/revoked connections raise ConnectionRequired. The next worker integration must turn that into a durable connection pause and reviewed resume; the current workflow runner would classify an unhandled exception as needs_review. Do not enable real workflows by bypassing this requirement.

## Scope review required per deployment

Gmail search/read can require restricted scopes; send has a separate scope. Calendar, Drive, Sheets, Slack, HubSpot and QuickBooks require per-tool scope review with the chosen OAuth app and organization policies. Prefer a separate read profile where feasible; connecting through Composio does not prove scopes are minimal or resolve OAuth verification obligations. Account selection UI, revoke/reconnect operations, direct Google/Microsoft OAuth alternative and incremental consent remain open.

Planner context now includes the registry rather than inventing vendor tool slugs. All actions are validated again by application code before being persisted/executed. No new production connection or external action was made in this increment. Mocked SDK tests validate ownership, version pinning, selection ambiguity, provider failure and input checks; live schemas remain unverified.

Official references consulted for this increment:
- https://docs.composio.dev/docs/tools-direct/executing-tools
- https://docs.composio.dev/reference/sdk-reference/python/connected-accounts
- https://docs.composio.dev/reference/api-reference/connected-accounts/getConnectedAccounts

## Carry-forward work

Phase 3 is not complete. Remaining work includes real tool contract tests for every listed action, richer provider mappings, postcondition verifiers, approved connection selection/persistence, connection pause/reconnect/revoke, the missing action families above, direct OAuth where required and end-to-end account testing. Earlier Phase 1/2 gaps remain tracked; demo stays independently runnable. No production-readiness or whole-phase completion claim is made.
