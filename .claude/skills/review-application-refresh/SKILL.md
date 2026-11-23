---
name: review-application-refresh
description: >-
  Use when the user asks, in conversation, to refresh, redo, re-run, update,
  or re-judge the analytical review (application_review.json) for a specific
  posting because the posting text or the CV/achievement library changed -
  e.g. "redo the review for Acme, I updated the posting text", "the
  achievement library changed, refresh the Globex review", "re-judge the
  Initech posting cold". This is the conversational front door to
  /review-application; it exists so the user does not have to remember the
  slash command. Do NOT use this for a plain read-only question about an
  existing review ("what gaps did the review flag for Acme?", "what's the
  match score for Globex?") - just read and answer from the JSON. Do NOT use
  this for a bulk re-application of scoring RULES across many postings after
  a weights/deal-breaker change in config/job_seeker.yaml - that is
  /rescore-application, a deterministic re-computation from stored
  sub-scores, not a fresh job-matcher judgement. Do NOT use this as part of
  /build-cv's own internal review step - that already runs on its own.
---

# review-application-refresh

The user asks to re-judge a posting's analytical review in conversation
rather than typing `/review-application {slug}`. Resolve the posting, then
run the command exactly as documented - do not restate its logic here.

## When this fires (and when it does not)

**Fires:** a request to write or refresh the structured
`application_review.json` for one named posting, because the posting text
changed, the CV/achievement library changed, or the user simply wants a
fresh cold judgement.

**Does not fire:**
- A read-only question about an existing review -> read
  `postings/{slug}/application_review.json` and answer directly.
- A scoring **rule** change applied across many postings (a weight, a
  role-family modifier, a deal-breaker) -> `/rescore-application`, which
  recomputes deterministically from stored sub-scores rather than re-judging
  the posting text. Point the user there instead of firing this skill.
- The review step already embedded inside `/build-cv` - that runs on its
  own; do not double-invoke.
- Drafting application-form answers -> `application-pack-refresh` skill /
  `/application-pack`.

If unsure whether the user wants a single fresh re-judgement or a rule-driven
bulk rescore, ask which one before proceeding.

## Steps

### 1. Resolve the posting slug

Identify `postings/{slug}/` from context. If ambiguous or unstated, ask
which posting.

### 2. Run `/review-application` for that slug

Follow `.claude/commands/review-application.md` in full - that file is the
single source of truth (load inputs, job-matcher scoring, essential/nice-to-have
criteria analysis, gaps, recommendations, artefact paths, schema-conformant
write). Do not duplicate or shortcut its steps here.

### 3. Sync the index

If `match_score` or `verdict` changed, update the corresponding entry in
`applications.yaml` (`match_score`, `verdict`) so the two stay in sync -
`/review-application` itself does not touch the index.

### 4. Report

Tell the user the new match score and verdict, what changed versus the
previous review (if one existed), and the path to the written JSON.
