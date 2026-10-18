# AI BD Copilot

[![CI](https://github.com/nayan-letscreate/ai-bd-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/nayan-letscreate/ai-bd-copilot/actions/workflows/ci.yml)

An assistant for business-development teams. Give it a lead (a name, a company, and optionally an e-mail and website)
and it researches the company, scores it against your ideal customer profile, drafts a first-touch e-mail, syncs the
contact to HubSpot, and asks a person to approve the draft in Slack or in a built-in dashboard.

**A human always decides.** Nothing is e-mailed without explicit approval, and real sending is switched off by default.

## What you get

* **Research, score and draft in one flow.** Web research (Tavily) and Claude produce a short brief, a 0-100 fit score
  with a written rationale, and a draft under 120 words that cites one concrete detail.
* **A review desk.** A dashboard where reps read the research, edit the draft, then approve, reject or retry. Slack
  buttons are optional.
* **Lower API bills.** A small built-in ML model (the *triage model*) screens out leads that are almost certainly poor
  fits **before any paid call is made**. It starts in a safe shadow mode and only skips when its measured track record
  supports it. See [docs/TRIAGE_ML.md](docs/TRIAGE_ML.md).
* **Works with zero accounts.** Every integration is optional. Without keys it runs in a clearly labelled mock mode,
  so you can try the whole flow before connecting anything.
* **Built to survive production.** A durable database-backed job queue (restarts never lose a lead), automatic retries
  with backoff, duplicate detection, rate and spend limits, JSON logs with secret redaction, and a security review.

```
 POST /leads · CSV upload · HubSpot "contact created" webhook
        │   validate → de-duplicate → save
        ▼
   leads table (PostgreSQL or SQLite)  ◄── durable queue
        │   worker threads claim jobs safely
        ▼
   triage (free)  ──poor fit──►  screened out (one click to override)
        │
        ▼
   research → score → draft → HubSpot → Slack ──► awaiting approval
                                                        │ approve
                                                        ▼
                                                 sent by SMTP (or dry run)
```

## Quick start (about five minutes, no accounts needed)

You need **Python 3.12 or newer** and Git.

**Windows (PowerShell)**

```powershell
git clone https://github.com/nayan-letscreate/ai-bd-copilot.git
cd ai-bd-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.in
copy .env.example .env
```

**macOS / Linux**

```bash
git clone https://github.com/nayan-letscreate/ai-bd-copilot.git
cd ai-bd-copilot
python -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.txt
cp .env.example .env
```

Open `.env` and set one line, so the dashboard has a key to ask for:

```
APP_API_KEYS=dev-key-change-me-0123456789
```

Start it and open the dashboard:

```bash
python -m uvicorn app.main:app --reload
# then visit http://localhost:8000/dashboard and enter the key
```

Add a test lead (PowerShell first, then curl):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/leads `
  -Headers @{ "X-API-Key" = "dev-key-change-me-0123456789" } -ContentType "application/json" `
  -Body '{"name":"Priya Shah","company":"WanderWorks Travel","email":"priya@wanderworks.example"}'
```

```bash
curl -X POST localhost:8000/leads -H "X-API-Key: dev-key-change-me-0123456789" \
  -H "content-type: application/json" \
  -d '{"name":"Priya Shah","company":"WanderWorks Travel","email":"priya@wanderworks.example"}'
```

A few seconds later the lead appears under **To review**, marked as mock data. Open it, edit the draft, and click
**Approve (dry run)**. Nothing is e-mailed.

## Connect real services

Add keys to `.env` one at a time, then verify them (a few tiny billable calls, nothing is written anywhere):

```bash
python scripts/live_check.py --confirm
```

| To enable | Set |
|---|---|
| Real research and drafting | `ANTHROPIC_API_KEY`, `TAVILY_API_KEY` |
| HubSpot sync | `HUBSPOT_TOKEN` (contacts read/write; add `crm.schemas.contacts.write` so the two custom properties are created for you) |
| HubSpot intake webhook | `HUBSPOT_CLIENT_SECRET`, `PUBLIC_BASE_URL`; subscribe to `contact.creation` and point it at `POST /webhook/hubspot` |
| Slack, notify only | `SLACK_WEBHOOK_URL` |
| Slack with Approve/Reject buttons | `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SLACK_SIGNING_SECRET`, `SLACK_APPROVER_IDS` (empty means nobody can approve from Slack) |
| Real e-mail | `OUTREACH_SEND_ENABLED=true`, `SMTP_*`, and `OUTREACH_FOOTER` (unsubscribe line and postal address; required) |

Every setting is documented in [.env.example](.env.example).

## Deploy

* **Render:** `render.yaml` is a Blueprint (web service, PostgreSQL, generated API key, health check). In Render choose
  *New → Blueprint*, pick the repository, then set the secrets marked `sync: false`.
* **Any Docker host:** the image runs as a non-root user and honours `$PORT`.
* **Production checklist:** `APP_ENV=production`, a strong `APP_API_KEYS` (24+ characters; the app refuses to start
  otherwise), PostgreSQL in `DATABASE_URL`, `PUBLIC_BASE_URL`, `ALLOWED_HOSTS`. Free hosting tiers sleep when idle (the
  background worker sleeps too) and free Postgres can expire, so use paid plans for real traffic.

## Cutting API costs with the triage model

Most inbound leads are poor fits, yet each one costs two searches and three LLM calls. The triage model predicts from
the company name, website and e-mail type whether a lead is worth processing, and screens out the clear misses for free.

* **Safe by default.** `TRIAGE_MODE=shadow` records what it *would* skip but processes everything. Skipping needs
  `TRIAGE_MODE=active` **and** a good measured record. A random spot-check, a circuit breaker and a one-click
  **Process anyway** button protect against its mistakes.
* **Learns from you.** Training labels come from your approve/reject decisions and LLM scores. You can also load past
  outcomes: `python scripts/train_triage.py history.csv` (read-only unless you add `--save`).
* **Honest numbers.** `GET /triage/status` shows what it has learned and what more proof it needs.
  `python scripts/triage_demo.py` simulates the savings on **synthetic** data, which demonstrates the mechanism but is
  not a prediction for your leads.

## API

All routes need an `X-API-Key` header except `/health`, `/ready`, `/dashboard` and the two signed webhooks. Set
`ENABLE_DOCS=true` to expose the interactive OpenAPI docs at `/docs`.

| | |
|---|---|
| `POST /leads` · `POST /leads/batch` | add one lead · upload a CSV (`name,company,email,domain`) |
| `GET /leads?group=review\|working\|finished\|problems\|screened` · `GET /leads/{id}` | browse and inspect |
| `PATCH /leads/{id}/draft` | edit a draft that is awaiting approval |
| `POST /leads/{id}/approve` · `/reject` · `/retry` · `/process` | decide, retry, or override the triage model |
| `DELETE /leads/{id}` | erase a lead (privacy requests) |
| `GET /metrics/summary` · `GET /status` | metrics with spend and estimated savings · which integrations are live |
| `GET /triage/status` · `POST /triage/retrain` · `POST /triage/import` | the triage model |
| `GET /health` · `GET /ready` | liveness · readiness (database and worker) |

Lead lifecycle: `queued → processing → awaiting_approval → approved → sending → sent`, plus `rejected`, `failed`,
`send_failed`, `duplicate` and `screened_out`.

## Security highlights

API-key authentication on every data route; HubSpot and Slack webhook signatures with replay protection; a Slack
approver allowlist; spend caps and rate limits; redacted JSON logs; untrusted text is delimited before it reaches the
model and escaped before it reaches Slack or the browser; a strict content-security policy; hash-pinned dependencies;
non-root container; model weights stored as JSON (never pickle). Details and known limits: [SECURITY.md](SECURITY.md)
and [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

## Development

```bash
pip install -r requirements-dev.txt
pytest                      # 262 tests, SQLite, no network needed
TEST_DATABASE_URL=postgresql://user:pass@localhost/test pytest      # the same suite on PostgreSQL
ruff check .
bandit -r app scripts smoke_test.py -ll
pip-audit -r requirements.txt --no-deps
python scripts/check_secrets.py
python smoke_test.py        # one lead end to end, isolated and mock-only
```

Dependencies live in `requirements.in`; regenerate the hash-locked `requirements.txt` with
`pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements.txt requirements.in`.

```
app/            application code (api routes, pipeline, worker, integrations, triage model, dashboard)
tests/          262 tests
scripts/        live_check, train_triage, triage_demo, seed_triage_demo, check_secrets, dashboard checks
docs/           design and operating documents
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `uvicorn is not recognized` | Run it as `python -m uvicorn app.main:app --reload`, and make sure the virtual environment is active (the prompt shows `(.venv)`). |
| `&&` is not a valid separator (older PowerShell) | Run the commands on separate lines. |
| `pip install --require-hashes` fails on Windows | Use `pip install -r requirements.in` instead (the lock file was generated on Linux). |
| Dashboard says the key was not accepted | The key must match `APP_API_KEYS` in `.env`; restart the server after editing `.env`. |
| App will not start in production | The error message names the unsafe setting (it never prints a secret). Fix it in the environment. |
| Nothing is e-mailed after approving | Expected: sending is off by default. Enable it as described under *Connect real services*. |

## Documentation

[docs/TRIAGE_ML.md](docs/TRIAGE_ML.md) (the cost-saving model) ·
[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) ·
[docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) ·
[docs/ERROR_REGISTRY.md](docs/ERROR_REGISTRY.md) (issues found in version 1 and how each was resolved) ·
[docs/CODEBASE_GUIDE.md](docs/CODEBASE_GUIDE.md) (maintainer notes)

## Status and limits

Tested with mocked services and a real PostgreSQL. Not yet exercised against live Anthropic, Tavily, HubSpot, Slack or
SMTP accounts (use `scripts/live_check.py`), the Docker image has not been built by the author (the CI `docker` job
does it), and the dashboard was checked in a DOM simulator rather than a real browser. The triage model's savings on
real leads are unmeasured. Details in [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).

## License

No license file has been chosen yet. Add a `LICENSE` file before sharing the repository publicly or accepting
contributions.
