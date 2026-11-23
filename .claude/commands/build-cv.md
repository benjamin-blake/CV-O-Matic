---
description: Generate a bespoke CV for the candidate for a given posting (analyse → select achievements → write configs → review → render → review report).
argument-hint: <posting_slug>
---

# /build-cv

Generate a bespoke CV for the posting at `postings/$1/`. Use **British English** throughout. No em-dashes.

**Posting slug:** `$1` (format: `YYYY-MM-DD_{company}_{title_kebab}`, e.g. `2026-01-15_acme_senior_data_analyst`)

If `$1` is empty, ask the user for the posting slug (a directory under `postings/`). If the user gives an undated slug, prepend today's UTC date and rename the directory before proceeding.

---

## Quick reference

- Character limits: summary 400-600 | each highlight 180-250 | each criteria response 80-150 | total work history ≤ 2,100
- Date format: `DD Month YYYY`
- Chronological order: the roles in `cv/cv_core_data.yaml -> roles`, which are listed newest first. That order IS the reverse-chronological order; never re-sort it.

---

## Step 0: Profile guard and pull from remote main (MANDATORY)

**Profile guard.** Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first. Do not build anything. (`python3 -m models.profile` with no flag prints the candidate's name, the CV file names `{name_slug}_cv.html` / `{name_slug}_cv.pdf`, and the guard state; use those names wherever this file says `{name_slug}_cv.*`.)

**Pull.**

Scan routines (`/scan-indeed`, `/scan-companies`) discover new postings on `claude/scan-*` branches that auto-merge to `main`. If the local clone is behind, the posting directory may not exist yet and `/build-cv` will fail to find it.

Before doing anything else:

```bash
git pull --ff-only origin main
```

If the pull fails (non-fast-forward, dirty working tree, detached HEAD, etc.), stop and surface the error to the user. Do not attempt to merge, rebase, or stash automatically. After a successful pull, verify `postings/$1/` exists before proceeding to Step 1; if it does not, list `postings/` matches by company keyword and ask the user to confirm the correct slug.

---

## Step 1: Analyse posting

Read `postings/$1/posting.txt` and extract:
- Job title, company, location, salary band (if stated), application deadline (if stated)
- Essential criteria (exact quotes)
- Nice-to-have / preferred criteria
- Technical skills, domain context, application requirements
- If line 1 looks like a URL: fetch it for additional context (WebFetch)

---

## Step 2: Select 9-11 achievements

Read `cv/cv_achievements.yaml` in full. Select achievement IDs that match the posting.

**Hard rules:**
- Include at least 1 achievement from each role in `cv/cv_core_data.yaml -> roles`.
- List in **reverse chronological order** (the newest role's IDs first in `config.yaml`, following the order of `roles`).
- Prioritise: semantic match + quantified impact + essential-criteria coverage.

**Also scan `role_id: n/a` entries** (personal / non-role achievements) against the nice-to-have criteria. If one directly matches a nice-to-have (e.g. a volunteering or community background for a charity posting), surface it explicitly: add a criteria response in Step 3, reference it in the summary, include it in the personal statement. Do not rely on the cv-reviewer to catch posting-specific differentiators - it's a backstop, not the primary identifier.

---

## Step 3: Generate config files

**Files split across two directories:**
- `postings/$1/config.yaml` - posting-root config (the generator reads this first)
- `postings/$1/config/*.yaml` - section configs (`summary.yaml`, `experience.yaml`, `skills.yaml`, `projects.yaml`, `criteria_responses.yaml`)

### 3a. `postings/$1/config.yaml`

```yaml
# Custom config for $1
# Generated: {DD Month YYYY}

job_title: "{exact title from posting}"
company: "{company name}"
color_scheme: "{tech_blue | fintech_green | creative_purple | corporate_navy | rust}"
selected_achievement_ids:
  # Example ids shown (from the example profile); use the ids in cv/cv_achievements.yaml.
  - bs_kpi_framework  # newest role first
  - bs_data_quality
  - dc_member_insights
  - dc_migration
  - ms_lab_pipeline
```

**Valid `color_scheme` keys** (from `cv/cv_config.yaml`): `tech_blue`, `fintech_green`, `creative_purple`, `corporate_navy`, `rust`. Any other value silently falls back to the default. Picking guide:
- `corporate_navy` - gov / public sector / civil service / regulated
- `fintech_green` - fintech, banking, energy and utilities
- `tech_blue` - generic enterprise tech, SaaS
- `creative_purple` - media, entertainment, gaming, consumer
- `rust` - AI / research labs, or anything wanting a warmer earthy palette

### 3b. `postings/$1/config/summary.yaml`

**Required nested format** - the generator reads `summary.statement`. A flat string silently falls back to the default summary in `cv/cv_core_data.yaml`.

```yaml
summary:
  statement: "{400-600 chars, bespoke for THIS company, mentions the org by name, mirrors posting language, makes a value proposition specific to this role}"
```

### 3c. `postings/$1/config/experience.yaml`

**Exact structure - plain string list, not dict keys:**

```yaml
experience:
  - role_id: baker_street  # newest first (example id; use the ids in cv_core_data.yaml roles)
    highlights:
      - "First highlight (180-250 chars, with impact metric)"
      - "Second highlight (180-250 chars, with impact metric)"

  - role_id: diogenes_club
    highlights:
      - "..."
      - "..."

  - role_id: montague_street  # oldest last
    highlights:
      - "..."
```

**Source fidelity:** Cross-check each highlight against the `description` and `impact` fields of the source achievement in `cv/cv_achievements.yaml`. Do **not** upgrade qualifier language ("minimal oversight" → "independently", "supported" → "led"). Do **not** inflate metrics beyond the source.

**Length check:** Target 180-250 chars per highlight (stripping `<strong>` tags). Don't count manually - the script in Step 4.5 will verify all lengths deterministically before cv-reviewer is invoked.

**Differentiator bolding (1-2 highlights max across the whole CV):**
Wrap the **full text** of 1-2 standout highlights in `<strong>` tags. Select on rarity + posting-fit, not just quality. Never bold more than 2.

### 3d. `postings/$1/config/skills.yaml`

**Comma-separated strings, NOT arrays.** Max 4-5 categories. Max ~100 chars per cell. Max 30 chars per category name.

**Two concerns, kept strictly separate:**

- **Tier (expert / comfortable / familiar)** reflects the candidate's actual proficiency, grounded in `cv/cv_core_data.yaml`. Never downgrade a skill from expert to comfortable just because the posting doesn't emphasise it - that misrepresents real competency downward. Upgrade only when a selected achievement provides direct evidence.

- **`<strong>` bold** marks tools that appear verbatim in the posting - i.e. tools the employer is specifically looking for. Bold can appear in any tier. It is a reader-navigation aid, not a proficiency claim, and should not influence tier placement.

**Entries should be actual tools and platforms, not concepts.** "GDPR compliance", "data quality frameworks", "dimensional modelling" are competencies the candidate holds regardless; they belong in highlights and criteria responses. The skills matrix is for named software a recruiter or engineer would search for.

```yaml
skills_matrix:
  - category: "Data Platforms"
    expert: "<strong>Snowflake</strong>, <strong>dbt Core</strong>, Power BI"
    comfortable: "BigQuery, PostgreSQL"
    familiar: "<strong>Databricks</strong>"
```

### 3e. `postings/$1/config/projects.yaml`

4-6 project titles with tech in parentheses. Real projects only - must be verifiable from achievement library.

### 3f. `postings/$1/config/criteria_responses.yaml`

```yaml
criteria_responses:
  - criterion: "{essential criterion, paraphrased or quoted}"
    response: "{80-150 chars, concrete, specific achievement, no filler}"
```

**Consolidate overlaps.** If three criteria mention the same tool family (for example a cloud platform and its deployment tooling), merge into one response or use brevity. Trim filler ("Successfully established comprehensive" → "Established"). Combine metrics ("80% faster, 75% fewer incidents") rather than separate sentences.

---

## Step 4: Write personal statement

`postings/$1/personal_statement.txt`. 200-280 words unless the posting specifies a word limit (then match exactly).

Structure:
1. **Who I am** (30-40w): Background + identity.
2. **Why interested** (60-80w): Reference specific posting / company details. Mirror posting language. Demonstrate research.
3. **Relevant skills** (80-120w): 3-4 achievements with metrics.
4. **Close** (30-40w): Enthusiasm + value proposition.

Avoid em-dashes. Use commas, colons, or parentheses for compound sentences.

---

## Step 4.5: Run the length-check script (MANDATORY)

Before invoking cv-reviewer, run the deterministic length checker:

```bash
cv/.venv/Scripts/python.exe cv/check_lengths.py postings/$1
# Unix: cv/.venv/bin/python cv/check_lengths.py postings/$1
```

The script strips HTML tags before counting (so `<strong>` markup doesn't inflate counts) and verifies:
- `summary.statement` is 400-600 chars
- Each `experience.*.highlight[*]` is 180-250 chars
- Total work history ≤ 2100 chars
- Each `criteria_responses[*].response` is 80-150 chars
- Each `skills_matrix[*]` cell ≤ 100 chars, category name ≤ 30 chars
- `personal_statement.txt` is 200-280 words

Exit code 0 = all pass. Exit code 1 = at least one fail.

**If any check fails:** fix the offending field in the YAML, re-run the script. Repeat until exit code 0. **Do not invoke cv-reviewer with failing lengths** - cv-reviewer's job is semantic review (British English, exaggeration, tone), not character counting. Wasted compute.

This step replaces the "count characters yourself" instructions in Step 3. The script is the source of truth for length contracts.

## Step 5: Invoke cv-reviewer subagent

Use the `Agent` tool with `subagent_type: cv-reviewer` and a prompt like:

> Review the CV for posting `$1`. Read all config files, the achievement library, and the posting. Produce a structured review per the cv-reviewer spec. Length checks have already been verified by `cv/check_lengths.py` - focus on semantic dimensions.

Wait for the report.

- **BLOCK** verdict: fix all Critical issues in the relevant config files, then re-invoke `cv-reviewer`. Do not proceed.
- **APPROVE WITH CHANGES**: fix Critical issues; take judgement on Warnings (prefer to implement); flag deferred Warnings to the user; proceed to Step 6.
- **APPROVE**: proceed to Step 6.

---

## Step 6: Render HTML and PDF

```bash
cd cv
.venv/Scripts/python.exe generate_cv.py --posting ../postings/$1
```

(On Unix: `cv/.venv/bin/python cv/generate_cv.py --posting ../postings/$1`.)

The script always generates `{name_slug}_cv.html` first, then renders `{name_slug}_cv.pdf` via Playwright Chromium. PDF generation works in Claude Code on the web too, not just locally: `scripts/setup-web-container.sh` (wired up as the environment's container Setup script) installs the `playwright` pip package system-wide and verifies it can render against the container's pre-installed Chromium at `/opt/pw-browsers`, so both HTML and PDF should be produced in the same run regardless of surface.

**If `cv/.venv` does not exist** (e.g. `setup-web-container.sh` was not configured as the Setup script for this environment), fall back to system Python: `python3 generate_cv.py --posting ../postings/$1` from `cv/`. If PDF generation then fails with an "Executable doesn't exist" error, that's the same Playwright-pip-vs-pre-installed-Chromium version mismatch the setup script works around - rerun with the browser pinned explicitly rather than giving up:

```bash
python3 -c "
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path('..').resolve()))
from models.profile import cv_filenames
names = cv_filenames()
html = Path('../postings/$1').resolve() / names['html']
pdf = Path('../postings/$1').resolve() / names['pdf']
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    page = browser.new_page()
    page.goto(html.as_uri(), wait_until='networkidle')
    page.pdf(path=str(pdf), format='A4', print_background=True)
    browser.close()
"
```

Only if PDF generation still fails after that fallback (e.g. `/opt/pw-browsers` genuinely absent on this surface): log the failure, leave `artefacts.cv_pdf` as `null` (Step 7.5 will pick this up from disk state), and continue to Step 7. Do not retry further or escalate - HTML remains the canonical output for the phone-side experience (semantic markup, easier for Claude to parse than OCR'd PDF) even when PDF isn't available.

**Validate the HTML before declaring success:**

1. Roles appear in the same order as `cv/cv_core_data.yaml -> roles` (newest first).
2. No `{'key': 'value'}` strings (dict literals leaking through).
3. No `['Python', 'AWS']` strings (array literals leaking through).
4. Custom summary text appears (if it shows the default summary from `cv/cv_core_data.yaml -> summary.statement`, the `summary.yaml` is in the wrong format - see Step 3b).
5. Page 2 fits the essential criteria + skills table within bounds.

Lengths are pre-verified by Step 4.5, so don't re-check them here. If a length check fails post-render, that's a generator bug, not a content bug.

---

## Step 6.5: Visual layout review (MANDATORY when rendering is available)

Character-count checks (Step 4.5) cannot see the rendered page, and some defects are purely visual: the left-hand column (Profile + Selected Projects + Education) overflowing so **Education is cut off**, content spilling onto an unwanted extra page, a lopsided block of whitespace, or page 2 not fitting the criteria + skills table. These ship silently unless someone looks at the page. So look at the page.

Render each page to a PNG and **Read every image**:

```bash
python cv/render_preview.py postings/$1
# prints one PNG path per page (to a temp dir); on Unix use cv/.venv/bin/python if the venv exists
```

`render_preview.py` reuses the pre-installed Chromium (same fallback as Step 6). If it exits 3 (Playwright/Chromium unavailable on this surface), skip this step exactly as you would a failed PDF render - it is non-fatal - and note in the completion summary that visual review was skipped.

Read each printed PNG and check:

1. **Nothing cut off** - the left column shows the full Education block (degree, institution, dates, all bullet points). If Education is truncated, the sidebar is over budget: shorten the Profile summary or trim Selected Projects (drop parenthetical tool lists - see Step 3e / pitfall 9), then re-render (Step 6) and re-review.
2. **No unwanted overflow** - the CV is 2 pages. A near-empty 3rd page (or content bleeding past page 2) means something is too long; trim and re-render.
3. **Page 2 fits** - Skills Matrix + Essential Criteria sit within the page, not clipped at the bottom edge.
4. **Reverse-chronological order** is visually correct (newest role first).
5. **No gross whitespace imbalance** - a large empty gap at the bottom of the Experience section usually means a role is short a highlight; consider adding one (grounded in the achievement library) or rebalancing.

Fix any layout defect at the **content** level (trim/pad the relevant config), never by editing the generator, template, or stylesheet (What NOT to touch). Re-render and re-read until the page is clean. This visual tier complements the deterministic text checks (Step 4.5) and the semantic text review (Step 5) - together they cover length, meaning, and layout.

---

## Step 7: Write structured application review

Use the `/review-application $1` slash command. It produces `postings/$1/application_review.json` conforming to `config/application_review.schema.json`, containing `posting_url`, `title`, `company`, `match_score`, `verdict`, criteria analysis, gaps, recommendations, and `artefacts` with paths to the generated CV.

### Step 7.5: Backfill artefact paths (MANDATORY)

After `/review-application` returns, **re-open `postings/$1/application_review.json`** and set the `artefacts.*` paths based on what actually exists on disk at this moment. Do not leave paths as `null` if the files are present.

| Field | Path if file exists | Else |
|---|---|---|
| `artefacts.posting` | `postings/$1/posting.txt` | (always exists) |
| `artefacts.personal_statement` | `postings/$1/personal_statement.txt` | `null` |
| `artefacts.cv_html` | `postings/$1/{name_slug}_cv.html` | `null` |
| `artefacts.cv_pdf` | `postings/$1/{name_slug}_cv.pdf` | `null` |

Write the JSON back.

---

## Step 7.6: Generate the application pack

Generate the ready-to-paste application answers by following `.claude/commands/application-pack.md` for this slug (`$1`). That command file is the single source of the pack logic; do not duplicate its steps here. Run its Steps 1 through 5 inline (extract the posting's questions, resolve the standard answers from `config/application_answers.yaml`, draft the posting-specific answers grounded in the selected achievements, write `postings/$1/application_pack.md`, and run the British-English and dash check). Skip its Steps 0 and 6 (pull and separate PR): the pack rides along in this build's own branch and commit rather than opening its own PR.

---

## Step 8: Update applications.yaml

Mark the CV as built in the root state spine:

```bash
python -c "
from models.applications_index import load, mark_cv_built, save
data = load()
mark_cv_built(data, '$1')
save(data)
"
```

This sets `cv_built_at` to today's date. Status stays at whatever it was (typically `open`); the candidate flips it to `applied` once the application is submitted (or `/check-email` does when a confirmation arrives).

---

## Step 9: Sync to Google Drive

```bash
python main.py sync
```

Uploads `posting.txt`, `personal_statement.txt`, `{name_slug}_cv.html`, `{name_slug}_cv.pdf` for the posting to `Drive/job-seeker/postings/$1/`, plus the root `applications.yaml` so the index reflects the new `cv_built_at` timestamp.

---

## Step 10: Completion summary

Report to the caller:
- Posting slug, job title, company, match score, verdict
- Achievement IDs selected, distribution by role
- Drive CV link
- Any deferred warnings from cv-reviewer
- Suggested next step (e.g. "review personal statement before applying, then flip status to applied in applications.yaml")

---

## Common pitfalls

1. Forgetting chronological order - the newest role (first in `cv_core_data.yaml -> roles`) must be first in `experience.yaml`.
2. Python dict/list literals in YAML - should be plain strings/arrays.
3. Skipping HTML validation before PDF.
4. Verbose criteria responses - 80-150 chars means very brief.
5. Not consolidating overlapping criteria.
6. American spellings or em-dashes slipping through - cv-reviewer should catch but check yourself first.
7. Downgrading expert skills in the skills matrix - tier reflects real proficiency, not posting centrality. If a tool is expert in `cv/cv_core_data.yaml`, keep it at expert. Use bold to signal posting relevance instead.
8. Skipping Step 0 - if the local clone is behind, newly-discovered postings from scan routines won't exist locally and `/build-cv` will report a missing directory.
9. Overloading the Selected Projects parentheses - projects live in the left-hand column alongside Profile and Education; long parenthetical tool lists inflate the sidebar and can push Education off the bottom of the page. In `config/projects.yaml`, keep a tool inside a project's parentheses only if that tool is named in the posting; otherwise drop the parenthetical (`KPI Governance Framework (Power BI, Snowflake, dbt Core)` → `KPI Governance Framework`). The Step 4.5 checker WARNs on ungrounded parentheticals and on an over-budget sidebar. (Captured in `docs/cv-tweak-ledger.yaml`.)
10. Skipping the visual review (Step 6.5) - character checks cannot see a truncated Education block or an unwanted 3rd page. If rendering is available, Read the page images before declaring success.
11. Pitching the technical register wrong for the reader. A highlight written in the vocabulary of the platform the work was done on reads as impenetrable to a reviewer on a different stack (highlights full of one vendor's service names in front of a shop that uses another), but stripping the product names out entirely leaves a vague claim a technical reviewer cannot place, and loses the ATS keyword. Aim for the middle: open each highlight with a plain-English subject, close on a plain-English outcome, and name the technology in a **supporting position** (a prepositional or parenthetical phrase) rather than as the subject of the sentence. Keep recognisable product names (Snowflake, BigQuery, Power BI, Tableau, dbt, Airflow); drop genuinely obscure implementation terms (internal macro systems, niche partitioning tricks). Worked example: "Built a dbt test suite with Snowflake alert routing" is too technical; "Built the automated checks that catch bad data" is too vague; "Built automated data quality checks on Snowflake that alert the owning team before stakeholders notice a problem" is the line to hit. This is a judgement call, not a deterministic check, so nothing in `check_lengths.py` enforces it. Apply the same register to `criteria_responses.yaml` and the application pack, which the same people read; posting-root `projects.yaml` is the exception, where pitfall 9 still says drop a parenthetical naming a tool the posting does not mention. (Captured in `docs/cv-tweak-ledger.yaml`.)

## Contract CV variant (`--contract`)

When invoked as `/build-cv {slug} --contract`, keep the normal rendering engine and checks unchanged, but alter the generated config content:

1. `summary.yaml` leads with a contractor frame: availability, delivery focus, and the specific stack requested.
2. `personal_statement.txt` is a short cover note, no more than half the normal length cap, focused on what the candidate will deliver in the first weeks rather than career trajectory.
3. Achievement selection weights delivery and outcome achievements above leadership-growth evidence unless the posting is explicitly a lead contract.
4. Never state a day rate in the CV, personal statement, HTML, or PDF. Rates belong in conversations and application packs only.
5. Run the same length checks, visual review, PDF generation, and cv-reviewer process as the permanent build.

## Leadership evidence for lead-family roles

When the posting title matches the `title_fragments` of a leadership-style role family in `config/job_seeker.yaml :: scoring.role_family_modifiers` (in the example profile, the `leadership` family: head of, lead, principal, director), select at least 3 achievements carrying `leadership` or `influence` signals from `cv/cv_achievements.yaml`. The summary and personal statement must open with the leadership arc before tools. A lead-role CV that reads like a senior individual-contributor CV is a documented failure mode.
