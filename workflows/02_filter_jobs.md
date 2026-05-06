# Workflow 02: Filter Jobs

## Objective
Score, deduplicate, and filter the raw job listings down to a quality set worth applying to.

## Required Inputs
- `.tmp/jobs_raw_indeed.json` (at least one raw file must exist)
- `.tmp/search_config.json` (used to tune scoring dynamically)

## Steps

1. Run the filter tool:
   ```
   python tools/filter_jobs.py
   ```

2. Review the top results printed to the terminal. Pay attention to any jobs flagged as `flagged_requires_jd: true`.

3. If any listings look like obvious mismatches (wrong field, internships, duplicates that slipped through), remove them from `.tmp/jobs_filtered.json` manually or note them as skipped.

4. If the filtered list is very short (fewer than 3 jobs), consider whether to widen the search by running `01_search_jobs.md` with a broader keyword or larger date window.

## Scoring Logic (automatic, in `filter_jobs.py`)
- +3: Job title contains any keyword from the user's search input
- +1: Title contains "paralegal" or "legal"
- +1: Location matches preference or is Remote
- -2: Description requires bar passage, JD, or licensed attorney (unless user searched for "attorney")
- -2: Listed salary is below user's minimum (if set)
- Threshold: score >= 1 to pass
- Deduplication: keep best platform version of same company + title pair (LinkedIn > Indeed > Glassdoor)

## Output
- `.tmp/jobs_filtered.json` — scored and ranked list ready for applications

## Next Step
Proceed to `03_apply_jobs.md`.
