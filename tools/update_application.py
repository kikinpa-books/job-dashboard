"""
Updates a single field on an existing application row, found by job_id.

Usage:
  python tools/update_application.py --job_id "linkedin_123456" --field "status" --value "Interviewing"
  python tools/update_application.py --job_id "linkedin_123456" --field "follow_up_sent" --value "2026-05-13"
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import get_sheet, APPLICATIONS_HEADERS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--field", required=True, help=f"Column name. One of: {', '.join(APPLICATIONS_HEADERS)}")
    parser.add_argument("--value", required=True)
    args = parser.parse_args()

    if args.field not in APPLICATIONS_HEADERS:
        print(f"ERROR: '{args.field}' is not a valid field. Choose from: {APPLICATIONS_HEADERS}")
        sys.exit(1)

    ws = get_sheet()
    col_index = APPLICATIONS_HEADERS.index(args.field) + 1

    all_ids = ws.col_values(1)
    try:
        row_index = all_ids.index(args.job_id) + 1
    except ValueError:
        print(f"ERROR: job_id '{args.job_id}' not found in tracker.")
        sys.exit(1)

    ws.update_cell(row_index, col_index, args.value)

    date_last_updated_col = APPLICATIONS_HEADERS.index("date_last_updated") + 1
    ws.update_cell(row_index, date_last_updated_col, date.today().isoformat())

    print(f"Updated row {row_index}: {args.field} = {args.value}")


if __name__ == "__main__":
    main()
