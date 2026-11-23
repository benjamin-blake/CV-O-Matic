---
name: negotiate-on-offer
description: >-
  Use when the user reports, in conversation, that they have actually received a
  job offer, or asks for help thinking through one - e.g. "I got an offer
  from Acme, £90k base plus equity", "Globex just offered me the role",
  "what should I counter with on this offer?", "help me negotiate the Initech
  offer". Also fires if the user surfaces or pastes in an offer email or a
  /check-email PR that flagged an `offer`-type email_activity entry and asks
  what to do about it. This is the conversational front door to /negotiate;
  it exists so the user does not have to remember the slash command at the
  one moment it matters most. Do NOT fire on speculative talk with no actual
  offer yet ("I think I'll get an offer soon", "how much should I ask for if
  they offer"). Do NOT fire for building a CV, drafting an application, or
  routine status updates.
---

# negotiate-on-offer

The user has a real offer in hand (or one just surfaced via `/check-email`)
and is discussing it in chat rather than typing `/negotiate {slug}`. Resolve
the posting, then run the command exactly as documented - do not restate its
logic here.

## When this fires (and when it does not)

**Fires:** the user states they have received an offer (with or without full
details), asks for a counter-offer strategy, or references an offer flagged
in a `/check-email` PR/email and wants a brief. Treat any concrete "they
offered me X" statement as firing, even if the offer details are incomplete
- the underlying command already asks for missing figures.

**Does not fire:**
- Speculative or hypothetical offer talk with no real offer yet -> just
  discuss normally, do not run the full brief.
- Interview scheduling, prep, or feedback -> `/log-interview`,
  `/prep-interview`.
- Status changes ("mark Acme as applied") -> edit `applications.yaml`
  directly.

If you are not sure whether an offer is real yet, ask one short clarifying
question before running the brief.

## Steps

### 1. Resolve the posting slug

Identify `postings/{slug}/` from context - the company the user named, or
the posting an offer email/PR referenced. If ambiguous or unstated, ask
which posting.

### 2. Run `/negotiate` for that slug

Follow `.claude/commands/negotiate.md` in full - that file is the single
source of truth (market position from `models/comp.py`, counter-anchor
grounded in `application_review.json`, non-base levers, walk-away line,
conversation script). Do not duplicate or shortcut its steps here. If offer
details were not given in the triggering message, ask for them per the
command's own Step 2 before drafting the brief.

### 3. Report

Deliver the brief in chat as `/negotiate` specifies (chat-only by default;
do not create or commit artefacts unless the user explicitly asks).
