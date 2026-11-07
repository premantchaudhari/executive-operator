# Phase 0 — full-scope baseline and implementation backlog

Date: 2026-11-07. Status: repository audit and implementation planning complete; external feasibility and production acceptance remain open.

Audited local source commit: 4ce86788595185c9b139a109b2501452d2ee245a. Remote history differs because source was uploaded through GitHub's UI; match files, not local/remote commit IDs. No production-readiness assertion is made.

## Product contract

Build the complete business AI Operator discussed in this conversation. Four capability layers: (1) Python/LangGraph orchestration and messaging, (2) native SaaS tools and OAuth, (3) autonomous browser fallback, (4) E2B code and file execution. Commercial packages are separate from capability layers.

Primary interfaces: web PWA and Telegram. WhatsApp and n8n are excluded by the corrected architecture, not deferred missing features. Gemini and Claude are required planner adapters. Retain a separate, realistic, resettable fictional demo alongside live operation. Do not silently reduce full requirements to pilot limitations.

Payments, banking execution and OTP verification remain owner handoffs. External emails and calendar cancellations require exact-action approval. Browser consequential submissions require a reviewed proposal and state revalidation. Read-only bookkeeping and explicitly approved bookkeeping changes are supported scope; financial-service integration does not imply permission to move money.

Status legend: P = partial implementation; M = missing; U = implemented adapter or configuration but externally unverified. No feature is marked fully complete solely because demo tests pass.

## Feature traceability matrix

| ID | Requirement | Status / code evidence | Target phase |
|---|---|---|---|
| F01 | Owner/team login, sessions, account recovery, MFA/SSO integration path | M; server.py uses one shared bearer token | 1 |
| F02 | Organizations, membership roles, authorization and isolation | M; core.py owner field is not tenant isolation | 1 |
| F03 | Production API server, migrations and operational database | M; stdlib HTTP and ad-hoc SQLite schema | 1 |
| F04 | Separate demo/live deployments, credentials and data | P; two compose files, deployment separation needs verification | 1,10 |
| F05 | Conversational PWA, history and clarification | P; dashboard is structured form, no chat/history | 2,7 |
| F06 | Durable multi-step LangGraph plan/execute/pause/resume | P; orchestration.py has two nodes, no graph checkpointer | 2 |
| F07 | Gemini and Claude provider routing | U Gemini single-step REST; M Claude | 2 |
| F08 | Durable jobs, execution ledger, leases and crash recovery | P; SQLite states and process lock; no workers/leases/outbox | 1,2 |
| F09 | Native-first typed tool registry, discovery and risk policy | P; five hardcoded actions, no registry | 2,3 |
| F10 | Hosted Composio OAuth links and intent-driven connection detection | U Gmail/Calendar links; current task must be resubmitted | 3 |
| F11 | Scope profiles, multiple account selection, reconnect/revoke and ownership verification | P active-account filtering; M selection/revocation UI and lifecycle | 3 |
| F12 | Gmail search/read/draft/reply/send, attachments and thread identity | U read/send adapter only; selected tool schemas unverified | 3 |
| F13 | Calendar search/create/update/cancel, attendees and timezones | U cancellation only | 3 |
| F14 | Google Drive search/read/upload/share within authorized scope | M | 3 |
| F15 | Sheets read/write/append, types, ranges and concurrency | M | 3 |
| F16 | Slack authorized search/read/post | M | 3 |
| F17 | HubSpot contacts/deals/notes and approved updates | M | 3 |
| F18 | QuickBooks read and approved bookkeeping workflows, no payment execution | M | 3 |
| F19 | Direct Google/Microsoft OAuth alternative where required | M; implement adapter interface and provider-specific need assessment | 3 |
| F20 | Exact-action approvals, immutable versions and policy enforcement | P; basic persisted approval, expiry and one-time consumption | 2,4 |
| F21 | Recipient/account/resource resolution and ambiguity handling | M beyond basic email syntax | 2,4 |
| F22 | Financial/OTP handoff across native, browser and sandbox paths | P no such native tool today; cross-layer policy missing | 4,5,6 |
| F23 | Browserbase + Stagehand/computer-use browser operation and fallback | U read-only Browserbase/Playwright; M actions/agent fallback | 5 |
| F24 | Protected session reuse, login handoff and session revocation | M | 5 |
| F25 | Screenshot proposal, owner review, revalidation and consequential browser writes | M | 5 |
| F26 | Browser downloads/uploads, portal playbooks and health checks | M | 5 |
| F27 | E2B Python/shell, packages and enforced resource budgets | U Python adapter, template/lifetime/network config; M shell/package policies and RAM verification | 6 |
| F28 | Uploaded CSV/Excel transformation and controlled scraping | M | 6 |
| F29 | Private object storage, scanned files, output artifacts and expiring downloads | M | 1,6 |
| F30 | Mobile PWA install, notifications, timeline and approval/connection inbox | P manifest/worker; M complete product UI and device QA | 7 |
| F31 | Telegram chat, progress, files, commands and inline approvals | U inbound text adapter; M remaining features | 7 |
| F32 | Scheduling, recurring jobs, timezone/DST and missed-run policy | M | 8 |
| F33 | Durable notifications, webhook deduplication and replay protection | P request deduplication; M delivery outbox and reconciliation | 2,7,8 |
| F34 | Usage ledger, cost reservations, budgets and concurrency limits | P task count cap only | 1,9 |
| F35 | Packages, setup fees, retainers, invoicing/billing and maintenance scope | M; blueprint estimates are not measured COGS | 9 |
| F36 | Client procedures/preferences with source, permissions, expiry and deletion | M | 2,7 |
| F37 | Real-data preview/dry run separate from fictional demo | M | 4,10 |
| F38 | Reusable playbooks and versioned workflow releases | M | 2,10,11 |
| F39 | Evidence-based completion and verified outcome analytics | M; tool success currently treated as completion | 2,9 |
| F40 | Exception inbox, pause/cancel/kill switch and operator recovery | P needs_review state only | 2,4,7 |
| F41 | Guided realistic demos, reset, all capability layers and sales scenarios | P fictional inbox/action previews only | 10 |
| F42 | Monitoring, alerts, audit export and security observability | P local audit table; HTTP logging disabled | 1,11 |
| F43 | Encryption, retention, deletion, backup/restore and incident response | P backup helper; M full lifecycle | 1,11 |
| F44 | Dependency lock, CI integration/E2E/load/security tests and image scans | P core CI only; live deps installed locally but unpinned | 1,11 |
| F45 | HTTPS deployment, staging, rollback and controlled paid pilot | M | 11 |

