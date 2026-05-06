# Workflow 00: Master Orchestration

## Overview
This is the entry point. Read this first on every run. It decides which sub-workflow to execute based on context and user intent.

## Two Run Modes

### Mode A: Search and Apply (run daily or on demand)
Full pipeline: search for new jobs, filter, apply, track, refresh dashboard.

### Mode B: Follow-Up (run every 3 days)
Read the tracker, identify applications pending 7+ days, send follow-up emails.

---

## Mode A: Search and Apply

### Step 1: Get search parameters
Run `tools/prompt_search_config.py` to collect job title, location, and optional minimum salary from the user.

Check if `.tmp/jobs_filtered.json` already exists and is less than 4 hours old. If it is, skip steps 2 and 3 and go straight to Step 4.

### Step 2: Search for jobs
Follow `workflows/01_search_jobs.md`.
Run the three search tools (Indeed, Glassdoor, LinkedIn).

### Step 3: Filter listings
Follow `workflows/02_filter_jobs.md`.
Score and deduplicate results. Review any flagged listings before proceeding.

### Step 4: Apply
Follow `workflows/03_apply_jobs.md`.
For each job in the filtered list (highest score first), generate a cover letter and submit the application.
Hard stop at 10 successful applications per run.

### Step 5: Track and dashboard
After all applications are done, run:
```
python tools/update_dashboard.py
```
This refreshes the Dashboard tab in the Google Sheet.

Confirm the run summary to the user:
- How many jobs were applied to
- How many were skipped (already applied, cooldown, errors)
- Link to the Google Sheet for review

---

## Mode B: Follow-Up

Follow `workflows/05_follow_up.md`.

1. Run `tools/check_follow_up_queue.py`
2. Show the queue to the user and ask for approval before sending anything
3. Send approved follow-up emails via `tools/send_followup_email.py`
4. Update the tracker and refresh the dashboard

---

## Decision Logic

```
If the user says "follow up" or "check on my applications":
  -> Run Mode B

If the user says "search", "apply", "find jobs", or gives a job title:
  -> Run Mode A

If no instruction is given and it has been 3+ days since last run:
  -> Ask: "Run a new job search, or check on existing applications?"
```

---

## Failure Handling

| Situation | Action |
|-----------|--------|
| A search tool returns 0 results | Skip that platform, continue with others |
| CAPTCHA on LinkedIn | Save screenshot, pause, alert user to resolve manually |
| 3 consecutive application failures | Stop applying, alert user, log errors to Sheet |
| Google Sheets authentication fails | Run `python tools/sheets_client.py` to refresh token |
| Cover letter generation fails | Log the error, skip the job, continue to next |
| Session expired on LinkedIn | Re-authenticate in search tool, save new session |

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `.env` | All credentials and config |
| `.tmp/search_config.json` | Current search parameters |
| `.tmp/jobs_filtered.json` | Scored jobs ready to apply to |
| `.tmp/session_linkedin.json` | LinkedIn session cookies |
| `.tmp/follow_up_queue.json` | Applications needing follow-up |
| `resume.pdf` | Your resume (must exist in project root) |
| `cover_letter_template.md` | Base cover letter template |
| Google Sheet | Single source of truth for all applications |

---

## First-Time Setup Checklist

- [ ] Fill in all values in `.env`
- [ ] Place `resume.pdf` in the project root
- [ ] Customize `cover_letter_template.md` with your background
- [ ] Create a Google Sheet and set `GOOGLE_SHEET_ID` in `.env`
- [ ] Download `credentials.json` from Google Cloud Console to the project root
- [ ] Run `python tools/sheets_client.py` once to complete OAuth (opens browser)
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `playwright install chromium`
- [ ] Run a test search: `python tools/search_indeed.py --keywords "Paralegal" --location "Miami, FL" --days 7`
