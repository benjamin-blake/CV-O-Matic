# job-seeker - Claude Code conventions

This repo is **agent-first**: discovery, CV generation, and application tracking are driven by Claude routines and slash commands. Python is a thin layer for things Claude shouldn't do at runtime (OAuth, Playwright PDF rendering, Google Drive sync, the index helper).

## First run

The repo ships with a **fictional example profile** (Sherlock Holmes, a public-domain character) so every file has a realistic shape to copy. It is not anyone's real data.

- Run **`/onboard`** first. It replaces the example with the candidate's own CV, job criteria and standard answers, builds a first tailored CV, and then offers the optional automation (scheduled scans, Gmail tracking, ntfy, Drive sync).
- The guard is `models.profile.is_example_profile()`, backed by `config/job_seeker.yaml -> profile.is_example_profile`. Every command that acts on real data runs `python3 -m models.profile --check` first and **stops until onboarding is done** (exit code 3 while the example is active). Scheduled (`--auto` or routine) runs exit quietly. Only `/briefing` (read-only) and `/onboard` are exempt.
- `cv/generate_cv.py --allow-example` renders on the example profile. It exists for smoke tests only; never use it to produce a CV for a real application.
- `python3 -m models.profile` prints the candidate's name, the generated CV file names and the guard state.

## End goal

Scheduled routines find new job postings, score them against `config/job_seeker.yaml`, and append entries to `applications.yaml` at the repo root (status: `open`). They do **not** build CVs - the candidate runs `/build-cv {slug}` manually for postings they want to apply to. The candidate uses Claude Code (web / desktop / cloud) as the interface for everything: status updates, on-demand CV builds, status queries. Google Drive (optional) is pure object storage for the generated PDFs. Nothing in this repo ever submits an application or sends an email.

## Privacy

The template may be public, but a personal copy holding `applications.yaml`, salary expectations and Gmail links **must be private**. Create your own private repo from the template. Never commit `.env`, `token.json` or the ntfy topic URL.

## Layout

