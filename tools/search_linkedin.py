"""
Searches LinkedIn for job listings using a saved session and saves results to .tmp/jobs_raw_linkedin.json.
Only collects Easy Apply jobs (these can be submitted programmatically).

Usage:
  python tools/search_linkedin.py --keywords "Personal Injury Paralegal" --location "Miami, FL" --days 7
  python tools/search_linkedin.py  # reads from .tmp/search_config.json
"""

import argparse
import json
import os
import time
import random
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")

SESSION_FILE = TMP / "session_linkedin.json"


def load_config(args):
    config_file = TMP / "search_config.json"
    if not args.keywords and config_file.exists():
        with open(config_file) as f:
            cfg = json.load(f)
        return cfg.get("job_title", ""), cfg.get("location", ""), 7
    return args.keywords, args.location, args.days


def login_linkedin(page):
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        print("ERROR: LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env")
        sys.exit(1)

    page.goto("https://www.linkedin.com/login", wait_until="networkidle", timeout=60000)
    time.sleep(random.uniform(2, 4))
    page.wait_for_selector("#username", timeout=30000)
    page.fill("#username", email)
    page.fill("#password", password)
    page.click("button[type='submit']")
    time.sleep(random.uniform(3, 5))

    if "checkpoint" in page.url or "challenge" in page.url:
        print("WARNING: LinkedIn is asking for verification. Complete it manually in the browser, then press Enter.")
        input()

    print("LinkedIn login successful.")


def save_session(context):
    cookies = context.cookies()
    with open(SESSION_FILE, "w") as f:
        json.dump(cookies, f)


def load_session(context):
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False


def build_linkedin_url(keywords, location, days):
    from urllib.parse import urlencode
    age_map = {1: "r86400", 3: "r259200", 7: "r604800", 14: "r1209600", 30: "r2592000"}
    time_filter = min((v for k, v in age_map.items() if k >= days), default="r2592000")
    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": time_filter,
        "f_AL": "true",
    }
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


def parse_linkedin_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("li.jobs-search-results__list-item, div.job-card-container")
    for card in cards:
        try:
            title_el = card.select_one("a.job-card-list__title, a.job-card-container__link")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            job_id_match = re.search(r"/jobs/view/(\d+)", href)
            job_id = f"linkedin_{job_id_match.group(1)}" if job_id_match else f"linkedin_{hash(title)}"
            apply_url = f"https://www.linkedin.com{href}" if href.startswith("/") else href

            company_el = card.select_one(".job-card-container__company-name, .artdeco-entity-lockup__subtitle")
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one(".job-card-container__metadata-item, .artdeco-entity-lockup__caption")
            location = location_el.get_text(strip=True) if location_el else ""

            easy_apply = bool(card.select_one(".job-card-container__apply-method"))

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "date_posted": "",
                "apply_url": apply_url,
                "salary_listed": "",
                "easy_apply": easy_apply,
                "platform": "LinkedIn",
                "description": "",
                "scraped_date": date.today().isoformat(),
            })
        except Exception:
            continue

    return jobs


def search_linkedin(keywords, location, days=7):
    url = build_linkedin_url(keywords, location, days)
    all_jobs = []

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
                print("Session expired. Logging in again...")
                login_linkedin(page)
                save_session(context)
        else:
            login_linkedin(page)
            save_session(context)

        page.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(2, 4))

        screenshot = TMP / "linkedin_search.png"
        page.screenshot(path=str(screenshot))

        if "captcha" in page.content().lower() or "robot" in page.content().lower():
            print(f"CAPTCHA detected. Screenshot saved to {screenshot}. Complete it manually, then press Enter.")
            input()

        for page_num in range(1, 6):
            html = page.content()
            jobs = parse_linkedin_jobs(html)
            if not jobs:
                break
            all_jobs.extend(jobs)
            print(f"  Page {page_num}: found {len(jobs)} listings ({sum(1 for j in jobs if j['easy_apply'])} Easy Apply)")

            next_btn = page.query_selector("button[aria-label='Next']")
            if not next_btn:
                break
            next_btn.click()
            time.sleep(random.uniform(2, 4))

        save_session(context)
        browser.close()

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    keywords, location, days = load_config(args)

    if not keywords:
        print("ERROR: No keywords provided. Run prompt_search_config.py first or pass --keywords.")
        sys.exit(1)

    print(f"Searching LinkedIn: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_linkedin(keywords, location, days)

    if len(jobs) < 5 and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_linkedin(keywords, location, days * 2)

    output = TMP / "jobs_raw_linkedin.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
