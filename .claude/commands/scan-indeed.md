---
description: Search Indeed for new postings matching config/job_seeker.yaml, score them, and append entries to applications.yaml. Discovery-only - CVs are built on request via /build-cv. Pushes a notification to your phone via ntfy when STRONG / MODERATE-STRONG matches are found.
argument-hint: [--dry-run] [--no-notify]
---

# /scan-indeed

Discover new job postings on Indeed, score them against `config/job_seeker.yaml`, write `posting.txt` + `application_review.json` per match, append entries to `applications.yaml`, commit and open a PR. **British English** throughout. No em-dashes.

This routine is **discovery-only**. It does NOT build CVs - you run `/build-cv {slug}` manually for postings you want to apply to. Email triage is handled by `/check-email`, not here.

Supports `--dry-run` (score only, no writes, no commit).

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. Scheduled runs exit quietly without committing, opening a PR, or notifying.

## Step 1: Load requirements and dedup set

Read `config/job_seeker.yaml` in full. Note `target_roles`, `location`, `must_have`, `deal_breakers`, `discovery.*`.

**Build the dedup set from `applications.yaml`** - load every entry's `slug`, strip the `YYYY-MM-DD_` prefix, and collect the `{company}_{title}` keys into a set. `applications.yaml` is the source of truth for "already seen". Do not maintain a separate URL list - Indeed redirector URLs are per-click and never repeat.

## Step 2: Search Indeed

**Preferred:** use the Indeed connector available in the routine environment. Issue searches across the `target_roles` x `location` matrix.

**Fallback:** WebSearch with `site:uk.indeed.com "{role}" "{location}" posted:7d`, then WebFetch each result. Indeed serves captchas to non-browser clients - if WebFetch returns a blocked page, log the URL and continue, don't retry.

Filter the result set:
- For each candidate, derive its dedup key: `{company_snake}_{title_snake}` (lowercase, ASCII, punctuation stripped, spaces -> `_`). Drop if already in the dedup set.
- Drop postings older than `discovery.freshness_days` (default 14) from `config/job_seeker.yaml`.
- Cap to `discovery.max_candidates_per_run` (default 20) to keep cost bounded.

## Step 3: Score each candidate in parallel

For each candidate from Step 2, spawn the `job-matcher` subagent in parallel (single message, multiple Agent tool calls):

- `subagent_type: job-matcher`
- prompt: include the posting URL, raw text, and `discovered_via: "indeed"`

Each subagent returns the structured JSON assessment.

## Step 4: Persist artefacts and update the index

If `--dry-run`: print a sorted summary table only. Skip writing files.

**For each NEW candidate:**

1. **Mint the slug from this routine, not from the job-matcher subagent.** Call `mint_slug` from `models/slug.py` (run from repo root):
   ```bash
   python -c "from models.slug import mint_slug; print(mint_slug('<company>', '<title>'))"
   ```
   The helper handles snake-casing and the UTC date prefix.
2. Create `postings/{slug}/`.
3. Write `postings/{slug}/posting.txt` (raw posting body).
4. Write `postings/{slug}/application_review.json` conforming to `config/application_review.schema.json`. Set:
   - `discovered_via: "indeed"`
   - `generated_at: {ISO 8601 UTC}`
   - `summary: {office_and_location, compensation, mission_and_culture, technical_fit, overall}` - carry through the structured summary from the job-matcher output verbatim. This is the human-readable "is this for me?" brief; do not abbreviate.
   - `artefacts.posting: "postings/{slug}/posting.txt"`
   - `artefacts.cv_pdf` / `cv_html` / `personal_statement`: `null` (populated by `/build-cv` later if you choose to apply)
5. **Append to `applications.yaml`** via the index helper. Load, upsert, save:
   ```python
   from models.applications_index import load, upsert, set_last_run, save
   data = load()
   upsert(
       data,
       slug=slug,
       company=company,
       title=title,
       location=location,
       posting_url=posting_url,
       discovered_via="indeed",
       match_score=match_score,
       verdict=verdict,
   )
   set_last_run(data, "scan_indeed")
   save(data)
   ```
   New entries start at `status: open`, `cv_built_at: null`.