```
.claude/
  commands/                      Slash commands (user-invocable + routine entry points)
    onboard.md                   First-run setup: replaces the example profile, builds a first CV, offers the optional automation. Re-runnable.
    scan-indeed.md               Search Indeed, score, append to applications.yaml, open PR (discovery-only)
    scan-companies.md            Scan watchlist via ATS APIs, score, append to applications.yaml (discovery-only)
    check-email.md               Read Gmail, attach email links to applications.yaml, auto-flip applied/rejected status, draft nudges/recruiter replies
    build-cv.md                  Generate bespoke CV for a posting and mark cv_built_at in the index, supports --contract
    application-pack.md          Draft ready-to-paste UK application-form answers (standard + posting-specific) into postings/{slug}/application_pack.md. Also auto-triggered conversationally by the application-pack-refresh skill.
    review-application.md        Write or refresh application_review.json for a posting. Also auto-triggered conversationally by the review-application-refresh skill.
    rescore-application.md       Deterministically re-apply current scoring rules to scored postings (one slug, or a status/family/all scope) via models/rescore.py; skips deal-breakers and prior REJECTs
    prune-watchlist.md           Probe every ATS slug in company_watchlist.yaml and flag stale entries. Interactive by default; --auto (scheduled quarterly) skips confirmation and auto-removes only DEAD entries via PR.
    discover-companies.md        Discovery of new candidates for company_watchlist.yaml. Interactive by default; --auto (scheduled quarterly) runs an unattended broad sweep and opens a PR.
    capture-cv-tweaks.md         Diff a built CV against the hand-finished version, classify recurring edit patterns, promote stable ones into build-cv.md / check_lengths.py
    negotiate.md                 Offer-stage negotiation brief using local salary intelligence from models/comp.py. Also auto-triggered conversationally by the negotiate-on-offer skill.
    log-interview.md             Capture interview notes and set the optional application stage
    prep-interview.md            Generate a role-specific interview prep pack and drill mode
    prune-open.md                Weekly liveness sweep for stale open postings. Scheduled via a Routine.
    briefing.md                  On-demand decision briefing (read-only, chat-only)
  agents/                        Subagents (invoked from slash commands)
    cv-reviewer.md               Quality-review subagent, read-only
    job-matcher.md               Score a single posting vs job_seeker.yaml
  skills/                        Auto-triggered skills (matched by description, no slash needed)
    cv-edit-capture/SKILL.md     Recognise a conversational request to edit a built CV (Path B); apply it, re-render + visual review, then run the cv-tweak-capture loop automatically
    application-pack-refresh/SKILL.md      Conversational front door to /application-pack - fires on "draft/refresh my application answers for X", not on read-only questions
    review-application-refresh/SKILL.md    Conversational front door to /review-application - fires on "redo/refresh the review for X" (posting or CV changed), not on rule-driven bulk rescoring (that's /rescore-application) or read-only questions
    negotiate-on-offer/SKILL.md            Conversational front door to /negotiate - fires when the candidate reports an actual offer, not on speculative offer talk

applications.yaml                **THE SOURCE OF TRUTH FOR STATUS.** One entry per posting. Statuses:
                                 open / applied / declined / closed / rejected. Entries may also carry
                                 engagement (permanent / contract), stage, follow_up, and email_activity.
                                 Edit directly to flip status. Empty in the template.

docs/
  cv-tweak-ledger.yaml           Memory for /capture-cv-tweaks: one entry per captured CV edit (date, slug, pattern, detail, reason, action). Two-strike rule promotes recurring patterns into rules.

interview_prep.md                Interview playbook and feedback log. Keeps the recurring final-round pattern from real
                                 feedback (lead with a concrete example + decision + outcome, not the approach), a
                                 story bank mapped to cv/cv_achievements.yaml, and a pre-interview checklist.

config/
  job_seeker.yaml                The candidate's job requirements - single source of truth (also holds the profile.is_example_profile guard)
  company_watchlist.yaml         Companies to monitor for off-board postings
  application_answers.yaml       Canonical base answers for UK application forms (keyed by question type, sector variants); consumed by /application-pack
  application_review.schema.json JSON Schema for application_review.json (detailed analysis only)

models/
  profile.py                     candidate_name / name_slug / cv_filenames / is_example_profile / require_real_profile; CLI `python3 -m models.profile [--check]`
  applications_index.py          load / save / upsert / set_status / mark_cv_built / set_last_run helpers
  application_review.py          Dataclass + load/dump helpers for application_review.json
  comp.py                        Local salary-market analyser over applications.yaml and application_review.json (`python3 -m models.comp`)
  rescore.py                     Deterministic scoring-rule engine behind /rescore-application
  slug.py                        mint_slug() - canonical slug builder

cv/                              CV generation engine (Python, load-bearing - do not refactor)
  generate_cv.py                 HTML -> PDF via Playwright Chromium (--allow-example for smoke tests only)
  check_lengths.py               Deterministic length-checker (called by /build-cv before cv-reviewer)
  render_preview.py              Render the built CV to per-page PNGs for visual layout review (/build-cv Step 6.5)
  cv_core_data.yaml              Roles (newest first), education, contact details, skills matrix
  cv_achievements.yaml           Achievement library (source of truth for all CV claims)
  cv_config.yaml                 Colour schemes, template settings
  cv_template.html               Jinja2 template
  cv_styles.css                  Base stylesheet
  lib/                           Loader / processor / CSS helpers
  .venv/                         CV-generation venv (created by setup.py)

postings/{slug}/                 slug = YYYY-MM-DD_{company}_{title_kebab} (ASC-sortable by date)
  posting.txt                    Raw job description (input)
  application_review.json        Detailed analytical review (criteria, gaps, recommendations)
  application_pack.md            Ready-to-paste application-form answers (standard + posting-specific); generated by /application-pack or /build-cv Step 7.6
  interview_notes.md             Structured notes appended by /log-interview after each interview round
  interview_prep_pack.md         Role-specific prep pack generated by /prep-interview
  config.yaml                    CV posting-root config (only present once /build-cv has run)
  config/                        CV section configs (summary, experience, skills, projects, criteria_responses)
  personal_statement.txt         Generated by /build-cv
  {name_slug}_cv.html            Generated by /build-cv
  {name_slug}_cv.pdf             Generated by /build-cv
                                 ({name_slug} comes from the candidate's name; `python3 -m models.profile`
                                 prints the exact file names, `models.profile.cv_filenames()` in Python)

integrations/
  google_drive.py                OAuth + sync (optional, working - do not refactor)

scripts/                         setup-web-container.sh (renderer setup on Claude Code web), fetch_ats_cache.py (ATS cache for /scan-companies)

main.py                          CLI: `sync` (Google Drive)
setup.py                         Creates cv/.venv and installs Playwright Chromium

.github/workflows/
  auto-merge-routine.yml         Path-scoped auto-merge for routine PRs (same-repo claude/** branches only)
  sync-drive.yml                 Runs python main.py sync on push to main (paths: postings/**, applications.yaml); skips cleanly when Drive is not configured
  fetch-ats-cache.yml            Refreshes the ATS cache used by /scan-companies
  claude.yml                     @claude PR assistant - fires on @claude mentions from owners, members and collaborators only
```

