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

    cards = soup.select(
        "li[data-testid='jobsList-item'], "
        "article[data-testid='job-card'], "
        "div.SerpJob"
    )

    for card in cards:
        try:
            title_el = card.select_one(
                "a[data-testid='job-title'], "
                "h2[data-testid='jobTitle'] a, "
                "a.jobposting-title"
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")

            job_id_match = re.search(r"/job/([a-zA-Z0-9_-]+)", href)
            raw_id = job_id_match.group(1) if job_id_match else str(abs(hash(title + href)))
            job_id = f"simplyhired_{raw_id}"

            apply_url = href if href.startswith("http") else f"https://www.simplyhired.com{href}"

            company_el = card.select_one(
                "[data-testid='company-name'], "
                "span[data-testid='companyName'], "
                "span.jobposting-company"
            )
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one(
                "[data-testid='job-location'], "
                "span[data-testid='jobLocation'], "
                "span.jobposting-location"
            )
            location_text = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.select_one(
                "[data-testid='job-estimated-salary'], "
                "span[data-testid='compensation'], "
                "div[class*='salary']"
            )
            salary = salary_el.get_text(strip=True) if salary_el else ""

            date_el = card.select_one(
                "[data-testid='job-date'], "
                "span[data-testid='pubDate'], "
                "time"
            )
            date_posted = date_el.get_text(strip=True) if date_el else ""

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location_text,
                "date_posted": date_posted,
                "apply_url": apply_url,
                "salary_listed": salary,
                "easy_apply": False,
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
        browser = p.chromium.launch(headless=False)
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
