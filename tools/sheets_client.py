"""
Shared Google Sheets authentication and connection helper.
All other tools that read or write the tracker import get_sheet() from here.

First-time setup:
  1. Download credentials.json from your Google Cloud project to the project root.
  2. Run this file directly: python tools/sheets_client.py
     This opens a browser OAuth flow and saves token.json for future runs.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]

CREDENTIALS_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"

SHEET_NAME_APPLICATIONS = "Applications"
SHEET_NAME_FOLLOW_UP_LOG = "Follow-Up Log"
SHEET_NAME_DASHBOARD = "Dashboard"

APPLICATIONS_HEADERS = [
    "job_id", "date_applied", "company", "title", "location",
    "platform", "apply_url", "status", "follow_up_sent", "notes",
    "cover_letter_used", "salary_listed", "easy_apply", "date_last_updated",
]

FOLLOW_UP_LOG_HEADERS = [
    "job_id", "company", "title", "date_sent", "method", "response_received",
]


def _get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: {CREDENTIALS_FILE} not found.")
                print("Download credentials.json from your Google Cloud project and place it in the project root.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return creds


def get_client():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    print(f"DEBUG get_client: GOOGLE_SERVICE_ACCOUNT_JSON present={bool(sa_json)}, len={len(sa_json) if sa_json else 0}")
    if sa_json:
        try:
            from google.oauth2.service_account import Credentials as SACredentials
            sa_info = json.loads(sa_json)
            creds = SACredentials.from_service_account_info(
                sa_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            return gspread.authorize(creds)
        except Exception as e:
            print(f"ERROR: Service account auth failed: {e}")
            raise
    creds = _get_credentials()
    return gspread.authorize(creds)


def get_workbook():
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID is not set in .env")
        sys.exit(1)
    client = get_client()
    return client.open_by_key(sheet_id)


def get_sheet(tab_name=SHEET_NAME_APPLICATIONS):
    wb = get_workbook()
    existing = [ws.title for ws in wb.worksheets()]

    if tab_name not in existing:
        ws = wb.add_worksheet(title=tab_name, rows=1000, cols=20)
        if tab_name == SHEET_NAME_APPLICATIONS:
            ws.append_row(APPLICATIONS_HEADERS)
        elif tab_name == SHEET_NAME_FOLLOW_UP_LOG:
            ws.append_row(FOLLOW_UP_LOG_HEADERS)
        print(f"Created new tab: {tab_name}")
    else:
        ws = wb.worksheet(tab_name)

    return ws


if __name__ == "__main__":
    print("Testing Google Sheets connection...")
    ws = get_sheet()
    print(f"Connected. Tab '{SHEET_NAME_APPLICATIONS}' has {ws.row_count} rows.")
    ws2 = get_sheet(SHEET_NAME_FOLLOW_UP_LOG)
    print(f"Connected. Tab '{SHEET_NAME_FOLLOW_UP_LOG}' ready.")
    print("OAuth setup complete. token.json saved.")
