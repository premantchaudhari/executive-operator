# Phase 4 — owner approvals and pause controls increment

Migration 0005 binds workflow approval to the approving subject and adds organization pause state. Only organization owners may decide an approval or edit a pending action. Operator/admin membership alone no longer authorizes these decisions. Before each dispatch the engine rechecks the submitter's current execution permission, organization pause state, and the owner's continuing approval authority. Removing/downgrading an approver invalidates the grant before the next dispatch.

PATCH /v1/organizations/{org}/workflows/{wid}/steps/{sid} accepts the current digest and a validated plan. Only pending/reviewable actions may change. Editing updates the digest, clears approval identity/deadline and requires a fresh review for write actions. Completed/running/uncertain actions are not editable through this route. POST /v1/organizations/{org}/pause takes a strict paused boolean and requires an owner. Pausing stops future step dispatch; it cannot undo an already-started external effect. As with cancellation, results from in-flight calls still need reconciliation. An approval check and external network request cannot be one atomic transaction; no claim of instantaneous revocation of in-flight work is made.

Tests cover pause/resume, approval invalidation after edit, operator denial and revoked submitter access. Existing digest/expiry/replay/tenant checks remain. Full browser-state binding, connection-account binding, resource/recipient resolution, destination/disclosure rules, payment/OTP boundaries across arbitrary sandbox code, and policy UI remain open. Do not consider Phase 4 complete based only on these native sequential-workflow controls.

## Recurring continuation handoff

Requested objective: continue implementing all requirements in phase-0-scope-and-backlog.md, preserving separate demo/live behavior, then perform a complete application audit. Resume by reading current repository state and this backlog, not by assuming a previous local scratch directory still exists. Work on incomplete dependencies before advancing phase labels; commit reviewable changes, run relevant tests/CI and update evidence. Mark live-provider/deployment checks blocked when credentials/access are missing; never mark them passed from mocks. Do not create payments, buy resources, modify ShaadiMint deployment, send client communications or publish the private repository as public. After all implementation and verification gates pass, produce a full source/security/UX/integration/operations audit and disable the continuation task. Do not claim completion or a successful audit without evidence.

Scheduling limitation encountered: the available automation service supports a minimum interval of one hour. No half-hour automation was created; the user must choose the supported hourly alternative before creation. This handoff records intent, not a running schedule or background worker.

## Follow-up verification

Hourly continuation is now enabled by user request. The initial half-hour limitation above is historical; an hourly task was successfully created on 2026-11-07.

Production workflows now reject browser/sandbox actions before enqueue and again before dispatch until dedicated cross-layer policies exist. Preview validates exact native plans and exposes write-approval requirements without creating jobs, reserving budget, calling providers, or approving anything. It is an offline preview, not the real-data dry run required by F37. Owner-only exception listing is tenant scoped. Expired reviews can be refreshed without granting approval; the original digest remains required. Added regression checks for rejection, replay, expired-review recovery and approver demotion.

Validation: 47 foundation tests (46 passed, one PostgreSQL-only check deferred to CI), 33 legacy demo tests passed locally. Phase 4 remains open: exact connected-account/resource binding, disclosure destinations and real-data dry run are not implemented, and browser/sandbox cross-layer enforcement requires phases 5/6. No phase-complete claim is justified by the offline tests. Next continuation must close those requirements rather than advance the phase label.

## Account substitution guard

Native writes now require an explicit connected-account ID even when exactly one account is active. A missing/revoked explicitly selected account raises ConnectionRequired and never substitutes the remaining account. Added regression tests for both cases. This is a gateway guard, not full persisted approval-to-account binding; that requirement remains open. Local validation: 49 foundation tests (48 passed, one PostgreSQL-only skip), 33 demo tests passed. Remote publication and CI for this increment remain pending.

## Gateway validation boundary

The Composio gateway now runs full canonical action validation before account lookup or provider dispatch. Previously it checked native argument fields but skipped the stricter gmail recipient/header validation and rejection of unexpected top-level plan fields. Regression tests cover header injection and tenant-field injection, asserting no provider call. Validation: 51 foundation tests (50 passed, one PostgreSQL skip), 33 demo tests passed. Git publication remains blocked through available CLI/API credentials: git requires authentication and the connected GitHub API returns 404 for this private repository. Browser publication is still pending; no remote CI success is claimed for the two local increments.

## Disclosure destination enforcement

Native writes now require a trusted per-integration `allowed_destinations` map, keyed by action and containing exact allowed destination strings. Example: `"allowed_destinations":{"gmail.send":["client@example.com"]}`. Wildcards and domain matching are not interpreted. Missing policies deny writes. Coverage includes email, Slack channel, spreadsheet, calendar/event and CRM contact destinations. Read operations remain unaffected. This is a deployment allowlist, not recipient identity resolution or approval-account binding. Existing configurations without this map intentionally fail closed for writes. Tests cover missing policies, wrong destinations, wildcard rejection, exact match and read behavior.

Local foundation verification: 57 tests, 56 passed and one PostgreSQL-only skip. Publication, PostgreSQL CI and live-provider checks remain pending. Phase 4 is still open for persisted account/resource binding, live-data dry run and cross-layer policy integration; these are not replaced by destination allowlists.

## Persisted account binding