## Concrete audit findings and backlog

| Ticket | Severity | Finding / evidence | Required change and acceptance |
|---|---|---|---|
| R01 | Critical before multiple clients | Shared API token and server-configured owner in server.py | Authenticated organization/member principal; cross-tenant API/job/file/connection tests return no foreign data |
| R02 | Critical before autonomous loops | External data can influence future plans; no information-flow enforcement | Tool-level destination/scope policy; malicious email/web/file fixtures cannot authorize tools or exfiltrate content |
| R03 | High | core.py holds process lock during provider calls; no durable workers | Queue jobs transactionally, lease workers, isolate provider side effects; restart tests never blindly repeat a write |
| R04 | High | Task state and audit changes are separate autocommit statements | Atomic state transitions plus execution ledger/outbox; fault injection leaves a coherent recoverable record |
| R05 | High | orchestration.py persists requests before task cap; failed planner calls uncapped | Admission control and budget reservation before planning; cap planner failures and concurrent work |
| R06 | High | Same natural-language idempotency key is cached, but no global external-action guarantee | Per-step action key, provider idempotency/reconciliation, uncertain outcome state; timeout-after-send produces no automatic resend |
| R07 | High | Any provider exception becomes needs_review without failure classification | Distinguish configuration/auth/validation/transient/uncertain-write errors; redact diagnostics and surface appropriate recovery |
| R08 | High | Browser hostname routing comment overstates network protection | Egress-level private-network denial, DNS/redirect/WebSocket coverage and trusted domain policy; block metadata/internal targets |
| R09 | High | E2B RAM allocation is assumed from template; output not bounded; cleanup may mask original failure | Verify allocation, explicit code/request deadlines and output quotas; preserve primary outcome while recording cleanup failures |
| R10 | High | Only exact native action whitelist enforces current payment boundary | Central action/resource/disclosure policy for native, browser and sandbox; bookkeeping actions classified separately |
| R11 | High | Telegram webhook processes work synchronously and then sends notification | Acknowledge after durable enqueue, outbox delivery; unsupported updates handled without endless retries |
| R12 | High | No OAuth verification/scope/owner lifecycle matrix | Document auth config owner, scopes, consent/verification requirements and test revocation per integration |
| R13 | High | No tool-specific result validation/readback | Typed output and business postcondition checks; HTTP success alone never claims verified completion |
| R14 | High | HTTP auth rate limits missing, CSP allows inline script/style, bearer login unsuitable for teams | Production framework, secure session design, CSRF policy, CSP migration, request IDs and ingress/auth limits |
| R15 | Medium | Queued/running recovery is coarse and no cancellation while synchronous call runs | Persist step state, cancellation checkpoints, timeout/cleanup semantics; cancel blocks future actions |
| R16 | Medium | Demo returns synthetic outputs; no reset or complete walkthrough | Isolated fixtures and deterministic reset, guided scenarios and persistent simulation labels |
| R17 | High | requirements-live.txt unpinned, Docker builds not executed | Resolve and commit tested lock; clean build/check/import/contract tests and vulnerability review |
| R18 | High | Logs off; local audit not tamper-evident; sensitive plans retained indefinitely | Structured redacted logs, metrics, retention and protected audit export; prove no secrets in logs |

