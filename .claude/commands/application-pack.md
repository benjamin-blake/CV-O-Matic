---
description: Generate a per-posting application_pack.md of ready-to-paste answers for UK application forms (standard questions plus posting-specific ones).
argument-hint: <posting_slug>
---

# /application-pack

Generate `postings/$1/application_pack.md`: a draft of ready-to-paste answers to the questions UK application forms ask, so submitting an application becomes a copy-paste job rather than a fresh writing session.

**Posting slug:** `$1` (format: `YYYY-MM-DD_{company}_{title_kebab}`).

Use **British English** throughout. **No em-dashes or en-dashes.** First person singular ("I built", not "we built"). The pack is a **draft for the candidate to paste and adapt**: this command never submits anything anywhere.

If `$1` is empty, ask the user for the posting slug (a directory under `postings/`).

**Grounding rule (hard).** Every metric, qualifier, or claim in a drafted answer must trace to `cv/cv_achievements.yaml`, `cv/cv_core_data.yaml`, `config/job_seeker.yaml`, or `config/application_answers.yaml`. Never cite a metric that is absent from the achievements selected in this posting's `config.yaml`. This is the same rule `cv/check_lengths.py` enforces on `criteria_responses`.

---

## Step 0: Profile guard and pull from remote main

**Profile guard.** Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

**Pull.**

```bash
git pull --ff-only origin main
```

If it fails (non-fast-forward, dirty tree, detached HEAD), stop and surface the error. After a successful pull, verify `postings/$1/` exists; if not, list `postings/` matches by company keyword and ask the user to confirm the slug. A built CV is not strictly required, but the pack is far richer when `config.yaml`, `config/`, `application_review.json`, and `personal_statement.txt` already exist (i.e. `/build-cv $1` has run). If they are absent, draft the standard section anyway and note in the posting-specific section which inputs were missing.

---

## Step 1: Extract the posting's own questions

Read `postings/$1/posting.txt`. Pull out any application questions the posting itself lists verbatim: supporting-statement prompts, "why do you want to work here", competency or values questions, "is there anything else", word or character limits attached to any of them. Keep the exact wording; you will use it as a heading. If the posting lists none, the posting-specific section still covers the standard "why this company" and "why this role" pair.

---

## Step 2: Resolve the standard answers

Read `config/application_answers.yaml`. Assemble the standard section from it, resolving the two dynamic parts:

**2a. Date-sensitive notice period.** `notice_period` carries `date_sensitive: true`, a `final_day` (null until notice is handed in), and three phrasings: `standard`, `while_serving_notice` and `after_final_day`. Re-derive which applies from today's date, do not paste a stale sentence:

```bash
python3 -c "
import datetime, yaml
d = yaml.safe_load(open('config/application_answers.yaml'))['notice_period']
today = datetime.date.today()
if not d.get('final_day'):
    print(d['standard'])
else:
    final = datetime.date.fromisoformat(d['final_day'])
    if today <= final:
        print(d['while_serving_notice'].format(final_day=d['final_day'], available_from=d.get('available_from')))
    else:
        print(d['after_final_day'])
"
```

Use the printed line verbatim as the notice-period answer. (Selection logic: `final_day` null -> `standard`; today on or before `final_day` -> `while_serving_notice`; after it -> `after_final_day`.)

**2b. Sector-variant answers.** Keys with a `variants` block hold a `private_sector` and a `uk_civil_service` value. Detect the sector from `posting.txt` using the signals already documented in `config/job_seeker.yaml` -> `compensation.sector_floor_overrides.uk_civil_service.rationale` (Civil Service Pension, Success Profiles, Civil Service Behaviours, a nationality requirement, or a central-government employer such as GDS, DSIT, Defra, Cabinet Office, DfE, DWP, HMRC, MoJ, Home Office, UKHSA, MOD). If any signal is present, use `uk_civil_service`; otherwise use `private_sector`. State which variant you picked in the pack.

**2c. Salary expectation (single figure preferred, range as fallback).** `salary_expectation.variants.{sector}` is a nested block, not a flat string: `figure_gbp` (a plain integer for a numeric form field), `single` (a one-line answer stating that figure), and `range` (a hedged prose answer). The default preference is the single figure (`preference: single_figure`): when an application form has a numeric salary box, type the number, and use the range only for a free-text box or a conversation where room to negotiate is wanted. Surface **both** in the pack (see Step 4) so the candidate can pick per form, leading with the single figure. Do not invent or round the figures; paste `figure_gbp`, `single`, and `range` for the detected sector verbatim.

Non-varying keys (`right_to_work`, `security_clearance`, `location_and_hybrid`, `interview_availability`, `referees`, `why_leaving`) are pasted as-is. If `security_clearance` is null, omit that answer from the pack (do not write a heading for it).

