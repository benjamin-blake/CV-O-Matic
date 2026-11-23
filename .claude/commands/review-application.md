---
description: Write or refresh the structured application_review.json for a posting. Used by /build-cv after CV generation, and re-runnable manually if posting or CV changes.
argument-hint: <posting_slug>
---

# /review-application

Write `postings/$1/application_review.json` (the detailed analytical review) for the posting. The JSON must conform to `config/application_review.schema.json`. Status / cv_built_at / notes live in the root-level `applications.yaml`, not here.

**Posting slug:** `$1`

If `$1` is empty, ask the user for the posting slug.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

## Step 1: Load inputs

Read in full:
- `postings/$1/posting.txt`
- `postings/$1/config.yaml`
- `postings/$1/config/*.yaml` (all section configs)
- `postings/$1/personal_statement.txt` (if it exists)
- `cv/cv_achievements.yaml`, `cv/cv_core_data.yaml`
- `config/job_seeker.yaml`
- `config/application_review.schema.json` - for the canonical shape

If an `application_review.json` already exists, read it and preserve `discovered_via` and `posting_url` unless the caller passes a flag to reset them.

## Step 2: Score against job_seeker requirements

You may invoke the `job-matcher` subagent with the local `posting.txt` to get the structured assessment. Use its output to populate `match_score`, `verdict`, `verdict_justification`, `summary` (office_and_location / compensation / mission_and_culture / technical_fit / overall), `dimension_scores`, and `deal_breakers_triggered`. The `summary` block is the human-readable "is this for me?" brief - carry it through verbatim; do not abbreviate.

## Step 3: Analyse essential and nice-to-have criteria

For each essential criterion in the posting:
- Locate the matching entry in `postings/$1/config/criteria_responses.yaml` (if any).
- Locate the strongest supporting highlight in `postings/$1/config/experience.yaml`.
- Classify match as `FULL` / `PARTIAL` / `NONE`.
- Write one sentence of evidence citing concrete facts from the CV configs and the source achievement.

Repeat for nice-to-have criteria.

## Step 4: Identify gaps

Surface 3-5 gaps where the CV does not fully address an essential or high-priority nice-to-have criterion. For each:
- `issue`: what the gap is
- `impact`: how a hiring manager is likely to read it
- `mitigation`: what to say in interview, or a recommended addition to the personal statement / criteria response

## Step 5: Recommendations

3-5 actionable suggestions for the candidate: interview prep angles, language to use in the cover note, references to surface.

## Step 6: Assemble artefacts paths

**Check the filesystem for each artefact.** The CV file names come from the candidate's name: run `python3 -m models.profile` to print them (in Python, `models.profile.cv_filenames()`). Do not copy the example below verbatim - actually check `postings/$1/` for each file and set paths accordingly.

```json
"artefacts": {
  "posting": "postings/$1/posting.txt",
  "cv_pdf": "postings/$1/{name_slug}_cv.pdf",          // null if file does not exist
  "cv_html": "postings/$1/{name_slug}_cv.html",        // null if file does not exist
  "personal_statement": "postings/$1/personal_statement.txt" // null if file does not exist
}
```

For each of `cv_pdf`, `cv_html`, `personal_statement`: use Glob or Read to verify the file exists in `postings/$1/`. If it does, set the path string. If it doesn't, set `null`.

## Step 7: Write the JSON

Write `postings/$1/application_review.json` conforming to `config/application_review.schema.json`. Set `generated_at` to the current UTC ISO 8601 timestamp. Validate (mentally) against the schema before writing - required fields, enum values, types.

## Step 8: Return summary

Return to the caller:
- Posting slug, match score, verdict
- Number of essential criteria covered FULL / PARTIAL / NONE
- Number of gaps surfaced
- Path to the JSON written
