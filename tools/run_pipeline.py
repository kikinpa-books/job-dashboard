"""
Full job application pipeline orchestrator.

Steps:
  1. Search Indeed
  2. Filter jobs (Indeed → auto-apply, others → manual tab)
  3. Apply to Indeed jobs (skip FBI / attorney / counsel titles, max 10)
  4. Export dashboard data to docs/data/applications.json

Usage:
  python tools/run_pipeline.py
  HEADLESS=1 python tools/run_pipeline.py  # headless mode for remote/CI
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)

SKIP_TITLE_KEYWORDS = [
    "fbi", "special agent", "attorney", "counsel",
]

MAX_APPLICATIONS = 5


def run(cmd, **kwargs):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), **kwargs)
    return result.returncode == 0


def main():
    env = {**os.environ, "HEADLESS": os.environ.get("HEADLESS", "1")}

    # Load search config to get all job titles
    config_path = TMP / "search_config.json"
    job_titles = ["Personal Injury Paralegal"]
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        job_titles = cfg.get("job_titles") or [cfg.get("job_title", "Personal Injury Paralegal")]

    def search_platform(step_name, script, raw_filename):
        print(f"\n=== {step_name} ===")
        raw_path = TMP / raw_filename
        all_raw = []
        for title in job_titles:
            print(f"\n  Searching: '{title}'")
            run([sys.executable, script, "--keywords", title], env=env)
            if raw_path.exists():
                with open(raw_path) as f:
                    batch = json.load(f)
                all_raw.extend(batch)
                print(f"  Found {len(batch)} jobs for '{title}'")
        seen_ids = set()
        merged = []
        for job in all_raw:
            jid = job.get("job_id", "")
            if jid not in seen_ids:
                seen_ids.add(jid)
                merged.append(job)
        with open(raw_path, "w") as f:
            json.dump(merged, f, indent=2)
        print(f"  Total unique: {len(merged)}")

    # 1. Search all platforms
    search_platform("Step 1: Search Adzuna (aggregated)",  "tools/search_adzuna.py",      "jobs_raw_adzuna.json")
    search_platform("Step 2: Search Indeed",               "tools/search_indeed.py",      "jobs_raw_indeed.json")
    search_platform("Step 3: Search ZipRecruiter",         "tools/search_ziprecruiter.py", "jobs_raw_ziprecruiter.json")
    search_platform("Step 4: Search SimplyHired",          "tools/search_simplyhired.py",  "jobs_raw_simplyhired.json")

    # 4. Filter
    print("\n=== Step 4: Filter jobs ===")
    ok = run([sys.executable, "tools/filter_jobs.py"], env=env)
    if not ok:
        print("ERROR: filter_jobs.py failed.")
        sys.exit(1)

    # 5. Apply
    print("\n=== Step 5: Apply to Indeed jobs ===")
    filtered_path = TMP / "jobs_filtered.json"
    if not filtered_path.exists():
        print("No jobs_filtered.json found, skipping apply step.")
    else:
        with open(filtered_path) as f:
            jobs = json.load(f)

        applied = 0
        for job in jobs:
            if applied >= MAX_APPLICATIONS:
                print(f"Reached max {MAX_APPLICATIONS} applications, stopping.")
                break

            title_lower = job.get("title", "").lower()
            if any(kw in title_lower for kw in SKIP_TITLE_KEYWORDS):
                print(f"  SKIP (excluded title): {job['company']} | {job['title']}")
                continue

            job_id = job["job_id"]
            apply_url = job["apply_url"]
            company = job.get("company", "")
            title = job.get("title", "")

            print(f"\n  Applying: {company} | {title}")

            # Generate cover letter
            cover_letter_path = TMP / f"cover_letter_{job_id}.pdf"
            run([
                sys.executable, "tools/generate_cover_letter.py",
                "--job_id", job_id,
                "--title", title,
                "--company", company,
                "--description", job.get("description", ""),
            ], env=env)

            # Apply
            result = subprocess.run(
                [
                    sys.executable, "tools/apply_indeed.py",
                    "--job_id", job_id,
                    "--apply_url", apply_url,
                    "--resume_path", "resume.pdf",
                    "--cover_letter_path", str(cover_letter_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )

            try:
                output = json.loads(result.stdout.strip().splitlines()[-1])
                success = output.get("success", False)
                error = output.get("error")
            except Exception:
                success = result.returncode == 0
                error = result.stderr[:200] if result.stderr else None

            if success:
                applied += 1
                print(f"    Applied ({applied}/{MAX_APPLICATIONS})")
                run([
                    sys.executable, "tools/log_application.py",
                    "--job_id", job_id,
                    "--title", title,
                    "--company", company,
                    "--location", job.get("location", ""),
                    "--platform", job.get("platform", "Indeed"),
                    "--apply_url", apply_url,
                ], env=env)
            else:
                print(f"    FAILED: {error}")

        print(f"\nApplied to {applied} jobs.")

    # 6. Apply to ATS-hosted jobs (Greenhouse, Lever, iCIMS, Workday)
    print("\n=== Step 6: Apply to ATS jobs ===")
    ats_path = TMP / "jobs_filtered_ats.json"
    if not ats_path.exists():
        print("No jobs_filtered_ats.json found, skipping ATS apply step.")
    else:
        with open(ats_path) as f:
            ats_jobs = json.load(f)

        ats_applied = 0
        for job in ats_jobs:
            if ats_applied >= MAX_APPLICATIONS:
                print(f"Reached max {MAX_APPLICATIONS} ATS applications, stopping.")
                break

            title_lower = job.get("title", "").lower()
            if any(kw in title_lower for kw in SKIP_TITLE_KEYWORDS):
                print(f"  SKIP (excluded title): {job['company']} | {job['title']}")
                continue

            job_id    = job["job_id"]
            apply_url = job["apply_url"]
            company   = job.get("company", "")
            title     = job.get("title", "")
            platform  = job.get("platform", "ATS")

            print(f"\n  Applying [{platform}]: {company} | {title}")

            cover_letter_path = TMP / f"cover_letter_{job_id}.pdf"
            run([
                sys.executable, "tools/generate_cover_letter.py",
                "--job_id", job_id,
                "--title", title,
                "--company", company,
                "--description", job.get("description", ""),
            ], env=env)

            result = subprocess.run(
                [
                    sys.executable, "tools/apply_generic.py",
                    "--job_id", job_id,
                    "--apply_url", apply_url,
                    "--resume_path", "resume.pdf",
                    "--cover_letter_path", str(cover_letter_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )

            try:
                output = json.loads(result.stdout.strip().splitlines()[-1])
                success = output.get("success", False)
                error   = output.get("error")
            except Exception:
                success = result.returncode == 0
                error   = result.stderr[:200] if result.stderr else None

            if success:
                ats_applied += 1
                print(f"    Applied ({ats_applied}/{MAX_APPLICATIONS})")
                run([
                    sys.executable, "tools/log_application.py",
                    "--job_id", job_id,
                    "--title", title,
                    "--company", company,
                    "--location", job.get("location", ""),
                    "--platform", platform,
                    "--apply_url", apply_url,
                ], env=env)
            else:
                print(f"    FAILED: {error}")

        print(f"\nApplied to {ats_applied} ATS jobs.")

    # 7. Export dashboard
    print("\n=== Step 7: Export dashboard data ===")
    run([sys.executable, "tools/export_dashboard_data.py"], env=env)

    print("\n=== Pipeline complete ===")



if __name__ == "__main__":
    main()
