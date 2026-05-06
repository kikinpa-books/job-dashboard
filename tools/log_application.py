"""
Appends a new application row to the Google Sheet tracker.

Usage:
  python tools/log_application.py \
    --job_id "linkedin_123456" \
    --title "Personal Injury Paralegal" \
    --company "Smith & Associates" \
    --location "Miami, FL" \
    --platform "LinkedIn" \
    --apply_url "https://linkedin.com/jobs/view/123456" \
    --status "Applied" \
    --notes "" \
    --cover_letter "cover_letter_linkedin_123456.pdf" \
    --salary "55000" \
    --easy_apply "TRUE"
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import get_sheet, get_workbook, APPLICATIONS_HEADERS


def job_id_exists(ws, job_id):
    all_ids = ws.col_values(1)
    return job_id in all_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--location", default="")
    parser.add_argument("--platform", default="")
    parser.add_argument("--apply_url", default="")
    parser.add_argument("--status", default="Applied")
    parser.add_argument("--notes", default="")
    parser.add_argument("--cover_letter", default="")
    parser.add_argument("--salary", default="")
    parser.add_argument("--easy_apply", default="")
    args = parser.parse_args()

    ws = get_sheet()

    if job_id_exists(ws, args.job_id):
        print(f"SKIP: job_id '{args.job_id}' already exists in tracker.")
        return

    today = date.today().isoformat()
    row = [
        args.job_id,
        today,
        args.company,
        args.title,
        args.location,
        args.platform,
        args.apply_url,
        args.status,
        "",
        args.notes,
        args.cover_letter,
        args.salary,
        args.easy_apply,
        today,
    ]

    ws.append_row(row)
    print(f"Logged: {args.company} | {args.title} | {args.status}")


if __name__ == "__main__":
    main()
