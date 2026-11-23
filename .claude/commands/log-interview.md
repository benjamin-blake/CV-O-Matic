---
description: Capture an interview round, set the application stage, and append terminal feedback when applicable.
argument-hint: <slug>
---

# /log-interview {slug}

Capture a structured interview round for `postings/{slug}/interview_notes.md`, update the optional stage field in `applications.yaml`, and keep `interview_prep.md` feedback honest. British English, no em-dashes.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

## Inputs to ask for

Ask the user for these fields before writing:

1. Interview date.
2. Format: recruiter screen, technical, hiring-manager, final, offer, or other.
3. Interviewer names and roles, if known.
4. Stage, one of `screen`, `tech`, `hiring_manager`, `final`, `offer` from `models.applications_index.STAGES`.
5. Questions they asked, with `What I said` and `How it landed` for each.
6. Questions the user asked.
7. Gaps, stumbles, weak answers, or follow-up actions.
8. Outcome if known: continuing, rejected, offer, withdrawn, or unknown.
9. Feedback-log theme and category if the outcome is terminal.

## Write `interview_notes.md`

Append a new round section. Use this structure exactly:

```markdown
## {YYYY-MM-DD} - {stage label}

**Format:** {format}
**Interviewers:** {names and roles}
**Overall feel:** {short summary}

### Questions they asked

#### {question}

**What I said:** {answer summary}

**How it landed:** {reaction or self-assessment}

### Questions I asked

- {question}

### Gaps and stumbles

- {gap or stumble}

### Follow-up actions

- {action}
```

If the file already exists, append the new section. Do not overwrite earlier rounds.

## Update stage

Run the equivalent of:

```python
from models.applications_index import load, save, set_stage

data = load()
set_stage(data, slug, stage, notes="{date} {format}: {one-line summary}")
save(data)
```

Stage is orthogonal to status. Do not change status unless the user explicitly asks.

## Terminal outcomes

If the outcome is `rejected` or `offer`, append exactly one row to the Feedback log table in `interview_prep.md` with: date, company, role, stage, outcome, lesson, and category. If the row already exists, do not duplicate it.

## Commit

Commit the changed files on the current branch. Expected files: `postings/{slug}/interview_notes.md`, `applications.yaml`, and possibly `interview_prep.md`.