## Golden rules

- **British English everywhere.** Generated CV text, summaries, application reviews, personal statements. No em-dashes (use commas, colons, parentheses) - they read as LLM-generated to human reviewers.
- **The achievement library is the source of truth.** Highlights in `postings/{slug}/config/experience.yaml` must not exaggerate metrics or upgrade qualifier language beyond what `cv/cv_achievements.yaml` states. The `cv-reviewer` subagent enforces this. Never invent roles, dates, skills or metrics.
- **Reverse chronological order.** Roles in `experience.yaml` follow the order of `roles` in `cv/cv_core_data.yaml`, which is listed newest first; that order IS the reverse-chronological order. No exceptions.
- **CV venv lives at `cv/.venv/`.** Activate with `cv/.venv/Scripts/activate` (Windows) or `cv/.venv/bin/activate` (Unix). Run CV generation from inside `cv/`.
- **`applications.yaml` is the canonical state spine.** All five statuses (`open`, `applied`, `declined`, `closed`, `rejected`) live there, keyed by `slug`. Scan routines append entries via `models.applications_index.upsert`; status transitions happen by editing the YAML directly (manually, or via Claude Code). `/check-email` is the only routine that auto-flips status, and only on high-confidence signals: an ATS confirmation email flips `open` -> `applied` (proof the candidate actually submitted), and a rejection email flips to `rejected`. The per-posting `application_review.json` is the **detailed analysis**, not state.
- **Discovery routines do not build CVs.** `/scan-indeed` and `/scan-companies` write `posting.txt` + `application_review.json` + the index entry and stop. The candidate chooses which to apply to and runs `/build-cv {slug}` on demand.
- **Slug format.** Posting directories are named `YYYY-MM-DD_{company_kebab}_{title_kebab}` where the date is the discovery date in UTC, e.g. `2026-01-15_acme_senior_data_analyst`. The date prefix never changes once set; renaming a posting requires a `git mv` and a matching `slug` field update in `applications.yaml`.
- **Slash commands are the agent surface.** Don't add Python equivalents for `discover` / `notify` / `generate` in `main.py` - these are slash commands now. `main.py` is for `sync` only.
- **Profile guard.** Commands that act on real data start with `python3 -m models.profile --check` and stop if it fails (see "First run").

## Status lifecycle

