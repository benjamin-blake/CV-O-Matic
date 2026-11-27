---
description: First-run setup. Replaces the fictional example profile (Sherlock Holmes) with your own CV, job criteria and standard answers, gets you to your first tailored CV, then offers the optional daily automation (job-board scans, Gmail tracking, Drive sync, phone notifications).
---

# /onboard

Walk a new user from a fresh copy of this template to their first tailored CV.
The user may be new to Claude Code, so this is also a guided tour: explain what
you are doing and why in a sentence or two at each phase, and finish each phase
with one short **Tip** about using Claude Code. Keep tips practical (how to
review a diff, how to ask for a change, how to undo), never more than two lines.

Re-runnable. If `python3 -m models.profile --check` already passes, the user has
onboarded before: ask which phases they want to redo and skip the rest.

## Ground rules

- **Never invent.** Every role, date, skill tier, achievement and metric comes
  from the user (their CV, their answers). If an achievement has no number, ask
  once whether there is one; if not, record an honest qualitative impact. The
  achievement library is the source of truth for every future CV, and
  `cv-reviewer` enforces it, so accuracy now saves rework later.
- **British English, no em-dashes or en-dashes** in anything you write into the repo.
- **Ask in small batches.** Use `AskUserQuestion` for choices with sensible
  options (2 to 4 questions per call); use plain chat for free text. Never dump
  a 20-question form.
- **Show, then write.** Before writing each file, summarise what will go in it
  and get a yes. After writing, show the user how to see the change (`git diff`
  or the file in their editor).
- **Privacy check first.** This repo will hold salary expectations, application
  history and Gmail links. In Phase 0, check whether the repo is public (ask the
  user, or inspect the remote with the GitHub tools if available). If it is
  public, stop and recommend making their own copy private before continuing:
  the public template is for sharing the tooling, not their job search.

## Phase 0 - Welcome and orientation

1. Greet the user and explain in five lines or fewer what this repo does:
   discovers postings, scores them against their criteria, builds a tailored
   CV and application answers on request, and tracks every application in
   `applications.yaml`. Everything is driven by asking Claude Code in plain
   English; slash commands like `/build-cv` are shortcuts.
2. Run `python3 -m models.profile` and show the result: the example profile
   (Sherlock Holmes) is in place, and that is what this command replaces.
3. Do the privacy check above.
4. Outline the phases (CV in, what you want, standard answers, watchlist,
   first CV, save, optional automation) and roughly how long it takes (20 to
   40 minutes, can be paused and resumed at any phase).

**Tip:** you can interrupt at any point, ask "why?", or say "go back".

## Phase 1 - Your CV in

Files: `cv/cv_core_data.yaml`, `cv/cv_achievements.yaml`.

1. Ask the user to share their current CV: upload a PDF or Word file, or paste
   the text. A LinkedIn profile export works too. Read it fully.
2. Draft `personal_info`: name, headline title, location, phone, email, and
   optional GitHub / portfolio URL. Leave `birth_date` and `nationality` empty
   unless the user insists (UK practice is to omit them). Explain that the name
   here also names their generated CV files.
3. Draft `roles`, **newest first**. Give each a short, stable snake_case `id`
   (company-based, e.g. `home_office`). Explain that this order is the CV's
   reverse-chronological order everywhere.
4. Draft `education`.
5. Draft `skills_matrix`: group tools into 4 to 8 categories, then ask the user
   to place each tool in `expert` / `comfortable` / `familiar`. Do not guess
   tiers from the CV; confirm them. Named tools and platforms only (concepts
   such as "stakeholder management" belong in achievements).
6. Draft `achievements`: one entry per distinct CV bullet or accomplishment,
   with `id` (`{role prefix}_{topic}`), `role_id`, `description`, `impact`,
   `impact_metric`, `visual_emphasis` (true for the 2 or 3 strongest per role)
   and `signals`. Then ask: "Is there anything you are proud of that is not on
   this CV?" Capture those too; the library should be larger than any single CV.
7. Draft a default `summary.statement` (3 sentences) from the above.
8. Show a compact summary (roles, count of achievements per role, skill
   categories), confirm, then overwrite both files completely. Remove the
   `>>> EXAMPLE PROFILE <<<` header comments.

**Tip:** to see exactly what changed, ask "show me the diff of what you just wrote".

## Phase 2 - What you are looking for

File: `config/job_seeker.yaml`. Read it first and use its comments to explain
each section briefly as you go.

Ask, in batches:

