"""
Reads Google Sheets data, writes docs/data/applications.json,
then commits and pushes to the kikinpa-books/job-dashboard GitHub repo.

Call this at the end of any agent run (same as update_dashboard.py).
Requires: gh CLI authenticated, git initialized in the repo root.
"""

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import get_sheet, APPLICATIONS_HEADERS

ROOT = Path(__file__).resolve().parent.parent
DOCS_DATA = ROOT / "docs" / "data"
JSON_PATH = DOCS_DATA / "applications.json"
TMP = ROOT / ".tmp"
FILTERED_PATH = TMP / "jobs_filtered.json"

FOLLOW_UP_DAYS = 7


def build_payload(rows):
    today = date.today()
    cutoff = (today - timedelta(days=FOLLOW_UP_DAYS)).isoformat()

    status_counts = Counter(r.get("status", "") for r in rows)
    platform_counts = Counter(r.get("platform", "") for r in rows)

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

    return {
        "generated": today.isoformat(),
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
        "recent": [
            {k: r.get(k, "") for k in ["date_applied", "company", "title", "location", "platform", "status"]}
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
    }


def git_push(payload):
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"Wrote {JSON_PATH}")

    git = ["git", "-C", str(ROOT)]

    # Check if this is a git repo
    result = subprocess.run(git + ["rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("Not a git repo — skipping push. Run setup_git.py first.")
        return

    subprocess.run(git + ["add", "docs/data/applications.json"], check=True)

    status = subprocess.run(git + ["status", "--porcelain"], capture_output=True, text=True)
    if not status.stdout.strip():
        print("No changes to commit.")
        return

    today = date.today().isoformat()
    subprocess.run(git + ["commit", "-m", f"dashboard: update data {today}"], check=True)
    subprocess.run(git + ["push"], check=True)
    print("Pushed to GitHub. Dashboard will update in ~30 seconds.")


def main():
    print("Publishing dashboard...")
    ws = get_sheet()
    rows = ws.get_all_records()
    payload = build_payload(rows)
    git_push(payload)
    print(f"Done. Total: {payload['summary']['total']} | "
          f"Interviewing: {payload['summary']['interviewing']} | "
          f"Follow-up needed: {payload['summary']['needs_follow_up']}")


if __name__ == "__main__":
    main()
