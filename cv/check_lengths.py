"""Length and content checks for posting configs.

Verifies that summary, experience highlights, criteria responses, skills cells,
and personal statement all fit within the contract documented in /build-cv.
Strips HTML tags (e.g. ``<strong>``) before counting so rendering markup does
not count toward limits.

Also runs three deterministic content checks (Item 3 of WORKFLOW_IMPROVEMENTS.md):
 3a. skill-band coherence vs ``cv_core_data.yaml`` (WARN on up/downgrade).
 3b. metric tokens in ``criteria_responses`` must be grounded in the descriptions
     of selected achievements (FAIL).
 3c. British English / em-dash detection (FAIL).

Usage:
    cv/.venv/Scripts/python.exe cv/check_lengths.py <posting_path>
    cv/.venv/bin/python cv/check_lengths.py postings/2026-05-14_xxx

Exit code 0 if all checks pass, 1 if any FAIL (length or content), 2 on usage
error. WARNs are reported but do not fail the run. Output is one line per
check plus a summary header. Designed to be called from /build-cv after
writing configs and before invoking the cv-reviewer subagent.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


# (lower bound, upper bound). None means unbounded on that side.
LIMITS: dict[str, tuple[int | None, int | None]] = {
    "summary":            (400, 600),     # chars, HTML stripped
    "highlight":          (180, 250),     # chars, HTML stripped
    "criteria_response":  (80, 150),      # chars
    "skill_cell":         (None, 100),    # chars, HTML stripped
    "skill_category":     (None, 30),     # chars
    "personal_statement": (200, 280),     # WORDS, not chars
    "total_work_history": (None, 2100),   # chars, HTML stripped, sum of highlights
}

# Lenient sidebar budget for the left-hand column (Profile + Selected Projects +
# Education). WARN-only heuristic, not a hard gate: CV-O-Matic CVs tolerate an
# approximate signal here rather than the rendered-height measurement that a
# precise check would need. Calibrated above the typical shipped projects-total
# so it flags egregiously long sidebars (which risk truncating Education) while
# staying quiet on normal ones.
PROJECTS_SIDEBAR_WARN = 450


@dataclass
class Check:
    label: str
    value: int
    lo: int | None
    hi: int | None
    unit: str = "chars"
    preview: str | None = None

    @property
    def ok(self) -> bool:
        if self.lo is not None and self.value < self.lo:
            return False
        if self.hi is not None and self.value > self.hi:
            return False
        return True

    def format(self) -> str:
        status = "OK  " if self.ok else "FAIL"
        bounds = f"[{self.lo if self.lo is not None else '-'}, {self.hi if self.hi is not None else '-'}]"
        line = f"  [{status}] {self.label}: {self.value} {self.unit} {bounds}"
        if not self.ok and self.preview:
            line += f"\n           text: {self.preview!r}..."
        return line


SEVERITY_FAIL = "FAIL"
SEVERITY_WARN = "WARN"


@dataclass
class Issue:
    """A content-check finding. Severity drives exit code (FAIL → 1, WARN → 0)."""
    label: str
    severity: str
    detail: str
    location: str | None = None

    def format(self) -> str:
        loc = f" ({self.location})" if self.location else ""
        return f"  [{self.severity}] {self.label}{loc}: {self.detail}"


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", s)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ----------------------------------------------------------------------------
# Length checks (original behaviour)
# ----------------------------------------------------------------------------

def check_summary(posting: Path, checks: list[Check]) -> None:
    f = posting / "config" / "summary.yaml"
    if not f.exists():
        return
    data = load_yaml(f)
    summary = data.get("summary")
    if not isinstance(summary, dict) or "statement" not in summary:
        checks.append(Check(
            "summary.yaml structure",
            value=0,
            lo=1, hi=None,
            preview=repr(summary)[:60],
        ))
        return
    stmt = strip_html(summary["statement"])
    lo, hi = LIMITS["summary"]
    checks.append(Check("summary.statement", len(stmt), lo, hi, preview=stmt[:60]))


def check_experience(posting: Path, checks: list[Check]) -> None:
    f = posting / "config" / "experience.yaml"
    if not f.exists():
        return
    data = load_yaml(f)
    total = 0
    for role in data.get("experience", []):
        role_id = role.get("role_id", "?")
        for i, h in enumerate(role.get("highlights", []), 1):
            stripped = strip_html(h)
            total += len(stripped)
            lo, hi = LIMITS["highlight"]
            checks.append(Check(
                f"experience.{role_id}.highlight[{i}]",
                len(stripped), lo, hi,
                preview=stripped[:60],
            ))
    lo, hi = LIMITS["total_work_history"]
    checks.append(Check("total_work_history", total, lo, hi))


def check_criteria(posting: Path, checks: list[Check]) -> None:
    f = posting / "config" / "criteria_responses.yaml"
    if not f.exists():
        return
    data = load_yaml(f)
    for i, item in enumerate(data.get("criteria_responses", []), 1):
        resp = strip_html(item.get("response", ""))
        lo, hi = LIMITS["criteria_response"]
        checks.append(Check(
            f"criteria_responses[{i}]",
            len(resp), lo, hi,
            preview=resp[:60],
        ))


def check_skills(posting: Path, checks: list[Check]) -> None:
    f = posting / "config" / "skills.yaml"
    if not f.exists():
        return
    data = load_yaml(f)
    for i, cat in enumerate(data.get("skills_matrix", []), 1):
        name = cat.get("category", "")
        lo, hi = LIMITS["skill_category"]
        checks.append(Check(f"skills[{i}].category", len(name), lo, hi, preview=name))
        for level in ("expert", "comfortable", "familiar"):
            v = strip_html(cat.get(level, ""))
            if v:
                lo, hi = LIMITS["skill_cell"]
                checks.append(Check(f"skills[{i}].{level}", len(v), lo, hi, preview=v[:60]))


def check_personal_statement(posting: Path, checks: list[Check]) -> None:
    f = posting / "personal_statement.txt"
    if not f.exists():
        return
    text = f.read_text(encoding="utf-8")
    words = len(text.split())
    lo, hi = LIMITS["personal_statement"]
    checks.append(Check("personal_statement", words, lo, hi, unit="words"))


# ----------------------------------------------------------------------------
# Content checks (Item 3 expansion)
# ----------------------------------------------------------------------------

BAND_ORDER = {"expert": 3, "comfortable": 2, "familiar": 1}


def _extract_skill_tokens(cell: str) -> list[str]:
    """Lossy tokenisation per plan: split on ``,`` only (keeps ``SQS/SNS`` as one
    token), strip HTML, drop parenthetical scope (``AWS (S3, Lambda)`` → ``AWS``).
    Multi-word tools stay intact, which is why 3a is WARN not FAIL.
    """
    if not cell:
        return []
    cell = strip_html(cell)
    tokens: list[str] = []
    for raw in cell.split(","):
        tok = raw.strip()
        tok = re.sub(r"\s*\(.*$", "", tok)  # drop parenthetical scope
        tok = tok.strip()
        if tok:
            tokens.append(tok)
    return tokens


def _build_band_map(skills_matrix: list[dict]) -> dict[str, str]:
    """Return ``{tool_lower: band}`` for a skills_matrix structure. First
    occurrence wins; a tool listed in two bands of the same source is itself
    an authoring error but outside the scope of this check.
    """
    out: dict[str, str] = {}
    for cat in skills_matrix or []:
        for band in ("expert", "comfortable", "familiar"):
            for tok in _extract_skill_tokens(cat.get(band, "") or ""):
                out.setdefault(tok.lower(), band)
    return out


def check_skill_bands(posting: Path, cv_dir: Path, issues: list[Issue]) -> None:
    """3a. Posting skill bands vs ``cv_core_data.yaml``. WARN on mismatch."""
    posting_skills = posting / "config" / "skills.yaml"
    core_data = cv_dir / "cv_core_data.yaml"
    if not posting_skills.exists() or not core_data.exists():
        return
    posting_bands = _build_band_map(load_yaml(posting_skills).get("skills_matrix", []))
    core_bands = _build_band_map(load_yaml(core_data).get("skills_matrix", []))
    for tool, p_band in posting_bands.items():
        c_band = core_bands.get(tool)
        if c_band is None or c_band == p_band:
            continue
        direction = "upgrade" if BAND_ORDER[p_band] > BAND_ORDER[c_band] else "downgrade"
        issues.append(Issue(
            f"skill_band.{direction}",
            SEVERITY_WARN,
            f"posting marks '{tool}' as {p_band} but core says {c_band}",
            location="config/skills.yaml",
        ))



_METRIC_REGEXES = [
    re.compile(r"\d+%"),
    re.compile(r"£\d[\d,.]*[km]?", re.IGNORECASE),
    re.compile(r"\d+\+"),
    re.compile(r"\d+x", re.IGNORECASE),
    re.compile(r"\d{2,}"),
]
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
NAMED_METRIC_PHRASES = ["SCD Type 2", "Type 1/2", "petabyte", "terabyte"]


def _extract_metric_tokens(text: str) -> set[str]:
    """Extract candidate metric tokens from a criteria response. Years are
    dropped before return (the plan's ``\\b(19|20)\\d{2}\\b`` exclusion).
    """
    candidates: set[str] = set()
    for rx in _METRIC_REGEXES:
        for m in rx.finditer(text):
            candidates.add(m.group(0))
    years = {m.group(0) for m in _YEAR_RE.finditer(text)}
    candidates -= years
    lower = text.lower()
    for phrase in NAMED_METRIC_PHRASES:
        if phrase.lower() in lower:
            candidates.add(phrase)
    return candidates


def check_achievement_grounding(posting: Path, cv_dir: Path, issues: list[Issue]) -> None:
    """3c. Metric tokens in ``criteria_responses`` must be substring-matched
    against the description+impact text of every achievement listed in
    ``config.yaml :: selected_achievement_ids``. FAIL on any unmatched token.
    """
    config_path = posting / "config.yaml"
    crit_path = posting / "config" / "criteria_responses.yaml"
    ach_path = cv_dir / "cv_achievements.yaml"
    if not (config_path.exists() and crit_path.exists() and ach_path.exists()):
        return
    config = load_yaml(config_path)
    crit_data = load_yaml(crit_path)
    ach_data = load_yaml(ach_path)

    selected_ids = set(config.get("selected_achievement_ids", []))
    if not selected_ids:
        return

    # Grounding corpus: concatenation of description and impact for each selected
    # achievement. Including impact catches headline metrics that live there
    # (e.g. e.g. an achievement whose impact reads "trust scores from 65% to 95%").
    parts: list[str] = []
    for ach in ach_data.get("achievements", []):
        if ach.get("id") in selected_ids:
            parts.append(ach.get("description", "") or "")
            parts.append(ach.get("impact", "") or "")
    grounding = " ".join(parts).lower()

    for i, item in enumerate(crit_data.get("criteria_responses", []), 1):
        resp = strip_html(item.get("response", "") or "")
        if not resp:
            continue
        for token in sorted(_extract_metric_tokens(resp)):
            if token.lower() not in grounding:
                issues.append(Issue(
                    "criteria.grounding",
                    SEVERITY_FAIL,
                    f"cites '{token}' but no selected achievement contains this",
                    location=f"config/criteria_responses.yaml[{i}]",
                ))


# (us, uk) - \b prevents "colorimeter" matching "color". Case-insensitive.
US_TO_UK = {
    "fulfillment": "fulfilment",
    "organization": "organisation",
    "organize": "organise",
    "optimize": "optimise",
    "optimization": "optimisation",
    "analyze": "analyse",
    "behavior": "behaviour",
    "color": "colour",
    "favor": "favour",
    "labor": "labour",
    "modeling": "modelling",
    "specialization": "specialisation",
    "specialize": "specialise",
}

# Em-dash, en-dash. CLAUDE.md style rule. ASCII `--` handled separately
# because a literal `\b--\b` lookalike via plain `find` matches the YAML
# document separator `---`, which is legitimate. Below we use a regex that
# matches exactly two consecutive hyphens (not three or more).
_PAIR_DASH_RE = re.compile(r"(?<!-)--(?!-)")
DASH_CHARS = ("—", "–")

_BRITISH_FILES = (
    "config/summary.yaml",
    "config/experience.yaml",
    "config/skills.yaml",
    "config/criteria_responses.yaml",
    "personal_statement.txt",
)


def check_british_english(posting: Path, issues: list[Issue]) -> None:
    """3d. US spellings and forbidden dashes. FAIL on any hit."""
    for rel in _BRITISH_FILES:
        path = posting / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        # (i) US → UK pairs
        for us, uk in US_TO_UK.items():
            pattern = re.compile(rf"\b{re.escape(us)}\b", re.IGNORECASE)
            for m in pattern.finditer(text):
                line = text[: m.start()].count("\n") + 1
                issues.append(Issue(
                    "british_english.spelling",
                    SEVERITY_FAIL,
                    f"'{m.group(0)}' should be British '{uk}'",
                    location=f"{rel}:{line}",
                ))
        # (ii) Dash detection - separate code path, not in US_TO_UK.
        for dash in DASH_CHARS:
            idx = text.find(dash)
            while idx != -1:
                line = text[: idx].count("\n") + 1
                issues.append(Issue(
                    "british_english.dash",
                    SEVERITY_FAIL,
                    f"forbidden dash {dash!r} found",
                    location=f"{rel}:{line}",
                ))
                idx = text.find(dash, idx + 1)
        # ASCII `--` (exactly two hyphens; skip `---` YAML separators and CLI
        # flags like `--no-edit` are not in these YAML / txt files anyway).
        for m in _PAIR_DASH_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            issues.append(Issue(
                "british_english.dash",
                SEVERITY_FAIL,
                "forbidden dash '--' found",
                location=f"{rel}:{line}",
            ))


_PAREN_RE = re.compile(r"\([^)]*\)")


def _project_strings(projects_yaml: Path) -> list[str]:
    """Return each project as a plain string. Most postings use a list of
    strings; a few use ``{title: ...}`` dicts - join their values so both
    shapes are counted.
    """
    if not projects_yaml.exists():
        return []
    data = load_yaml(projects_yaml)
    out: list[str] = []
    for p in data.get("projects", []) or []:
        if isinstance(p, dict):
            p = " ".join(str(v) for v in p.values())
        out.append(str(p))
    return out


def check_projects(posting: Path, issues: list[Issue]) -> None:
    """3e. Left-hand column hygiene (CV-O-Matic CV sidebar). WARN only.

    Projects render in the left column with Profile and Education; long project
    strings push Education off the bottom of the page. Two lenient, build-time
    WARNs (never FAIL, so exit code is unaffected):
      - a parenthetical tool list naming no tool from the posting: drop it to
        save sidebar space (see /build-cv Common pitfalls).
      - total projects text over ``PROJECTS_SIDEBAR_WARN``: trim to avoid the
        sidebar overflowing and truncating Education.
    """
    projects = _project_strings(posting / "config" / "projects.yaml")
    if not projects:
        return
    posting_txt = posting / "posting.txt"
    posting_text = (
        posting_txt.read_text(encoding="utf-8").lower() if posting_txt.exists() else ""
    )
    total = 0
    for i, proj in enumerate(projects, 1):
        stripped = strip_html(proj)
        total += len(stripped)
        for m in _PAREN_RE.finditer(stripped):
            inner = m.group(0)[1:-1]
            tools = [t.strip() for t in inner.split(",") if t.strip()]
            grounded = any(posting_text and t.lower() in posting_text for t in tools)
            if not grounded:
                issues.append(Issue(
                    "projects.parenthetical",
                    SEVERITY_WARN,
                    f"project[{i}] parenthetical '{inner}' names no posting tool; "
                    f"drop it to save sidebar space",
                    location="config/projects.yaml",
                ))
    if total > PROJECTS_SIDEBAR_WARN:
        issues.append(Issue(
            "projects.sidebar_length",
            SEVERITY_WARN,
            f"projects total {total} chars > {PROJECTS_SIDEBAR_WARN}; left-hand "
            f"column may overflow and truncate Education",
            location="config/projects.yaml",
        ))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python cv/check_lengths.py <posting_path>", file=sys.stderr)
        return 2

    posting = Path(sys.argv[1])
    if not posting.is_dir():
        print(f"Error: {posting} is not a directory", file=sys.stderr)
        return 2

    cv_dir = Path(__file__).resolve().parent

    checks: list[Check] = []
    check_summary(posting, checks)
    check_experience(posting, checks)
    check_criteria(posting, checks)
    check_skills(posting, checks)
    check_personal_statement(posting, checks)

    issues: list[Issue] = []
    check_skill_bands(posting, cv_dir, issues)
    check_achievement_grounding(posting, cv_dir, issues)
    check_british_english(posting, issues)
    check_projects(posting, issues)

    length_fails = [c for c in checks if not c.ok]
    content_fails = [i for i in issues if i.severity == SEVERITY_FAIL]
    content_warns = [i for i in issues if i.severity == SEVERITY_WARN]

    print(f"Length check - {posting.name}")
    print(f"{len(checks) - len(length_fails)} pass, {len(length_fails)} fail")
    print()
    for c in checks:
        print(c.format())

    if issues:
        print()
        print(f"Content check - {len(content_fails)} fail, {len(content_warns)} warn")
        print()
        for issue in issues:
            print(issue.format())

    return 1 if (length_fails or content_fails) else 0


if __name__ == "__main__":
    sys.exit(main())
