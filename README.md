# CV-O-Matic

An agent-first job search, driven by [Claude Code](https://claude.com/claude-code). Describe what you want in plain English; Claude finds postings, scores them against your criteria, builds a tailored CV and application answers on request, and keeps track of every application.

**Who it is for:** anyone looking for a job. It started life as a UK data and analytics job search, so the examples, the example profile and the starter company watchlist all lean that way, but nothing in the engine is specific to data: your CV, your criteria and your watchlist decide what it looks for and how it scores. `/onboard` sets all three up for your field.

## What it is, and what it is not

**It does:**

- **Discover** new postings from Indeed and directly from company careers pages (via ATS APIs).
- **Score** each posting against your own criteria (`config/job_seeker.yaml`) and explain the gaps.
- **Build** a tailored, reviewed, one-click-to-PDF CV and ready-to-paste application-form answers for the postings you pick.
- **Track** every application in one YAML file, and (optionally) read your Gmail to link emails to applications and spot rejections, interview invitations and offers.
- **Prepare** you for interviews and offers (prep packs, drill mode, a negotiation brief grounded in your own pipeline's salary data).

**It does not:** apply for jobs, send email, or invent anything about you. Every claim in a generated CV comes from an achievement library that you confirm during onboarding, and a reviewer subagent checks each CV against it.

## Quick start

Prerequisites: a Claude plan that includes Claude Code, and a GitHub account. Python 3.10+ is only needed if you render CVs on your own machine (Claude Code on the web sets itself up).

1. **Use this template.** Click "Use this template" on GitHub and create a **private** repository. Your copy will hold your CV, salary expectations and application history, so it must not be public.
2. **Open it in Claude Code** (web, desktop app or CLI).
3. **Type `/onboard`.**

That is it. `/onboard` replaces the fictional example profile (Sherlock Holmes) with your own CV and criteria, builds your first tailored CV from a real posting, saves your work as a pull request, and then offers the optional automation. It takes 20 to 40 minutes, explains each step as it goes, and can be paused and resumed. Until it has run, every command that acts on real data stops and points you back to `/onboard`.

## What you get after onboarding

You can use slash commands, but you do not have to remember them. Just ask:

- "What's worth applying to?" (a pipeline briefing: top picks, ageing matches, interviews, evidence gaps, funnel)
- "Build me a CV for the Home Office posting"
- "Draft my application answers for the Home Office"
- "Shorten the summary on the Home Office CV" (the edit is applied, re-rendered, and the reason is remembered so the same tweak happens automatically next time)
- "Mark the Home Office as applied"
- "I got an offer from the Home Office, £62k base" (triggers a negotiation brief)
- "Oh, I've done that!" when a posting mentions experience that is not in your library yet (see below)

### It gets better the more it knows

Every CV, review and application answer is built only from your **achievement library** (`cv/cv_achievements.yaml`): nothing is ever invented to fill a gap. So the quality of everything it produces rises with the detail you give it.

Most of us under-describe our own experience, and the best reminder of forgotten work is a job posting that asks for it: "oh, I've done that, I should write it down!" CV-O-Matic is built to catch that moment for you:

- **Before each CV is built**, it lists anything the posting asks for that your library does not cover, and asks whether you have done it.
- **In your briefing**, it highlights gaps that keep coming up across several good postings, where one new entry pays off the most.
- **Any time in conversation**, saying something like "I actually led a migration like that" captures it properly: what you did, what changed, and a number if there is one. You confirm it before it is saved.

The habit worth building: whenever a posting jogs your memory, say so. It takes a minute, and every future application benefits.

### Optional automation

Everything above works on demand. If you want the repo to work while you sleep, `/onboard` Phase 8 (or a later re-run) can set up any of:

- **Daily job discovery:** `/scan-indeed` and `/scan-companies` as scheduled Claude Code routines that open a PR with new matches.
- **Daily Gmail tracking:** `/check-email` links application emails, marks rejections and confirmations, and drafts (never sends) replies. Needs the Gmail connector.
- **Phone notifications** via [ntfy.sh](https://ntfy.sh) (no account needed).
- **Google Drive sync** of generated CVs.
- **Housekeeping:** weekly `/prune-open`, quarterly `/prune-watchlist --auto` and `/discover-companies --auto`.

Scheduled runs use your Claude plan's usage. Skip any or all of it; nothing else depends on it.

## How it works

```
.claude/commands/    Slash commands: the agent surface (discover, build, track, prepare)
.claude/agents/      Subagents: job-matcher (scores a posting), cv-reviewer (checks a CV)
.claude/skills/      Auto-triggered skills: plain-English front doors to the commands
config/              Your criteria, company watchlist and standard application answers
cv/                  Your CV data and achievement library, plus the HTML -> PDF renderer
models/              Small Python helpers: profile guard, applications index, scoring, salary stats
postings/{slug}/     One folder per posting: text, review, CV, application pack, interview notes
applications.yaml    The source of truth for status (open, applied, declined, closed, rejected)
```

Claude does the thinking; Python only does what Claude should not do at runtime: render the PDF with Playwright, sync to Google Drive, and maintain the applications index. `CLAUDE.md` is the detailed map of the repo and is loaded into every Claude Code session. Ask Claude to explain any part of it.

## Commands

| Command | What it does |
| --- | --- |
| `/onboard` | First-run setup: your CV, criteria, answers, first CV, optional automation |
| `/briefing` | Read-only pipeline snapshot: top picks, ageing, in flight, interviews, evidence gaps, funnel |
| `/scan-indeed` | Search Indeed, score, add matches to `applications.yaml` via PR |
| `/scan-companies` | Scan the company watchlist via ATS APIs, score, add matches |
| `/build-cv {slug}` | Tailored CV, personal statement and application pack for a posting |
| `/application-pack {slug}` | Ready-to-paste answers for UK application forms |
| `/review-application {slug}` | Re-judge a posting's analytical review |
| `/rescore-application` | Re-apply changed scoring rules to scored postings, deterministically |
| `/capture-cv-tweaks {slug}` | Learn from your manual CV edits so they are made automatically |
| `/check-email` | Link Gmail activity to applications, flag rejections and offers |
| `/log-interview {slug}` | Record an interview round and set the stage |
| `/prep-interview {slug}` | Role-specific prep pack and drill mode |
| `/negotiate {slug}` | Offer-stage negotiation brief |
| `/prune-open` | Close postings that are demonstrably dead |
| `/prune-watchlist` | Find stale companies in the watchlist |
| `/discover-companies` | Find new companies to watch |

## Customising

- **What you are looking for:** `config/job_seeker.yaml` holds target roles, seniority, location and office-day rules, pay floors and targets, must-haves, deal-breakers, role families and scoring weights. Edit it directly or ask Claude to ("raise my salary floor to 75k", "add fintech to the deal-breakers"), then `/rescore-application` to re-apply the rules to existing postings.
- **Where to look:** `config/company_watchlist.yaml` lists employers checked directly. It ships tuned for UK data and analytics roles; if you work in another field, `/onboard` and `/discover-companies` will help you replace it with employers in yours. Prune it by hand or with `/prune-watchlist`.
- **How the CV looks:** `cv/cv_config.yaml` has the colour schemes and template settings. Ask for a different scheme in plain English, or set `default_color_scheme`.
- **What the CV says:** `cv/cv_core_data.yaml` (roles, education, skills) and `cv/cv_achievements.yaml` (the achievement library). These are your source of truth; edit them via `/onboard` or by asking Claude, and keep every metric honest.

## Privacy and safety

- Keep your copy **private**. `applications.yaml`, postings and Gmail links are personal.
- Never commit `.env`, `token.json` or your ntfy topic URL (treat the topic URL like a password).
- The `@claude` GitHub assistant only responds to repository owners, members and collaborators, and auto-merge only applies to same-repo `claude/*` branches that touch posting data.

## Licence

MIT. See `LICENSE`.
