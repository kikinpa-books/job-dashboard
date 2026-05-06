"""
Interactively asks the user for job search parameters and saves them to .tmp/search_config.json.
Run this at the start of every search session.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)
OUTPUT = TMP / "search_config.json"


def ask(prompt, default=None):
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    response = input(f"{prompt}: ").strip()
    return response


def main():
    print("\n===== Job Application Agent =====")
    print("Answer the questions below to configure this search run.\n")

    title = ask("Job title / keywords (e.g. Personal Injury Paralegal)")
    if not title:
        print("Error: Job title is required.")
        sys.exit(1)

    location = ask("Location (e.g. Miami, FL  |  Remote  |  Remote or Miami, FL)")
    if not location:
        print("Error: Location is required.")
        sys.exit(1)

    salary_input = ask("Minimum salary (optional, press Enter to skip)", default="")
    min_salary = None
    if salary_input:
        cleaned = salary_input.replace("$", "").replace(",", "").strip()
        try:
            min_salary = int(float(cleaned))
        except ValueError:
            print(f"Warning: Could not parse salary '{salary_input}', skipping salary filter.")

    config = {
        "job_title": title,
        "keywords": [kw.strip() for kw in title.split(",")],
        "location": location,
        "min_salary": min_salary,
    }

    with open(OUTPUT, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nSearch config saved to {OUTPUT}")
    print(f"  Title:    {title}")
    print(f"  Location: {location}")
    print(f"  Min salary: {'Not set' if min_salary is None else f'${min_salary:,}'}")
    print()
    return config


if __name__ == "__main__":
    main()
