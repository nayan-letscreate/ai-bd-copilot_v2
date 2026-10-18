# Security notes

## Reporting
Please report vulnerabilities privately to the repository owner rather than opening a public issue.

## Threat model in one paragraph
The service stores business-contact PII, can spend money (LLM and search calls), writes to a CRM, and can send
e-mail on a company's behalf. The main risks are therefore: unauthorised use of those capabilities, leaked
credentials, leaked contact data, and attacker-controlled text (web pages, CSV cells, CRM fields) steering the
LLM or the UI. Every control below maps to one of those.

## Controls
| Area | Control |
|---|---|
| Authentication | Every data route requires `X-API-Key`; keys are compared in constant time; several keys may be active for rotation; production refuses to start without strong keys (24+ chars). |
| Webhooks | HubSpot `X-HubSpot-Signature-v3` and Slack `v0` signatures verified with a 5 minute replay window; disabled entirely when their secrets are not configured. |
| Authorisation | Slack approvals require the clicking user to be in `SLACK_APPROVER_IDS` (empty list = nobody). Approve/reject are atomic, so double clicks cannot send twice. |
| Spend limits | Daily cap on new leads, per-key rate limit, CSV size/row caps, request body cap, e-mail daily cap. |
| Secrets | `SecretStr` everywhere; redacting JSON logger (known secret values, token formats, bearer tokens, e-mail addresses); error messages stored on leads are redacted; config errors never echo values. |
| Injection | SQLAlchemy bound parameters only (no SQL from input); untrusted text is delimited and neutralised before reaching the LLM; LLM output is schema-validated; Slack text is escaped; e-mail headers reject line breaks. |
| Browser | Dashboard builds the DOM with `textContent` (no `innerHTML`), strict CSP (`script-src 'self'`, no inline code), `X-Frame-Options: DENY`, `nosniff`, no-store caching, HSTS in production. |
| Outbound traffic | Fixed API hosts; redirects not followed; Slack `response_url` must be `https://hooks.slack.com`; webhook URL must be on `hooks.slack.com`. |
| Email | Dry run by default; real sending needs SMTP settings **and** a footer (unsubscribe + postal address); every send is preceded by explicit human approval. |
| Supply chain | Hash-pinned `requirements.txt` (`pip install --require-hashes`), `pip-audit` in CI, minimal non-root container image. |
| ML layer | Model weights are JSON in the database (no pickle/joblib; a test forbids importing code-executing serialisers); features come only from company name, website and e-mail type (never contact names); imported history stores derived features only; skipping requires measured evidence, keeps a random spot-check, can pause itself, and every skip is reversible by a person. |
| Data | Erase endpoint (`DELETE /leads/{id}`) and optional retention purge (`DATA_RETENTION_DAYS`). |

## Known limits (be aware)
* **The triage model can be steered by whoever can approve, reject or import labels** (all authenticated). A wrong or malicious label stream could make it skip good leads. The evidence gate, random spot-check, circuit breaker and override button bound the damage, and `GET /triage/status` makes drift visible; keep `TRIAGE_MODE=shadow` if you do not trust your label sources yet.
* **Rate limiting is per process.** With several instances the effective limit multiplies; put a gateway limit in front for strict control. The daily lead cap is database-backed and holds across instances.
* **The dashboard keeps the API key in `sessionStorage`** (tab-scoped). A strict CSP and DOM-only rendering mitigate XSS, but a shared browser profile is still a risk. Sign out on shared machines.
* **Single shared secret model.** API keys identify callers only by a short fingerprint; there are no per-user roles. Put SSO in front (e.g. an authenticating proxy) if you need individual accountability.
* **Data at rest** is as protected as your database provider makes it; the app does not add field-level encryption.
* **Cold e-mail compliance** (consent, local anti-spam law) is the operator's responsibility; the footer requirement is a safeguard, not legal advice.
* The Postgres and SQLite paths are tested; the Docker image and Render blueprint were validated piecewise but not built in the authoring environment, so run the CI `docker` job once.
* A chunked upload without `Content-Length` is not size-limited by the app before parsing; rely on your proxy (Render, nginx) request-size limit as well.
