"""
Searches SimplyHired for job listings and saves results to .tmp/jobs_raw_simplyhired.json.

Usage:
  python tools/search_simplyhired.py --keywords "Personal Injury Paralegal" --location "Fort Lauderdale, FL" --days 7
  python tools/search_simplyhired.py  # reads from .tmp/search_config.json
"""

import argparse
import json
import time
import random
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")


def load_config(args):
    config_file = TMP / "search_config.json"
    cfg = {}
    if config_file.exists():
        with open(config_file) as f:
            cfg = json.load(f)
    keywords = args.keywords or cfg.get("job_title", "")
    location = args.location or cfg.get("location", "")
    days = args.days or cfg.get("days", 7)
    return keywords, location, days


def build_url(keywords, location, days):
    # SimplyHired uses age param in days
    params = {
        "q": keywords,
        "l": location,
        "age": days,
        "sort": "date",
    }
    return "https://www.simplyhired.com/search?" + urlencode(params)


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.find_all("div", attrs={"data-testid": "searchSerpJob"})

    for card in cards:
        try:
            job_key = card.get("data-jobkey", "")
            if not job_key:
                continue

            title_el = card.find("h2", attrs={"data-testid": "searchSerpJobTitle"})
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            job_id = f"simplyhired_{job_key}"
            apply_url = f"https://www.simplyhired.com/job/{job_key}"

            company_el = card.find("span", attrs={"data-testid": "companyName"})
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.find("span", attrs={"data-testid": "searchSerpJobLocation"})
            location_text = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.find("span", attrs={"data-testid": re.compile(r"^salaryChip")})
            salary = salary_el.get_text(strip=True) if salary_el else ""

            date_el = card.find("p", attrs={"data-testid": "searchSerpJobDateStamp"})
            date_posted = date_el.get_text(strip=True) if date_el else ""

            quick_apply = bool(card.find("p", attrs={"data-testid": "searchSerpJobQuickApply"}))

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location_text,
                "date_posted": date_posted,
                "apply_url": apply_url,
                "salary_listed": salary,
                "easy_apply": quick_apply,
                "platform": "SimplyHired",
                "description": "",
                "scraped_date": date.today().isoformat(),
            })
        except Exception:
            continue

    return jobs


def search_simplyhired(keywords, location, days=7):
    url = build_url(keywords, location, days)
    all_jobs = []

    with sync_playwright() as p:
        headless = os.environ.get("HEADLESS", "0") == "1"
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(2, 4))

        for page_num in range(1, 6):
            html = page.content()
            jobs = parse_jobs(html)
            if not jobs:
                print(f"  Page {page_num}: no jobs found, stopping.")
                break
            all_jobs.extend(jobs)
            print(f"  Page {page_num}: found {len(jobs)} listings")

            next_btn = page.query_selector(
                "a[aria-label='Next'], "
                "button[data-testid='pagination-next'], "
                "a[data-testid='pagination-page-next']"
            )
            if not next_btn:
                break
            next_btn.click()
            time.sleep(random.uniform(2, 4))

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

    print(f"Searching SimplyHired: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_simplyhired(keywords, location, days)

    if len(jobs) < 5 and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_simplyhired(keywords, location, days * 2)

    output = TMP / "jobs_raw_simplyhired.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
