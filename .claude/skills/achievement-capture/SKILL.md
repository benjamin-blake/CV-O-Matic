---
name: achievement-capture
description: >-
  Use when the user volunteers experience, a skill, a tool or an accomplishment
  that might not be in their achievement library yet - e.g. "oh, I've done
  that!", "I actually used Tableau at my last job", "I forgot to mention I led
  the migration", "add this to my achievements", "I've got experience with
  stakeholder workshops too", "that posting mentions GDPR, I did a lot of that".
  Also use when the user answers an evidence prompt from /build-cv or the
  EVIDENCE GAPS section of /briefing. This is how the achievement library grows:
  capture the experience properly (what, impact, number), confirm it, and write
  it to cv/cv_achievements.yaml (and the skills matrix if a tool is named) so
  every future CV and review can use it. Do NOT use this for editing the wording
  of an already-built CV (that is cv-edit-capture), for changing job criteria
  (config/job_seeker.yaml), or for a read-only question about what is in the
  library.
---

# Achievement capture

The achievement library (`cv/cv_achievements.yaml`) is the ceiling on every CV
this repo produces: `/build-cv` can only select what is written there, and
`cv-reviewer` rejects any claim that is not. Most people under-describe their
own experience, and the best prompt to remember something is a posting that
asks for it. This skill turns "oh, I've done that!" into a reusable, accurate
library entry in about a minute.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, the repo is still
on the fictional example profile: tell the user to run `/onboard` first and stop.

## Step 1: Check it is not already there

Read `cv/cv_achievements.yaml` and the `skills_matrix` in `cv/cv_core_data.yaml`.
If an existing entry already covers it, show that entry and ask whether to
strengthen it (a missing number, a sharper impact) rather than add a duplicate.

## Step 2: Ask the three questions

Ask in one short message, plain chat, and accept "not sure" for any of them:

1. **Where and when?** Which role (list the role names from
   `cv/cv_core_data.yaml -> roles`), or personal / cross-role (`role_id: n/a`).
2. **What did you do?** One or two sentences, in their words. Probe once for
   their personal part if it sounds like a team effort ("what was your bit?").
3. **What changed because of it?** The outcome, and a number if there is one
   (time saved, money, people, volume, error rate, satisfaction). If there is
   no number, an honest qualitative outcome is fine. Never suggest or estimate
   a figure for them.

If they mention a named tool or platform, also ask how comfortable they are with
it: expert, comfortable or familiar.

## Step 3: Draft and confirm

Draft the entry in the library's schema:

```yaml
- id: {role prefix}_{short_topic}     # unique; match the existing prefix convention
  role_id: {role id or n/a}
  description: {what they did, active voice, British English, no em-dashes}
  impact: {what changed}
  impact_metric: {the headline number or outcome, exactly as they stated it}
  visual_emphasis: false
  signals: [technical_depth | delivery | influence | leadership | commercial | ai_tooling]
```

Show the draft (and any skills-matrix change) and ask for a yes or edits. Keep
their qualifiers: "helped deliver" must not become "led". Accuracy beats polish.

## Step 4: Write it

On confirmation, append the entry to `cv/cv_achievements.yaml` under the other
entries for that role, and update `skills_matrix` if a tool was added or
re-tiered. Validate the YAML still loads:

```bash
python3 -c "import yaml; yaml.safe_load(open('cv/cv_achievements.yaml')); yaml.safe_load(open('cv/cv_core_data.yaml')); print('ok')"
```

## Step 5: Put it to work

- If this came up during `/build-cv`, return to that build and include the new
  entry in achievement selection.
- If it came up while discussing a posting that already has a review or a CV,
  offer to refresh them (the `review-application-refresh` skill, or a rebuild),
  since the match score may now be higher.
- Otherwise, mention which open postings in `applications.yaml` it is relevant
  to, if any.

Commit the library change with the rest of the session's work (or on its own,
with a message like `Add achievement: {short topic}`), via the usual branch and PR.

Close with one line of encouragement to keep doing this: every captured
achievement improves every future CV, review and application answer.