1. **Roles and level:** target job titles (offer suggestions based on their
   CV), seniority floor and ceiling. Explain that these titles also drive the
   company-watchlist title filter, and offer to add broader fragments to
   `discovery.title_keywords` (e.g. a word that appears in most relevant
   titles in their field, or a naming convention a target employer uses).
2. **Location:** home city, remote / hybrid / on-site acceptability, maximum
   required office days per week in their home city, other acceptable cities
   and the maximum days per month there.
3. **Pay:** base salary floor, target and stretch. Whether to keep the UK civil
   service sector override (lower base accepted because of the pension) and at
   what figures. Whether contract roles are of interest, and if so day rates.
4. **Must-haves** (every one should appear in a good posting) and **strong
   preferences** (boost but optional). Offer suggestions drawn from their
   skills matrix and achievements.
5. **Deal-breakers:** sectors, technologies, working patterns or pay they
   will not accept. Offer the example list as a starting point.
6. **Role families:** explain the idea in two sentences (a "core" family they
   are proven in gets a small boost; a "stretch" family they aspire to is
   judged strictly; a "leadership" family is judged on capability rather than
   named tools). Propose title fragments for each from their target roles and
   confirm. They can rename, drop or add families.

Leave `scoring.weights`, `seniority_salary_override`, `discovery` and `style`
at their defaults unless the user asks; mention they exist.

Write the file with `profile.is_example_profile` still **true** (it flips in
Phase 5, once everything is in place). Remove the example header comment.

## Phase 3 - Standard application answers

File: `config/application_answers.yaml`. These are reused across every
application form.

Ask for: notice period (and final day / start date if notice is already
served), right to work, any security clearance actually held (else null),
salary expectation phrasing (derived from Phase 2 figures; confirm single
figure vs range preference), location and hybrid statement, interview
availability, and a positive one-paragraph "why are you looking to move".
Draft each answer, confirm, write.

## Phase 4 - Company watchlist

File: `config/company_watchlist.yaml`.

Explain that this is a list of employers whose careers pages are checked
directly (many roles never reach job boards), that only companies on one of
five public ATS platforms can be listed, and that it ships with two
fictional placeholder entries (Baskerville & Co, Reichenbach Analytics) and
no real companies, so it has to be built for their field. Then:

1. Ask whether there are specific employers they already want to watch
   (plain chat, free text). For each, probe the ATS slugs exactly as
   `/discover-companies` Step 4 does and keep only verified hits; tell them
   which had no supported ATS (those are covered by `/scan-indeed` instead).
2. Offer a `/discover-companies` sweep (interactive mode; it skips its
   profile guard when run from here) to suggest more, themed from the
   criteria written in Phase 2. Suggest aiming for 10 to 30 companies to
   start with: enough to surface postings, few enough to review.
3. Ask how they would like the list grouped (by sector, priority, size, or
   not at all) and write the group comment headers to match.
4. Show the final list, confirm, then write `config/company_watchlist.yaml`:
   remove both fictional entries, their "Example group" header and the
   `>>> EXAMPLE WATCHLIST <<<` paragraph, and keep the schema comments.

If they would rather skip this for now, remove the two fictional entries and
leave `companies: []`: `/scan-companies` and the ATS cache workflow both
handle an empty list cleanly, and they can run `/discover-companies` later.

## Phase 5 - Remove the example

1. Check that no example data remains: grep the repo (excluding `.git`) for
   `Sherlock`, `Holmes`, `baker_street`, `diogenes_club`, `montague_street`,
   `example.com`, `Baskerville`, `Reichenbach`, `FICTIONAL`, `bs_`, `dc_`,
   `ms_` ids in the data files (including `config/company_watchlist.yaml`). Data files must be
   clean. Example snippets inside `.claude/` prompts and `README.md` are
   documentation and stay.
2. Set `profile.is_example_profile: false` in `config/job_seeker.yaml`.
3. Run `python3 -m models.profile --check` and show it passing.

## Phase 6 - Your first tailored CV

1. Make sure the CV renderer is installed: if `cv/.venv` does not exist, run
   `python3 setup.py` (local machine) or `bash scripts/setup-web-container.sh`
   (Claude Code on the web). Explain this installs a headless browser used to
   print the CV to PDF.
2. Ask the user for a real posting they are interested in (paste the text or a URL).
3. Create `postings/{YYYY-MM-DD}_{company_kebab}_{title_kebab}/posting.txt`
   using today's UTC date (see `models/slug.py`), and add the index entry with
   `models.applications_index.upsert`.