Workflow plans now support a bounded `account_id` field that is stored within the canonical plan and included in its approval digest. Owner edits to this field follow the existing edit path and invalidate approval. Gateway dispatch selects that bound account and rejects a conflicting account override. Tests verify persisted edit invalidation, substitution rejection and selected-account dispatch. Legacy unbound plans still exist; admission and owner selection UI must require binding before production writes can be enabled. This increment therefore does not close Phase 4.

Validation: 60 foundation tests (59 passed, one PostgreSQL skip) and 33 demo tests passed locally. No live provider tests, remote publication or CI verification were performed for this increment. Phase 5 inspection confirms it still has only the proposal fingerprint primitive; durable browser approval, session lifecycle, trusted capture/revalidation and verified actions remain unimplemented. Both phases remain open.

## Mandatory binding before approval

Unbound write plans can remain drafts but owners cannot approve them until an owner edit binds an account. Dispatch also invalidates legacy approved writes lacking an account. Added a regression journey: unbound draft -> approval rejected -> owner account edit -> fresh review -> approval -> one dispatch with bound account. Validation: 61 foundation tests (60 passed, one PostgreSQL skip), 33 demo tests passed. This increment is local; publication and remote CI pending. Account ownership is still checked at the gateway, not at review time; live ownership resolution, real-data dry run and the production worker adapter remain open.

## Native workflow runner

Added `python -m foundation.native_worker --workflow-id ID`, an internal CLI that resumes persisted workflows through the organization-scoped gateway. Completed steps are not dispatched again. Account ownership, pinned tool mapping and destination enforcement remain at the gateway. Native writes remain blocked because no generic postcondition verifier is supplied; rejected or uncertain outcomes enter needs_review and cannot silently retry. This explicit runner does not replace the leased queue worker or enable production writes. Tests cover once-only scoped read dispatch and owner approval followed by verifier denial/review. Live acceptance and remote CI remain pending.

## Read-data preview service

Added internal `foundation.dry_run.preview`: owner authorization and organization pause are rechecked per step; reads require explicit account selection and use the scoped gateway; write steps return proposals without dispatch. Audit rows record proposal digests without provider data. It does not create workflow jobs or approve writes. Mock-based tests verify read-only dispatch, tenant/role denial and paused organization denial. This service is not yet exposed through the API/UI, has no preview usage reservation, and has not fetched live provider data. Those remain release blockers, not completed F37 acceptance.

Validation: 66 foundation tests (65 passed, one PostgreSQL skip) and 33 demo tests passed locally. Publication/CI and live acceptance remain pending for this increment. No phase advancement is claimed.

## Authenticated read-data preview endpoint

Added POST /v1/organizations/{org}/read-data-preview with strict existing WorkflowBody schema and owner authorization before provider construction. It is disabled by default (503); READ_DATA_PREVIEW_ENABLED=true is an explicit deployment opt-in, not a substitute for the missing usage reservation. Provider errors are sanitized. HTTP tests cover disabled state, viewer denial and mixed read/write preview with only a read dispatched. Local validation: 69 foundation tests (68 passed, one PostgreSQL skip), 33 demo tests passed. No live provider calls were made. UI, budget enforcement, reviewed live tool mappings, publication and remote CI remain pending; keep deployment disabled until those gates pass.

## Preview preflight and output bounds

Read-data preview now validates account presence for every read before dispatching any provider call. A later unbound read cannot trigger earlier billable reads before rejection. Aggregate serialized provider output is bounded to 256000 UTF-8 bytes; nonfinite JSON values are rejected. This output limit does not replace usage budgeting or provider timeouts. Regression checks cover no dispatch on a missing later account and combined-output rejection. Validation: 71 foundation tests (70 passed, one PostgreSQL skip), 33 demo tests passed. Live verification remains blocked by missing COMPOSIO_API_KEY, INTEGRATION_CONFIG and DATABASE_URL; publication and remote CI for local increments remain pending. Phase 4 stays open.

## In-flight pause and result evidence checks

Verified pause during an active provider call preserves that step's receipt, blocks the next step, and resumes without repeating completed work. Workflow result persistence now enforces the 64000-byte cap using UTF-8 bytes and rejects nonfinite JSON numbers; invalid evidence enters needs_review. Added regression checks for these cases. Validation: full foundation suite 83 tests (82 passed, one PostgreSQL-only skip), 33 demo tests passed. This total includes prior browser/network/sandbox groundwork. Publication and remote CI remain pending; no live provider verification or phase completion claimed.

## Approval-time integrity and authorization

Approval now revalidates canonical stored plans and verifies their persisted digest before granting authority. It also checks current submitter permissions and organization pause state at decision time, in addition to dispatch-time checks. Rejection remains available while paused. Tests cover paused approval denial and tampered plan rejection. Validation: 85 foundation tests (84 passed, one PostgreSQL skip), 33 demo tests passed. Live credentials remain absent; publication and remote CI for pending local increments remain outstanding. No phase completion or full-audit acceptance claimed.

## PostgreSQL publication correction

GitHub PostgreSQL CI found preview audit resource IDs exceeded the schema's 36-character limit. Preview audit references now use a deterministic organization-scoped UUID derived from the proposal digest; the returned approval/preview digest remains unchanged. This fixes actual PostgreSQL truncation rather than loosening schema validation. Local full suite passes; the corrected remote run must establish PostgreSQL acceptance.
