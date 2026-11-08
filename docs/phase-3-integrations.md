# Phase 3 — native integration registry and gateway increment

The provider-independent registry currently covers seven services and 16 actions. These are semantic application contracts, not asserted Composio tool names or already-live connections.

| Service | Current contracts | Remaining full-scope actions |
|---|---|---|
| Gmail | Search/read query, exact message retrieval, opt-in send with sent-copy readback verification | Threads, draft lifecycle, attachments, reply identity, live schema acceptance |
| Calendar | Read window, create event, cancel by ID | Updates, attendee resolution, conflict detection |
| Drive | Search and read by ID | Upload, controlled sharing and downloads/artifact pipeline |
| Sheets | Read range, append JSON rows with opt-in RAW/readback postcondition | Typed updates, broader input support, concurrency and resource resolution |
| Slack | Search, channel message | Channel/member permissions and targeted resource resolution |
| HubSpot | Search, exact contact read, create contact with opt-in properties readback | Deals, notes, updates and duplicate resolution |
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

## Owner connection lifecycle increment — 2026-11-08

Added POST `.../integrations/{app}/accounts/{account_id}/reconnect` and `/revoke`, both owner-only. Gateway retrieves the exact account and checks organization identity, account ID and configured auth-config ownership before either operation. Reconnect uses a fresh hosted `link()` flow and explicitly requires account selection afterward; it does not mutate any workflow or approval. The deprecated refresh path is not used. Revoke uses the SDK revocation operation, then reads back `REVOKED` before returning `connection_disabled: true`. Already-revoked accounts return idempotently. Provider failures remain unconfirmed errors; upstream token revocation is described as best effort, never guaranteed. Credential state is never returned. Successful administrative operations have organization-scoped UUID audit references.

Tests cover foreign organizations, mismatched auth configs, readback failure, repeated revoke, sanitized errors, secret exclusion and API owner authorization before provider calls. These are mocked contracts, not live SDK acceptance. SDK pinning, unsupported-provider revocation/handoff UX, a durable administrative operation ledger, connection-pause/resume state, account-selection UI, scope review and live revocation tests remain open. An active external call cannot be undone by revoking a connection.

Official API/SDK references checked for this change:
- https://docs.composio.dev/docs/auth-configuration/connected-accounts
- https://docs.composio.dev/reference/sdk-reference/python/connected-accounts

## Durable account pause and owner resume — 2026-11-08

Native pre-dispatch account absence or ambiguous account selection now persists `awaiting_connection` on the step, workflow and job. The queue does not automatically retry these jobs. The owner exception inbox includes the blocked step's app and bound account, without provider credentials or authorization links. Completed earlier steps and their receipts are preserved. Connection pauses invalidate any previous write approval.

After completing the hosted connection flow, the owner must explicitly select an account with POST `/v1/organizations/{org}/workflows/{wid}/steps/{sid}/connection`, supplying `{ "digest": "<current step digest>", "account_id": "<selected active account>" }`. The endpoint rechecks owner/submitter authorization, pause state, tenant workflow/step scope, exact plan digest and provider-confirmed account ownership/auth config/active status. It queues the persisted job with the selected account bound into the plan. Writes return to fresh approval; the connection endpoint never approves a write. No callback or hosted link completion is trusted as account proof.

Resume only accepts a job fully parked in `awaiting_connection`; a concurrent request before the dispatcher releases its lease receives 409 and may be retried after the visible job status updates. Duplicate resume, stale digests, inactive/foreign accounts and cancelled or uncertain workflows cannot requeue work. Gateway failures after dispatch or during postcondition verification remain `needs_review`, even if the exception concerns a connection. They cannot use this resume path to repeat an uncertain effect.

Tests cover restart-style API resume, completed-step preservation, ambiguous accounts through the actual gateway with a fake SDK client, write approval invalidation, inactive/foreign accounts, cross-tenant/viewer denial, pause/cancel, repeated resume and sanitized verification failure. These tests do not establish live consent, SDK compatibility or actual delivery. Provider verifiers, rich resource resolution, scope review, bounded SDK calls and user-facing connection UI remain dependencies before the complete acceptance journey is available.

## First built-in provider postcondition — Gmail

The registry now has 15 actions across seven services. `gmail.get(message_id)` adds an exact resource read contract. An explicitly configured `google.gmail.sent_plaintext.v1` verifier can check a Gmail send through the production gateway/worker without an injected generic verifier. It reads the returned message ID through the same bound account, checks the sent-copy state and exact approved content, then records evidence distinguishing sent-copy confirmation from recipient delivery. Failed readback leaves the workflow in review with its returned ID, never a reconnect retry or automatic resend. All other write tools still require their own reviewed provider handlers.

See `gmail-verification.md` for strict schema configuration, scope and MIME limits, failure semantics and external acceptance gates. This supersedes the earlier statement that no postcondition handlers exist; it does not establish complete Phase 3 or A02 acceptance. Tests use a fake SDK client through the actual production gateway and dispatcher; no live email was sent.

## HubSpot and Sheets postconditions

Two additional opt-in handlers now verify exact-account readback after contact creation and Sheets append. `hubspot.get_contact(contact_id)` adds the sixteenth semantic action. The contact handler checks the returned ID, active/nonarchived state and exact approved email/name properties. The Sheets handler requires RAW input/unformatted row-major reads, constrains returned ranges to the explicitly approved sheet/columns/rows, and compares every intended cell. Returned contact IDs and append ranges are retained on unconfirmed outcomes for manual reconciliation; neither a timeout nor revoked account enables automatic write replay.

See `crm-sheets-verification.md` for configuration and supported input contracts. This increment exercises a two-write persisted workflow with separate approvals and partial-failure evidence through the actual gateway/dispatcher and fake SDK clients. Native CRM search/resource selection, typed inter-step dataflow, remaining provider write handlers, live SDK mappings and complete A02 acceptance are still unfinished.
