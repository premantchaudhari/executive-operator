# Architecture and trust boundaries

Dashboard / Telegram → authenticated owner mapping → validated plan → capability gate → durable task → approval if required → bounded provider adapter → persisted result.

States: queued, awaiting_approval, running, completed, simulated, rejected, expired, awaiting_connection, needs_review. Approval records cannot be edited through the API. Rejecting, expiring or consuming approval prevents further execution. SQLite stores provider-independent task state; Composio owns OAuth credentials, Browserbase owns ephemeral browser sessions and E2B owns code execution.

Natural language is converted to exactly one allowlisted action. The model cannot select arbitrary tool slugs, credentials, client identities or provider endpoints. Prompts are guidance; action schema and executable tool allowlist enforce the boundary. Native write tools and sandbox execution always require owner approval.

The adapter is synchronous and held under a single-process lock. Long provider calls can delay other writes; this is acceptable for the initial owner-only pilot. Production queue workers need transactional claims, durable outbox delivery, provider idempotency, job leases and per-client authorization before scaling. Never simply add server workers.

Browser inspection is deliberately limited to read-only navigation. A screenshot checkpoint alone would not prove the next browser click is safe or unchanged. Version 2 needs a structured, short-lived action proposal bound to browser state and server-side verification before adding browser writes.

Live submission uses a LangGraph StateGraph with validate_plan and persist_and_route nodes. The compiled graph has no checkpointer and makes no claim of durable graph replay: the SQLite task engine is the durable boundary. Demo mode uses the same Python functions directly. Web PWA and Telegram are the supported channels.
