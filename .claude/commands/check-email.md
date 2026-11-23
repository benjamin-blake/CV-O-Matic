---
description: Read Gmail for application-related activity since the last run, append email links to applications.yaml, auto-flip status on high confidence (confirmation / rejection), surface unmatched recruiter outreach for manual triage, and push a digest notification to your phone via ntfy. Designed for a daily scheduled routine.
argument-hint: [--dry-run] [--since YYYY-MM-DD] [--no-notify]
---

# /check-email

Query the authorised Gmail account for application-related activity since the last run, attach the matching emails to entries in `applications.yaml`, and auto-flip status only on high confidence. Open a PR. **British English** throughout. No em-dashes.

This routine is the post-discovery counterpart to `/scan-indeed` and `/scan-companies`: those find new jobs; this updates the status of the ones already in flight.

Supports `--dry-run` (no commit / no PR; the ntfy push is still sent with a `[DRY RUN]` title prefix so the notification step can be exercised in isolation), `--since YYYY-MM-DD` (override the watermark for backfill / debugging), and `--no-notify` (skip the ntfy push step entirely).

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. Scheduled runs exit quietly without committing, opening a PR, or notifying.

## Step 1: Load state and watermark

Read `applications.yaml`. Note `metadata.last_check_email_run` - this is the watermark for the Gmail search. If absent or `--since` was passed, default to 7 days ago (UTC).

Build a lookup keyed by lowercase `{company} | {title}` -> entry. Also pre-compute a list of `(company, slug)` pairs for fuzzy company-only matching when the title doesn't appear in the subject.

## Step 2: Gmail search

Use the Gmail MCP `search_threads` tool. If the Gmail MCP server is not connected in this environment, log "Gmail MCP unavailable, aborting" and exit cleanly with no commit - do not error out.

**Search query:**

```
after:{watermark_date} -in:trash -in:spam (
  from:(no-reply@greenhouse.io OR @lever.co OR @workday.com OR @smartrecruiters.com OR @ashbyhq.com OR @recruitee.com OR @bamboohr.com OR @teamtailor.com OR @pinpointhq.com)
  OR subject:(application OR interview OR opportunity OR "next steps" OR "we'd like to" OR shortlist OR offer OR rejected OR rejection OR unfortunately OR "thanks for applying")
  OR body:("we received your application" OR "moving forward" OR "schedule a call" OR "phone screen" OR "unfortunately" OR "offer letter" OR "delighted to offer")
)
```

The query is scoped to the authorised Gmail account's own mailbox; it deliberately contains no hard-coded address. If an address is needed (for example to tell sent mail from received), read it from `cv/cv_core_data.yaml -> personal_info.email` or use `from:me` / `to:me`.

Cap results at 100 to bound cost. If the cap is hit, expand the watermark on the next run by shortening the lookback.

For each thread returned, fetch the first message via `get_thread` and extract: `id` (thread id), `subject`, `from` (sender email + name), `date` (UTC ISO), `body_snippet` (first ~1500 chars).

## Step 3: Classify each message

For each message, classify into one `EmailActivityType`:

| Type | Signals |
|---|---|
| `confirmation` | "we received your application", "thanks for applying", typical ATS auto-reply |
| `additional_questions` | "could you provide", "complete this assessment", "take-home", "answer a few questions" |
| `interview_invitation` | "we'd like to schedule", "phone screen", "next step", "speak with you" |
| `interview_scheduled` | "your interview is confirmed", "calendar invite", explicit date+time confirmation after prior invitation |
| `rejection` | "unfortunately", "not moving forward", "we won't be progressing", "decided to proceed with other candidates" |
| `offer` | "offer letter", "delighted to offer", "extending an offer", explicit salary in body |
| `withdrawn` | role pulled, company-side withdrawal (rare) |
| `other` | recruiter outreach, networking, ambiguous |

Where the type is ambiguous, prefer `other` and surface for manual triage rather than guessing.

## Step 4: Match each message to an applications.yaml entry

