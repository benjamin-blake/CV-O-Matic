---
description: On-demand decision briefing - live top picks, ageing strong matches, in-flight applications, interviews, recurring evidence gaps, and funnel counts.
---

# /briefing

Produce the user's decision queue on demand. Run it whenever you want a snapshot of where the pipeline stands. Read-only over posting artefacts: it does not flip statuses, build CVs, create postings, stamp watermarks, or commit anything. Chat-only output. British English, no em-dashes.

## Inputs

Read `applications.yaml` and available `postings/{slug}/application_review.json` files. Gracefully handle missing `stage`, `follow_up`, `cv_built_at`, or review JSON fields.

## Output, at most 35 lines

Always include each posting's `posting_url` as a clickable link so the user can open and view it themselves, in every section that lists individual postings (TOP PICKS, AGING, IN FLIGHT, INTERVIEWS). If `posting_url` is null or missing, say so inline (for example `(no link on file)`) rather than omitting the posting.

1. **TOP PICKS:** up to 5 open STRONG or MODERATE-STRONG entries, ranked by `match_score` then freshness. Include company, role, score, salary if stated, days since discovery, whether a CV exists, and a link to the posting.
2. **AGING:** open STRONG entries older than 10 days with no `cv_built_at`; link each posting and ask for an explicit apply-or-decline decision.
3. **IN FLIGHT:** applied entries with days since latest `email_activity`; link each posting, show due or overdue `follow_up` nudges, and flag the two nudge-worthy states (applied with no confirmation email on file, or an interview outcome outstanding 7+ days) rather than every quiet entry - an application the ATS has confirmed but not yet progressed is not a nudge candidate.
4. **INTERVIEWS:** entries with `stage` set and status still applied; link each posting.
5. **EVIDENCE GAPS:** read `gaps` (and any `must_have_coverage` / criteria with match `NONE` or `PARTIAL`) from the review JSONs of open STRONG, MODERATE-STRONG and MODERATE postings. Group similar themes and show at most 3 that recur across **2 or more** postings, each with the count and the companies (for example "Stakeholder workshops: 4 postings (Home Office, Scotland Yard, ...)"). End with one line inviting the user to say "I've done that" for any of them, which captures it into the achievement library (the `achievement-capture` skill). Omit the section when nothing recurs.
6. **FUNNEL:** counts by status and total.