The five statuses in `applications.yaml` are orthogonal to optional `stage` (`screen`, `tech`, `hiring_manager`, `final`, `offer`). Only `/log-interview` or manual edits set stage. Optional `follow_up` records one pending draft nudge or recruiter reply.

The five statuses in `applications.yaml`:

| Status | Meaning |
| --- | --- |
| `open` | Discovered, not yet acted on. Default for new entries. |
| `applied` | Application submitted. Auto-flipped by `/check-email` when an ATS confirmation email is detected for an `open` entry; can also be set manually after sending the application. |
| `declined` | Consciously passed on. |
| `closed` | Posting closed before applying (deadline missed, role filled, etc.). |
| `rejected` | Application was rejected by the company. Auto-flipped by `/check-email` when a rejection email is detected; can also be set manually. |

Only `/check-email` auto-flips status, on two high-confidence signals: a confirmation email (`open` -> `applied`) and a rejection email (-> `rejected`). Everything else (`declined`, `closed`, or `applied` set some other way) is a manual transition - the candidate edits the YAML directly or asks Claude Code to.

## Common workflows

### First run: onboard

```
/onboard
```

Phased and re-runnable: CV in, job criteria, standard application answers, watchlist, remove the example (flips the guard), first tailored CV, save via PR, then the optional automation (Phase 8). Everything after Phase 7 is optional; skipped parts can be set up later by running `/onboard` again.

### Routine (scheduled): find new jobs

Scheduling is optional and set up in `/onboard` Phase 8, using Claude Code scheduled routines. Two complementary scan routines:

- **`/scan-indeed`** - broad Indeed search. Reads `config/job_seeker.yaml`, searches Indeed via the connector or WebSearch fallback, dedups against `applications.yaml`, scores via the `job-matcher` subagent, writes `posting.txt` + `application_review.json` per match, appends index entries via `models.applications_index.upsert`, commits to a `claude/scan-indeed-*` branch, opens a PR.
- **`/scan-companies`** - whole watchlist via three-tier fetch (ATS cache manifest -> WebSearch -> WebFetch). Same downstream: dedup, score, write artefacts, append to index.

Both produce PRs that the `auto-merge-routine.yml` workflow validates (path-scope only) and squash-merges. If Drive sync is configured, the merge fires `sync-drive.yml`, which pushes the new `applications.yaml` + posting artefacts to Drive.

### On-demand: decision briefing

- **`/briefing`** - run it whenever you want a pipeline snapshot. Produces TOP PICKS, AGING, IN FLIGHT, INTERVIEWS, and FUNNEL sections. Read-only and chat-only: it does not stamp a watermark, commit, or push a notification.

### Routine (scheduled): prune stale open postings

- **`/prune-open`** - weekly liveness sweep over `open` postings at least `--min-age-days` old (default 40). Age only decides what gets checked; it closes only demonstrably dead URLs, stamps `metadata.last_prune_open_run`, and sends a low-priority ntfy summary unless `--no-notify` is passed. Postings confirmed `live` or `unknown` stay open no matter how old - there is no auto-decline on age alone, that stays a human call surfaced via `/briefing`'s AGING section.

### Routine (scheduled): refresh status from Gmail

- **`/check-email`** - reads Gmail since `metadata.last_check_email_run`, classifies each application-related message, matches it to an `applications.yaml` entry by company + title, and appends an `email_activity` record with a direct Gmail thread link. Auto-flips status only on `rejection` (open|applied -> rejected). Interview invitations and offers are surfaced prominently in the PR description; the candidate acts on them manually - mentioning an offer in chat (or pasting one in) fires the `negotiate-on-offer` skill automatically (see below), so there is no need to remember `/negotiate`. It also drafts nudges (max one per application, only when an application has no confirmation email on file, or when an interview outcome is outstanding - never on an application the ATS has already confirmed) and recruiter replies in the PR body, but never sends email.

Requires the Gmail MCP to be authorised on the routine's connector list. Same auto-merge path as the scan routines.