For each classified message, attempt to match in this order:

1. **Exact subject contains company + role keyword** (e.g. "Home Office - Senior Data Analyst").
2. **Sender domain matches a known company domain** (for example `@examplecorp.com`) combined with title overlap from subject/body. Build the sender domain -> company map from `config/company_watchlist.yaml :: companies[*].careers_url`.
3. **Body mentions company + title** with reasonable token overlap.
4. **Sender or subject mentions company name** only - log as low-confidence match.

If multiple candidates match, pick the most recent open entry; flag the ambiguity in the report.

If no match at all and `type != "other"`: surface in the "Unmatched - manual triage" section of the PR.

If no match and `type == "other"`: this is most likely cold recruiter outreach. Surface in the "Unmatched recruiter outreach" section with subject, sender, snippet, and Gmail link. **Do not auto-create** an `applications.yaml` entry - the user reviews these manually.

## Step 5: Update applications.yaml

For each matched message, build the email-activity record:

```python
from models.applications_index import load, save, append_email_activity, set_status, set_last_run

data = load()

for msg in matched_messages:
    link = f"https://mail.google.com/mail/u/0/#inbox/{msg['thread_id']}"
    append_email_activity(
        data,
        slug=msg["slug"],
        date=msg["date"][:10],
        type=msg["type"],
        subject=msg["subject"],
        sender=msg["from"],
        link=link,
        summary=msg.get("summary"),  # 1-2 sentences for interview slots, offer terms, etc.
    )
    # Auto-flip status only on high confidence:
    if msg["type"] == "rejection":
        set_status(data, msg["slug"], "rejected", notes=f"Rejection email {msg['date'][:10]}: {msg['subject']}")
    elif msg["type"] == "confirmation" and data["applications"][msg["slug"]]["status"] == "open":
        # An ATS confirmation email is proof the candidate actually submitted the application -
        # flip open -> applied. Only from "open": never override declined/closed/rejected,
        # and never re-flip an entry already marked applied.
        set_status(data, msg["slug"], "applied", notes=f"Application confirmation email {msg['date'][:10]}: {msg['subject']}")
    # offer / interview_invitation / interview_scheduled: log only, do not flip.

set_last_run(data, "check_email")
save(data)
```

**Status-flip policy (conservative):**

| Email type | Status change? |
|---|---|
| `confirmation` | Flip `open` -> `applied`. An ATS "we received your application" auto-reply is treated as proof the candidate submitted. Only applies from `open`; a confirmation on an entry that is already `applied`/`declined`/`closed`/`rejected` is logged but does not change status. |
| `additional_questions` | None. Log only. |
| `interview_invitation` | None. Surface prominently in PR. |
| `interview_scheduled` | None. Surface prominently in PR. |
| `rejection` | Flip to `rejected`. |
| `offer` | None. Surface prominently in PR - the user acts manually. |
| `withdrawn` | None. Surface in PR. |
| `other` | None. |

`append_email_activity` is idempotent on `link`, so re-running over the same date range is safe.

## Step 6: Commit, push, open PR

If `--dry-run`: print the report and skip the commit.

```bash
if git rev-parse --abbrev-ref HEAD | grep -qE '^(main|master)$'; then
  git checkout -b "claude/check-email-$(date -u +%Y%m%d-%H%M%S)"
fi

git add applications.yaml
git commit -m "check-email: {S} status changes, {A} activity logged ({YYYY-MM-DD})"
git push -u origin HEAD

branch=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$(gh pr list --head "$branch" --json number --jq '.[0].number')" ]; then
  gh pr create \
    --base main \
    --title "check-email: {S} status changes, {A} activity logged ({YYYY-MM-DD})" \
    --body "{report from Step 7}"
fi
```

The diff is scoped to `applications.yaml`, so `auto-merge-routine.yml` will pass scope-check and squash-merge automatically. The merge fires `sync-drive.yml`, pushing the updated index to Drive root.

If there are zero matches AND zero unmatched-for-triage, still commit (the watermark advances) and open a PR - keeps the cadence visible.

