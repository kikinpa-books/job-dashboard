"""
Submits a LinkedIn Easy Apply application using Playwright.
Only works for jobs flagged as easy_apply=True.

Usage:
  python tools/apply_linkedin.py \
    --job_id "linkedin_123456" \
    --apply_url "https://www.linkedin.com/jobs/view/123456" \
    --resume_path "resume.pdf" \
    --cover_letter_path ".tmp/cover_letter_linkedin_123456.pdf"

Outputs JSON to stdout: {"success": true/false, "job_id": "...", "error": null/"message"}
"""

import argparse
import json
import os
import time
import random
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
load_dotenv(ROOT / ".env")

SESSION_FILE = TMP / "session_linkedin.json"


def result(success, job_id, error=None):
    print(json.dumps({"success": success, "job_id": job_id, "error": error}))


def load_session(context):
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False


def save_session(context):
    cookies = context.cookies()
    with open(SESSION_FILE, "w") as f:
        json.dump(cookies, f)


def login_linkedin(page):
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    time.sleep(random.uniform(1, 2))
    page.fill("#username", email)
    page.fill("#password", password)
    page.click("button[type='submit']")
    time.sleep(random.uniform(3, 5))

    if "checkpoint" in page.url or "challenge" in page.url:
        print("WARNING: LinkedIn verification required. Complete it in the browser, then press Enter.")
        input()


def fill_easy_apply_form(page, resume_path, cover_letter_path):
    name = os.getenv("USER_FULL_NAME", "")
    email = os.getenv("USER_EMAIL", "")
    phone = os.getenv("USER_PHONE", "")

    for step in range(10):
        time.sleep(random.uniform(1, 2))

        resume_input = page.query_selector("input[type='file'][accept*='pdf'], input[type='file'][name*='resume']")
        if resume_input and resume_path and Path(resume_path).exists():
            resume_input.set_input_files(str(resume_path))
            time.sleep(1)

        cover_input = page.query_selector("input[type='file'][name*='cover']")
        if cover_input and cover_letter_path and Path(cover_letter_path).exists():
            cover_input.set_input_files(str(cover_letter_path))
            time.sleep(1)

        for selector, value in [
            ("input[id*='phoneNumber'], input[name*='phone'], input[type='tel']", phone),
            ("input[id*='firstName'], input[placeholder*='First']", name.split()[0] if name else ""),
            ("input[id*='lastName'], input[placeholder*='Last']", name.split()[-1] if name else ""),
            ("input[type='email']", email),
        ]:
            try:
                el = page.query_selector(selector)
                if el and value:
                    current = el.input_value()
                    if not current:
                        el.fill(value)
                        time.sleep(0.3)
            except Exception:
                pass

        submit_btn = page.query_selector("button[aria-label='Submit application']")
        if submit_btn:
            submit_btn.click()
            time.sleep(2)
            return True

        next_btn = page.query_selector(
            "button[aria-label='Continue to next step'], "
            "button[aria-label='Review your application'], "
            "button:has-text('Next'), "
            "button:has-text('Review')"
        )
        if next_btn:
            next_btn.click()
        else:
            break

    return False


def apply_linkedin(job_id, apply_url, resume_path, cover_letter_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        session_loaded = load_session(context)
        if session_loaded:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            time.sleep(2)
            if "login" in page.url:
                login_linkedin(page)
        else:
            login_linkedin(page)

        save_session(context)

        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(2, 3))

        easy_apply_btn = page.query_selector("button.jobs-apply-button, button:has-text('Easy Apply')")
        if not easy_apply_btn:
            browser.close()
            return False, "Easy Apply button not found. This may not be an Easy Apply job."

        easy_apply_btn.click()
        time.sleep(random.uniform(1, 2))

        success = fill_easy_apply_form(page, resume_path, cover_letter_path)

        screenshot_path = TMP / f"confirmation_{job_id}.png"
        page.screenshot(path=str(screenshot_path))

        save_session(context)
        browser.close()

    return success, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_id", required=True)
    parser.add_argument("--apply_url", required=True)
    parser.add_argument("--resume_path", default="resume.pdf")
    parser.add_argument("--cover_letter_path", default="")
    args = parser.parse_args()

    resume = ROOT / args.resume_path if not Path(args.resume_path).is_absolute() else Path(args.resume_path)
    if not resume.exists():
        result(False, args.job_id, f"Resume not found: {resume}")
        sys.exit(1)

    try:
        success, error = apply_linkedin(args.job_id, args.apply_url, str(resume), args.cover_letter_path)
        result(success, args.job_id, error)
    except PlaywrightTimeout as e:
        result(False, args.job_id, f"Timeout: {e}")
    except Exception as e:
        result(False, args.job_id, str(e))


if __name__ == "__main__":
    main()