Even on a zero-posting run, `set_last_run(data, "scan_indeed")` + `save(data)` so the metadata timestamp updates.

## Step 5: Commit, push, open PR

```bash
# Create routine branch if currently on main
if git rev-parse --abbrev-ref HEAD | grep -qE '^(main|master)$'; then
  git checkout -b "claude/scan-indeed-$(date -u +%Y%m%d-%H%M%S)"
fi

git add postings/ applications.yaml
git commit -m "scan-indeed: {N} new postings ({YYYY-MM-DD})"
git push -u origin HEAD

branch=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$(gh pr list --head "$branch" --json number --jq '.[0].number')" ]; then
  gh pr create \
    --base main \
    --title "scan-indeed: {N} new postings ({YYYY-MM-DD})" \
    --body "Automated \`/scan-indeed\` routine output. Discovered {N} postings on Indeed; entries appended to \`applications.yaml\` with \`status: open\`. Run \`/build-cv {slug}\` manually for any you want to apply to. The \`auto-merge-routine.yml\` workflow will validate scope and merge."
fi
```

When running via `/schedule`, the Claude Code routine system may wrap your work in branch/push/PR machinery automatically - the conditionals above make these commands safe to run regardless.

## Step 6: Report

Return to the caller:

```
## /scan-indeed - {DD Month YYYY}

**{N} new postings** found.

### Top matches (review and decide whether to apply)
For each top match, surface a richer brief lifted from the `summary` block of the posting's `application_review.json` (which contains office_and_location / compensation / mission_and_culture / technical_fit / overall). Do not just print scores - the user reads this on their phone and wants enough to decide:

1. **{Company} - {Title}** ({location} . {remote_policy}) . score {0.81} . STRONG
   - **Office and location:** {summary.office_and_location}
   - **Compensation:** {summary.compensation}
   - **Mission and culture:** {summary.mission_and_culture}
   - **Technical fit:** {summary.technical_fit}
   - **Overall:** {summary.overall}
   - Run `/build-cv {slug}` to build a bespoke CV.

### Weaker matches (logged for completeness)
- {Company} - {Title} (score {X.XX}). Reason: {one-line}.

### Rejects
- {N} postings filtered by deal-breakers or low score.
```

## Step 7: ntfy push notification

Unless `--no-notify` was passed or `NTFY_URL` is unset, push a notification to your phone via ntfy. See `## Notifications (ntfy)` in `CLAUDE.md` for the URL secret.

**Skip-on-no-news policy:** push only when there is at least one STRONG or MODERATE-STRONG match. A routine that found zero matches, or only weak ones, stays silent - the PR is still the canonical record and you can read it when you want to. This avoids notification fatigue from a daily cron.

```bash
if [ "${NO_NOTIFY:-0}" = "1" ] || [ -z "${NTFY_URL:-}" ]; then
  exit 0
fi

# Count STRONG + MODERATE-STRONG matches; skip if none.
strong_count="${STRONG_COUNT:-0}"
[ "$strong_count" -eq 0 ] && exit 0

prefix=""
[ "${DRY_RUN:-0}" = "1" ] && prefix="[DRY RUN] "

title="${prefix}scan-indeed: ${strong_count} strong match(es)"

# Body: top 3-5 matches as title + score, one per line. Cap to ~1500 chars.
# The full briefs (office_and_location / compensation / etc.) stay in the PR.
body=$(printf '%s' "$TOP_MATCHES_SUMMARY" | head -c 1500)

curl -fsS \
  -H "Title: ${title}" \
  -H "Priority: default" \
  -H "Tags: briefcase,sparkles" \
  -H "Click: ${PR_URL:-https://github.com}" \
  -d "${body}" \
  "${NTFY_URL}" \
  || echo "ntfy push failed; PR is still the canonical record." >&2
```

## Routine configuration

Recommended `/schedule` cron: `0 7 * * *` (07:00 UTC daily).