## Step 7: Report

Return to the caller AND use as the PR body:

```
## /check-email - {DD Month YYYY}

Watermark: {last_check_email_run} -> {now}

### Status changes ({S})
- **Home Office - Senior Data Analyst**: applied -> rejected
  Email: {subject} ({date})
  https://mail.google.com/mail/u/0/#inbox/{thread_id}
- **Scotland Yard - Analytics Manager**: open -> applied
  Email: {subject} ({date})
  https://mail.google.com/mail/u/0/#inbox/{thread_id}

### [OFFER] (if any)
- **{Company} - {Title}**: offer received
  {summary - extracted terms if visible}
  https://mail.google.com/mail/u/0/#inbox/{thread_id}
  Next step: tell Claude Code about this offer (or paste the terms) to get a negotiation brief - the `negotiate-on-offer` skill picks it up automatically, no need to remember `/negotiate {slug}`.

### [INTERVIEW INVITATIONS] (if any)
- **{Company} - {Title}**: interview proposed
  {summary - proposed date/time if extractable}
  https://mail.google.com/mail/u/0/#inbox/{thread_id}

### Activity logged ({A})
- **{Company} - {Title}**: {type} on {date} - {subject}
  https://mail.google.com/mail/u/0/#inbox/{thread_id}
- ...

### Unmatched - manual triage ({U})
Likely application responses I could not match to an existing entry. Edit applications.yaml or run /scan-indeed if these correspond to a new role.

- {subject} from {sender}
  {first 200 chars of body}
  https://mail.google.com/mail/u/0/#inbox/{thread_id}

### Unmatched recruiter outreach ({R})
Cold approaches about specific roles - not added to applications.yaml automatically. Review and add manually if of interest.

- {subject} from {sender}
  {first 200 chars of body}
  https://mail.google.com/mail/u/0/#inbox/{thread_id}
```

## Step 8: ntfy push notification

Unless `--no-notify` was passed, push a digest notification to the user's phone via ntfy. This is the notification surface, since the routine runs unattended and the summary is best on the lock screen rather than buried in a PR. See `## Notifications (ntfy)` in `CLAUDE.md` for the full ntfy setup and the URL secret.

The push is one HTTP POST via `curl`. Title summarises the run (status changes + any offer / interview flags); body is a trimmed Step 7 report; `Click` header opens the PR (or the first Gmail thread on `--dry-run` when there is no PR). Always `default` priority unless an offer or interview invitation is present, in which case bump to `high` so the phone breaks through Do Not Disturb.

```bash
# Skip the push entirely if --no-notify was passed.
if [ "${NO_NOTIFY:-0}" = "1" ]; then
  exit 0
fi

# Skip with a warning if the URL is not configured. Don't fail the routine.
if [ -z "${NTFY_URL:-}" ]; then
  echo "NTFY_URL not set; skipping push notification." >&2
  exit 0
fi

# Build the title from the run's signals (S = status changes, A = activity logged,
# any_offers / any_interview_invitations = bool flags from Step 5).
prefix=""
[ "${DRY_RUN:-0}" = "1" ] && prefix="[DRY RUN] "

if [ "${any_offers}" = "true" ]; then
  title="${prefix}OFFER - check-email"
  priority="high"
  tags="tada,mailbox"
elif [ "${any_interview_invitations}" = "true" ]; then
  title="${prefix}Interview invitation - check-email"
  priority="high"
  tags="calendar,mailbox"
elif [ "${S}" -gt 0 ]; then
  title="${prefix}check-email: ${S} status change(s)"
  priority="default"
  tags="mailbox"
else
  # Daily heartbeat - still ping so the absence-of-signal is positive evidence the routine ran.
  title="${prefix}check-email: nothing new"
  priority="low"
  tags="mailbox"
fi

# Body: trimmed Step 7 report. Cap to ~2000 chars - ntfy accepts more, but a phone
# notification is unreadable beyond that. Drop the "Unmatched" sections; keep
# status changes, offers, interview invitations, and the activity list.
body=$(printf '%s' "$STEP7_REPORT" | head -c 2000)

# Click target: prefer the PR URL (the full report can be reviewed on a bigger
# screen); fall back to the first Gmail thread link on dry-run.
click_url="${PR_URL:-${FIRST_THREAD_URL:-https://github.com}}"

curl -fsS \
  -H "Title: ${title}" \
  -H "Priority: ${priority}" \
  -H "Tags: ${tags}" \
  -H "Click: ${click_url}" \
  -d "${body}" \
  "${NTFY_URL}" \
  || echo "ntfy push failed; PR is still the canonical record." >&2
```