4. Run `/build-cv {slug}` and walk through its output together: the
   analysis, the evidence check, the selected achievements, the reviewer
   report, the PDF. When the evidence check asks about criteria the library
   does not cover, explain why it matters: this is how the library grows.
5. Invite one round of edits in plain English ("make the summary shorter").
   This triggers the `cv-edit-capture` skill, which also records the reason so
   the same tweak is made automatically next time. Point that out.

**Tip:** you never need to remember slash commands; "build me a CV for the Home Office
posting" works too.

## Phase 7 - Save your work

Explain in two sentences that the repo is version-controlled: changes are
saved as commits, and nothing is lost. Then:

1. Create a branch, commit Phases 1 to 6 with a clear message, push.
2. Open a pull request and show the user where to review and merge it.
   Explain that every routine in this repo works the same way (it opens a PR),
   so learning to read one now pays off.

## Phase 8 - Optional: the automation

Say, in these words or close to them:

> "By the way, this repo already has all of the scaffolding and code to check
> job boards and your Gmail for you every day. It is entirely optional, but
> would you like to set any of it up too?"

Then offer a multi-select (`AskUserQuestion`, `multiSelect: true`):

- **Daily job discovery** - `/scan-indeed` and `/scan-companies` run on a
  schedule, score new postings and add the good ones to `applications.yaml`
  via a PR. They never build CVs or apply for anything.
- **Daily Gmail tracking** - `/check-email` links application emails to each
  entry, marks rejections and confirmations, and drafts (never sends) replies.
  Needs the Gmail connector authorised in Claude.
- **Phone notifications** - one ntfy.sh push per routine run, no account needed.
- **Google Drive sync** - generated CVs copied into Drive folders automatically.
- **Weekly / quarterly housekeeping** - `/prune-open` closes dead postings
  weekly; `/prune-watchlist --auto` and `/discover-companies --auto` refresh the
  watchlist quarterly.

For each chosen item, walk through the setup one step at a time, waiting for
the user to confirm each step. Read `CLAUDE.md` ("Common workflows",
"GitHub repo configuration", "Notifications (ntfy)") for the details:

- **Scheduled routines:** create them with Claude Code's scheduled routines
  feature, one per command, at the suggested times (scans 07:00 and 08:00 UTC,
  Gmail 09:00 UTC). Mention that scheduled runs use their Claude plan's usage.
- **ATS cache (needed for company scans):** `.github/workflows/fetch-ats-cache.yml`
  fetches the watchlist's job boards daily at 05:00 UTC and commits the
  results to `data/ats-cache/`, because scheduled-agent containers usually
  cannot reach the ATS hosts. It skips itself while the example profile is
  active, so it does nothing until Phase 5 is merged. Make sure Actions are
  enabled on their repo (forks and template copies sometimes start with them
  disabled), then offer to trigger it once by hand (Actions tab, "Fetch ATS
  cache", "Run workflow") so the first `/scan-companies` has data.
- **Auto-merge:** in the GitHub repo settings, enable "Allow auto-merge" so
  routine PRs that only touch `postings/` and `applications.yaml` merge
  themselves (`.github/workflows/auto-merge-routine.yml`).
- **ntfy:** generate a private topic with
  `python3 -c "import secrets; print('cv-o-matic-' + secrets.token_hex(8))"`,
  put `https://ntfy.sh/{topic}` in `.env` as `NTFY_URL` and in the routine's
  environment, then subscribe in the ntfy phone app. Stress that the topic URL
  is a password: never commit it.
- **Drive:** create a Google Cloud OAuth client, put the client id and secret
  in `.env`, run `python main.py sync` once locally to create `token.json`, then
  add the three repo secrets listed in `CLAUDE.md`. Never commit `.env` or
  `token.json`.

If they decline everything, that is fine: tell them they can run `/onboard`
again later and jump straight to this phase.

## Finish

Summarise in a few lines: what is set up, what was skipped, and the four
things they will do most often:

- "What's worth applying to?" (or `/briefing`)
- "Build me a CV for {posting}" (`/build-cv`)
- "Mark {company} as applied"
- "Oh, I've done that!" whenever a posting mentions something they have
  experience with but that is not in their library yet

Spend two sentences on the last one, because it is the habit people do not
have by instinct: the tool can only use what is written in the achievement
library, and postings are the best reminder of forgotten experience. Every
captured achievement makes every future CV, review and application answer
better, and `/build-cv` and `/briefing` will prompt them when they spot a gap.

**Tip:** `CLAUDE.md` is the map of the whole repo; ask Claude to explain any part of it.
