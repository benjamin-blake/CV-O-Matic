---
description: Explore additions to config/company_watchlist.yaml. Interactively asks about sectors/themes and lets you pick which to add; --auto runs an unattended broad sweep for scheduled triggers and opens a PR instead.
argument-hint: [optional theme or sector hint] [--auto]
---

# /discover-companies

Surface companies that meet the candidate's preferences (per `config/job_seeker.yaml`) but aren't yet being monitored in `config/company_watchlist.yaml`.

Pair this with `/prune-watchlist` for the quarterly maintenance ritual: prune dead, discover new.

**Two modes:**
- **Interactive (default)** - a conversation: ask the user where to look (Step 2), then let them pick which verified candidates to add (Step 5).
- **`--auto`** - for the scheduled quarterly trigger. No `AskUserQuestion` (nobody is there to answer it on an unattended cron firing): skip Step 2 and run a broad general sweep by default (see Step 2a), and skip the Step 5 multi-select - instead auto-add every ATS-verified, deal-breaker-clean candidate directly to the watchlist and open a PR for the user to prune down and merge. The user loses the "tell me what to look for" steering on this run in exchange for not having to remember to run it at all; they can still run the interactive version any time for a targeted sweep.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. `--auto` (scheduled) runs exit quietly without committing, opening a PR, or notifying.

## Step 1: Ground in current preferences and coverage

Read `config/job_seeker.yaml` (target roles, location, must-haves, deal-breakers, mission preference) and `config/company_watchlist.yaml` (current companies, grouped). Internalise:

- **Target roles** - the `target_roles` and role families in `config/job_seeker.yaml`.
- **Location** - `location.primary`, `location.remote_ok`, `location.onsite_ok` and `location.international` (avoid companies that only hire in regions the candidate cannot work from, unless they hire UK/EU remote).
- **Deal-breakers** - the `deal_breakers` list and salary floor in `config/job_seeker.yaml`.
- **Sectors and preferences** - the sectors, mission and culture preferences stated in `config/job_seeker.yaml`.
- **Current groupings** - the group headings in `config/company_watchlist.yaml`.

Note which sectors are densely covered and which feel thin. Surface that to the user in Step 2 as a prompt.

## Step 2: Ask the user where to look

**Interactive mode only** (skip entirely in `--auto` mode - go straight to Step 2a). Use `AskUserQuestion` with 1-2 questions tailored to the gap analysis. Examples (adapt to context):

- "Where do you want to dig today? Specific sector (e.g. AI safety research orgs, climate / energy data, healthtech, B2B fintech infra), specific stage (true seed / series A vs C+ scale-up), or specific companies you've heard about?"
- "Open to remote-EMEA US companies, or strict UK/EU only this run?"

If the user passed a hint as `$ARGUMENTS`, treat it as the starting theme and only ask follow-up questions if needed.

## Step 2a: Default theme for `--auto` mode

No conversation to draw a theme from, so use a fixed default: a **broad general sweep** - 10-15 candidates across sectors not yet covered on the watchlist (not narrowed to one sector), same approach as an ad-hoc "no specific theme" interactive run. Geo scope: **UK/EU primary, but include US-HQ companies that explicitly hire UK/EU-remote** - a sensible default for UK-based candidates (adjust to `location` in `config/job_seeker.yaml`). For each US-HQ candidate that clears the ATS probe (Step 4), do the extra check from that session: pull the full job list and count how many roles actually match `target_roles` AND carry a UK/EU/remote location label. If that count is zero or the company's board is overwhelmingly US-onsite (e.g. hundreds of roles, single-digit or zero UK-eligible matches), drop the candidate from this auto-run entirely rather than adding a watchlist entry that will churn empty every quarter. Note dropped US megacorp candidates in the PR body as "checked, not enough UK-eligible roles to justify watchlisting" so the reviewer can see the check happened.

## Step 3: Generate candidates

Based on the user's direction, list 10-15 candidate companies that:

- Plausibly fit `target_roles` (data / AI / platform engineering at senior level - not pure ML research scientist roles unless that's what the user wants)
- Are based in (or hire from) UK / EU, unless the user explicitly opened up to US-remote
- Aren't already in `company_watchlist.yaml` (check by name, case-insensitive)
- Aren't disqualified by `deal_breakers`

For each, give a one-line rationale: `{Company} - {sector}, {stage / size}, {why it fits}`.

If you're not sure whether a company is still operating, flag it: many AI startups churn fast. Recent acquisitions, pivots, and shutdowns are common.

## Step 4: Probe ATS slugs in parallel

For each candidate, probe all five supported ATSes via Bash curl in parallel (limit ~8 concurrent). Use the company name lowercased and de-spaced as the primary slug guess. For misses, try 2-3 likely variants:
- Company name with no spaces (e.g. "Hugging Face" → `huggingface`)
- Company name as kebab-case (e.g. "Robin AI" → `robin-ai`)
- Common suffix variants (`{name}app`, `{name}ai`, `{name}hq`, `with{name}`)

Endpoints:
- `greenhouse`: GET `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- `lever`: GET `https://api.lever.co/v0/postings/{slug}?mode=json&limit=1`
- `ashby`: GET `https://api.ashbyhq.com/posting-api/job-board/{slug}`
- `smartrecruiters`: GET `https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1`
- `workable`: POST `https://apply.workable.com/api/v3/accounts/{slug}/jobs` with body `{"query":"","department":[],"location":[]}`

Report which slugs returned 200 with ≥1 job. For generic-sounding slugs (`peak`, `modal`, `notion`, `aligned`, `linear`, `magic`), fetch one job's title or description to verify it's the right company - slug collisions across companies are real (we hit this with "aligned" pointing to alignedup.com in Israel rather than Aligned AI).

## Step 5: Confirm and update the file

**Interactive mode:** present verified candidates to the user. Use `AskUserQuestion` (multiSelect, max 4 options per question - split into batches for longer lists) so they can pick which to add.

**`--auto` mode:** skip the question. Add every candidate that both (a) returned a verified ATS hit in Step 4 (content-checked for generic slugs) and (b) passed the Step 2a UK-eligibility check for US-HQ candidates. Do not apply further judgement calls the user would normally make in conversation (stage preference, "I've heard of this one" steers) - those are exactly what interactive mode is for; `--auto` errs towards including and lets the user prune in PR review instead.

For each addition (both modes):

- Insert into the appropriate group (Group 1 / 2 / 3) in `config/company_watchlist.yaml`. Preserve alphabetical ordering within groups where it exists, otherwise append to the end of the group.
- Default `priority: medium`. Bump to `high` only if the user explicitly says so in interactive mode (e.g. "top-tier mission match"); never bump priority automatically in `--auto` mode.
- Skip `notes` unless there's something specific to flag (slug deviates from name, large board, niche caveat, or - in `--auto` mode - the auto-added date and a one-line rationale so the reviewer can judge it in PR review without the conversation that would normally justify it).

Drop candidates without an ATS hit - same rule as the rest of the file. Note them in the report as "no ATS hit - will rely on `/scan-indeed` if they post to Indeed".

## Step 6: Commit and report

**Interactive mode:** don't commit. Leave the diff for the user to review and decide whether to commit directly to `main` or via a PR.

**`--auto` mode:** commit the additions to a `claude/discover-companies-{YYYYMMDD}` branch and open a PR to `main`. The PR body lists every company added (with its one-line rationale), every US-HQ candidate checked-and-dropped for insufficient UK-eligible roles, and every candidate with no ATS hit. This is a normal review-and-merge PR (not auto-merge scope, since it's a judgement call on new watchlist entries, not routine data) - the user prunes and merges it themselves, same spirit as the interactive mode's manual review, just after the fact instead of before.

## Cadence

Interactive mode: ad-hoc whenever the user wants to expand coverage or target a specific sector. `--auto` mode: quarterly, scheduled via a Routine calling `/discover-companies --auto` - see `CLAUDE.md` for the trigger, paired with the `/prune-watchlist --auto` cadence.
