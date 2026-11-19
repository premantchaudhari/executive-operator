# Executive Operator

**Approval-first automation research and working owner-only demo, written in Python.**

Executive Operator explores a practical problem: how can an assistant execute bounded business tasks while keeping the human owner in control of the precise side effects?

> **Status: development / portfolio preview.** This is not an unrestricted autonomous agent, a production-ready multi-tenant SaaS or a verified live integration service. The repository currently remains private and proprietary; see [LICENSE](LICENSE).

## Highlights

- **Exact-action approvals:** a pending external action must be reviewed; edits invalidate authorization and expired or consumed approvals cannot be reused.
- **Failure-aware execution:** idempotency, audit transitions and explicit `needs_review` handling for ambiguous outcomes help prevent accidental repeated writes.
- **Bounded capability access:** allowlisted tools, model-plan validation and safe demo mode distinguish planning from authorization.
- **Two code tracks:** a runnable owner-only SQLite pilot in `operator_app/`, and a larger PostgreSQL/SQLAlchemy foundation in `foundation/` with Alembic migrations.
- **Integration verification research:** controlled post-action readback for Gmail, HubSpot contacts and Google Sheets, with uncertain results retained for review.
- **Tests and CI:** dedicated pilot and foundation suites; see [implementation evidence](docs/progress.md).

### Architecture

```text
Owner / dashboard / Telegram
          |
   authenticated request
          v
       planner
          |
   schema + policy checks
          v
  persisted proposed action
          |
    exact owner approval
          v
  bounded provider adapter
          |
 verified result or review
          v
   audited task transition
```

The pilot persists approvals and task state in SQLite. The separate foundation develops tenant-aware APIs, workers, connection lifecycle handling, and verified write contracts. **Do not assume the foundation's planned or partially implemented features are available from the pilot dashboard.**

## Try the owner-only demo

Requires Python 3.12+; the local demo uses the standard library and **does not send external emails or make external changes**.

### macOS / Linux

```bash
git clone https://github.com/premantchaudhari/executive-operator.git
cd executive-operator
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste the generated random value as OPERATOR_API_TOKEN in .env
set -a; . ./.env; set +a
python -m operator_app.server
```

### Windows PowerShell

```powershell
$env:OPERATOR_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:OPERATOR_MODE = "demo"
python -m operator_app.server
```

Open **http://127.0.0.1:8080**. Enter the bearer token, create a fictional task, review its exact action, and approve or reject. Demo output is simulated and must not be mistaken for an actual provider action.

**Never use the example token in `.env.example` as a real credential.** Bind the demo to localhost. Provider settings and live execution are separate and require explicit configuration and controlled testing.

## Implementation versus roadmap

| Area | Status | Evidence / limits |
| --- | --- | --- |
| Single-owner demo, local task history | Implemented | `operator_app/`, `tests/` |
| Validated plans, approval expiry, idempotency, audit states | Implemented in pilot | Mock/demo scenarios are not live-provider acceptance |
| Gmail / Calendar / Composio adapters | Coded; live acceptance incomplete | Provider schemas and accounts must be configured and tested |
| Read-only browser and E2B primitives | Limited implementations | Not arbitrary browser action or unrestricted execution |
| Tenant-aware PostgreSQL foundation | In development | `foundation/`, `migrations/`, `tests_foundation/` |
| CRM / Sheets write verification | Implemented as opt-in contracts; live-unverified | Exact-account postconditions, no blind retries |
| Multi-tenant production SaaS, general workflows, billing, scheduling | Incomplete / planned | Do not deploy or market as finished |

The dated engineering status and outstanding gates are in [docs/progress.md](docs/progress.md). The [production release gate](docs/production-release.md) documents what remains unverified.

## Run the checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q operator_app
```

The larger foundation has additional dependencies and a separate CI workflow. Consult [foundation setup](docs/phase-1-foundation.md) and [the foundation CI workflow](.github/workflows/foundation.yml). A previously recorded result (November 8, 2026) reported 148 passing foundation tests, one PostgreSQL-dependent skip, and 33 demo tests; this is historical evidence, **not a fresh test run**.

## Technical documentation

- [Architecture and trust boundaries](docs/architecture.md)
- [Development progress and incomplete work](docs/progress.md)
- [Provider setup](docs/providers.md)
- [Live vs demo deployment](docs/deployment.md)
- [Production release and safety gate](docs/production-release.md)
- [Testing notes](docs/validation.md)
- [Responsible disclosure and publication review](SECURITY.md)
- [Contributing guidance](CONTRIBUTING.md)

## Licensing and publication

This repository **is not currently offered under an open-source license**. Its existing [LICENSE](LICENSE) reserves rights. Documentation preparation is not permission to redistribute the code.

Before any public release: decide whether to open-source the whole implementation or publish a separate demo/core; audit all files and Git history for credentials and confidential data; verify third-party rights; then add an appropriate open-source license to the exact code being released. See [SECURITY.md](SECURITY.md).

Built as an engineering and research showcase. No claims of autonomous performance superiority, production security certification, or tested real-world customer outcomes are made.
