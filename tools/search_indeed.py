"""
Searches Indeed for job listings and saves results to .tmp/jobs_raw_indeed.json.

Usage:
  python tools/search_indeed.py --keywords "Personal Injury Paralegal" --location "Miami, FL" --days 7
  python tools/search_indeed.py  # reads from .tmp/search_config.json if no args
"""

import argparse
import json
import time
import random
import re
import sys
from datetime import date
from pathlib import Path

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
    if not args.keywords and config_file.exists():
        with open(config_file) as f:
            cfg = json.load(f)
        return cfg.get("job_title", ""), cfg.get("location", ""), 7
    return args.keywords, args.location, args.days


def build_indeed_url(keywords, location, days):
    from urllib.parse import urlencode, quote_plus
    age_map = {1: 1, 3: 3, 7: 7, 14: 14, 30: 30}
    fromage = min((v for v in age_map if v >= days), default=30)
    params = {
        "q": keywords,
        "l": location,
        "fromage": fromage,
        "sort": "date",
    }
    return "https://www.indeed.com/jobs?" + urlencode(params)


def parse_job_cards(html, platform="Indeed"):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("div.job_seen_beacon, div[data-testid='jobCard']")
    for card in cards:
        try:
            title_el = card.select_one("h2.jobTitle a, a[data-jk]")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            job_id_match = re.search(r"jk=([a-zA-Z0-9]+)", href)
            job_id = f"indeed_{job_id_match.group(1)}" if job_id_match else f"indeed_{hash(title)}"
            apply_url = f"https://www.indeed.com{href}" if href.startswith("/") else href

            company_el = card.select_one("[data-testid='company-name'], .companyName")
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one("[data-testid='text-location'], .companyLocation")
            location = location_el.get_text(strip=True) if location_el else ""

            date_el = card.select_one("[data-testid='myJobsStateDate'], .date")
            date_posted = date_el.get_text(strip=True) if date_el else ""

            salary_el = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet")
            salary = salary_el.get_text(strip=True) if salary_el else ""

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "date_posted": date_posted,
                "apply_url": apply_url,
                "salary_listed": salary,
                "easy_apply": False,
                "platform": "Indeed",
                "description": "",
                "scraped_date": date.today().isoformat(),
            })
        except Exception as e:
            continue

    return jobs


def search_indeed(keywords, location, days=7):
    url = build_indeed_url(keywords, location, days)
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
            jobs = parse_job_cards(html)
            if not jobs:
                print(f"  Page {page_num}: no jobs found, stopping pagination.")
                break
            all_jobs.extend(jobs)
            print(f"  Page {page_num}: found {len(jobs)} listings")

            next_btn = page.query_selector("a[data-testid='pagination-page-next'], a[aria-label='Next Page']")
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

    print(f"Searching Indeed: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_indeed(keywords, location, days)

    if not jobs and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_indeed(keywords, location, days * 2)

    output = TMP / "jobs_raw_indeed.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
