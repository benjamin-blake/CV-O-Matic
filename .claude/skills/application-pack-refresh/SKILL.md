---
name: application-pack-refresh
description: >-
  Use when the user asks, in conversation, to generate, draft, write, refresh,
  regenerate, redo, or update the ready-to-paste application-form answers for
  a posting - e.g. "draft my application answers for the Acme posting",
  "refresh the application pack for Globex, the form asks different questions
  now", "redo the application pack, my notice period changed", "write the
  application answers for the Initech role". This is the conversational
  front door to /application-pack; it exists so the user does not have to
  remember the slash command. Do NOT use this for a plain read-only question
  about an existing pack ("what did I say about my notice period on the Acme
  pack?", "show me the application pack for Globex") - just read and answer
  from the file. Do NOT use this for building a CV from scratch (/build-cv)
  or for writing the analytical review (see review-application-refresh).
---

# application-pack-refresh

The user asks for application-form answers in conversation rather than typing
`/application-pack {slug}`. Resolve the posting, then run the command exactly
as documented - do not restate its logic here.

## When this fires (and when it does not)

**Fires:** a request to produce or refresh the pasteable application-form
answers for a specific posting. Signals: "draft/write/generate my
application answers", "refresh/redo/update the application pack", "the form
asks different questions now", "my notice period/salary expectation
changed, update the pack".

**Does not fire:**
- A read-only question about an existing pack -> just read
  `postings/{slug}/application_pack.md` and answer.
- Building a new CV -> `/build-cv {slug}`.
- Writing or refreshing the analytical review -> `review-application-refresh`
  skill / `/review-application`.
- Bulk re-scoring after a scoring **rule** change -> `/rescore-application`
  (deterministic, not this).

If you are unsure whether the user wants a fresh pack or just wants to see
the existing one, ask one short clarifying question rather than guessing.

## Steps

### 1. Resolve the posting slug

Identify `postings/{slug}/` from context - a company name, a recently
discussed posting, or an explicit slug. If ambiguous or unstated, ask which
posting.

### 2. Run `/application-pack` for that slug

Follow `.claude/commands/application-pack.md` in full - that file is the
single source of truth for this logic (grounding rule, standard vs
posting-specific sections, notice-period and salary-expectation resolution,
British-English/dash check, commit and PR). Do not duplicate or shortcut its
steps here.

### 3. Report

Tell the user what changed since the pack was last generated (if it existed
before), the sector detected, and the PR link. Flag any `[TODO]` markers they
need to fill before submitting. (The command begins with the profile guard: if `python3 -m models.profile --check` fails, tell the user to run `/onboard` first.)
