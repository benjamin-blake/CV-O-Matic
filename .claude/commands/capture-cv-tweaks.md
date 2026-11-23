---
description: Capture the manual tweaks the candidate made to a built CV, classify the recurring patterns, and promote stable ones into build-cv.md guidance or check_lengths.py checks.
argument-hint: <posting_slug>
---

# /capture-cv-tweaks

Turn the edits the candidate makes by hand after `/build-cv` into standing rules, so
each class of tweak never has to be made twice. This is the CV-O-Matic
friction-capture loop: diff what `/build-cv` generated against what the candidate
actually shipped, classify the delta, and - on a pattern's **second** appearance
across postings - promote it into `build-cv.md` guidance or a deterministic
`cv/check_lengths.py` check. The ledger at `docs/cv-tweak-ledger.yaml` is the
memory that distinguishes a one-off from a recurring pattern.

**Posting slug:** `$1` (a directory under `postings/`, e.g. `2026-01-15_home_office_senior_data_analyst`)

If `$1` is empty, ask the user which posting to capture from.

**Step 0 - profile guard.** Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

Use **British English** throughout. No em-dashes.

---

## How it works (read this to the user if they ask)

There are two ways an edit reaches the ledger, and both end in the same place:

1. **Detected from git** - the candidate edits the config files (or the generated
   artefacts) by hand after the build, then runs this command. The command
   diffs the `/build-cv` commit for the posting against current HEAD and reads
   the delta straight out of the diff.
2. **Described in chat** - the user tells Claude Code what to change
   ("trim the summary, it runs onto a second line", "swap 'spearheaded' for
   'led'"), Claude applies it to the config files, and the command captures both
   the mechanical change **and the reason the user gave** into the ledger.

Either way, the ledger records the *why*, not just the *what*: the `reason`
field on each entry persists the user's rationale so that when a pattern is
eventually promoted to a rule, the rule carries its justification. A pattern is
only promoted on its **second** sighting across different postings (the
two-strike rule); the first sighting is logged as `observed`.

---

## Step 1: Locate the build baseline

Find the commit where `/build-cv` generated this posting's CV - the most recent
commit that touched the posting's generated artefacts (`config/`, `config.yaml`,
`{name_slug}_cv.html`, `personal_statement.txt`; `python3 -m models.profile` prints the file names).

```bash
git log --oneline -- postings/$1/config postings/$1/config.yaml \
  postings/$1/{name_slug}_cv.html postings/$1/personal_statement.txt | head
```

The topmost hash from a `build-cv:` / "Build CV" / "Render ... CV" commit is the
build baseline. If several commits look like builds (an initial build plus a
re-render), take the newest one that represents the generated-not-hand-edited
state. If you are unsure which commit is the clean baseline, show the candidate
list to the user and ask.

---

## Step 2: Compute the manual delta

Diff the baseline against the current working tree (staged, unstaged, and
committed hand-edits all count) for the posting directory:

```bash
git diff <baseline_hash> -- postings/$1/config postings/$1/config.yaml \
  postings/$1/personal_statement.txt postings/$1/{name_slug}_cv.html
git diff -- postings/$1/            # uncommitted hand-edits in the working tree
```

Also fold in any edits made **in this session** (the "described in chat" path):
if the user asked for changes and Claude applied them during this conversation,
treat each of those as part of the delta with the reason given at the time.

**If there is no manual delta and nothing was changed in-session**, stop and
report: `no manual changes detected for $1`. Do not touch the ledger,
`build-cv.md`, or `check_lengths.py`. (Acceptance criterion: clean exit.)

---

## Step 3: Classify each hunk

Group the delta into these pattern classes (same set the ledger documents):

| Pattern class | What it looks like |
|---|---|
| `length_reduction` | a section trimmed to fit the page - record which section and roughly how much (chars / lines) |
| `wording_substitution` | a phrase swapped - record the `from -> to` pair |
| `achievement_swap` | a selected achievement replaced with a different one |
| `ordering_change` | highlights or sections reordered |
| `skills_band_change` | a skill moved tier, or `<strong>` bold added/removed |
| `other` | anything that does not fit the above |

For each hunk capture: the **class**, a concrete **detail** (the actual
from/to, the section, the magnitude), and the **reason** - the user's rationale.
If the edit came from git and the reason is not obvious, **ask why** rather
than guessing; the reason is the point of the exercise.

---

## Step 4: Consult the ledger and decide promotion (two-strike rule)

Read `docs/cv-tweak-ledger.yaml`. For each classified pattern, check whether a
prior entry with the **same class and same substance** exists from a
**different** posting.

