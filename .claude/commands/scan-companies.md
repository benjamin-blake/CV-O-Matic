---
description: Scan all companies in config/company_watchlist.yaml (or one with --only) for off-board postings, filter against job_seeker.yaml, score, and append entries to applications.yaml. Discovery-only - CVs are built on request. Pushes a notification to your phone via ntfy when STRONG / MODERATE-STRONG matches are found.
argument-hint: [--only <company_name>] [--no-notify]
---

# /scan-companies

Iterate over every company in `config/company_watchlist.yaml`, fetch their open postings via the three-tier strategy below, filter against the candidate's requirements in `config/job_seeker.yaml`, score with the `job-matcher` subagent, append entries to `applications.yaml`, and open one consolidated PR. **British English** throughout. No em-dashes.

This catches roles that never reach Indeed (employers who only post on their own careers page, niche or smaller companies), which are easy to miss on a broad job-board search.

This routine is **discovery-only**. It does NOT build CVs - you run `/build-cv {slug}` manually for postings you want to apply to.

Supports `--only <name>` to scan a single company (interactive use). Without it, scans the full watchlist.

## Design rationale

This command consolidates what used to be N per-company routines into a single omnibus routine. Reasons:

- **One PR per run** - easier to review one daily PR than N tiny ones.
- **One Drive sync** per run, not N (path-filtered workflow only fires once).
- **Single source of truth for filters** - `job_seeker.yaml :: target_roles` and `location` drive both `/scan-indeed` and `/scan-companies`. No per-company keyword duplication to maintain.
- **Failure isolation is per-company within the run** - a flaky API for one company logs and continues; it doesn't block the others.

Trade-off: no per-company cadence. If you ever need one company monitored 4x daily while the rest are fine daily, schedule a second routine using `--only {company}`.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. Scheduled runs exit quietly without committing, opening a PR, or notifying.

## Step 1: Load requirements and dedup set

Read `config/job_seeker.yaml` in full. The fields that drive filtering:
- `target_roles` and the optional `discovery.title_keywords` - title topic tokens (case-insensitive partial match; see Step 3)
- `location.primary`, `location.acceptable_uk_cities`, `location.remote_ok`, `location.onsite_ok`, `location.international`
- `must_have`, `deal_breakers` - used by `job-matcher`, not directly here

Read `config/company_watchlist.yaml` for the `companies[*]` list. Each entry has:
- `name`, `careers_url` - required
- `ats: {type, slug}` - optional; if present, drives Tier 1 fetch
- `priority` - `high` / `medium` / `low`; scan order, not cadence
- `notes` - free text, may include fallback URLs

**Build the dedup set from `applications.yaml`** - load every entry's `slug`, strip the `YYYY-MM-DD_` prefix, and collect the `{company}_{title}` keys into a set.

If `--only <name>` was passed: filter to just the matching entry (case-insensitive). Error out with the list of available names if no match.

## Step 2: Scan each company in priority order

Iterate companies sorted by `priority` (high -> medium -> low). For each, apply the three-tier fetch:

### Tier 1 - Read `data/ats-cache/manifest.json` (default)

Scheduled-agent containers often cannot reach ATS hosts (egress allowlists block the ATS providers). The `fetch-ats-cache.yml` GitHub Actions workflow runs daily at 05:00 UTC on a GitHub runner (open egress), fetches the ATS list endpoints + filtered bodies, and commits them to the default branch. It only runs once Actions is enabled on your fork; until then (and on a fresh template) `data/ats-cache/` is empty. `manifest.json` is the **index**; the bodies it points at live under `data/ats-cache/bodies/{YYYY-MM-DD}/` as individual markdown files. This step reads both from disk - no network needed.

**Procedure:**

1. Read `data/ats-cache/manifest.json`. **If the file does not exist** (fresh template, Actions not yet enabled, or the first workflow run has not happened), do not error: log "no ATS cache manifest, falling through to Tier 2 for every company" and go straight to Tier 2. Otherwise verify:
   - `fetched_at_utc` is within the last 36 hours. If older, treat the whole manifest as missing and fall through to Tier 2 for every watchlist company.
   - The JSON parses. If it doesn't, treat as missing and fall through.
   - Log `watchlist_diff_since_last.added` and `removed` if non-empty so newly-added companies are surfaced (they will fall to Tier 2 for one cycle until the next manifest refresh).