### Routine (scheduled, quarterly): watchlist maintenance

- **`/prune-watchlist --auto`** - probes every ATS slug in `config/company_watchlist.yaml`, auto-removes only unambiguous `DEAD` (404) entries, flags `EMPTY` entries for manual review, and opens a PR. The interactive form (no `--auto`, run on demand) confirms removals via `AskUserQuestion` instead.
- **`/discover-companies --auto`** - runs a broad, unattended sweep for new watchlist candidates (no theme steering, since nobody is there to answer the theme question), UK/EU-primary but including US-HQ companies that clear a UK-eligible-roles check, and opens a PR with every ATS-verified addition for the candidate to prune and merge. The interactive form (no `--auto`, run on demand) is a themed conversation with a final multi-select instead.

Both are optional Claude Code scheduled routines (quarterly cron, one calendar quarter apart from each other); each run spawns a fresh session. Both open a normal review-and-merge PR (not the `auto-merge-routine.yml` fast path), since removing or adding watchlist companies is a judgement call, not routine status data.

### On-demand: build a CV for a posting

```
/build-cv {slug}
```

Runs the full analyse -> select -> write configs -> review -> render -> review pipeline. At the end:
1. `application_review.json` is written with detailed analysis.
2. `cv_built_at` in `applications.yaml` is set to today's date.
3. If Drive sync is configured, `python main.py sync` pushes the new PDF/HTML to Drive.

`status` stays at whatever it was. Flip to `applied` manually once you submit.

After hand-finishing a CV, run `/capture-cv-tweaks {slug}` so the edit never has to be made twice.

`/build-cv` calls `/review-application` internally (Step 7.5) and can call `/application-pack` internally (Step 7.6). Both are also reachable directly, either by typing the slash command or by just asking - see the next two entries.

### On-demand: draft application-form answers

```
/application-pack {slug}
```

Drafts `postings/{slug}/application_pack.md`: ready-to-paste answers to standard UK application-form questions plus posting-specific ones, grounded strictly in `cv/cv_achievements.yaml` / `config/application_answers.yaml`. `/build-cv` already generates this at Step 7.6, so you mostly need this standalone form when a form's questions change or the pack needs a refresh without rebuilding the CV.

You do not have to remember the slash form. The `application-pack-refresh` skill (`.claude/skills/application-pack-refresh/SKILL.md`) auto-triggers on a conversational request ("draft my application answers for Acme", "refresh the Globex pack, the form's different now") and runs this command for you. It does not fire on a plain read-only question about an existing pack.

### On-demand: refresh a posting's analytical review

```
/review-application {slug}
```

Writes or refreshes `postings/{slug}/application_review.json` by re-invoking the `job-matcher` subagent against the current posting text and achievement library. `/build-cv` already calls this internally at Step 7.5, so the standalone form is for when the posting text or the achievement library changed and the sub-scores need re-judging cold.

