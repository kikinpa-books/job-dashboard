"""
Merges raw job files from all platforms, scores each listing, deduplicates,
and writes .tmp/jobs_filtered.json with only the candidates worth applying to.

Usage:
  python tools/filter_jobs.py
  python tools/filter_jobs.py --min_score 2
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"

EXCLUDE_TITLE_KEYWORDS = [
    "intern", "internship", "volunteer", "law clerk", "law student",
]

REQUIRE_JD_PATTERNS = [
    r"\bjd\b", r"juris doctor", r"bar passage", r"licensed attorney",
    r"esquire", r"\besq\b", r"j\.d\.",
]


def load_search_config():
    config_file = TMP / "search_config.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {}


def load_raw_jobs():
    all_jobs = []
    for fname in ["jobs_raw_adzuna.json", "jobs_raw_indeed.json", "jobs_raw_linkedin.json",
                  "jobs_raw_glassdoor.json", "jobs_raw_ziprecruiter.json", "jobs_raw_simplyhired.json"]:
        path = TMP / fname
        if path.exists():
            with open(path) as f:
                jobs = json.load(f)
            all_jobs.extend(jobs)
            print(f"  Loaded {len(jobs)} jobs from {fname}")
        else:
            print(f"  Skipping {fname} (not found)")
    return all_jobs


def normalize_salary(salary_str):
    if not salary_str:
        return None
    numbers = re.findall(r"[\d,]+", salary_str.replace("$", ""))
    if not numbers:
        return None
    values = [int(n.replace(",", "")) for n in numbers]
    avg = sum(values) / len(values)
    if avg < 1000:
        avg *= 1000
    return int(avg)


def score_job(job, config):
    title = job.get("title", "").lower()
    description = job.get("description", "").lower()
    location = job.get("location", "").lower()
    salary = normalize_salary(job.get("salary_listed", ""))

    score = 0
    keywords = config.get("keywords", [])
    job_title_input = config.get("job_title", "").lower()
    pref_location = config.get("location", "").lower()
    min_salary = config.get("min_salary")

    for kw in keywords:
        if kw.lower() in title:
            score += 3
            break

    if "paralegal" in title:
        score += 1
    if "legal" in title:
        score += 1

    if pref_location:
        pref_city = pref_location.split(",")[0].strip().lower()
        if pref_city in location or "remote" in location or "remote" in pref_location.lower():
            score += 1

    text = title + " " + description
    requires_jd = any(re.search(p, text) for p in REQUIRE_JD_PATTERNS)
    is_attorney_search = any(w in job_title_input for w in ["attorney", "lawyer", "counsel"])
    if requires_jd and not is_attorney_search:
        score -= 2

    if salary and min_salary and salary < min_salary:
        score -= 2

    return score, requires_jd


def deduplicate(jobs):
    seen = {}
    for job in jobs:
        key = (job.get("company", "").lower().strip(), job.get("title", "").lower().strip())
        existing = seen.get(key)
        if not existing:
            seen[key] = job
        else:
            platform_priority = {"LinkedIn": 3, "Indeed": 2, "Glassdoor": 1}
            if platform_priority.get(job.get("platform"), 0) > platform_priority.get(existing.get("platform"), 0):
                seen[key] = job
    return list(seen.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min_score", type=int, default=1)
    args = parser.parse_args()

    config = load_search_config()
    if not config:
        print("WARNING: .tmp/search_config.json not found. Scoring will use generic rules.")

    print("Loading raw job files...")
    all_jobs = load_raw_jobs()
    if not all_jobs:
        print("WARNING: No raw job files found — writing empty filter output.")
        output = TMP / "jobs_filtered.json"
        manual_output = TMP / "jobs_manual.json"
        with open(output, "w") as f:
            json.dump([], f)
        with open(manual_output, "w") as f:
            json.dump([], f)
        return

    print(f"\nScoring {len(all_jobs)} total listings...")
    scored = []
    for job in all_jobs:
        title_lower = job.get("title", "").lower()
        if any(kw in title_lower for kw in EXCLUDE_TITLE_KEYWORDS):
            continue
        score, requires_jd = score_job(job, config)
        if score >= args.min_score:
            job["score"] = score
            job["flagged_requires_jd"] = requires_jd
            scored.append(job)

    print(f"After scoring: {len(scored)} pass the threshold (min score {args.min_score})")

    # Only Indeed jobs are auto-applied remotely; everything else goes to manual review
    AUTO_PLATFORMS = {"Indeed"}
    # Adzuna redirects to external sites so always manual

    auto = [j for j in scored if j.get("platform") in AUTO_PLATFORMS]
    manual = [j for j in scored if j.get("platform") not in AUTO_PLATFORMS]

    # Also surface all non-Indeed LinkedIn/ZipRecruiter/SimplyHired jobs that scored below
    # threshold (so user sees them even if they didn't pass scoring)
    manual_ids = {j.get("job_id") for j in manual}
    for job in all_jobs:
        if job.get("platform") in AUTO_PLATFORMS:
            continue
        title_lower = job.get("title", "").lower()
        if any(kw in title_lower for kw in EXCLUDE_TITLE_KEYWORDS):
            continue
        if job.get("job_id") not in manual_ids:
            manual.append(job)
            manual_ids.add(job.get("job_id"))

    REASON_MAP = {
        "LinkedIn": "LinkedIn non-Easy-Apply",
        "ZipRecruiter": "Apply on ZipRecruiter",
        "SimplyHired": "Apply on SimplyHired",
        "Glassdoor": "Apply on Glassdoor",
    }
    for job in manual:
        platform = job.get("platform", "")
        job["reason"] = REASON_MAP.get(platform, f"Apply on {platform}")
        # Clean duplicated title text (LinkedIn scraper artifact)
        title = job.get("title", "")
        mid = len(title) // 2
        if title[:mid] == title[mid:]:
            job["title"] = title[:mid]
        elif " with verification" in title:
            job["title"] = title.split(" with verification")[0]

    auto = deduplicate(auto)
    auto.sort(key=lambda j: j["score"], reverse=True)
    manual = deduplicate(manual)

    print(f"After deduplication: {len(auto)} auto-apply, {len(manual)} manual-apply listings")

    output = TMP / "jobs_filtered.json"
    with open(output, "w") as f:
        json.dump(auto, f, indent=2)

    manual_output = TMP / "jobs_manual.json"
    with open(manual_output, "w") as f:
        json.dump(manual, f, indent=2)

    print(f"\nTop 5 auto-apply results:")
    for job in auto[:5]:
        print(f"  [{job['score']}] {job['company']} | {job['title']} | {job['location']} | {job['platform']}")

    print(f"\nSaved {len(auto)} filtered jobs to {output}")
    print(f"Saved {len(manual)} manual-apply jobs to {manual_output}")


if __name__ == "__main__":
    main()