## Architecture decisions for Phase 1

Proposed implementation baseline (recorded decisions for the next phase, not already implemented):

- Python API and LangGraph remain; use a production ASGI framework/server in place of the stdlib HTTP server.
- PostgreSQL with migrations is the operational system of record for organizations, members, conversations, workflows, steps, approvals, jobs, outbox, usage and artifact metadata.
- PostgreSQL-backed LangGraph checkpoints persist graph progress. Business tables control authorization/approval/side-effect execution. Checkpoints may not independently authorize a write.
- Begin with a PostgreSQL-backed durable job queue and leases to avoid an unnecessary second queue datastore. Reassess Redis only against measured needs.
- API processes never run long provider workflows inline. Workers claim jobs, execute bounded steps and emit persisted progress events.
- Prefer mature identity/session infrastructure over designing password/MFA cryptography. Auth provider selection stays replaceable; email/password recovery and team-role acceptance are mandatory if chosen.
- Private object storage holds artifacts; database metadata carries tenant owner, classification, retention, hash and access policy. Reauthorize every download request before issuing a short-lived link.
- Demo and live use separate deployment projects, credentials, databases and object-store namespaces. Sharing application code does not permit sharing customer records.
- Native tools use a typed registry: arguments/results, scopes, tenant/account owner, effect class, retry semantics, verifier, deadline and expected cost. Browser and code adapters follow the same policy boundary.
- Never advertise exactly-once cross-provider effects. Use durable intent, bounded retries, idempotency where available and explicit reconciliation elsewhere.

## Trust and data flow

PWA/Telegram -> verified principal/channel mapping -> admission and budget -> conversation/plan -> durable job -> per-step authorization -> connection selection -> approval if required -> provider -> postcondition verification -> ledger/result/outbox -> authenticated owner view.

Untrusted sources: chat text, emails, attachments, websites, tool responses, generated code and callbacks. These are data, never permission grants. Trusted authorization inputs: authenticated membership, server policies, provider-confirmed account ownership and immutable owner decisions. Secrets stay in managed credentials/vault; worker logs, model prompts, artifacts and sandbox environments must not receive general application secrets.

Browser profiles and OAuth tokens are credentials. Approval screenshots are sensitive client data. Telegram is an optional channel, not the sensitive-document store. External data shown in the UI must be rendered as data with output escaping.

## Ordered implementation phases and exits

| Phase | Backlog | Exit gate |
|---|---|---|
| 0 | This audit, scope matrix, risks, acceptance scenarios and feasibility register | All agreed capabilities traceable; unverified requirements labelled |
| 1 | F01–04,F08 foundation,F29 storage foundation,F34 budgets foundation,F42–44 baseline | Two organizations isolated; migrations reversible/tested; durable job lease; private artifact authorization; no demo/live crossover |
| 2 | F05–09,F21,F33,F36,F38–40 | Persisted multi-step workflow pauses/resumes after restart; ambiguity clarified; partial/uncertain outcomes visible |
| 3 | F10–19 | Each of eight named integrations has a reviewed action/scope matrix, contract tests and controlled live acceptance |
| 4 | F20–22,F37,F40 | Exact-action approval, edits invalidate it, expired/replayed/wrong-user decisions fail; kill switch blocks future effects |
| 5 | F23–26 | Portal workflow performs approved actions with screenshot/state binding, isolated sessions and verified postconditions |
| 6 | F27–29 | Uploaded report -> sandbox processing -> private downloadable artifact, with measured resource limits and egress controls |
| 7 | F30–31,F33,F36,F40 | Full PWA/Telegram journey, authenticated approvals/files, durable notifications and mobile QA |
| 8 | F32–33 | Restart-safe schedules, timezone/DST/misfire policy and duplicate delivery tests |
| 9 | F34–35,F39 | Usage/cost reconciliation, hard budgets, package limits and bounded maintenance billing |
| 10 | F04,F37–38,F41 | Resettable guided demonstrations cover complete workflows without client data or real effects |
| 11 | F42–45 | Locked dependencies, E2E/failure/load/security evidence, restore drill, staged rollout and paid pilot acceptance |

