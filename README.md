# Executive Operator · v0.1.1

Private pilot for a business owner to delegate bounded tasks and approve exact external changes. Python 3.12+, no dependencies for the demo. Not a production multi-tenant SaaS.

## Run in five minutes

```bash
# Linux / macOS, from this repository
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(32))'
# Put the generated value into OPERATOR_API_TOKEN in .env.
# Load only your own trusted .env file:
set -a
. ./.env
set +a
python -m operator_app.server
```

Open http://127.0.0.1:8080 and enter your token. Keep `OPERATOR_MODE=demo` initially. Choose a task template, edit arguments and create the task. An email waits for approval; approve or reject it to exercise the state machine. All demo results explicitly say no external action occurred.

PowerShell alternative:

```powershell
$env:OPERATOR_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:OPERATOR_MODE = "demo"
python -m operator_app.server
# Use the token from $env:OPERATOR_API_TOKEN in the dashboard.
```

## Implemented scope

| Capability tier | Available actions |
|---|---|
| 1 · Assistant | Read Gmail through a configured native tool; Gemini intent planning |
| 2 · Native operator | Gmail send and calendar cancellation, both explicitly approved; Composio connection links |
| 3 · Browser operator | Browserbase / Playwright read-only inspection of administrator-approved HTTPS hosts |
| 4 · Sandbox operator | E2B Python execution after review of exact code; output captured as text |

These are capability gates, not subscription billing plans. All higher tiers include lower ones. `OPERATOR_TIER` defaults to 4. Demo mode simulates every action. Tier 1 still requires the relevant connection in live mode.

- Owner-only web PWA shell (online only), bearer authentication and persistent SQLite task records.
- Telegram inbound webhook secret verification and private-chat sender allowlist.
- Single-step Gemini JSON planning; unsupported actions and malformed parameters rejected.
- Approval bound to the persisted exact action, valid for 15 minutes, consumed once.
- Idempotency keys, rolling daily task cap, state transition audit table.
- Ambiguous provider failures and interrupted tasks become `needs_review`, never automatically retried.
- Composio connection links returned as `awaiting_connection`; authorize then submit a fresh task for fresh approval.

## Explicit v1 limits

WhatsApp, Slack, Drive, Sheets, HubSpot, QuickBooks, arbitrary browser clicks, browser screenshots/approval continuations, persistent browser login sessions, file upload/download buckets, scheduling, subscription billing, monetary usage metering, and multi-step agent loops are **not implemented**. Telegram approvals happen in the dashboard, not inline chat buttons. Gemini is the only live planner adapter; Claude is a future integration. Live submissions use Python/LangGraph; n8n is excluded. LangGraph routes validated plans into the explicit SQLite state machine; approvals remain durable there.

The host never executes model-generated code. E2B is the only code execution path. Browser writes, payments, banking and OTP verification have no executable tool path. Even internal emails require approval in this pilot. Browser and sandbox outputs are data; they are not fed back into an autonomous planning loop.

Live SDK integrations are implemented but **not live-tested**. They require credentials, optional dependencies, reviewed Composio tool schemas and pinned tool versions. Do not sell an unrestricted autonomous service based on the demo.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q operator_app
```

See [Provider setup](docs/providers.md), [Deployment](docs/deployment.md), [Architecture](docs/architecture.md) and [Validation](docs/validation.md).

## Create the private GitHub repository

If working from the supplied source bundle and GitHub CLI is installed/authenticated:

```bash
git init -b main
git add .
git commit -m "Build Executive Operator private pilot v0.1.1"
gh repo create executive-operator --private --source=. --remote=origin --push
gh repo view --json nameWithOwner,isPrivate,url
```

Verify `isPrivate` is `true`. Never upload `.env`, credentials, client data or the SQLite database. No public license is granted; see LICENSE.

## Separate demonstration and live instances · v0.2 development

Keep the demonstration on port 8080 with `.env` (`OPERATOR_MODE=demo`) and the original compose file. Its fictional inbox and action previews demonstrate approvals without sending anything.

For live setup, copy `.env.example` to `.env.live`, set a **different random owner token**, configure your providers, then run:

```bash
docker compose -p operator-live -f compose.live.yaml up -d --build
```

The live instance uses port 8081 and a separate database volume. Both ports bind to localhost. Add HTTPS reverse proxy routing before remote use. In the dashboard, **Check setup** reports missing configuration without exposing secret values. “Configured” is not proof OAuth or provider execution works. Live startup refuses an unconfigured planner.

The live image includes SDK dependencies; these are not yet locked or provider-contract verified. This is an implementation step toward the working pilot, not a claim of production readiness. Account credentials and controlled end-to-end provider tests remain necessary. Do not replace an existing demonstration database with live client data.
