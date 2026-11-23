# /negotiate {slug}

Prepare an offer-stage negotiation brief grounded only in this repository's evidence. This command is chat-only by default: do not create or commit artefacts unless the user explicitly asks.

## Step 0: Profile guard

Run `python3 -m models.profile --check`. If it exits non-zero, stop: tell the user the repo is still on the fictional example profile and to run `/onboard` first.

## Inputs

1. Read `applications.yaml` and `postings/{slug}/application_review.json`.
2. Ask the user for the offer details if they were not supplied in the prompt: base salary, bonus, equity, pension percentage, leave, remote or office terms, and any deadline.
3. Run `python3 -m models.comp` and use its local dataset distribution for the posting's role family.
4. Read `config/job_seeker.yaml` for the floor, target and stretch figures (`compensation.base_salary_min_gbp` / `base_salary_target_gbp` / `base_salary_stretch_gbp`), applying any matching `compensation.sector_floor_overrides` entry. Never use figures from memory or from this file; the config is the only source.

## Brief structure

Keep the brief concise, British English, no em-dashes.

1. **Market position**: state where the base offer sits against the observed p25, median and p75 for the family and overall dataset. If the family has fewer than 10 parseable salary entries, say the sample is thin and avoid overclaiming.
2. **Counter-anchor**: propose a base counter or total-package counter. Ground the one-line justification in the strongest matched criteria from `application_review.json`; never invent external market claims.
3. **Non-base levers**: rank pension, leave, remote days, review timing, sign-on bonus and learning budget by likely give, based on the offer details and job context.
4. **Walk-away line**: derive this from the relevant floor in `config/job_seeker.yaml`, applying the civil-service override when the review clearly signals that sector.
5. **Conversation script**: provide a short first-person script the user can use in the counter conversation.

## Guardrails

- Do not browse the web. The point is to use the repo's own market sample.
- Do not fabricate pay distributions beyond `models/comp.py` output.
- If the offer is below the configured floor, say so plainly and recommend either a corrected counter or walking away.
- If critical offer details are missing, present the brief with explicit assumptions and a short list of follow-up questions.
