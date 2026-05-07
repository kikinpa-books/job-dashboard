"""
Submits a job application on Indeed using Playwright browser automation.

Usage:
  python tools/apply_indeed.py \
    --job_id "indeed_abc123" \
    --apply_url "https://www.indeed.com/viewjob?jk=abc123" \
    --resume_path "resume.pdf" \
    --cover_letter_path ".tmp/cover_letter_indeed_abc123.pdf"

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

SESSION_FILE = TMP / "session_indeed.json"


def result(success, job_id, error=None):
    print(json.dumps({"success": success, "job_id": job_id, "error": error}))


def login_indeed(page):
    email = os.getenv("INDEED_EMAIL")
    password = os.getenv("INDEED_PASSWORD")
    if not email or not password:
        return False

    page.goto("https://secure.indeed.com/account/login", wait_until="domcontentloaded")
    time.sleep(2)
    try:
        page.fill("input[name='__email']", email)
        page.click("button[type='submit']")
        time.sleep(1)
        page.fill("input[name='__password']", password)
        page.click("button[type='submit']")
        time.sleep(3)
    except Exception:
        return False
    return True


def save_session(context, path):
    cookies = context.cookies()
    with open(path, "w") as f:
        json.dump(cookies, f)


def load_session(context, path):
    if path.exists():
        with open(path) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False


def apply_indeed(job_id, apply_url, resume_path, cover_letter_path):
    with sync_playwright() as p:
        headless = os.environ.get("HEADLESS", "0") == "1"
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        session_loaded = load_session(context, SESSION_FILE)
        if session_loaded:
            page.goto("https://www.indeed.com", wait_until="domcontentloaded")
            time.sleep(2)
            if "login" in page.url or page.query_selector("a[href*='login']"):
                login_indeed(page)
                save_session(context, SESSION_FILE)
        else:
            login_indeed(page)
            save_session(context, SESSION_FILE)

        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(3, 5))

        # Take screenshot so we can see what loaded
        page.screenshot(path=str(TMP / f"apply_page_{job_id}.png"))

        # Try multiple apply button selectors
        apply_btn = page.query_selector(
            "button#indeedApplyButton, "
            "a[id='applyButtonLinkContainer'], "
            "button[data-testid='apply-button'], "
            "a[data-testid='apply-button'], "
            "button:has-text('Apply now'), "
            "button:has-text('Apply on company site')"
        )
        if apply_btn:
            apply_btn.click()
            time.sleep(random.uniform(2, 3))
        else:
            # Check if we were redirected to an external site already
            if "indeed.com" not in page.url:
                print(f"Redirected to external site: {page.url}")
            else:
                print("Apply button not found, attempting to proceed with current page state")

        frames = page.frames
        apply_frame = None
        for frame in frames:
            if "apply" in (frame.url or "").lower() or "indeedapply" in (frame.url or "").lower():
                apply_frame = frame
                break
        ctx = apply_frame if apply_frame else page

        resume_input = ctx.query_selector("input[type='file'][accept*='pdf'], input[type='file'][name*='resume']")
        if resume_input and Path(resume_path).exists():
            resume_input.set_input_files(str(resume_path))
            time.sleep(1)

        name = os.getenv("USER_FULL_NAME", "")
        email = os.getenv("USER_EMAIL", "")
        phone = os.getenv("USER_PHONE", "")

        for selector, value in [
            ("input[name*='name'], input[placeholder*='name' i]", name),
            ("input[name*='email'], input[type='email']", email),
            ("input[name*='phone'], input[type='tel']", phone),
        ]:
            try:
                el = ctx.query_selector(selector)
                if el and value:
                    el.fill(value)
                    time.sleep(0.3)
            except Exception:
                pass

        for _ in range(5):
            next_btn = ctx.query_selector("button[type='submit']:not([disabled]), button:has-text('Continue'), button:has-text('Next')")
            if not next_btn:
                break
            next_btn.click()
            time.sleep(random.uniform(1, 2))

            submit_btn = ctx.query_selector("button:has-text('Submit'), button:has-text('Apply Now')")
            if submit_btn:
                submit_btn.click()
                time.sleep(2)
                break

        screenshot_path = TMP / f"confirmation_{job_id}.png"
        page.screenshot(path=str(screenshot_path))

        save_session(context, SESSION_FILE)
        browser.close()

    return True


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
        apply_indeed(args.job_id, args.apply_url, str(resume), args.cover_letter_path)
        result(True, args.job_id)
    except PlaywrightTimeout as e:
        result(False, args.job_id, f"Timeout: {e}")
    except Exception as e:
        result(False, args.job_id, str(e))


if __name__ == "__main__":
    main()
