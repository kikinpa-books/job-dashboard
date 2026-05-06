# Workflow 01: Search Jobs

## Objective
Collect raw job listings from LinkedIn, Indeed, and Glassdoor based on the user's current search configuration.

## Required Inputs
- `.tmp/search_config.json` (created by `tools/prompt_search_config.py`)
  - `job_title`: search keywords
  - `location`: city/state or "Remote"
  - `min_salary`: optional minimum salary filter

## Steps

1. Verify `.tmp/search_config.json` exists. If not, run `tools/prompt_search_config.py` first.

2. Run each search tool. These can run sequentially (LinkedIn is most likely to need attention):
   ```
   python tools/search_indeed.py
   python tools/search_glassdoor.py
   python tools/search_linkedin.py
   ```

3. Each tool reads `search_config.json` automatically if no arguments are passed.

4. Each tool writes its output:
   - `.tmp/jobs_raw_indeed.json`
   - `.tmp/jobs_raw_glassdoor.json`
   - `.tmp/jobs_raw_linkedin.json`

## Edge Cases

**CAPTCHA on LinkedIn:** The tool will save a screenshot to `.tmp/linkedin_search.png` and pause. Complete the CAPTCHA manually in the browser window, then press Enter in the terminal.

**0 results from a platform:** The tools will automatically retry with double the date range (up to 14 days). If still empty, skip that platform and continue.

**LinkedIn session expired:** The tool will re-authenticate. If login fails due to security checkpoint, handle it manually.

**Rate limiting:** Each tool waits 2-4 seconds between page loads. Do not run all three tools simultaneously.

## Output
- `.tmp/jobs_raw_indeed.json`
- `.tmp/jobs_raw_linkedin.json`
- `.tmp/jobs_raw_glassdoor.json`

## Next Step
Proceed to `02_filter_jobs.md`.
