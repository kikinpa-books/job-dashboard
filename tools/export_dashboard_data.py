"""
Reads Google Sheets and writes docs/data/applications.json.
Used by GitHub Actions — authenticates via service account (GOOGLE_SERVICE_ACCOUNT_JSON env var).
For local use, falls back to the standard OAuth token.json flow.
Does NOT commit or push — the workflow handles that.
"""

import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DATA = ROOT / "docs" / "data"
JSON_PATH = DOCS_DATA / "applications.json"
TMP = ROOT / ".tmp"
FILTERED_PATH = TMP / "jobs_filtered.json"

FOLLOW_UP_DAYS = 7
SHEET_NAME_APPLICATIONS = "Applications"
MANUAL_PATH = TMP / "jobs_manual.json"


def get_sheet_rows():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        # Fall back to .env for local use
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID is not set.")
        sys.exit(1)

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if sa_json:
        # GitHub Actions path — service account
        import gspread
        from google.oauth2.service_account import Credentials

        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        client = gspread.authorize(creds)
    else:
        # Local path — reuse existing OAuth token
        sys.path.insert(0, str(Path(__file__).parent))
        from sheets_client import get_client
        client = get_client()

    wb = client.open_by_key(sheet_id)
    ws = wb.worksheet(SHEET_NAME_APPLICATIONS)
    return ws.get_all_records()


def build_payload(rows):
    today = date.today()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cutoff = (today - timedelta(days=FOLLOW_UP_DAYS)).isoformat()

    status_counts = Counter(r.get("status", "") for r in rows)
    platform_counts = Counter(r.get("platform", "") for r in rows)
    title_counts = Counter(r.get("title", "") for r in rows if r.get("title"))

    needs_follow_up = [
        r for r in rows
        if r.get("status") == "Applied"
        and r.get("date_applied", "") <= cutoff
        and not r.get("follow_up_sent", "")
    ]

    recent = sorted(rows, key=lambda r: r.get("date_applied", ""), reverse=True)[:20]

    ready_to_apply = []
    if FILTERED_PATH.exists():
        with open(FILTERED_PATH) as f:
            ready_to_apply = json.load(f)

    manual_apply = []
    if MANUAL_PATH.exists():
        with open(MANUAL_PATH) as f:
            manual_apply = json.load(f)

    return {
        "generated": now_utc,
        "summary": {
            "total": len(rows),
            "applied": status_counts.get("Applied", 0),
            "interviewing": status_counts.get("Interviewing", 0),
            "offer": status_counts.get("Offer", 0),
            "rejected": status_counts.get("Rejected", 0),
            "withdrew": status_counts.get("Withdrew", 0),
            "errors": status_counts.get("Error", 0),
            "needs_follow_up": len(needs_follow_up),
        },
        "by_platform": platform_counts.most_common(),
        "by_title": title_counts.most_common(),
        "recent": [
            {k: r.get(k, "") for k in ["date_applied", "company", "title", "location", "platform", "status", "apply_url"]}
            for r in recent
        ],
        "follow_up": [
            {k: r.get(k, "") for k in ["date_applied", "company", "title", "platform", "apply_url"]}
            for r in needs_follow_up
        ],
        "ready_to_apply": [
            {k: j.get(k, "") for k in ["score", "company", "title", "location", "platform", "apply_url"]}
            for j in ready_to_apply
        ],
        "manual_apply": [
            {k: j.get(k, "") for k in ["company", "title", "location", "platform", "apply_url", "salary_listed", "reason"]}
            for j in manual_apply
        ],
    }


def main():
    print("Reading Google Sheets...")
    rows = get_sheet_rows()
    print(f"Found {len(rows)} applications.")

    payload = build_payload(rows)

    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"Wrote {JSON_PATH}")
    print(f"Total: {payload['summary']['total']} | "
          f"Interviewing: {payload['summary']['interviewing']} | "
          f"Follow-up needed: {payload['summary']['needs_follow_up']}")


if __name__ == "__main__":
    main()