2. For each company in the watchlist, find the matching entry in `manifest.companies[]` by `name`.
3. For each entry where `status == "ok"` or `status == "ok_partial"`:
   - Iterate `filtered_jobs[]`. Each entry has `title`, `location`, `url`, `candidate_slug`, `body_path`, `body_source` (always `"bundle"` in the current implementation).
   - Read the body from disk: `Read(body_path)`. The file starts with a small header (title, location, URL) followed by the raw ATS body.
   - `status == "ok_partial"` means the GHA fetcher exceeded its 50-bodies-per-company cap (SmartRecruiters / Workable). The candidates that did make it are still valid.
4. For each company with `status == "error"` or absent from the manifest, fall through to Tier 2 (WebSearch) for that company specifically.

**Slug from manifest:** the manifest's `candidate_slug` is minted by the GHA fetcher using the same `models/slug.py :: mint_slug` contract as Step 5. **Tier 1 candidates: reuse `candidate_slug` directly - do not re-mint.** Tier 2 / Tier 3 candidates do not appear in the manifest; for those, mint a slug via the helper at Step 5.

### Tier 2 - WebSearch with `site:` qualifier

If no `ats` field, or Tier 1 failed, use WebSearch:

```
site:{careers_domain} ({target_role_1} OR {target_role_2} OR ...) {location_hint}
```

Build the query from `job_seeker.yaml :: target_roles` and `location.primary`. WebSearch returns SERP titles + URLs. For each result, `WebFetch(url, prompt="Return the full job description ...")`.

### Tier 3 - Direct WebFetch on `careers_url`

Last resort. `WebFetch(url=careers_url, prompt="Extract all job posting URLs visible on this page along with their titles and locations.")`. If empty or blocked, log and move on - that company is "unreachable this run".

### Track tier per company

Record which tier succeeded for each company. Surface in the Step 7 report.

## Step 3: Filter to relevant postings

Tier 1 candidates have already been filtered by `scripts/fetch_ats_cache.py :: passes_filters` (broad topic-token title check + junior-hint blocker + location check) before they reach the manifest. Do not re-apply the title filter to them - accept anything the manifest returns and proceed to dedup + scoring.

For Tier 2 / Tier 3 candidates (no manifest), apply the same semantics here:

**Title filter - broad topic match, seniority NOT checked at this stage:**
- Pass if the (lowercased) title contains any topic token. Tokens are derived exactly as `scripts/fetch_ats_cache.py :: derive_title_tokens` does: every `target_roles` entry lowercased, the same entry with leading seniority words (senior, lead, principal, staff, ...) stripped, and every `discovery.title_keywords` entry. Print them with `python3 -c "import sys,yaml; sys.path.insert(0,'scripts'); import fetch_ats_cache as f; print(f.derive_title_tokens(yaml.safe_load(open('config/job_seeker.yaml'))))"`.
- Reject if the title contains a junior hint (junior, graduate, intern, apprentice, trainee).

**Location filter:**
- Match if the job's location contains `location.primary`, any entry from `location.acceptable_uk_cities`, or remote/hybrid when `location.remote_ok` is `true`.
- Drop if explicitly international + `location.international: false`, or onsite-only outside the primary location (`location.primary`) + `location.onsite_ok: false`.

**Dedup:** derive `{company_snake}_{title_snake}` key. Drop if in the dedup set.

## Step 4: Score each candidate in parallel

Spawn `job-matcher` subagents in parallel (single message, multiple Agent tool calls). For each:
- `subagent_type: job-matcher`
- prompt: include the posting URL, raw text, and `discovered_via: "company_watchlist"`

Cap at 20 total candidates across all companies per run to bound cost.

## Step 5: Persist artefacts and update the index

For each candidate:

1. **Slug source depends on tier.** For Tier 1 candidates: reuse `candidate_slug` from the manifest verbatim. For Tier 2 / Tier 3 candidates: mint via `mint_slug` from `models/slug.py`:
   ```bash
   python -c "from models.slug import mint_slug; print(mint_slug('<company>', '<title>'))"
   ```
   Pass the watchlist entry's `name` field verbatim as `company` (not the company name as it might appear in the posting body).
2. Create `postings/{slug}/`.
3. Write `posting.txt` (raw body, HTML-stripped if necessary).
4. Write `application_review.json` conforming to `config/application_review.schema.json`. Set:
   - `discovered_via: "company_watchlist"`, `generated_at: now`
   - `summary: {office_and_location, compensation, mission_and_culture, technical_fit, overall}` - carry through the structured summary from the job-matcher output verbatim. This is the human-readable "is this for me?" brief; do not abbreviate.
   - `artefacts.posting`, with `cv_pdf`/`cv_html`/`personal_statement` as `null`
