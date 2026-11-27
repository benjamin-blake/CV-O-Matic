---
description: Probe every ATS slug in config/company_watchlist.yaml and flag stale entries (404 or 0 jobs). Interactively confirms removals; --auto runs unattended for scheduled triggers. Quarterly cadence.
argument-hint: [--auto]
---

# /prune-watchlist

Run a health check on every company in `config/company_watchlist.yaml`. For each entry, hit the configured ATS endpoint and report which slugs have gone stale.

This is a maintenance command - slugs rot when companies change ATS providers, get acquired, or shut down. Smaller and start-up employers are especially prone to churn.

**Two modes:**
- **Interactive (default)** - run on demand. Confirms removals with the user via `AskUserQuestion` before editing the file, and leaves the diff uncommitted for review.
- **`--auto`** - for the scheduled quarterly trigger. No `AskUserQuestion` (nobody is there to answer it on an unattended cron firing): auto-removes only unambiguous `DEAD` entries, commits, and opens a PR for the user to review and merge. `EMPTY` entries are never auto-removed - they're only ever flagged, in both modes, since a temporarily-empty board isn't evidence the company stopped hiring.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. `--auto` (scheduled) runs exit quietly without committing, opening a PR, or notifying.

## Step 1: Load the watchlist

Read `config/company_watchlist.yaml`. For each entry under `companies[*]`, extract `name`, `ats.type`, `ats.slug`. Ignore entries without `ats` (none should exist, since the watchlist is ATS-only, but be defensive). Also ignore the fictional placeholder entries (`notes` starting "FICTIONAL"): report them as "example placeholder, replace via /onboard Phase 4" rather than DEAD.

## Step 2: Probe each in parallel

For each company, hit the matching endpoint with a 12-second timeout. Run probes in parallel via Bash (curl `&` with `wait`, limit to ~8 concurrent).

| `ats.type` | Probe request |
|---|---|
| `greenhouse` | GET `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` |
| `lever` | GET `https://api.lever.co/v0/postings/{slug}?mode=json&limit=1` |
| `ashby` | GET `https://api.ashbyhq.com/posting-api/job-board/{slug}` |
| `smartrecruiters` | GET `https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1` |
| `workable` | POST `https://apply.workable.com/api/v3/accounts/{slug}/jobs` with body `{"query":"","department":[],"location":[]}` |

Classify each response:

- **OK** - 200 with ≥1 job returned
- **EMPTY** - 200 with 0 jobs (slug is valid but no current openings; may be temporary)
- **DEAD** - 404 (slug is gone; company likely switched ATS or shut down)
- **FLAKY** - timeout, 5xx, or unparseable response (transient; do not act this run)

## Step 3: Report

Print a clean grouped summary:

```
## /prune-watchlist - {DD Month YYYY}

DEAD ({count} - recommend removal):
- {name} | {ats.type}/{ats.slug} | HTTP 404

EMPTY ({count} - review, may be temporary):
- {name} | {ats.type}/{ats.slug} | 0 jobs

FLAKY ({count} - re-probe next run):
- {name} | {ats.type}/{ats.slug} | {error}

OK ({count}):
- Summary only - no per-company list.
```

## Step 4: Apply removals

**Interactive mode (no `--auto`):** use `AskUserQuestion` to confirm:
- "Remove the {N} DEAD entries from `config/company_watchlist.yaml`?" (yes / no)
- If `EMPTY` count > 0: "Also remove the {M} EMPTY entries? (Recommended only if you've seen them empty for ≥2 consecutive runs.)" (yes / no / skip)

On confirmation, edit `config/company_watchlist.yaml` to delete the relevant entries. Preserve the group section headers and surrounding comments.

**`--auto` mode:** skip `AskUserQuestion` entirely - there is nobody to answer it. Remove only the `DEAD` entries automatically (a 404 is unambiguous evidence the slug is gone). Never auto-remove `EMPTY` entries in this mode; list them in the PR body under "Review manually" instead, since a live-but-currently-empty board might fill up again and removing it needs a human call.

## Step 5: Commit and report

**Interactive mode:** do not commit automatically. Leave the diff for the user to review and commit normally - the change is small enough to commit directly to `main`, but they may want a PR for traceability.

**`--auto` mode:** commit the `DEAD`-entry removals to a `claude/prune-watchlist-{YYYYMMDD}` branch and open a PR to `main` whose body is the Step 3 report (DEAD entries removed, EMPTY entries flagged for manual review, FLAKY entries noted for re-probing next run). If zero `DEAD` entries were found, still open the PR only if there is something to report (EMPTY entries worth flagging); otherwise skip the PR and just log a one-line "nothing stale this run" summary - do not open an empty no-op PR.

## Cadence

Quarterly. Scheduled via a Routine calling `/prune-watchlist --auto` - see `CLAUDE.md` for the trigger. Also run manually (interactive mode) whenever `/scan-companies` reports an unusual number of Tier 1 failures.
