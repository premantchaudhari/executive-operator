# Live provider setup

Use one deployment per client for v1. Do not reuse another client's identity or token. Keep credentials in deployment environment settings, not chat or Git.

1. Create a project-local virtual environment and install optional live SDKs using `pip install -r requirements-live.txt`. This file is intentionally not a verified dependency lock: resolve compatible versions, record a lock and complete integration tests before deploying live. The demo Docker image intentionally contains no live SDKs.
2. Set `GEMINI_API_KEY` and `GEMINI_MODEL` to a model enabled for your account. No historical model ID is hardcoded. Set `OPERATOR_MODE=live` only when ready to make real calls.
3. In Composio create Gmail and Google Calendar auth configurations with the minimum necessary scopes. Set their IDs and `COMPOSIO_API_KEY`. Hosted connection flow uses `connected_accounts.link`, not the old entity/initiate API. A provider-confirmed ACTIVE account for the exact owner and auth configuration is required; a callback is never trusted as proof.
4. Configure reviewed Composio tool slugs and versions in `GMAIL_READ_TOOL`, `GMAIL_SEND_TOOL`, `CALENDAR_CANCEL_TOOL` and their `_VERSION` fields. Verify your chosen version's input schema accepts the exact v1 fields: Gmail read `{query}`, Gmail send `{recipient_email, subject, body}`, cancellation `{event_id}`. If it differs, implement and test an explicit mapping in providers.py; do not pass arbitrary model-selected tool names or tools. Missing configuration fails closed.
5. Browserbase requires `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, optional Playwright Python SDK and `BROWSER_ALLOWED_HOSTS` as exact comma-separated administrator-reviewed public hostnames. Include only trusted hosts; all requests (including redirects and subresources) are filtered. Do not allow private-address hostnames or domains controlled by untrusted users. No stored cookies or persisted login contexts: cookies are credentials, not non-sensitive state. Egress-level private network denial remains a production requirement.
6. E2B requires `E2B_API_KEY` and its code interpreter SDK. Review exact code before approval. A sandbox has a 60-second lifetime and is killed in a finally block. Only stdout/stderr is returned; arbitrary artifact publishing is deferred.
7. For Telegram, configure `TELEGRAM_BOT_TOKEN`, a random `TELEGRAM_WEBHOOK_SECRET` and your numeric `TELEGRAM_OWNER_ID`. Expose `/webhooks/telegram` over HTTPS and call Telegram `setWebhook` yourself with that URL and matching `secret_token`. Only private messages from that sender are accepted. Do not expose the admin token to Telegram. Any write remains pending in the dashboard.

## Pilot acceptance checklist

- Connect/revoke/reconnect a test Gmail account; ensure inactive accounts cannot execute.
- Confirm each tool schema/version with test data; send to a controlled mailbox only.
- Confirm a new task is needed after connection, with fresh approval for writes.
- Test revoked OAuth, browser timeouts, E2B failures and restart during a write.
- Confirm webhook retries use the same task and do not repeat provider execution.
- Verify Browserbase sessions are released and E2B sandboxes are killed.
- Measure provider invoices for a representative workload before quoting fixed usage.

## Official references consulted

- https://docs.composio.dev/docs/auth-configuration/migrating-initiate-to-link
- https://docs.composio.dev/reference/sdk-reference/python/connected-accounts
- https://ai.google.dev/api/generate-content
- https://github.com/e2b-dev/E2B

Browserbase and Composio SDK contracts still require account-specific live validation. Optional SDK versions are not claimed to have been verified by the offline tests.

## Corrected v0.1.1 baseline

The primary interfaces are the web PWA shell and Telegram. WhatsApp is excluded from this product baseline. No Meta policy interpretation is needed to enable either supported interface.

Live task submission now requires Python LangGraph (`validate_plan` → `persist_and_route`). The SQLite state machine remains the authority for approval and execution, with no n8n dependency. The dependency-free demo exercises the same prepare/persist functions without LangGraph. Graph runtime integration needs installation and live-environment validation.

Composio remains the selected OAuth adapter; direct Google/Microsoft OAuth is an alternative architecture, not an implemented integration. Configure separate auth configs with least-privilege scopes: Gmail read-only for inbox access, send-only for mail sending, and narrowly scoped calendar access where supported. Because this pilot uses one Gmail config for both actions, a read-only deployment must omit the send action by capability tier and use a read-only auth config. Review the actual provider consent screen and deny broad Drive/full-mailbox scopes unless a specific supported task requires them. OAuth scope configuration is an operator deployment responsibility, not a guarantee made by the SDK.

E2B now requires `E2B_TEMPLATE_ID` and never falls back to an unreviewed default template. Build an E2B code-interpreter-compatible template with **1024 MiB provider-enforced RAM**; resource allocation is configured at template build time, not as an invented `Sandbox.create(memory=...)` argument. Confirm the provider template's allocation before enabling live code. V1 does not remotely verify this allocation. The sandbox lifetime is fixed at 60 seconds, network access is disabled, and no host directory mounts, credential forwarding or local subprocess execution are provided. `finally` attempts cleanup; provider expiry is the backstop if the request fails.

The PWA provides a manifest, standalone display and a network-only service worker. It requires HTTPS (or localhost), keeps tokens in tab memory and caches no private data. Offline tasks and push notifications are not supported. Installation behavior and icons still need testing on target Android/iOS browsers.
