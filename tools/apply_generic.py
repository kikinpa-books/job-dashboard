"""
Best-effort application submission for external job sites (non-LinkedIn, non-Indeed).
Attempts to locate common form fields, fill them, and submit.
Logs errors gracefully so one failure does not block the whole run.

Usage:
  python tools/apply_generic.py \
    --job_id "glassdoor_789" \
    --apply_url "https://firmname.com/careers/apply" \
    --resume_path "resume.pdf" \
    --cover_letter_path ".tmp/cover_letter_glassdoor_789.pdf"

Outputs JSON: {"success": true/false, "job_id": "...", "error": null/"message"}
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


def result(success, job_id, error=None):
    print(json.dumps({"success": success, "job_id": job_id, "error": error}))


COMMON_FIELD_PATTERNS = [
    ("first_name", ["input[name*='first' i]", "input[placeholder*='first' i]", "input[id*='firstName' i]"]),
    ("last_name",  ["input[name*='last' i]",  "input[placeholder*='last' i]",  "input[id*='lastName' i]"]),
    ("email",      ["input[type='email']", "input[name*='email' i]", "input[placeholder*='email' i]"]),
    ("phone",      ["input[type='tel']",   "input[name*='phone' i]", "input[placeholder*='phone' i]"]),
]


def get_field_values():
    name = os.getenv("USER_FULL_NAME", "")
    parts = name.split(" ", 1)
    return {
        "first_name": parts[0] if parts else "",
        "last_name":  parts[1] if len(parts) > 1 else "",
        "email":      os.getenv("USER_EMAIL", ""),
        "phone":      os.getenv("USER_PHONE", ""),
    }


def apply_generic(job_id, apply_url, resume_path, cover_letter_path):
    values = get_field_values()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(2, 3))

        for field_key, selectors in COMMON_FIELD_PATTERNS:
            for selector in selectors:
                try:
                    el = page.query_selector(selector)
                    if el and values.get(field_key):
                        current = el.input_value()
                        if not current:
                            el.fill(values[field_key])
                            time.sleep(0.2)
                        break
                except Exception:
                    continue

        for file_selector in [
            "input[type='file'][accept*='pdf']",
            "input[type='file'][name*='resume' i]",
            "input[type='file'][name*='cv' i]",
            "input[type='file']",
        ]:
            try:
                file_input = page.query_selector(file_selector)
                if file_input and resume_path and Path(resume_path).exists():
                    file_input.set_input_files(str(resume_path))
                    time.sleep(1)
                    break
            except Exception:
                continue

        if cover_letter_path and Path(cover_letter_path).exists():
            for cl_selector in [
                "input[type='file'][name*='cover' i]",
                "input[type='file'][name*='letter' i]",
            ]:
                try:
                    cl_input = page.query_selector(cl_selector)
                    if cl_input:
                        cl_input.set_input_files(str(cover_letter_path))
                        time.sleep(1)
                        break
                except Exception:
                    continue

        submit_btn = page.query_selector(
            "button[type='submit']:has-text('Apply'), "
            "button[type='submit']:has-text('Submit'), "
            "input[type='submit']"
        )
        if submit_btn:
            submit_btn.click()
            time.sleep(2)

        screenshot_path = TMP / f"confirmation_{job_id}.png"
        page.screenshot(path=str(screenshot_path))
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
        apply_generic(args.job_id, args.apply_url, str(resume), args.cover_letter_path)
        result(True, args.job_id)
    except PlaywrightTimeout as e:
        result(False, args.job_id, f"Timeout: {e}")
    except Exception as e:
        result(False, args.job_id, str(e))


if __name__ == "__main__":
    main()
