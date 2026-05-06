# Workflow 05: Follow-Up

## Objective
Identify applications with no response after 7+ days and send a polite follow-up email.

## When to Run
Every 3 days, or manually when you want to check on pending applications.

## Steps

**1. Get the follow-up queue**
```
python tools/check_follow_up_queue.py
```
This reads the Applications sheet and outputs `.tmp/follow_up_queue.json`.
Criteria for inclusion:
- Status is "Applied"
- Date applied is 7 or more days ago
- follow_up_sent column is blank

**2. Review the queue with the user**
Print the list of companies and titles that need a follow-up. Ask the user to confirm before sending anything. Do not send automatically.

Example prompt to user:
"The following applications are pending over 7 days and have no response. Would you like me to send follow-up emails to these?
  - Smith & Associates | Personal Injury Paralegal (applied 2026-04-28)
  - Jones Law Group | Litigation Paralegal (applied 2026-04-25)"

**3. Send follow-up emails**
For each approved entry in the queue (only if `to_email` is available in the tracker):
```
python tools/send_followup_email.py \
  --job_id "<job_id>" \
  --to_email "<hiring manager email>" \
  --company "<company>" \
  --title "<title>" \
  --date_applied "<date_applied>"
```

**4. Update the tracker**
After each successful send:
```
python tools/update_application.py --job_id "<job_id>" --field "follow_up_sent" --value "<today>"
python tools/update_application.py --job_id "<job_id>" --field "status" --value "Followed Up"
```

**5. Log to Follow-Up Log tab**
Append a row to the "Follow-Up Log" sheet tab:
- job_id, company, title, date_sent = today, method = "Email", response_received = (blank)

**6. Refresh the Dashboard**
```
python tools/update_dashboard.py
```

## LinkedIn Follow-Ups
Do not attempt to automate LinkedIn direct messages. It is too risky and likely to result in account restriction.
Instead, flag these entries for the user to handle manually.

## Follow-Up Email Tone Guidelines
- No em dashes (—) anywhere in the message.
- Keep it short, 3-4 sentences maximum.
- Sound like a real person. Do not use formal corporate phrasing.
- Express genuine continued interest, not desperation.
- Do not demand a timeline.

## Email Template (used by `send_followup_email.py`)
> Subject: Following Up: {title} Application
>
> Dear Hiring Manager,
>
> I wanted to follow up on my application for the {title} position at {company}, which I submitted on {date_applied}.
>
> I remain very interested in this opportunity. My background in legal support and client advocacy aligns well with what your firm needs, and I would welcome the chance to speak with you further.
>
> Please let me know if you need any additional materials from me. Thank you for your time and consideration.
>
> Best regards,
> {user_name}

## Output
- Updated status and follow_up_sent date in the Applications sheet
- New rows in the Follow-Up Log sheet
- Refreshed Dashboard
