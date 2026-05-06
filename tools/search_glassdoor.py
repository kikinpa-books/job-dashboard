"""
Searches Glassdoor for job listings and saves results to .tmp/jobs_raw_glassdoor.json.

Usage:
  python tools/search_glassdoor.py --keywords "Personal Injury Paralegal" --location "Miami, FL" --days 7
  python tools/search_glassdoor.py  # reads from .tmp/search_config.json
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


def build_glassdoor_url(keywords, location, days):
    from urllib.parse import urlencode
    params = {
        "keyword": keywords,
        "locT": "C",
        "locName": location,
        "fromAge": days,
        "sort.descending": "true",
        "sort.sortType": "date",
    }
    return "https://www.glassdoor.com/Job/jobs.htm?" + urlencode(params)


def parse_glassdoor_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.select("li.react-job-listing, article.JobCard")
    for card in cards:
        try:
            title_el = card.select_one("a[data-test='job-title'], .JobCard_jobTitle__GLyJ1")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            job_id_match = re.search(r"jobListingId=(\d+)|/job-listing/[^/]+-JV_IC\d+_KO\d+,\d+_KE(\d+),", href)
            raw_id = job_id_match.group(1) if job_id_match and job_id_match.group(1) else hash(title + href)
            job_id = f"glassdoor_{raw_id}"
            apply_url = f"https://www.glassdoor.com{href}" if href.startswith("/") else href

            company_el = card.select_one("[data-test='employer-name'], .EmployerProfile_employerName__Ug7W8")
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one("[data-test='emp-location'], .JobCard_location__N_iYE")
            location = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.select_one("[data-test='detailSalary'], .JobCard_salaryEstimate__QpbTW")
            salary = salary_el.get_text(strip=True) if salary_el else ""

            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "date_posted": "",
                "apply_url": apply_url,
                "salary_listed": salary,
                "easy_apply": False,
                "platform": "Glassdoor",
                "description": "",
                "scraped_date": date.today().isoformat(),
            })
        except Exception:
            continue

    return jobs


def search_glassdoor(keywords, location, days=7):
    url = build_glassdoor_url(keywords, location, days)
    all_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(3, 5))

        close_btn = page.query_selector("button.modal_closeIcon, [alt='Close']")
        if close_btn:
            close_btn.click()
            time.sleep(1)

        for page_num in range(1, 4):
            html = page.content()
            jobs = parse_glassdoor_jobs(html)
            if not jobs:
                break
            all_jobs.extend(jobs)
            print(f"  Page {page_num}: found {len(jobs)} listings")

            next_btn = page.query_selector("button[data-test='pagination-next'], li.next button")
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

    print(f"Searching Glassdoor: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_glassdoor(keywords, location, days)

    if len(jobs) < 5 and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_glassdoor(keywords, location, days * 2)

    output = TMP / "jobs_raw_glassdoor.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
