"""
Searches Adzuna API for job listings and saves results to .tmp/jobs_raw_adzuna.json.
Adzuna aggregates Indeed, LinkedIn, ZipRecruiter, and other boards.

Requires env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY
Free tier: https://developer.adzuna.com (250 calls/month)

Usage:
  python tools/search_adzuna.py --keywords "Paralegal" --location "Fort Lauderdale, FL"
  python tools/search_adzuna.py  # reads from .tmp/search_config.json
"""

import argparse
import http.client
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/us/search"
RESULTS_PER_PAGE = 50


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


def fetch_json(url):
    req = Request(url, headers={"User-Agent": "KikinpaJobTracker/1.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


DOMAIN_TO_PLATFORM = {
    "indeed.com":        "Indeed",
    "linkedin.com":      "LinkedIn",
    "ziprecruiter.com":  "ZipRecruiter",
    "simplyhired.com":   "SimplyHired",
    "glassdoor.com":     "Glassdoor",
    "monster.com":       "Monster",
    "careerbuilder.com": "CareerBuilder",
    "dice.com":          "Dice",
    "jobble.com":        "Jobble",
    "snagajob.com":      "Snagajob",
    "recruitics.com":    "Recruitics",
    "lever.co":          "Lever",
    "greenhouse.io":     "Greenhouse",
    "workday.com":       "Workday",
    "icims.com":         "iCIMS",
}


def _platform_from_host(host):
    host = host.lower().lstrip("www.")
    for domain, name in DOMAIN_TO_PLATFORM.items():
        if domain in host:
            return name
    return None


def _source_from_url(url):
    if not url:
        return "Adzuna"
    try:
        parsed = urlparse(url)
        # Check if the URL already points to a known board directly
        direct = _platform_from_host(parsed.netloc)
        if direct:
            return direct
        # Follow one redirect to find the real destination
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=5)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        conn.request("HEAD", path, headers={"User-Agent": "KikinpaJobTracker/1.0"})
        resp = conn.getresponse()
        location = resp.getheader("Location", "")
        conn.close()
        if location:
            dest_host = urlparse(location).netloc
            found = _platform_from_host(dest_host)
            if found:
                return found
    except Exception:
        pass
    return "Adzuna"


def search_adzuna(keywords, location, days=7, max_pages=3):
    app_id  = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("ERROR: ADZUNA_APP_ID and ADZUNA_APP_KEY must be set.")
        return []

    # Extract city from "Fort Lauderdale, FL" → "Fort Lauderdale"
    city = location.split(",")[0].strip() if location else ""

    all_jobs = []
    for page in range(1, max_pages + 1):
        params = {
            "app_id":           app_id,
            "app_key":          app_key,
            "results_per_page": RESULTS_PER_PAGE,
            "what":             keywords,
            "where":            city,
            "distance":         20,
            "sort_by":          "date",
            "max_days_old":     days,
            "content-type":     "application/json",
        }
        url = f"{ADZUNA_BASE}/{page}?{urlencode(params)}"

        try:
            data = fetch_json(url)
        except HTTPError as e:
            print(f"  Adzuna API error on page {page}: {e.code} {e.reason}")
            break
        except Exception as e:
            print(f"  Adzuna request failed on page {page}: {e}")
            break

        results = data.get("results", [])
        if not results:
            print(f"  Page {page}: no results, stopping.")
            break

        print(f"  Page {page}: {len(results)} listings")

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        for r in results:
            created = r.get("created", "")
            if created and created < cutoff:
                continue

            job_id = f"adzuna_{r.get('id', '')}"
            title   = r.get("title", "").strip()
            company = r.get("company", {}).get("display_name", "").strip()
            loc     = r.get("location", {}).get("display_name", "").strip()
            url_job = r.get("redirect_url", "")
            salary_min = r.get("salary_min")
            salary_max = r.get("salary_max")
            salary = ""
            if salary_min and salary_max:
                salary = f"${int(salary_min):,} – ${int(salary_max):,}/yr"
            elif salary_min:
                salary = f"${int(salary_min):,}+/yr"

            # Extract the source board from the redirect URL
            platform = _source_from_url(url_job)

            all_jobs.append({
                "job_id":        job_id,
                "title":         title,
                "company":       company,
                "location":      loc,
                "date_posted":   created[:10] if created else "",
                "apply_url":     url_job,
                "salary_listed": salary,
                "easy_apply":    False,
                "platform":      platform,
                "description":   r.get("description", "")[:500],
                "scraped_date":  date.today().isoformat(),
            })

        if len(results) < RESULTS_PER_PAGE:
            break

        time.sleep(0.5)

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--days",     type=int, default=7)
    args = parser.parse_args()

    keywords, location, days = load_config(args)
    if not keywords:
        print("ERROR: No keywords provided.")
        sys.exit(1)

    print(f"Searching Adzuna: '{keywords}' in '{location}' (last {days} days)...")
    jobs = search_adzuna(keywords, location, days)

    if not jobs and days < 14:
        print(f"Only {len(jobs)} results. Retrying with {days * 2} days...")
        jobs = search_adzuna(keywords, location, days * 2)

    output = TMP / "jobs_raw_adzuna.json"
    with open(output, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"Done. {len(jobs)} jobs saved to {output}")


if __name__ == "__main__":
    main()
