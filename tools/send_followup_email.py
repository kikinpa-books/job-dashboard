"""
Sends a follow-up email for a specific application using the Gmail API.

Usage:
  python tools/send_followup_email.py \
    --job_id "indeed_abc123" \
    --to_email "hiring@firmname.com" \
    --company "Smith & Associates" \
    --title "Personal Injury Paralegal" \
    --date_applied "2026-04-28"

Outputs JSON: {"success": true/false, "job_id": "...", "error": null/"message"}
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from sheets_client import TOKEN_FILE, CREDENTIALS_FILE
load_dotenv(ROOT / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("ERROR: Run tools/sheets_client.py first to complete OAuth setup.")
            sys.exit(1)
    return build("gmail", "v1", credentials=creds)


def format_date(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return date_str


def build_email_body(company, title, date_applied_str, user_name):
    date_display = format_date(date_applied_str)
    body = f"""Dear Hiring Manager,

I wanted to follow up on my application for the {title} position at {company}, which I submitted on {date_display}.

I remain very interested in this opportunity. My background in legal support and client advocacy aligns well with what your firm needs, and I would welcome the chance to speak with you further.

Please let me know if you need any additional materials from me. Thank you for your time and consideration.

Best regards,
{user_name}"""
    return body


def send_email(to_email, subject, body, from_email):
    service = get_gmail_service()

    message = MIMEText(body, "plain")
    message["to"] = to_email
    message["from"] = from_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def result(success, job_id, error=None):
    print(json.dumps({"success": success, "job_id": job_id, "error": error}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--to_email", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--date_applied", required=True)
    args = parser.parse_args()

    user_name = os.getenv("USER_FULL_NAME", "")
    from_email = os.getenv("USER_EMAIL", "")
    subject = f"Following Up: {args.title} Application"
    body = build_email_body(args.company, args.title, args.date_applied, user_name)

    try:
        send_email(args.to_email, subject, body, from_email)
        result(True, args.job_id)
        print(f"Follow-up sent to {args.to_email} for {args.company} | {args.title}")
    except Exception as e:
        result(False, args.job_id, str(e))


if __name__ == "__main__":
    main()