**Skip conditions** (do not push):

- `--no-notify` was passed.
- `NTFY_URL` is not set in the environment (log a warning, continue).
- The Gmail MCP server is not connected (the routine has already exited cleanly at Step 2 in that case).

**Idempotency.** A subsequent run will push a fresh notification. That is intentional - each run is one digest. On the ntfy app, swipe to clear; on iOS the lock-screen banner is replaced by the latest push for the same topic if the previous one is unread.

## Routine configuration

Recommended `/schedule` cron: `0 9 * * *` (09:00 UTC daily, one hour after `/scan-companies` so all three discovery / status routines stagger neatly).

For active job-searching periods, consider `0 9,17 * * *` (twice daily).

## Required connectors

This routine requires the **Gmail MCP** to be authorised on the routine's connector list. Without it the routine exits cleanly with no writes.

## Follow-up drafts and recruiter replies

After the normal classification pass, add two draft-only sections. Never send email from this routine.

### Nudges

A nudge is warranted in exactly two situations, never simply because an application has gone quiet. Both require the entry to be `applied`. At most 1 nudge per application, and never on an entry that already has a pending or completed nudge in `follow_up`. Apply a 7-day timing gate to both cases (do not nudge inside the first week). Draft a three-sentence status enquiry in British English, signed off with the candidate's name from `cv/cv_core_data.yaml -> personal_info.name`, include it in the PR body under `Nudges due`, and call `set_follow_up(data, slug, due_date, "nudge")`. Do not discuss salary in nudges.

**Case A - application not acknowledged.** The entry is `applied` but its `email_activity` contains **no `confirmation` record** (no ATS "we received your application" auto-reply). The candidate submitted but has no proof the application landed, so a nudge to prompt one is worthwhile. Reference date = the most recent `email_activity.date` if any, otherwise `status_changed_at`. If that is 7+ days ago and no confirmation or other reply has since arrived, draft a nudge that politely asks the company to confirm the application was received and enquires about next steps.

**Case B - awaiting a post-interview outcome.** The entry is `applied`, its most recent `email_activity` is an `interview_invitation` or `interview_scheduled` (or `stage` is set to a live interview stage), and no `rejection` / `offer` / later reply has arrived since. Reference date = that interview contact's date, falling back to `stage_changed_at`. If that is 7+ days ago, draft a nudge that asks about the outcome or next steps after the interview.

**Not a nudge.** An `applied` entry that **has** a `confirmation` record and no interview activity is never nudged, however long it stays quiet. Being acknowledged by the ATS but not yet progressed is the normal waiting state, so silence after a confirmation is not a trigger - only Case A or Case B is.

### Recruiter replies

For unmatched recruiter outreach, draft a reply under `Recruiter replies`. Include interest or a polite pass, availability derived from the current date and the notice period / availability in `config/application_answers.yaml -> notice_period`, remote or hybrid constraints from `config/job_seeker.yaml`, permanent compensation floor from the sector-adjusted config, contract terms from `contracting` only when the message is contract-shaped, and a pointer to the current CV. Sign every nudge and reply off with the candidate's name, read from `cv/cv_core_data.yaml -> personal_info.name`. Drafts appear only in the PR description for the user to copy into Gmail.

The status-flip policy remains unchanged: `/check-email` auto-flips only confirmations and rejections as documented above.
