"""
Reads the Applications sheet and writes a summary Dashboard tab.
Call this at the end of every run (search, apply, or follow-up).

Dashboard tab layout:
  - Summary stats block (total, by status, by platform)
  - Recent applications table (last 10)
  - Follow-up needed table
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import get_sheet, get_workbook, APPLICATIONS_HEADERS, SHEET_NAME_DASHBOARD

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"


def parse_rows(ws):
    all_rows = ws.get_all_records()
    return all_rows


def main():
    print("Updating dashboard...")

    apps_ws = get_sheet()
    rows = parse_rows(apps_ws)

    wb = get_workbook()
    existing_tabs = [ws.title for ws in wb.worksheets()]
    if SHEET_NAME_DASHBOARD not in existing_tabs:
        dash = wb.add_worksheet(title=SHEET_NAME_DASHBOARD, rows=100, cols=10)
    else:
        dash = wb.worksheet(SHEET_NAME_DASHBOARD)
        dash.clear()

    today = date.today().isoformat()
    total = len(rows)

    status_counts = Counter(r.get("status", "") for r in rows)
    platform_counts = Counter(r.get("platform", "") for r in rows)

    applied = status_counts.get("Applied", 0)
    interviewing = status_counts.get("Interviewing", 0)
    offer = status_counts.get("Offer", 0)
    rejected = status_counts.get("Rejected", 0)
    withdrew = status_counts.get("Withdrew", 0)
    errors = status_counts.get("Error", 0)

    follow_up_threshold = 7
    cutoff = (date.today() - timedelta(days=follow_up_threshold)).isoformat()
    needs_follow_up = [
        r for r in rows
        if r.get("status") == "Applied"
        and r.get("date_applied", "") <= cutoff
        and not r.get("follow_up_sent", "")
    ]

    recent = sorted(rows, key=lambda r: r.get("date_applied", ""), reverse=True)[:10]

    output = []

    output.append(["JOB APPLICATION DASHBOARD", "", "", "", "", ""])
    output.append([f"Last updated: {today}", "", "", "", "", ""])
    output.append(["", "", "", "", "", ""])

    output.append(["SUMMARY", "", "", "", "", ""])
    output.append(["Total Applications", total, "", "", "", ""])
    output.append(["Applied (pending)", applied, "", "", "", ""])
    output.append(["Interviewing", interviewing, "", "", "", ""])
    output.append(["Offers", offer, "", "", "", ""])
    output.append(["Rejected", rejected, "", "", "", ""])
    output.append(["Withdrew", withdrew, "", "", "", ""])
    output.append(["Errors", errors, "", "", "", ""])
    output.append(["Need Follow-Up", len(needs_follow_up), "", "", "", ""])
    output.append(["", "", "", "", "", ""])

    output.append(["BY PLATFORM", "", "", "", "", ""])
    for platform, count in platform_counts.most_common():
        output.append([platform or "Unknown", count, "", "", "", ""])
    output.append(["", "", "", "", "", ""])

    output.append(["RECENT APPLICATIONS (last 10)", "", "", "", "", ""])
    output.append(["Date", "Company", "Title", "Location", "Platform", "Status"])
    for r in recent:
        output.append([
            r.get("date_applied", ""),
            r.get("company", ""),
            r.get("title", ""),
            r.get("location", ""),
            r.get("platform", ""),
            r.get("status", ""),
        ])
    output.append(["", "", "", "", "", ""])

    output.append([f"FOLLOW-UP NEEDED (pending over {follow_up_threshold} days)", "", "", "", "", ""])
    if needs_follow_up:
        output.append(["Date Applied", "Company", "Title", "Platform", "Apply URL", ""])
        for r in needs_follow_up:
            output.append([
                r.get("date_applied", ""),
                r.get("company", ""),
                r.get("title", ""),
                r.get("platform", ""),
                r.get("apply_url", ""),
                "",
            ])
    else:
        output.append(["No follow-ups needed right now.", "", "", "", "", ""])

    output.append(["", "", "", "", "", ""])

    filtered_path = TMP / "jobs_filtered.json"
    if filtered_path.exists():
        with open(filtered_path) as f:
            filtered_jobs = json.load(f)
        output.append(["READY TO APPLY (click links below to apply manually)", "", "", "", "", ""])
        output.append(["Score", "Company", "Title", "Location", "Platform", "Apply Link"])
        for j in filtered_jobs:
            output.append([
                j.get("score", ""),
                j.get("company", ""),
                j.get("title", ""),
                j.get("location", ""),
                j.get("platform", ""),
                j.get("apply_url", ""),
            ])
    else:
        output.append(["No filtered jobs found. Run a search first.", "", "", "", "", ""])

    dash.update(range_name="A1", values=output)

    print(f"Dashboard updated. Total: {total} | Interviewing: {interviewing} | Follow-up needed: {len(needs_follow_up)}")


if __name__ == "__main__":
    main()
