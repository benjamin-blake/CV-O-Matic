---
description: Re-apply the current scoring RULES in config/job_seeker.yaml to already-scored postings, deterministically, via models/rescore.py. Works for a single slug or a whole scope (status / family / all). Delegates the run + summary to a subagent. Dry-run first; only writes on confirmation.
argument-hint: "[slug | --status open | --family <family key> | --all]"
---

# /rescore-application

Re-apply the **current** `config/job_seeker.yaml` scoring rules (weights,
role-family modifiers, salary-aware seniority, affinity tilt, verdict caps) to
postings that already have an `application_review.json`, and sync the refreshed
`match_score` + `verdict` back into `applications.yaml`.

This is a **rules/weights** operation. It recomputes from the sub-scores already
stored in each review, deterministically, without re-judging the posting text.
It is not single-slug: pass a slug to rescore one, or a scope to rescore many.

> **When to use which command**
> - **`/rescore-application`** - you changed the scoring *rules* (a weight, a
>   role-family modifier, a sector floor, the seniority/salary logic). Fast,
>   reproducible, no LLM re-judge. Bulk-capable.
> - **`/review-application {slug}`** - the *posting text* or the *achievement
>   library* changed and the sub-scores themselves need re-judging cold. That
>   path re-invokes the `job-matcher` subagent for a single posting.

The engine is `models/rescore.py`. It skips any review that triggered a
deal-breaker or was a prior REJECT (a rejection is not lifted by arithmetic),
and leaves untouched any posting where no rule actually applies.

**Scope argument:** `$1` (may be empty)

- empty → default scope is `--status open` (the postings you might still act on)
- a slug (e.g. `2026-01-15_acme_senior_data_analyst`) → just that posting
- `--all` → every posting with a review
- `--status <status>` → restrict by `applications.yaml` status
- `--family <key>` → restrict by role family, where `<key>` is a family defined in `scoring.role_family_modifiers` in `config/job_seeker.yaml` (the example config defines `core`, `stretch`, `leadership`)

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

## Step 1: Delegate the run to a subagent

Spawn a subagent with the **Agent** tool (`subagent_type: "general-purpose"`).
The subagent's job is to run the engine in **dry-run** mode and summarise, not
to reason about individual postings. Give it this brief (substitute the scope
resolved from `$1`):

> Run the deterministic rescore engine from the repo root and summarise the
> result. Do not pass `--write` on this run.
>
> 1. Execute: `python -m models.rescore <SCOPE_FLAGS> --format md`
>    (for a bare slug, use `--slug <slug>`; for empty input, use `--status open`).
> 2. If it errors, return the stderr verbatim and stop.
> 3. Summarise the delta table for the user: how many reviewed / moved / skipped
>    (and the skip reasons); the net direction per role family; every verdict
>    threshold crossing (▲ up / ▼ down), grouped by family; and call out any row
>    whose `Salary` column looks mis-parsed (e.g. an OTE or equity-inclusive
>    figure inflating seniority) so it can be eyeballed. Reproduce the full
>    markdown table so the user can review every row.
> 4. Surface the baseline-drift note if the engine emitted one.
> 5. Do NOT write anything. End by stating the exact command that WOULD persist
>    the change: `python -m models.rescore <SCOPE_FLAGS> --write`.

Relay the subagent's summary to the user.

## Step 2: Confirm, then persist

Unless the user already asked to apply in one shot, wait for their go-ahead
after they have seen the dry-run delta. On confirmation, run the same command
with `--write` appended (either directly or via the subagent). The engine:

- rewrites `dimension_scores`, `match_score`, `verdict`, `score_modifier_applied`
  and an audit `rescored` block in each moved `postings/{slug}/application_review.json`;
- updates `match_score` + `verdict` on the matching `applications.yaml` entries
  via `models.applications_index`, preserving every other field
  (`status`, `status_changed_at`, `cv_built_at`, `notes`, `email_activity`, …).

## Step 3: Follow-ups

After a write, if any posting newly reached `STRONG` / `MODERATE-STRONG` and its
`applications.yaml` entry has `cv_built_at: null`, list those slugs and suggest
`/build-cv {slug}` for the ones the user wants to pursue. Do not auto-build.

Note that any family with `cap_verdict_below` set in `config/job_seeker.yaml`
(the example `stretch` family) is held below that verdict by design; do not
suggest `/build-cv` for those postings while the cap stands.

## Step 4: Do not commit

Stop after writing. Do not `git add` / commit / push. The user reviews the
delta and the regenerated files, then commits when satisfied.

## Office-days compatibility note

Reviews written before the office-days scoring change do not carry an `office_days` sub-field. `models/rescore.py` recomputes from stored sub-scores only, so old reviews are unaffected by rescoring. Run a cold `/review-application {slug}` when you need the new office-days rule applied to an older posting.