You do not have to remember the slash form. The `review-application-refresh` skill (`.claude/skills/review-application-refresh/SKILL.md`) auto-triggers on a conversational request ("redo the review for Acme, I updated the posting", "the achievement library changed, refresh Globex's review"). It does not fire for a rule-driven bulk rescore across many postings (that's `/rescore-application`, below) or for a plain read-only question.

### On-demand: capture recurring CV tweaks

```
/capture-cv-tweaks {slug}
```

Every built CV tends to need the same few manual tweaks (adopt different wording, trim a section to fit the page). This command diffs what `/build-cv` generated against the version the candidate actually shipped (or the edits they asked Claude Code to make in-session), classifies each edit into a pattern class, and records it in `docs/cv-tweak-ledger.yaml` with the **reason** behind it. On a pattern's **second** appearance across different postings (the two-strike rule), it proposes a generalised rule - either a `build-cv.md` guidance line or a deterministic `cv/check_lengths.py` check - and, on explicit approval, promotes it so the tweak is made automatically next time. The ledger is the memory: one-off edits stay `observed`; recurring ones become `rule_added`. Nothing is written to `build-cv.md` or `check_lengths.py` without per-proposal approval.

You do not have to remember to run this. The `cv-edit-capture` skill (`.claude/skills/cv-edit-capture/SKILL.md`) auto-triggers whenever you ask Claude Code to change the content of an already-built CV ("shorten the summary on the Acme CV", "reword that highlight"): it applies the edit, re-renders with visual review, and runs this capture loop for you, then opens a PR to merge.

### On-demand: rescore a posting after a scoring change

```
/rescore-application [slug | --status open | --family <family> | --all]
```

When the scoring **rules** change (a weight, a role-family modifier, a sector floor override, the salary-aware seniority logic, the affinity tilt), use this to re-apply them to postings that already have an `application_review.json`. It is not single-slug: pass a slug to rescore one, or a scope (`--status`, `--family`, `--all`; default `--status open`) to rescore many. `--family` takes a family key defined in `config/job_seeker.yaml` (the example profile defines `core`, `stretch` and `leadership`, resolved in `scoring.family_precedence` order). The command delegates to a subagent that runs the deterministic engine `models/rescore.py` and summarises the delta; it recomputes from each review's stored sub-scores rather than re-judging the posting, so it is fast and reproducible. It skips reviews that triggered a deal-breaker or were a prior REJECT (a rejection is not lifted by arithmetic) and leaves untouched any posting where no rule applies. Dry-run first; on confirmation it overwrites the moved review JSONs (adding an audit `rescored` block) and syncs `match_score` + `verdict` into `applications.yaml`. If a posting newly reaches STRONG / MODERATE-STRONG with no CV built, it suggests a follow-up `/build-cv`.

For the complementary case - the posting text or achievement library changed and the sub-scores themselves need re-judging cold - use `/review-application {slug}` instead, which re-invokes the `job-matcher` subagent.

### On-demand: prepare for and log interviews

```
/prep-interview {slug}
/log-interview {slug}
```

`/prep-interview` writes `interview_prep_pack.md` and can drill answers in chat against the concrete example, decision, outcome rubric. `/log-interview` appends `interview_notes.md`, sets the optional stage field, and appends terminal feedback to `interview_prep.md`.

### On-demand: prepare an offer negotiation brief

```
/negotiate {slug}
```

At offer stage, this command combines the candidate's supplied offer details, the posting's `application_review.json`, sector-adjusted floors and targets from `config/job_seeker.yaml`, and the local salary distribution from `python3 -m models.comp`. It returns a chat-only brief covering market position, counter-anchor, non-base levers, walk-away line and a short British-English script. It does not browse the web or commit an artefact unless explicitly asked.

You do not have to remember the slash form at the one moment it matters most. The `negotiate-on-offer` skill (`.claude/skills/negotiate-on-offer/SKILL.md`) auto-triggers the moment the candidate reports an actual offer in chat ("I got an offer from Acme, base of 90k") - including one surfaced by a `/check-email` PR - and runs this command for them. It does not fire on speculative offer talk with no real offer yet.

### On-demand: flip a status

Edit `applications.yaml` directly, or ask Claude Code: "mark {company} as applied" / "set Acme to closed". Claude Code uses `models.applications_index.set_status`:

```python
from models.applications_index import load, set_status, save
data = load()
set_status(data, "2026-01-15_acme_senior_data_analyst", "closed",
           notes="Closed before I got round to applying.")
save(data)
```

### Querying status

"What postings have I not applied to?" - read `applications.yaml`, filter `status == "open"`, sort by `match_score` descending.

"What does my segment pay?" - run `python3 -m models.comp` to summarise stated-pay distributions by role family from the local application dataset.

"What did I apply to this month?" - filter `status == "applied"` and `status_changed_at` in the month.

"What heard back this week?" - scan every entry's `email_activity` for `date` in the last 7 days; group by type.

"How far did I get with each application this quarter?" - filter entries by quarter and group by optional `stage`.

"Where's my application to X?" - find the entry, walk `email_activity` in date order, follow the Gmail links for full context.

"What's the detailed analysis for X?" - read `postings/{slug}/application_review.json`.

### Manual: build a CV from a posting I paste

Create `postings/{YYYY-MM-DD}_{company}_{title_kebab}/posting.txt` with the posting body, then run `/build-cv {slug}`. Use today's date in UTC for the prefix. `/build-cv` calls `/review-application` internally which writes `application_review.json` and then marks `cv_built_at`; if you want the index entry to exist before building, call `models.applications_index.upsert` manually first.

## What NOT to touch

- `cv/generate_cv.py`, `cv/lib/`, `cv/cv_template.html`, `cv/cv_styles.css` - the rendering engine.
- `integrations/google_drive.py` - OAuth flow + sync.
- `cv/cv_core_data.yaml`, `cv/cv_achievements.yaml` - the candidate's source-of-truth data. Edit them via `/onboard` or on the candidate's explicit request, and never invent content in them.
- `.env` (GDrive credentials, ntfy URL) and `token.json` (refresh token). Never commit either.

## End-to-end pipeline

```
[Optional Claude Code scheduled routines: scan-indeed 07:00, scan-companies 08:00, check-email 09:00 UTC]
        |
/scan-indeed                /scan-companies              /check-email
   reads applications.yaml     reads applications.yaml      reads applications.yaml + watermark
   searches Indeed             reads ATS cache + WebSearch  searches Gmail since watermark
   scores via job-matcher      scores via job-matcher       classifies each email
   writes posting.txt + JSON   writes posting.txt + JSON    matches to existing entries
   upserts to index            upserts to index             appends email_activity + Gmail link
   (status: open)              (status: open)               auto-flips applied on confirmation, rejected on rejection
   commits to claude/scan-*    commits to claude/scan-*     commits to claude/check-email-*
   opens PR to main            opens PR to main             opens PR to main
        |
[GitHub] PR opened from a same-repo claude/** branch
        |
auto-merge-routine.yml fires
   asserts diff is constrained to postings/** + applications.yaml + config/company_watchlist.yaml
   if scope-clean: approves + squash-merges + deletes branch
        |
[GitHub] push to main with paths: postings/** or applications.yaml
        |
sync-drive.yml fires (optional; skips cleanly without Drive secrets)
   writes token.json from GDRIVE_TOKEN_JSON secret
   runs python main.py sync
   posting.txt, personal_statement.txt, {name_slug}_cv.html/.pdf -> per-posting Drive folders
   applications.yaml (with email_activity links) -> Drive root
        |
[Claude Code on phone / desktop] reads applications.yaml + per-posting JSON, answers status queries
   Gmail thread links in email_activity tap straight through to the right inbox view

[Manual] /build-cv {slug} when the candidate chooses to apply
   -> writes config/, personal_statement.txt, CV HTML+PDF
   -> sets cv_built_at in applications.yaml
   -> syncs to Drive (if configured)
   -> candidate submits and edits applications.yaml status to "applied"
```

**Quarterly watchlist maintenance** runs on a separate, optional schedule, again as Claude Code scheduled routines (each run spawns a fresh session):

```
[Routine: prune-watchlist --auto, 1st of Jan/Apr/Jul/Oct, 06:30 UTC]
   probes every ATS slug in config/company_watchlist.yaml
   auto-removes only unambiguous DEAD (404) entries; flags EMPTY for manual review
   commits to claude/prune-watchlist-{date} -> opens a review-and-merge PR (not auto-merge scope)

[Routine: discover-companies --auto, 1st of Jan/Apr/Jul/Oct, 07:30 UTC]
   broad unattended sweep for new watchlist candidates (no theme steering)
   UK/EU-primary; US-HQ companies included only if a UK-eligible-roles check passes
   probes ATS slugs, auto-adds every verified deal-breaker-clean candidate
   commits to claude/discover-companies-{date} -> opens a review-and-merge PR
```

The candidate reviews and merges both PRs manually - unlike the daily routines' PRs, these are not squash-merged automatically by `auto-merge-routine.yml`, since adding or removing watchlist companies is a judgement call rather than routine status data.

## GitHub repo configuration

**Repo secrets** (Settings -> Secrets and variables -> Actions). All of the Drive secrets are optional: without `GDRIVE_TOKEN_JSON`, `sync-drive.yml` skips its steps cleanly and succeeds.

- `GDRIVE_TOKEN_JSON` - full contents of your local `token.json`. Used by `sync-drive.yml` to authenticate to Drive.
- `GOOGLE_DRIVE_CLIENT_ID` - same value as in your local `.env`.
- `GOOGLE_DRIVE_CLIENT_SECRET` - same value as in your local `.env`.
- `CLAUDE_CODE_OAUTH_TOKEN` - written automatically by `/install-github-app`. Only needed for `claude.yml`.

**Workflow behaviour:**

- `claude.yml` (the `@claude` PR assistant) only responds to comments and issues from repo owners, members and collaborators, so strangers cannot trigger it on a public repo.
- `auto-merge-routine.yml` only auto-merges PRs from same-repo `claude/**` branches whose diff stays inside the allowed paths.

**Required repo setting for auto-merge:** Settings -> General -> **Allow auto-merge** must be enabled.

## Notifications (ntfy)

The three scheduled routines (`/scan-indeed`, `/scan-companies`, `/check-email`) can push a notification to the candidate's phone at the end of each run via [ntfy.sh](https://ntfy.sh). One HTTP POST, no auth, free, works on iOS and Android. Entirely optional; `/onboard` Phase 8 sets it up.

**Topic URL** is the only auth ntfy uses - anyone who knows it can publish to or subscribe to the topic. **Keep it out of the repo, including a private one.** Treat it like a password.

The URL has the form `https://ntfy.sh/{topic}` where `{topic}` is a long random string. It lives in:

- `.env` as `NTFY_URL` (for local runs). Already `.gitignore`d.
- GitHub Actions secret `NTFY_URL` (for any future workflow that pushes from CI).
- The scheduled routine's environment configuration (for the cron-driven routines themselves).

If you ever need to rotate it: generate a new random identifier (`python3 -c "import secrets; print('job-seeker-' + secrets.token_hex(8))"`), update all three locations above, and re-subscribe on the phone.

If `NTFY_URL` is unset, the push step in each routine logs a warning and exits cleanly. The PR remains the canonical record. Routines never fail because of a notification problem.

**Subscribing on the phone:**

1. Install the ntfy app: [iOS](https://apps.apple.com/us/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy).
2. Add subscription: paste the topic URL from your `.env` (or just the topic name portion - the default server is ntfy.sh).
3. Notifications appear on the lock screen. Tap to open the linked PR or Gmail thread in the browser.

**Push-vs-skip policy:**

| Routine | When does it push? |
| --- | --- |
| `/scan-indeed` | Only when >= 1 STRONG / MODERATE-STRONG match. Otherwise silent. |
| `/scan-companies` | Only when >= 1 STRONG / MODERATE-STRONG match. Otherwise silent. |
| `/check-email` | Every run - daily heartbeat at low priority when there's nothing new, default priority on status changes, high priority on offers / interview invitations. |
| `/prune-open` | Weekly low-priority summary unless `--no-notify` is passed. |

Each routine accepts a `--no-notify` flag to suppress the push (useful during testing / backfill).

**If privacy ever matters more:** self-host ntfy on a VPS (`docker run binwiederhier/ntfy serve`) and swap the URL. The app and the routines are otherwise unchanged.
