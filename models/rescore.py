"""Deterministic re-scoring engine for existing application reviews.

Re-applies the CURRENT scoring rules in ``config/job_seeker.yaml`` to the
sub-scores already stored in each ``postings/{slug}/application_review.json``,
without re-invoking the LLM job-matcher. This is the right tool for a
*rules/weights* change (new role-family modifier, salary-aware seniority,
affinity tilt): it is fast, reproducible, and auditable. For a *posting-text*
or *achievement-library* change, use ``/review-application`` instead, which
re-judges the posting cold.

What it re-derives from stored data (see .claude/agents/job-matcher.md for the
canonical rules this mirrors):

* **Capability-based must-haves for lifted families.** Any family with
  ``lift_must_haves_to_full: true`` in config (your proven core trajectory)
  that was capped under the old literal rule is lifted: a genuine match is
  treated as covering every must-have (1.0).
* **Salary-aware seniority_fit.** When the posting states a salary, seniority
  defers to it (a well-paid role is substantive regardless of a bare title).
* **Role-family affinity tilt.** Each family's ``score_modifier`` from config
  (e.g. ``+0.05`` / ``-0.10``) is added to the final score.
* **Verdict cap.** Families with ``cap_verdict_below`` in config are held
  below that verdict (e.g. STRONG).

Role families are config-driven: whatever ``scoring.role_family_modifiers``
defines, resolved in ``scoring.family_precedence`` order (fallback: the order
the families appear in the config).

Deal-breaker reviews (non-empty ``deal_breakers_triggered``) are left untouched.

Run from the repo root:

    python -m models.rescore                      # dry-run, all reviews, md table
    python -m models.rescore --slug 2026-01-15_acme_senior_data_analyst
    python -m models.rescore --status open --family core
    python -m models.rescore --all --write        # persist to json + applications.yaml
    python -m models.rescore --format json        # machine-readable deltas
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from models.applications_index import load as load_index, find as find_entry, save as save_index
except ModuleNotFoundError:  # run as a bare script rather than -m
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from models.applications_index import load as load_index, find as find_entry, save as save_index

REPO = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO / "config" / "job_seeker.yaml"
POSTINGS = REPO / "postings"

# Verdict bands, high to low. (lower_inclusive, verdict).
VERDICT_BANDS = [
    (0.80, "STRONG"),
    (0.65, "MODERATE-STRONG"),
    (0.50, "MODERATE"),
    (0.30, "WEAK"),
    (0.00, "REJECT"),
]
VERDICT_ORDER = ["REJECT", "WEAK", "MODERATE", "MODERATE-STRONG", "STRONG"]


def verdict_for(score: float) -> str:
    if score < 0.30:
        return "REJECT"
    for lower, name in VERDICT_BANDS:
        if score >= lower:
            return name
    return "REJECT"


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass
class Family:
    key: str
    fragments: list[str]
    must_have_evaluation: str
    score_modifier: float
    cap_verdict_below: str | None
    lift_must_haves_to_full: bool = False


@dataclass
class ScoringConfig:
    weights: dict[str, float]
    seniority_override: dict[str, float]
    families: list[Family]  # in precedence order, highest first
    base_floor: float
    base_target: float
    sector_overrides: dict[str, dict[str, float]]


def family_precedence(raw: dict) -> list[str]:
    """Family keys in precedence order (highest first), from config.

    Uses ``scoring.family_precedence``; any families it omits follow in
    ``role_family_modifiers`` order. Falls back to that dict order entirely.
    """
    scoring = raw.get("scoring", {}) or {}
    modifiers = scoring.get("role_family_modifiers", {}) or {}
    order = [k for k in (scoring.get("family_precedence") or []) if k in modifiers]
    order += [k for k in modifiers if k not in order]
    return order


def load_config(path: Path = CONFIG_PATH) -> ScoringConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    scoring = raw["scoring"]
    comp = raw["compensation"]
    modifiers = scoring.get("role_family_modifiers", {})

    families: list[Family] = []
    for key in family_precedence(raw):
        block = modifiers.get(key)
        if not block:
            continue
        families.append(
            Family(
                key=key,
                fragments=[f.lower() for f in block.get("title_fragments", [])],
                must_have_evaluation=block.get("must_have_evaluation", "literal"),
                score_modifier=float(block.get("score_modifier", 0.0)),
                cap_verdict_below=block.get("cap_verdict_below"),
                lift_must_haves_to_full=bool(block.get("lift_must_haves_to_full", False)),
            )
        )

    sector = {}
    for name, ov in (comp.get("sector_floor_overrides") or {}).items():
        sector[name] = {
            "floor": float(ov["base_salary_min_gbp"]),
            "target": float(ov["base_salary_target_gbp"]),
        }

    return ScoringConfig(
        weights={k: float(v) for k, v in scoring["weights"].items()},
        seniority_override={
            "at_or_above_target": float(scoring["seniority_salary_override"]["at_or_above_target"]),
            "between_floor_and_target": float(
                scoring["seniority_salary_override"]["between_floor_and_target"]
            ),
        },
        families=families,
        base_floor=float(comp["base_salary_min_gbp"]),
        base_target=float(comp["base_salary_target_gbp"]),
        sector_overrides=sector,
    )


def detect_family(title: str, cfg: ScoringConfig) -> Family | None:
    tl = (title or "").lower()
    for fam in cfg.families:  # already in precedence order
        if any(frag in tl for frag in fam.fragments):
            return fam
    return None


# --------------------------------------------------------------------------- #
# Salary parsing
# --------------------------------------------------------------------------- #

_USD_RE = re.compile(r"\$|\bUSD\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"£?\s*([\d][\d,]*(?:\.\d+)?)\s*(k)?", re.IGNORECASE)
USD_TO_GBP = 0.78
MIN_SALARY = 20_000  # ignore allowances / percentages / stray small figures


def parse_salary(text: str | None) -> float | None:
    """Return a representative annual GBP figure, or None if unparseable.

    Range -> midpoint of the first two figures (base band is stated first).
    Single figure -> that figure. USD strings are converted at ~0.78.
    Figures below MIN_SALARY (allowances, pension %, '£0') are dropped.
    """
    if not text:
        return None
    is_usd = bool(_USD_RE.search(text)) and "£" not in text
    figures: list[float] = []
    for m in _MONEY_RE.finditer(text):
        num = float(m.group(1).replace(",", ""))
        if m.group(2):  # 'k' suffix
            num *= 1000
        if num >= MIN_SALARY:
            figures.append(num)
    if not figures:
        return None
    band = figures[:2]
    rep = sum(band) / len(band)
    if is_usd:
        rep *= USD_TO_GBP
    return round(rep)


def sector_bands(sector_applied: str | None, cfg: ScoringConfig) -> tuple[float, float]:
    if sector_applied and sector_applied in cfg.sector_overrides:
        ov = cfg.sector_overrides[sector_applied]
        return ov["floor"], ov["target"]
    return cfg.base_floor, cfg.base_target


# --------------------------------------------------------------------------- #
# Recompute
# --------------------------------------------------------------------------- #


@dataclass
class Change:
    field: str
    old: Any
    new: Any
    rule: str


@dataclass
class Result:
    slug: str
    title: str
    status: str
    family: str | None
    salary_parsed: float | None
    prior_score: float
    new_score: float
    prior_verdict: str
    new_verdict: str
    dimension_scores: dict[str, float]
    changes: list[Change] = field(default_factory=list)
    skipped: str | None = None  # reason, if untouched
    baseline_drift: float = 0.0  # formula(old dims) - stored prior score

    @property
    def moved(self) -> bool:
        return not self.skipped and (
            abs(self.new_score - self.prior_score) >= 0.005
            or self.new_verdict != self.prior_verdict
        )


def _weighted(dims: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[k] * float(dims.get(k, 0.0)) for k in weights)


def recompute(review: dict, entry: dict, cfg: ScoringConfig) -> Result:
    slug = review.get("posting_slug") or entry.get("slug", "?")
    title = entry.get("title") or review.get("title") or ""
    status = entry.get("status", "unknown")
    prior_score = float(review.get("match_score") or 0.0)
    prior_verdict = review.get("verdict") or verdict_for(prior_score)
    dims = dict(review.get("dimension_scores") or {})

    res = Result(
        slug=slug,
        title=title,
        status=status,
        family=None,
        salary_parsed=None,
        prior_score=prior_score,
        new_score=prior_score,
        prior_verdict=prior_verdict,
        new_verdict=prior_verdict,
        dimension_scores=dict(dims),
    )

    if not dims:
        res.skipped = "no dimension_scores"
        return res
    # Deal-breakers are non-negotiable; never resurrect a triggered review.
    if review.get("deal_breakers_triggered"):
        res.skipped = "deal-breaker"
        return res
    # A REJECT is a REJECT. Rescore refines viable postings under new rules; it
    # must not lift a rejection to WEAK via arithmetic on stale sub-scores.
    if prior_verdict == "REJECT" or prior_score < 0.30:
        res.skipped = "prior REJECT"
        return res

    fam = detect_family(title, cfg)
    res.family = fam.key if fam else None

    baseline = _weighted(dims, cfg.weights)
    res.baseline_drift = round(baseline - prior_score, 3)

    new_dims = dict(dims)

    # 1. Capability-based must-haves for families flagged
    #    lift_must_haves_to_full: a genuine match covers every must-have.
    if fam and fam.lift_must_haves_to_full:
        cur = float(new_dims.get("must_have_coverage", 0.0))
        if cur < 1.0:
            new_dims["must_have_coverage"] = 1.0
            res.changes.append(
                Change("must_have_coverage", round(cur, 2), 1.0, f"{fam.key} capability-based (cap lifted)")
            )

    # 2. Salary-aware seniority_fit.
    salary = parse_salary(review.get("salary"))
    res.salary_parsed = salary
    if salary is not None:
        floor, target = sector_bands(review.get("sector_floor_applied"), cfg)
        prior_sen = float(new_dims.get("seniority_fit", 0.0))
        if salary >= target:
            new_sen = cfg.seniority_override["at_or_above_target"]
            rule = f"salary £{salary:,} >= target £{int(target):,}"
        elif salary >= floor:
            new_sen = max(prior_sen, cfg.seniority_override["between_floor_and_target"])
            rule = f"salary £{salary:,} in [floor £{int(floor):,}, target £{int(target):,})"
        else:
            new_sen = prior_sen
            rule = None
        if rule and abs(new_sen - prior_sen) >= 0.005:
            new_dims["seniority_fit"] = new_sen
            res.changes.append(Change("seniority_fit", round(prior_sen, 2), round(new_sen, 2), rule))

    res.dimension_scores = new_dims

    tilt = fam.score_modifier if fam else 0.0
    cap = fam.cap_verdict_below if fam else None
    # If no rule fired (no dimension change, no family tilt, no verdict cap),
    # leave the posting untouched rather than manufacture a delta from the
    # pre-existing rounding drift between its stored score and its sub-scores.
    if not res.changes and not tilt and not cap:
        res.skipped = "no rule applies"
        return res

    # 3. Weighted sum + family affinity tilt.
    score = _weighted(new_dims, cfg.weights)
    if fam and fam.score_modifier:
        before = score
        score = max(0.0, min(1.0, score + fam.score_modifier))
        res.changes.append(
            Change(
                "score_modifier",
                round(before, 2),
                round(score, 2),
                f"{fam.key} tilt {fam.score_modifier:+.2f}",
            )
        )

    verdict = verdict_for(score)

    # 4. Verdict cap for families with cap_verdict_below.
    if fam and fam.cap_verdict_below == "STRONG" and verdict == "STRONG":
        score = min(score, 0.79)
        verdict = "MODERATE-STRONG"
        res.changes.append(
            Change("verdict_cap", "STRONG", "MODERATE-STRONG", f"{fam.key} cap_verdict_below STRONG")
        )

    res.new_score = round(score, 2)
    res.new_verdict = verdict
    return res


# --------------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------------- #


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iter_reviews(slugs: list[str] | None = None):
    """Yield (slug, review_path, review_dict) for postings that have a review."""
    dirs = (
        [POSTINGS / s for s in slugs]
        if slugs
        else sorted(p for p in POSTINGS.iterdir() if p.is_dir()) if POSTINGS.is_dir() else []
    )
    for d in dirs:
        rp = d / "application_review.json"
        if not rp.exists():
            continue
        try:
            review = json.loads(rp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        yield d.name, rp, review


def write_review(path: Path, review: dict, res: Result) -> None:
    review["dimension_scores"] = {k: round(float(v), 4) for k, v in res.dimension_scores.items()}
    review["match_score"] = res.new_score
    review["verdict"] = res.new_verdict
    tilt = next((c for c in res.changes if c.field == "score_modifier"), None)
    review["score_modifier_applied"] = round(tilt.new - tilt.old, 2) if tilt else 0
    review["rescored"] = {
        "at": _now_utc(),
        "prior_match_score": res.prior_score,
        "prior_verdict": res.prior_verdict,
        "role_family_detected": res.family,
        "changes": [
            {"field": c.field, "old": c.old, "new": c.new, "rule": c.rule} for c in res.changes
        ],
    }
    path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_results(results: list[Result], reviews_by_slug: dict[str, tuple[Path, dict]]) -> int:
    """Persist moved results to their review JSON and to applications.yaml."""
    moved = [r for r in results if r.moved]
    if not moved:
        return 0
    for r in moved:
        path, review = reviews_by_slug[r.slug]
        write_review(path, review, r)
    data = load_index()
    for r in moved:
        entry = find_entry(data, r.slug)
        if entry is not None:
            entry["match_score"] = r.new_score
            entry["verdict"] = r.new_verdict
    save_index(data)
    return len(moved)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def _threshold_marker(old_v: str, new_v: str) -> str:
    if old_v == new_v:
        return ""
    oi, ni = VERDICT_ORDER.index(old_v), VERDICT_ORDER.index(new_v)
    return " ▲" if ni > oi else " ▼"


def render_markdown(results: list[Result], wrote: int | None) -> str:
    moved = [r for r in results if r.moved]
    moved.sort(key=lambda r: (r.new_score - r.prior_score), reverse=True)
    lines: list[str] = []
    lines.append(f"# Rescore delta - {len(results)} reviewed, {len(moved)} moved")
    lines.append("")
    if wrote is not None:
        lines.append(f"_Wrote {wrote} updated review(s) + applications.yaml._" if wrote else "_Dry run - nothing written._")
        lines.append("")
    lines.append("| Δ | Posting | Family | Score | Verdict | Salary | Drivers |")
    lines.append("|---|---------|--------|-------|---------|--------|---------|")
    for r in moved:
        delta = r.new_score - r.prior_score
        fam = r.family or "-"
        sal = f"£{r.salary_parsed:,}" if r.salary_parsed else "-"
        drivers = "; ".join(
            f"{c.field} {c.old}→{c.new}" for c in r.changes if c.field != "score_modifier"
        ) or "tilt only"
        mark = _threshold_marker(r.prior_verdict, r.new_verdict)
        lines.append(
            f"| {delta:+.2f} | {r.title} (`{r.slug}`) | {fam} | "
            f"{r.prior_score:.2f}→{r.new_score:.2f} | {r.prior_verdict}→{r.new_verdict}{mark} | {sal} | {drivers} |"
        )
    lines.append("")
    # Baseline-drift note: where formula(old dims) diverged from the stored score.
    drifted = [r for r in results if abs(r.baseline_drift) > 0.02 and not r.skipped]
    if drifted:
        lines.append(f"> Note: {len(drifted)} review(s) had >0.02 arithmetic drift between the stored "
                     f"match_score and the weighted sum of their stored sub-scores (pre-existing LLM "
                     f"rounding). The recompute uses the formula, so part of their delta corrects that.")
    skipped = [r for r in results if r.skipped]
    if skipped:
        from collections import Counter
        c = Counter(r.skipped for r in skipped)
        lines.append("")
        lines.append("Skipped: " + ", ".join(f"{n}× {reason}" for reason, n in c.items()))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministically rescore existing application reviews.")
    ap.add_argument("--slug", action="append", help="Restrict to this slug (repeatable).")
    ap.add_argument("--all", action="store_true", help="Every posting with a review (default).")
    ap.add_argument("--status", help="Restrict to this applications.yaml status (e.g. open).")
    ap.add_argument("--family", help="Restrict to a role family key from config (scoring.role_family_modifiers).")
    ap.add_argument("--write", action="store_true", help="Persist changes (default: dry run).")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)

    cfg = load_config()
    valid_families = [f.key for f in cfg.families]
    if args.family and args.family not in valid_families:
        ap.error(
            f"unknown --family {args.family!r}; choose from: "
            f"{', '.join(valid_families) or '(none defined in config)'}"
        )
    index = {e["slug"]: e for e in load_index()["applications"]}

    results: list[Result] = []
    reviews_by_slug: dict[str, tuple[Path, dict]] = {}
    for slug, path, review in iter_reviews(args.slug):
        entry = index.get(slug, {"slug": slug})
        if args.status and entry.get("status") != args.status:
            continue
        res = recompute(review, entry, cfg)
        if args.family and res.family != args.family:
            continue
        results.append(res)
        reviews_by_slug[slug] = (path, review)

    wrote = apply_results(results, reviews_by_slug) if args.write else None

    if args.format == "json":
        payload = [
            {
                "slug": r.slug, "title": r.title, "status": r.status, "family": r.family,
                "salary_parsed": r.salary_parsed, "prior_score": r.prior_score,
                "new_score": r.new_score, "prior_verdict": r.prior_verdict,
                "new_verdict": r.new_verdict, "moved": r.moved, "skipped": r.skipped,
                "baseline_drift": r.baseline_drift,
                "changes": [{"field": c.field, "old": c.old, "new": c.new, "rule": c.rule} for c in r.changes],
            }
            for r in results
        ]
        print(json.dumps({"wrote": wrote, "results": payload}, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(results, wrote))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
