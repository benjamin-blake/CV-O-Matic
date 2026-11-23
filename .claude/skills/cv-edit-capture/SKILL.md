---
name: cv-edit-capture
description: >-
  Use when the user asks Claude Code to change, reword, shorten, lengthen, trim,
  swap, reorder, soften, strengthen, or otherwise edit the CONTENT of an
  already-built CV for a specific posting - e.g. "shorten the summary on the
  Acme CV", "reword the second highlight on the Globex CV", "the projects are
  too long", "soften 'standards-setting' on the Initech CV", "swap that
  achievement", "make the skills matrix punchier". This is the conversational
  (Path B) route into the cv-tweak-capture loop: apply the edit to the posting's
  config, re-validate and re-render with visual review, and then persist the
  edit AND the reason behind it into docs/cv-tweak-ledger.yaml so recurring
  patterns become standing rules - all without the user having to remember to
  run /capture-cv-tweaks. Do NOT use this for building a NEW CV from scratch
  (that is /build-cv), for job discovery (/scan-*), or for status changes.
---

# cv-edit-capture

The user describes a change they want to a CV they have already built; you apply
it and quietly run the capture loop so the edit - and the reasoning - is never
lost and never has to be made twice. This is the automatic front door to
`/capture-cv-tweaks`; it exists so they do not have to remember the workflow.

Before anything else, run `python3 -m models.profile --check`. If it exits
non-zero, stop: the repo is still on the fictional example profile, so tell the
user to run `/onboard` first.

## When this fires (and when it does not)

**Fires:** a request to alter the content of an existing built CV for a known
posting. Signals: an imperative about CV text ("trim", "reword", "swap",
"reorder", "soften", "too long", "add a highlight") aimed at a posting that
already has generated artefacts under `postings/{slug}/`.

**Does not fire:**
- Building a CV that does not exist yet -> `/build-cv {slug}`.
- Finding or scoring jobs -> `/scan-indeed`, `/scan-companies`.
- Flipping application status ("mark Acme as applied") -> edit `applications.yaml`.
- A pure question about a CV ("what did I say about dbt?") -> just answer.

If you are unsure whether a message is an edit request, ask one short
clarifying question rather than guessing.

## Steps

### 1. Resolve the posting

Identify the target `postings/{slug}/`. If the message names a company
("the Acme CV", "the Globex one"), match it against `postings/` directories. If
ambiguous or unstated, ask which posting. Confirm the posting has been built
(a `config/` directory and generated `{name_slug}_cv.html` exist; `python3 -m models.profile` prints the file names); if it has
not, this is a build, not an edit - redirect to `/build-cv`.

### 2. Capture the reason BEFORE editing

The reason is the whole point of the ledger. If the user gave a rationale
("it spills onto a second line", "'standards-setting' sounds boastful"), keep it
verbatim. If they did not, ask one brief "what's the reason?" question - do not
invent one. Hold the reason for Step 5.

### 3. Apply the edit at the content level

Edit only the relevant file(s) under `postings/{slug}/`:
- summary -> `config/summary.yaml`
- experience highlights -> `config/experience.yaml` (and `config.yaml`
  `selected_achievement_ids` if you add/swap an achievement, so metric grounding
  still holds)
- skills -> `config/skills.yaml`
- projects -> `config/projects.yaml`
- criteria -> `config/criteria_responses.yaml`
- personal statement -> `personal_statement.txt`

Respect every `/build-cv` content rule: British English, no em-dashes,
achievement-library fidelity (never inflate a metric or upgrade qualifier
language beyond `cv/cv_achievements.yaml`), reverse-chronological role order.
**Never** edit the protected engine (`cv/generate_cv.py`, `cv/lib/`, the
template, the stylesheet). If the change genuinely needs the engine, do not
force it - record it in the ledger as `engine_blocked` and tell the user.

### 4. Re-validate and re-render (reuse the /build-cv tail)

Run the same gates `/build-cv` uses so an edit cannot silently break the CV:
- **Step 4.5** - `cv/check_lengths.py postings/{slug}` (exit 0; fix and re-run on FAIL).
- **Step 6** - regenerate `{name_slug}_cv.html` / `.pdf`.
- **Step 6.5** - `cv/render_preview.py postings/{slug}`, then Read each page image
  and confirm the edit reads correctly and nothing is truncated / overflowing.
  If rendering is unavailable (exit 3), say so and proceed text-only.

### 5. Run the capture loop

Now invoke the capture methodology in `.claude/commands/capture-cv-tweaks.md`
for this slug (that file is the single source of the capture logic - follow it,
do not restate it). In short: classify the edit into a pattern class, append a
`docs/cv-tweak-ledger.yaml` entry carrying `date`, `slug`, `pattern`, `detail`,
`reason` (from Step 2), and `action`. Apply the two-strike rule: first sighting
-> `observed`; a second sighting of the same pattern on a different posting ->
propose a generalised rule (a `build-cv.md` guidance line or a deterministic
`cv/check_lengths.py` check) and promote it ONLY on the user's explicit
per-proposal approval. Nothing lands in `build-cv.md` or `check_lengths.py`
without that approval.

### 6. Commit and open a PR

Commit the CV edit and the ledger entry (and any approved rule, as its own
commit) to the working `claude/...` branch, push, and open a PR to `main`.
The user merges it themselves. Because these edits can touch `docs/` and the rule
files (outside the routine auto-merge scope), the PR is a normal review-and-merge
PR, not an auto-merge routine PR.

### 7. Report

Tell the user: what changed, the visual-review result, the ledger entry (pattern
+ whether it is `observed` or newly `rule_added`), and the PR link.
