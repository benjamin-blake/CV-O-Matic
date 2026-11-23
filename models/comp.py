"""Salary intelligence over the repository's own application dataset.

The analyser intentionally uses only local data from ``applications.yaml`` and
per-posting ``application_review.json`` files. USD salaries are converted with a
single documented constant so market summaries stay reproducible and easy to
update when exchange-rate assumptions change.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS = ROOT / "applications.yaml"
JOB_SEEKER = ROOT / "config" / "job_seeker.yaml"
POSTINGS = ROOT / "postings"

# Planning assumption from config/job_seeker.yaml: compare US-headquartered
# USD salaries at roughly 0.78 GBP per USD. Keep this constant local and
# visible so a future negotiation pass can update one number deliberately.
USD_TO_GBP = 0.78
# Standard UK contract annualisation used elsewhere in the plans. Day rates are
# shown as comparable annual figures, not treated as permanent salary offers.
WORKING_DAYS_PER_YEAR = 220

MONEY_RE = re.compile(r"(?<![\d,])(?P<currency>£|\$|gbp|usd)?\s*(?P<amount>\d{1,3}(?:,\d{3})?|\d{2,3}(?:\.\d+)?)(?P<suffix>k)?(?![\d,])", re.I)
DAY_RE = re.compile(r"(?:£|gbp)?\s*(\d{3,4})\s*(?:/|per)?\s*day|day\s*rate", re.I)


@dataclass(frozen=True)
class SalaryBand:
    low: int
    high: int
    source: str
    original: str
    is_day_rate: bool = False

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2


def _normalise_amount(amount: str, suffix: str | None, currency: str | None) -> int:
    value = float(amount.replace(",", ""))
    if suffix or ("," not in amount and value < 1000):
        value *= 1000
    if currency and currency.lower() in {"$", "usd"}:
        value *= USD_TO_GBP
    return int(round(value))


def parse_salary(text: str | None) -> tuple[int, int] | None:
    """Parse common stated-pay shapes into a GBP annual low/high tuple.

    Handles ranges, single figures, k-suffixes, up-to figures and day rates.
    Returns ``None`` for text without a usable monetary amount.
    """
    if not text:
        return None
    raw = str(text).strip()
    if not raw or raw.lower() in {"none", "null", "competitive", "not stated"}:
        return None

    day_match = DAY_RE.search(raw)
    if day_match:
        nums = [int(n) for n in re.findall(r"\d{3,4}", raw)]
        if nums:
            vals = [n * WORKING_DAYS_PER_YEAR for n in nums]
            return min(vals), max(vals)

    matches = list(MONEY_RE.finditer(raw))
    amounts = []
    annual_amounts = []
    monthly_amounts = []
    for m in matches:
        if not m.group("amount"):
            continue
        end_context = raw[m.end(): m.end() + 24].lower()
        value = _normalise_amount(m.group("amount"), m.group("suffix"), m.group("currency"))
        if re.match(r"\s*(?:/\s*month|per\s+month|monthly)", end_context):
            monthly_amounts.append(value * 12)
        else:
            annual_amounts.append(value)
    # Filter out percentages and tiny incidental numbers that often appear in
    # benefit prose. Anything below £20k annualised is not a salary for this repo.
    if not any(a >= 20_000 for a in annual_amounts) and re.search(r"/\s*month|per\s+month|monthly", raw, re.I):
        monthly_amounts = [a * 12 for a in annual_amounts if a < 20_000] + monthly_amounts
        annual_amounts = []
    annual_amounts = [a for a in annual_amounts if a >= 20_000]
    monthly_amounts = [a for a in monthly_amounts if a >= 20_000]
    amounts = annual_amounts or monthly_amounts
    if not amounts:
        return None
    if re.search(r"up to|to a maximum|maximum", raw, re.I) and len(amounts) == 1:
        return (0, amounts[0])
    return (min(amounts), max(amounts))


def _load_yaml(path: Path) -> Any:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _families() -> dict[str, list[str]]:
    cfg = _load_yaml(JOB_SEEKER)
    mods = cfg.get("scoring", {}).get("role_family_modifiers", {})
    return {name: [str(f).lower() for f in spec.get("title_fragments", [])] for name, spec in mods.items()}


def _family_precedence() -> list[str]:
    """Family keys in precedence order: ``scoring.family_precedence``, then config order."""
    cfg = _load_yaml(JOB_SEEKER)
    scoring = cfg.get("scoring", {}) or {}
    mods = scoring.get("role_family_modifiers", {}) or {}
    order = [k for k in (scoring.get("family_precedence") or []) if k in mods]
    return order + [k for k in mods if k not in order]


def classify_family(title: str, families: dict[str, list[str]] | None = None) -> str:
    title_l = (title or "").lower()
    families = families or _families()
    precedence = [k for k in _family_precedence() if k in families]
    for name in precedence:
        if any(fragment in title_l for fragment in families.get(name, [])):
            return name
    for name, fragments in families.items():
        if any(fragment in title_l for fragment in fragments):
            return name
    return "other"


def _review_for(slug: str) -> dict[str, Any]:
    path = POSTINGS / slug / "application_review.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _entry_salary(entry: dict[str, Any], review: dict[str, Any]) -> tuple[str | None, str]:
    # Prefer the richer review field when available, then fall back to common
    # index keys observed in applications.yaml.
    for source, value in (
        ("review", review.get("salary")),
        ("application", entry.get("salary")),
        ("application", entry.get("salary_range")),
        ("application", entry.get("compensation")),
    ):
        if value:
            return str(value), source
    return None, ""


def collect() -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    data = _load_yaml(APPLICATIONS) or {}
    families = _families()
    rows: list[dict[str, Any]] = []
    failed: list[tuple[str, str]] = []
    for entry in data.get("applications") or []:
        slug = entry.get("slug", "")
        review = _review_for(slug)
        salary_text, source = _entry_salary(entry, review)
        if not salary_text:
            continue
        parsed = parse_salary(salary_text)
        if not parsed:
            failed.append((slug, salary_text))
            continue
        low, high = parsed
        title = review.get("title") or entry.get("title") or ""
        rows.append(
            {
                "slug": slug,
                "company": review.get("company") or entry.get("company"),
                "title": title,
                "status": entry.get("status"),
                "verdict": entry.get("verdict") or review.get("verdict"),
                "match_score": entry.get("match_score") or review.get("match_score") or 0,
                "salary_text": salary_text,
                "salary_source": source,
                "low": low,
                "high": high,
                "midpoint": (low + high) / 2,
                "family": classify_family(title, families),
            }
        )
    return rows, failed


def _percentile(values: list[float], q: float) -> int:
    if not values:
        return 0
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return int(round(vals[lo] * (1 - frac) + vals[hi] * frac))


def _fmt_gbp(value: float) -> str:
    return f"£{int(round(value)):,.0f}"


def _summarise(name: str, rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return [f"{name}: no parseable stated pay"]
    mids = [r["midpoint"] for r in rows]
    lines = [
        f"{name}: count={len(rows)} p25={_fmt_gbp(_percentile(mids, 0.25))} median={_fmt_gbp(median(mids))} p75={_fmt_gbp(_percentile(mids, 0.75))}"
    ]
    live = [r for r in rows if r.get("status") == "open"]
    top = sorted(live, key=lambda r: (r["midpoint"], r.get("match_score") or 0), reverse=True)[:5]
    if top:
        lines.append("  highest-paying live postings:")
        for r in top:
            lines.append(
                f"  - {_fmt_gbp(r['midpoint'])}: {r['company']} - {r['title']} ({r['slug']}, {r['salary_text']})"
            )
    return lines


def main() -> None:
    rows, failed = collect()
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_family.setdefault(row["family"], []).append(row)

    print("Salary intelligence from local applications dataset")
    print(f"Parseable stated-pay entries: {len(rows)}")
    print("")
    for line in _summarise("overall", rows):
        print(line)
    print("")
    for family in sorted(by_family):
        for line in _summarise(family, by_family[family]):
            print(line)
        print("")
    print(f"Unparseable stated-pay strings: {len(failed)}")
    for slug, text in failed[:20]:
        print(f"  - {slug}: {text}")


if __name__ == "__main__":
    main()
