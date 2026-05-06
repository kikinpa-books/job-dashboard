"""
Reads the Applications sheet and returns applications that need a follow-up.
Criteria: status = "Applied", date_applied >= threshold days ago, follow_up_sent is blank.

Usage:
  python tools/check_follow_up_queue.py
  python tools/check_follow_up_queue.py --days 7

Saves result to .tmp/follow_up_queue.json and prints a summary.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import get_sheet
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
load_dotenv(ROOT / ".env")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=int(os.getenv("FOLLOW_UP_THRESHOLD_DAYS", 7)))
    args = parser.parse_args()

    threshold_date = (date.today() - timedelta(days=args.days)).isoformat()

    ws = get_sheet()
    rows = ws.get_all_records()

    queue = []
    for row in rows:
        status = row.get("status", "")
        date_applied = row.get("date_applied", "")
        follow_up_sent = row.get("follow_up_sent", "")

        if (
            status == "Applied"
            and date_applied
            and date_applied <= threshold_date
            and not follow_up_sent
        ):
            queue.append(row)

    output = TMP / "follow_up_queue.json"
    with open(output, "w") as f:
        json.dump(queue, f, indent=2)

    if not queue:
        print("No applications need a follow-up right now.")
    else:
        print(f"Found {len(queue)} application(s) needing follow-up (pending over {args.days} days):\n")
        for r in queue:
            print(f"  {r.get('date_applied')} | {r.get('company')} | {r.get('title')} | {r.get('platform')}")

    print(f"\nQueue saved to {output}")
    return queue


if __name__ == "__main__":
    main()
