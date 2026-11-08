# Phase 2 — persistent sequential workflow increment

Migration 0003 adds organization-scoped workflows and ordered immutable action proposals. API accepts 1–20 steps, validates supported typed actions, reserves the existing per-job admission allocation and persists the entire plan. POST /v1/organizations/{org}/workflows takes instruction and steps plus Idempotency-Key. GET returns step-level plan, digest, status and result. Cross-organization membership/resource checks apply.

Internal `foundation.workflows.run(sessions, workflow_id, executor)` uses LangGraph to advance persisted steps. Completed steps are not repeated on resumed invocations. External effects occur outside database transactions; step.running and audit are committed before dispatch. A running step is never stolen or replayed. Recovery/reconciliation of an abandoned step must be an explicit operational workflow; this increment does not yet implement automatic crash detection for workflow steps.

Email sending, calendar cancellations and sandbox execution pause with an immutable digest and 15-minute approval deadline. Authenticated decisions are bound to organization/workflow/step/digest. POST .../workflows/{wid}/steps/{sid}/decision takes digest and strict boolean approved. Cancellation blocks future execution; an in-flight effect cannot necessarily be undone and its result is still recorded. Timeouts, oversized output and unverified results stop the sequence as needs_review. Step outputs are not automatically fed into later instructions, limiting implicit dataflow until typed references/policy are implemented.

The executor contract is an internal reviewed adapter that returns `verified: true` only after its provider-specific postcondition passes, and uses step ID for provider idempotency where supported. No public endpoint lets a user inject an executor or call run directly. Unit tests use controlled executors, not real providers. The CLI foundation worker still does not dispatch real tools: integration with job leases, budget enforcement, account ownership and provider registry remains open. Do not wire raw model/tool output into this verifier flag.

## Explicit remaining Phase 2 work

Conversational history, clarification state, natural-language multi-step planning with Gemini/Claude, typed inter-step outputs, recipient resolution, checkpoint/job-ledger integration, background dispatch, abandoned-step reconciliation, progress delivery, business memory, playbook versions and full policy classification remain open. This increment uses database rows as the sole durable progression authority; it does not pretend to have implemented a second LangGraph checkpointer. Existing budget allocation is not yet a verified whole-workflow cost ceiling.

Remaining Phase 1 browser login/invitation UI, storage delivery, budget settlement and operational controls carry forward. Full scope remains recorded in phase-0-scope-and-backlog.md. This is a tested execution increment, not a claim that all Phase 2 acceptance criteria are complete.

## Lease-expiry reconciliation

Recovery now marks abandoned queued/planning conversation turns and their planning conversation as needs_review. Nonterminal workflows and running steps are also placed into review without retrying external effects. Terminal completed/cancelled/rejected workflows are preserved. Regression coverage verifies abandoned planner visibility and idempotent recovery. Validation in this workspace: 86 foundation tests (85 passed, one PostgreSQL skip), 33 demo tests passed.

Workspace continuity blocker: this checkout began at 3c3fb60, lacking later dispatcher/heartbeat commits reported in chat. This isolated service recovery change must be reconciled with that newer work before publishing; do not overwrite remote or claim all later commits are present. Publication, remote CI and live-provider tests remain pending.

## Reconciled worker implementation

Restored unified queue dispatch, lazy integration loading, owner approval job wake-up, atomic lease renewal and periodic heartbeat into the checkout containing lease-expiry recovery. This supersedes the earlier continuity blocker for these worker features; missing unrelated branch increments still require comparison. The heartbeat is managed by a context manager and ownership is checked after planning and before every provider call. Tests exercise queue planning, approval pause/resume without replay, periodic renewal cleanup and permanent failure fencing. Validation: 90 foundation tests (89 passed, one PostgreSQL skip), 33 demo tests passed. Provider timeouts, PostgreSQL concurrency drills and full release acceptance remain open.

## Cancellation, edit wake-up and late-result fencing — 2026-11-08

Reconciled this checkout against private main `70bd775` using the repository tree and file hashes before modifying code. Cancellation now removes queued/approval-waiting jobs from claim eligibility and invalidates unused step approvals. Active calls keep their lease so a receipt can still be recorded, but subsequent steps remain cancelled. Editing a paused action wakes its job and presents the changed action for fresh review. API workflow mutations and worker transitions lock Job before Workflow, matching recovery's lock order.

Recovered steps cannot be completed by late provider responses: late receipts are retained as reconciliation evidence and the sequence remains in review. Dispatcher checks lease ownership after provider responses and respects cancellation/rejection or a new owner decision racing final dispatch bookkeeping. Tests cover queued cancellation, in-flight cancellation with receipt preservation, paused edit/review/resume, and recovery during an external call without replay.

Full local validation for this increment: 104 foundation tests (103 passed, PostgreSQL-only claim test skipped), 33 demo tests passed, dependency consistency and compilation passed. Remote PostgreSQL CI remains a separate publication gate. No live integrations or complete phase acceptance are established by these tests.