5. **Append to `applications.yaml`** via the index helper:
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
       discovered_via="company_watchlist",
       match_score=match_score,
       verdict=verdict,
   )
   set_last_run(data, "scan_companies")
   save(data)
   ```

Always call `set_last_run` + `save` even on a zero-posting run so the metadata timestamp updates.

## Step 6: Commit, push, open one consolidated PR

```bash
# Create routine branch if on main
if git rev-parse --abbrev-ref HEAD | grep -qE '^(main|master)$'; then
  git checkout -b "claude/scan-companies-$(date -u +%Y%m%d-%H%M%S)"
fi

git add postings/ applications.yaml
git commit -m "scan-companies: {N} new postings across {C} companies ({YYYY-MM-DD})"
git push -u origin HEAD

branch=$(git rev-parse --abbrev-ref HEAD)
if [ -z "$(gh pr list --head "$branch" --json number --jq '.[0].number')" ]; then
  gh pr create \
    --base main \
    --title "scan-companies: {N} new postings across {C} companies ({YYYY-MM-DD})" \
    --body "Automated \`/scan-companies\` routine output. Scanned {C} companies via {N1} Tier 1 / {N2} Tier 2 / {N3} Tier 3 fetches. Found {N} new postings; entries appended to \`applications.yaml\` with \`status: open\`. Run \`/build-cv {slug}\` manually for any you want to apply to. The \`auto-merge-routine.yml\` workflow will validate scope and merge."
fi
```

Always commit and open a PR, even on a zero-posting run - the metadata timestamp in `applications.yaml` should reach Drive so the last-run date stays current.

## Step 7: Report

```
## /scan-companies - {DD Month YYYY}

Scanned {C} companies. {N} new postings.

### Fetch tiers
- Tier 1 (ATS API): {N1} companies, {jobs_total} total jobs visible
- Tier 2 (WebSearch): {N2} companies
- Tier 3 (WebFetch fallback): {N3} companies
- Unreachable: {N4} companies - {list}

### Per-company breakdown
- **{Company A}**: Tier 1 (413 jobs), 3 matched filters
- **{Company B}**: Tier 1 (62 jobs), 0 matched filters
- ...

### Top matches (review and decide whether to apply)
For each top match, surface a richer brief lifted from the `summary` block of the posting's `application_review.json` (office_and_location / compensation / mission_and_culture / technical_fit / overall). The user reads this to decide whether to ask for a CV.

1. **{Company} - {Title}** ({location}) . score 0.91 . STRONG
   - **Office and location:** {summary.office_and_location}
   - **Compensation:** {summary.compensation}
   - **Mission and culture:** {summary.mission_and_culture}
   - **Technical fit:** {summary.technical_fit}
   - **Overall:** {summary.overall}
   - Run `/build-cv {slug}` to build a bespoke CV.
2. ...

### Weaker matches (logged for completeness)
- ...

### Rejects
- {N} postings filtered by deal-breakers or low score.
```

## Step 8: ntfy push notification

Unless `--no-notify` was passed or `NTFY_URL` is unset, push a notification to your phone via ntfy. See `## Notifications (ntfy)` in `CLAUDE.md` for the URL secret.

**Skip-on-no-news policy:** push only when there is at least one STRONG or MODERATE-STRONG match. A routine that found zero matches, or only weak ones, stays silent. This avoids notification fatigue from a daily cron.

```bash
if [ "${NO_NOTIFY:-0}" = "1" ] || [ -z "${NTFY_URL:-}" ]; then
  exit 0
fi

strong_count="${STRONG_COUNT:-0}"
[ "$strong_count" -eq 0 ] && exit 0

# Identify the dominant company so the title is informative when --only was used
# or when one company dominates a multi-company run.
if [ -n "${ONLY_COMPANY:-}" ]; then
  title="scan-companies (${ONLY_COMPANY}): ${strong_count} strong match(es)"
else
  title="scan-companies: ${strong_count} strong match(es) across ${COMPANIES_WITH_MATCHES:-?} company/companies"
fi

# Body: top 3-5 matches as title + company + score, one per line. Cap to ~1500 chars.
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

Recommended `/schedule` cron: `0 8 * * *` (08:00 UTC daily, one hour after `/scan-indeed` to avoid concurrent runs).
