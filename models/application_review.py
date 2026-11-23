"""ApplicationReview dataclass - load/dump helpers for postings/{slug}/application_review.json.

This is the detailed analytical review per posting. The workflow-spine fields
(status, status_changed_at, cv_built_at) live in the root-level applications.yaml,
not here. See config/application_review.schema.json for the canonical shape.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Match = Literal["FULL", "PARTIAL", "NONE"]
Verdict = Literal["STRONG", "MODERATE-STRONG", "MODERATE", "WEAK", "REJECT"]
DiscoveredVia = Literal["indeed", "company_watchlist", "email", "manual", "linkedin", "other"]


@dataclass
class CriterionAssessment:
    criterion: str
    match: Match
    evidence: str | None = None


@dataclass
class Gap:
    issue: str
    impact: str
    mitigation: str | None = None


@dataclass
class DimensionScores:
    must_have_coverage: float = 0.0
    strong_preference_coverage: float = 0.0
    seniority_fit: float = 0.0
    mission_alignment: float = 0.0
    compensation_fit: float = 0.0


@dataclass
class Summary:
    office_and_location: str = ""
    compensation: str = ""
    mission_and_culture: str = ""
    technical_fit: str = ""
    overall: str = ""


@dataclass
class Artefacts:
    posting: str | None = None
    cv_pdf: str | None = None
    cv_html: str | None = None
    personal_statement: str | None = None


@dataclass
class ApplicationReview:
    posting_slug: str
    title: str
    company: str
    match_score: float
    verdict: Verdict
    discovered_via: DiscoveredVia
    posting_url: str | None = None
    location: str | None = None
    salary: str | None = None
    remote_policy: str | None = None
    seniority: str | None = None
    deadline: str | None = None
    verdict_justification: str = ""
    summary: Summary = field(default_factory=Summary)
    dimension_scores: DimensionScores = field(default_factory=DimensionScores)
    essential_criteria: list[CriterionAssessment] = field(default_factory=list)
    nice_to_have: list[CriterionAssessment] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    deal_breakers_triggered: list[str] = field(default_factory=list)
    artefacts: Artefacts = field(default_factory=Artefacts)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @classmethod
    def load(cls, path: Path) -> "ApplicationReview":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["essential_criteria"] = [CriterionAssessment(**c) for c in data.get("essential_criteria", [])]
        data["nice_to_have"] = [CriterionAssessment(**c) for c in data.get("nice_to_have", [])]
        data["gaps"] = [Gap(**g) for g in data.get("gaps", [])]
        data["dimension_scores"] = DimensionScores(**data.get("dimension_scores", {}))
        data["summary"] = Summary(**data.get("summary", {}))
        data["artefacts"] = Artefacts(**data.get("artefacts", {}))
        return cls(**data)

    def dump(self, path: Path) -> None:
        Path(path).write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