Phase numbering preserves the agreed roadmap. Phase 4 controls are a dependency: every Phase 3 write remains disabled until those controls pass. Likewise artifact isolation precedes Phase 6 uploads. No feature is removed because of dependency order.

## Acceptance suite to implement with the corresponding phase

A01: Client A cannot read/approve/execute/download/reconnect any Client B resource, including guessed IDs and worker job manipulation.

A02: Find the client's latest email -> resolve HubSpot record -> update authorized tracking sheet -> draft reply -> review/edit -> approve -> send -> verify result. Repeat after worker restart and after duplicate webhook delivery. Ambiguous contact names pause for clarification.

A03: Download report from approved authenticated portal -> sandbox CSV/Excel processing -> private output link. Verify wrong-tenant access, expired links, malicious file, excessive output, blocked network target and cleanup.

A04: Owner rejects email; no email is sent. Editing recipients/body/attachments/account after approval invalidates it. Duplicate/expired approval cannot execute twice.

A05: Provider commits write but response times out. System shows uncertain state, queries evidence where available, and never silently resends. For a partial workflow, report every completed/failed/uncertain step and any possible compensation.

A06: OAuth revoked mid-workflow. Pause safely, reconnect correct account, revalidate intent/approval, resume only eligible steps. Never substitute another connected account.

A07: Malicious instructions in email/web/CSV cannot select another tenant, leak credentials, bypass approval, alter policies or send files to an unauthorized destination.

A08: Scheduled task survives restart; test timezone change, DST, downtime, cancellation and duplicate scheduling. Owner receives one intended notification through durable delivery semantics.

A09: Per-task budget exhausted during planning/browser/code retries. Stop safely, retain verified progress and show actual cost versus reservation without starting more effects.

A10: Global/client kill switch prevents new side effects and cancels future steps; active provider calls are reported honestly if cancellation cannot undo them.

A11: Demo reset restores fixtures and never touches live credentials/storage. Real-data preview remains read-only and separately labelled.

A12: Backup restore, schema upgrade and rollback run against representative data; provider-side actions are reconciled rather than assumed undone by database rollback.

## External feasibility register (not a coding blocker)

| Item | Required evidence | Current status |
|---|---|---|
| Gmail/Drive OAuth public onboarding | Exact scopes, OAuth-app owner and applicable verification/security assessment path | Open; previous official-doc review identified restricted Gmail read scopes |
| Composio actions | Selected dated toolkit versions and exact schemas for eight integrations | Open; SDK installed, no real connected accounts tested |
| Claude/Gemini | Enabled model IDs, structured/tool output contracts, usage and data handling configuration | Open; no paid model calls made |
| Browserbase/Stagehand | Session persistence, recording retention, account isolation, portal acceptance and egress behavior | Open; no managed sessions tested |
| E2B | Provider-reported resource allocation, runtime/network limits and private artifact flow | Open; SDK create/run_code signatures inspected locally only |
| Identity and hosting | Chosen auth provider, domains, secret storage and deployment access | Open; no changes to ShaadiMint or Oracle host authorized/performed by this audit |
| COGS | Measured tokens, minutes, seconds, maintenance and failed-attempt invoices | Open; original prices remain assumptions |

Prior official references: https://developers.google.com/workspace/gmail/api/auth/scopes ; https://docs.composio.dev/docs/tools-direct/executing-tools ; https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph ; https://e2b.dev/docs/sdk-reference/python-sdk/v2.5.0/sandbox_sync . External requirements must be rechecked when their integration is implemented; this document does not replace live contract validation.

## Evidence from this audit

- 33 existing tests passed under the installed live-SDK virtual environment.
- `pip check` reported no broken requirements. This is dependency consistency, not a vulnerability scan or reproducible lock.
- E2B SDK supports explicit create timeout/network parameters and run_code timeout/request_timeout parameters; current adapter does not supply the latter deadlines.
- Previous stubbed-provider LangGraph routing and backup-content checks passed; no live external provider or complete browser/mobile workflow was validated.
- Phase 0 makes no runtime behavior change and does not claim to complete Phases 1–11.

Next executable work: Phase 1 identity/tenant schema, production API, migrations and durable job foundation. Continue independent implementation while provider credentials/verification remain pending; never mark externally unverified work complete.