`why_leaving` is single-sourced in `config/application_answers.yaml`. Do not rewrite or embellish its facts here; paste the stored answer.

---

## Step 3: Draft the posting-specific answers

For each question from Step 1, plus "Why this company?" and "Why this role?" if not already covered, draft a grounded answer. Sources, in order of preference:

- `postings/$1/application_review.json` - the criteria analysis, gaps, and recommendations already computed for this posting.
- `postings/$1/personal_statement.txt` - the bespoke narrative already written for this company.
- The achievements listed in `postings/$1/config.yaml :: selected_achievement_ids`, read from `cv/cv_achievements.yaml`.

Apply the grounding rule strictly: a competency answer may only cite a number that appears in the `description` or `impact` of a selected achievement. If a question needs an example you cannot ground, write the answer around the qualitative facts and leave a clearly marked `[TODO: add a specific example]` rather than inventing one.

Keep answers first person singular, concrete, and to any word or character limit the posting stated. Lead with the specific example, then the decision, then the outcome (the `interview_prep.md` habit), not with general approach.

---

## Step 4: Write the pack

Write `postings/$1/application_pack.md` with exactly two top-level sections, each answer under a verbatim question heading:

```markdown
# Application pack - {Company}, {Job title}

Draft answers for the {Company} application. Paste and adapt; nothing here is submitted automatically.
Sector detected: {private_sector | uk_civil_service}. Notice-period answer derived on {today's date}.

## Standard answers

### Notice period / availability
{resolved notice_period answer}

### Right to work / sponsorship
{right_to_work}

### Security clearance (omit if `security_clearance` is null)
{security_clearance}

### Salary expectation
Preferred (numeric field): **£{figure_gbp}**
{single}
If a free-text box or a conversation with room to negotiate: {range}

### Location and hybrid working
{location_and_hybrid}

### Interview availability
{interview_availability}

### Referees
{referees}

### Why are you leaving your current role?
{why_leaving}

## Posting-specific answers

### {verbatim question 1 from the posting, or "Why this company?"}
{grounded answer}

### {verbatim question 2, or "Why this role?"}
{grounded answer}

### {further competency questions as needed}
{grounded answer}
```

Only include standard sub-headings whose answer is present. Keep the two `## ` section headings exactly as `## Standard answers` and `## Posting-specific answers`.

---

## Step 5: British-English and dash check (MANDATORY)

Reuse the `cv/check_lengths.py` conventions (US-to-UK spellings and forbidden dashes) against the generated pack:

```bash
python3 -c "
import sys
sys.path.insert(0, 'cv')
from check_lengths import US_TO_UK, DASH_CHARS, _PAIR_DASH_RE
import re
text = open('postings/$1/application_pack.md', encoding='utf-8').read()
fails = []
for us, uk in US_TO_UK.items():
    for m in re.finditer(rf'\b{re.escape(us)}\b', text, re.IGNORECASE):
        fails.append(f\"US spelling '{m.group(0)}' -> use '{uk}'\")
for dash in DASH_CHARS:
    if dash in text:
        fails.append(f'forbidden dash {dash!r}')
if _PAIR_DASH_RE.search(text):
    fails.append(\"forbidden '--'\")
print('CLEAN' if not fails else 'FAIL:\n' + '\n'.join(fails))
"
```

If it prints anything other than `CLEAN`, fix the offending text in the pack and re-run until clean. Do not proceed with US spellings or dashes in the file.

---

## Step 6: Commit and open a PR

Follow the routine flow: commit on a `claude/**` branch and open a PR to `main`.

```bash
git checkout -b claude/application-pack-$1 2>/dev/null || git checkout claude/application-pack-$1
git add postings/$1/application_pack.md
git commit -m "feat(application-pack): draft application answers for $1"
git push -u origin HEAD
```

Then open the PR with `mcp__github__create_pull_request` (base `main`). The pack lives under `postings/**`, so it is inside the `auto-merge-routine.yml` path scope and will squash-merge once validated.

---

## Step 7: Completion summary

Report to the caller: posting slug, company, job title, sector detected, notice-period phrasing used, the count of standard answers and posting-specific answers written, and any `[TODO]` markers the candidate needs to fill before submitting.

## Contract branch

If the posting or `applications.yaml` entry is `engagement: contract`, add standard answers for day-rate expectation, IR35 stance, and availability from `config/job_seeker.yaml :: contracting`. Use the configured day-rate minimum and target only in the application pack or conversation notes, never in generated CV or personal statement artefacts. If limited-company or umbrella status is needed and not present in config, mark it as a question for the candidate rather than inventing it.
