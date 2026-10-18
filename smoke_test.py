"""End-to-end smoke test: one lead through the whole pipeline in an isolated mock environment.

Safe by construction: it forces mock mode (all integration keys removed), uses a throwaway database,
and exits non-zero unless the lead reaches 'awaiting_approval'. It can never spend money, post to
Slack or write to HubSpot, even if a real .env is present.

    python smoke_test.py
"""
import os
import sys
import tempfile

SECRET_KEYS = [
    "ANTHROPIC_API_KEY", "TAVILY_API_KEY", "HUBSPOT_TOKEN", "HUBSPOT_CLIENT_SECRET", "SLACK_WEBHOOK_URL",
    "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SMTP_HOST", "SMTP_PASSWORD",
]
for key in SECRET_KEYS:
    os.environ.pop(key, None)

ORIGINAL_DIR = os.getcwd()
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows can hold file locks a moment longer
os.chdir(tmp.name)  # a stray .env in the project directory is never read
os.environ.update(APP_ENV="test", DATABASE_URL=f"sqlite:///{tmp.name}/smoke.db", OUTREACH_SEND_ENABLED="false", WORKER_ENABLED="false")

from app import db, worker  # noqa: E402


def main() -> int:
    db.init_db()
    lead_id, _ = db.create_lead(
        name="Priya Shah", company="WanderWorks Travel", email="priya@wanderworks.example", domain="wanderworks.example"
    )
    print(f"Created lead {lead_id}; running the worker once...")
    worker.run_once()
    lead = db.get_lead(lead_id)

    problems = []
    if lead["status"] != db.AWAITING_APPROVAL:
        problems.append(f"status is {lead['status']!r}, expected 'awaiting_approval' (error: {lead['error']})")
    if lead["mode"] != "mock":
        problems.append(f"mode is {lead['mode']!r}, expected 'mock' (isolation failed)")
    for field in ("brief", "draft", "score", "score_rationale"):
        if lead.get(field) in (None, ""):
            problems.append(f"{field} was not stored")

    # Approve and "send" (dry run) to cover the second half of the flow.
    if not problems:
        db.transition(lead_id, [db.AWAITING_APPROVAL], db.APPROVED, available_at=0, approved_by="smoke-test")
        worker.run_once()
        final = db.get_lead(lead_id)
        if final["status"] != db.SENT or final["send_mode"] != "dry_run":
            problems.append(f"send step ended as {final['status']!r}/{final['send_mode']!r}, expected sent/dry_run")

    db.dispose_engine()
    os.chdir(ORIGINAL_DIR)  # Windows cannot delete a directory the process is still inside
    tmp.cleanup()
    if problems:
        print("SMOKE TEST FAILED:\n  - " + "\n  - ".join(problems))
        return 1
    print("Smoke test passed: research -> score -> draft -> review -> approve -> (dry-run) send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
