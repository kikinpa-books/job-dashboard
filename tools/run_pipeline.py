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

MAX_APPLICATIONS = 10


def run(cmd, **kwargs):
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), **kwargs)
    return result.returncode == 0


def main():
    env = {**os.environ, "HEADLESS": os.environ.get("HEADLESS", "1")}

    # 1. Search Indeed
    print("\n=== Step 1: Search Indeed ===")
    ok = run([sys.executable, "tools/search_indeed.py"], env=env)
    if not ok:
        print("WARNING: Indeed search failed, continuing with existing data if available.")

    # 2. Filter
    print("\n=== Step 2: Filter jobs ===")
    ok = run([sys.executable, "tools/filter_jobs.py"], env=env)
    if not ok:
        print("ERROR: filter_jobs.py failed.")
        sys.exit(1)

    # 3. Apply
    print("\n=== Step 3: Apply to Indeed jobs ===")
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

    # 4. Export dashboard
    print("\n=== Step 4: Export dashboard data ===")
    run([sys.executable, "tools/export_dashboard_data.py"], env=env)

    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()
