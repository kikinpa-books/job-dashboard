# Workflow 03: Apply to Jobs

## Objective
Submit applications for each job in the filtered list that has not already been applied to.

## Required Inputs
- `.tmp/jobs_filtered.json`
- `resume.pdf` (must exist in project root)
- `cover_letter_template.md`
- `.env` fully filled in (ANTHROPIC_API_KEY, USER_FULL_NAME, USER_EMAIL, USER_PHONE, GOOGLE_SHEET_ID)

## Pre-flight Checks

Before applying to any job:
1. Confirm `resume.pdf` exists in the project root.
2. Confirm `GOOGLE_SHEET_ID` is set in `.env` (needed to log each application).
3. Confirm `ANTHROPIC_API_KEY` is set in `.env` (needed for cover letter generation).

## Steps (repeat for each job in `jobs_filtered.json`)

For each job, in order of score (highest first):

**1. Check if already applied**
Read the Applications sheet. If a row with this `job_id` already exists and status is not "Error", skip this job entirely.

**2. Check for same-company cooldown**
Read the Applications sheet. If any row for the same company has `date_applied` within the last 30 days, skip this job.

**3. Generate cover letter**
```
python tools/generate_cover_letter.py \
  --job_id "<job_id>" \
  --title "<title>" \
  --company "<company>" \
  --description "<description>"
```
Output: `.tmp/cover_letter_<job_id>.pdf`

**4. Submit the application**

Choose the right tool based on platform and easy_apply flag:
- LinkedIn + easy_apply = true: `python tools/apply_linkedin.py`
- Indeed: `python tools/apply_indeed.py`
- Glassdoor or other: `python tools/apply_generic.py`

All tools use the same argument format:
```
python tools/apply_<platform>.py \
  --job_id "<job_id>" \
  --apply_url "<apply_url>" \
  --resume_path "resume.pdf" \
  --cover_letter_path ".tmp/cover_letter_<job_id>.pdf"
```

**5. Log the result**
```
python tools/log_application.py \
  --job_id "<job_id>" \
  --title "<title>" \
  --company "<company>" \
  --location "<location>" \
  --platform "<platform>" \
  --apply_url "<apply_url>" \
  --status "Applied" \
  --cover_letter "cover_letter_<job_id>.pdf" \
  --salary "<salary_listed>" \
  --easy_apply "<true/false>"
```

If the apply tool returned `"success": false`, log with `--status "Error"` and include the error in `--notes`.

**6. Wait before next application**
Wait a random amount between 30 and 90 seconds before starting the next job.

## Hard Limits
- Stop after 10 successful applications per run (check `MAX_APPLICATIONS_PER_RUN` in `.env`).
- If 3 consecutive apply attempts fail (not counting "already applied" skips), stop and alert the user.
- Do not apply to the same company twice within 30 days.

## Output
- New rows in the Google Sheet "Applications" tab
- Screenshot per application in `.tmp/confirmation_<job_id>.png`
- Cover letter PDFs in `.tmp/cover_letter_<job_id>.pdf`

## Next Step
Run `tools/update_dashboard.py` to refresh the Dashboard tab, then proceed to `04_track_applications.md`.
