---
description: Build a role-specific interview preparation pack and optionally drill the user on concrete example, decision, outcome delivery.
argument-hint: <slug> [--stage screen|tech|hiring_manager|final]
---

# /prep-interview {slug}

Create `postings/{slug}/interview_prep_pack.md` for the next interview. British English, no em-dashes. The pack must be grounded in existing repo evidence only.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

## Inputs

Read:

- `postings/{slug}/posting.txt`
- `postings/{slug}/application_review.json`
- `postings/{slug}/config/` if the CV has been built
- `interview_prep.md` (the playbook: the recurring pattern, habits, STAR-R template, Human APIs, Story bank, Tooling, Pre-interview checklist, Feedback log)
- `cv/cv_achievements.yaml`
- any `postings/*/interview_notes.md` for the same company or the same failure themes

## Pack contents

Write `postings/{slug}/interview_prep_pack.md` with:

1. **Role readout:** company, role, stage, key risks, and what the interview likely needs to prove.
2. **Likely questions:** 8 to 12 questions tailored to the role and stage. Each must map to a named Story bank entry or achievement id, with the one number or concrete outcome to land.
3. **Decision-story prompts:** at least two prompts that force the user to state a named decision, the trade-off, and the result.
4. **Technical topics:** role-specific topics inferred from the posting and review JSON.
5. **Questions to ask:** three sharp questions, including one commercial-outcomes question.
6. **Checklist:** copy the Pre-interview checklist section from `interview_prep.md`.

Do not invent anecdotes. If a useful story is missing from the Story bank or achievement library, write `MISSING STORY: {need}` rather than filling the gap.

## Drill mode

After writing the pack, offer drill mode in chat. Drill mode writes nothing.

Ask one behavioural question at a time and grade the user's typed answer against exactly these three checks:

1. Concrete example appears within the first two sentences.
2. A named decision and trade-off are stated.
3. A number or concrete outcome is landed.

Keep feedback terse: `Example: pass/fail`, `Decision: pass/fail`, `Outcome: pass/fail`, then one specific improvement.

## Commit

Commit the pack on the current branch unless the user asked for a dry run.
