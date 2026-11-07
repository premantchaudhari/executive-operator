# Phase 2 — conversations and clarification increment

Migration 0004 persists organization-scoped conversations and turns linked to reserved jobs. POST /v1/organizations/{org}/conversations creates a conversation; POST .../{cid}/messages accepts instruction plus Idempotency-Key and returns a durable turn ID; GET .../{cid} returns history. The API never calls a model inline.

The internal planning command is `python -m foundation.planning_worker --turn-id <id>`. It atomically claims a queued turn, rechecks submitting-member authorization and invokes the configured model outside the database transaction. PLANNER_PROVIDER selects gemini or claude. Gemini requires GEMINI_API_KEY/GEMINI_MODEL; Claude requires ANTHROPIC_API_KEY/CLAUDE_MODEL. Model IDs are deployment configuration. No credentials are committed.

Planner output is either a bounded clarification question or a validated list of 1–20 currently supported steps. Clarification persists in history; a subsequent answer can be planned with preceding turns. Invalid output or provider uncertainty becomes needs_review. A planned turn creates the immutable workflow under the same job/budget reservation, without double charging admission. No external action executes during planning. Duplicate turn submissions use the stored response and never invoke the planner again. One outstanding planning turn per conversation avoids out-of-order conversational context.

The adapters currently support the existing five typed actions only. Missing integrations request clarification/unsupported-service handling instead of fabricating execution. Full integration scope remains Phase 3. These REST adapters have not been exercised with real credentials. The 60k-character context cap is a rejection boundary, not automatic summarization; messages and retained model output still require the broader retention/privacy controls.

## Remaining integration work

The one-turn command is an explicit dispatcher, not a continuously running job consumer. Do not run the generic foundation worker against conversation jobs: its placeholder needs_review behavior is not a planner dispatcher. Unify job leases, conversation claims, crash reconciliation and workflow resume in the next increment. A planning turn abandoned after claim requires explicit review; the system does not blindly retry a possibly billable call.

Typed references between steps, recipient-directory resolution, dialogue UI, streaming progress, automatic history summarization, persistent graph checkpoint design, playbook/business-memory workflows and whole-workflow spend enforcement remain open Phase 2 acceptance requirements. Original Phase 1 open items carry forward. No phase completion is claimed by this increment.
