"""
Searches ZipRecruiter for job listings and saves results to .tmp/jobs_raw_ziprecruiter.json.

Usage:
  python tools/search_ziprecruiter.py --keywords "Personal Injury Paralegal" --location "Fort Lauderdale, FL" --days 7
  python tools/search_ziprecruiter.py  # reads from .tmp/search_config.json
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
    # ZipRecruiter uses days_ago param (1, 3, 5, 10, 30)
    days_map = [(1, 1), (3, 3), (5, 5), (10, 10), (30, 30)]
    days_ago = next((v for k, v in days_map if days <= k), 30)
    params = {
        "search": keywords,
        "location": location,
        "days_ago": days_ago,
        "sort_by_date": 1,
    }
    return "https://www.ziprecruiter.com/jobs-search?" + urlencode(params)


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.find_all("article", id=re.compile(r"^job-card-"))

    for card in cards:
        try:
            card_id = card.get("id", "")
            uuid = card_id.replace("job-card-", "")

            title_el = card.find("h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            job_id = f"ziprecruiter_{uuid}"
            apply_url = f"https://www.ziprecruiter.com/ojob/{uuid}"

            company_el = card.find("a", attrs={"data-testid": "job-card-company"})
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.find("a", attrs={"data-testid": "job-card-location"})
            location_text = location_el.get_text(strip=True) if location_el else ""

            salary = ""
            for p in card.find_all("p"):
                t = p.get_text(strip=True)
                if "$" in t or "/yr" in t or "/hr" in t:
                    salary = t
                    break

            quick_apply = bool(card.find(string=re.compile(r"Quick apply", re.I)))

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location_text,
                "date_posted": "",
                "apply_url": apply_url,
                "salary_listed": salary,
                "easy_apply": quick_apply,
                "platform": "ZipRecruiter",
                "description": "",
                "scraped_date": date.today().isoformat(),
            })
        except Exception:
            continue

    return jobs


def search_ziprecruiter(keywords, location, days=7):
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
                "a[data-testid='pagination-next'], "
                "li.next a"
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

    print(f"Searching ZipRecruiter: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_ziprecruiter(keywords, location, days)

    if len(jobs) < 5 and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_ziprecruiter(keywords, location, days * 2)

    output = TMP / "jobs_raw_ziprecruiter.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