- **First appearance** -> this is `observed`. Log it to the ledger, propose no
  rule.
- **Second appearance across a different posting** -> this is a recurring
  pattern. Propose a **generalised** rule:
  - If the pattern is a **judgement call** (wording tone, which achievement fits
    a sector, how aggressively to trim): propose a guidance line for the
    **Common pitfalls** section of `.claude/commands/build-cv.md`.
  - If the pattern is **deterministic** (a length consistently N% over a cap, a
    specific banned phrase): propose a check in `cv/check_lengths.py` with a
    concrete threshold.
  - If the pattern genuinely needs engine changes (`generate_cv.py`, `cv/lib/`,
    the template, or the stylesheet - see **What NOT to touch** in `CLAUDE.md`):
    do **not** edit those. Log the entry as `engine_blocked` and surface it to
    the user as a separate decision.

Generalise, do not hard-code the instance. "The summary for the Home Office posting was 40 chars
too long" is not a rule; "summaries tend to run ~10% over the 600-char cap when
they name the company twice - target 540" is.

---

## Step 5: Present proposals one by one for approval

For each proposed rule (only the second-appearance ones), show the user:
- the pattern and the two postings it appeared in,
- the exact guidance line or check_lengths.py diff you would add,
- ask for explicit approval.

**No rule is written without explicit approval in the session.** If they decline,
the pattern still gets its `observed`/second-sighting ledger entry (so the
memory persists), but `build-cv.md` and `check_lengths.py` are left untouched.

---

## Step 6: Apply approved changes

For each **approved** proposal:

- **Guidance line** - append it as a new numbered item under the
  `## Common pitfalls` section of `.claude/commands/build-cv.md`.
- **Deterministic check** - add it to `cv/check_lengths.py`. It must:
  - be deterministic and fast (no network, no model calls),
  - preserve the binary exit-code contract (0 = all pass, 1 = any FAIL, 2 =
    usage error),
  - not break existing checks on current postings (regression-guard in Step 8).
  - Length-style checks belong in the `LIMITS` table + a `check_*` function
    appended to `checks`; content-style checks belong as a `check_*` that
    appends to `issues` with `SEVERITY_FAIL` or `SEVERITY_WARN`.

Make **each approved change its own commit** (the plan's rollback contract - a
bad rule can be reverted individually).

---

## Step 7: Update the ledger

Append one entry per classified pattern (both the observed-once and the
promoted-to-rule ones) to `docs/cv-tweak-ledger.yaml`:

```yaml
entries:
  - date: "{today UTC, YYYY-MM-DD}"
    slug: "$1"
    pattern: "{class}"
    detail: "{concrete from -> to / section / magnitude}"
    reason: "{the user's rationale, in their words}"
    action: "{observed | rule_added | engine_blocked}"
```

Validate it still parses:

```bash
python -c "import yaml; yaml.safe_load(open('docs/cv-tweak-ledger.yaml'))" && echo LEDGER_OK
```

---

## Step 8: Regression guard (only if a check_lengths.py check was added)

Re-run the length checker across every already-built posting and confirm no
posting that passed before now fails because of the new check:

```bash
for d in postings/*/; do
  [ -f "$d/config.yaml" ] && cv/.venv/bin/python cv/check_lengths.py "${d%/}"
done
```

(Windows: `cv/.venv/Scripts/python.exe`.) A new check that fails a
previously-passing, already-shipped CV is too aggressive - loosen the threshold
or downgrade it to a `WARN`.

---

## Step 9: Completion summary

Report to the user:
- the posting captured and how many hunks were classified,
- per pattern: class, detail, and whether it was `observed` (first sighting),
  `rule_added` (promoted), or `engine_blocked`,
- which files changed (`build-cv.md` / `check_lengths.py` / ledger only),
- for anything promoted, the exact rule text and its commit.

---

## Common pitfalls

1. Promoting on the first sighting - the two-strike rule exists so one-off edits
   do not calcify into rules. First appearance is `observed`, full stop.
2. Recording the instance instead of the generalisation - a promoted rule must
   apply to the next CV, not just describe the last one.
3. Editing the rendering engine - if a tweak needs `generate_cv.py`, `cv/lib/`,
   the template, or the stylesheet, log it `engine_blocked` and surface it; do
   not touch **What NOT to touch**.
4. Dropping the reason - the `reason` field is the point. If an edit came from
   git and the why is not obvious, ask; do not guess.
5. Writing a rule without approval - the ledger can log anything, but
   `build-cv.md` and `check_lengths.py` change only on explicit per-proposal
   approval.
