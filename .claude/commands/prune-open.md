---
description: Weekly liveness sweep for old open postings. Closes only demonstrably dead postings and leaves unknowns open.
argument-hint: [--no-notify] [--dry-run] [--min-age-days N]
---

# /prune-open

Sweep `status: open` entries older than a minimum age, classify the posting URL as live, dead, or unknown, and close only demonstrably dead postings. Never auto-decline on age alone - age only decides which postings get checked, a `closed` status still requires positive evidence the posting is gone. Err towards keeping opportunities open. British English, no em-dashes.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. Scheduled runs exit quietly without committing, opening a PR, or notifying.

## Steps

1. Load `applications.yaml` and select `status == open` entries with a `posting_url` and `discovered` at least `--min-age-days` old (default **40** - matches the point past which a posting realistically has gone stale or been filled). Sort oldest `discovered` first.
2. Cap at 60 checks per run. If the candidate pool exceeds the cap, state that clearly in the report and name how many were left unchecked this run (they'll be picked up next run since sorting is oldest-first).
3. For each entry, WebFetch the `posting_url` politely.
4. Classify:
   - `dead`: 404, clear role-filled language, no longer accepting applications, redirect to a generic careers index, or explicit closed status.
   - `live`: role page still exists and appears to accept applications.
   - `unknown`: fetch blocked, ambiguous redirect, login wall, or unclear content.
5. For `dead`, call `models.applications_index.set_status(data, slug, "closed", notes="Posting no longer live (liveness check YYYY-MM-DD, N days after discovery)")`.
6. Leave `live` and `unknown` untouched, however old - a stale but confirmed-live posting is still a real opportunity, not a rule-based decline. These surface for a human decision via `/briefing`'s AGING section.
7. Stamp `metadata.last_prune_open_run` via `set_last_run(data, "prune_open")`.
8. Save and commit only `applications.yaml` unless `--dry-run` was passed.

## Report and notification

Open a PR whose body lists closed slugs, live slugs, unknown slugs, and whether the cap was hit (with the unchecked count). Call out any `live` or `unknown` entries that are now well past the age threshold (say, 2x `--min-age-days`) as a nudge to apply, decline, or investigate manually - this command only closes, it never declines. Support `--no-notify`; otherwise send a low-priority ntfy summary. Notification failure must not fail the run.
