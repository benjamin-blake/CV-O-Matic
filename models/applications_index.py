"""applications.yaml helpers - load, mutate, save the root state spine.

The index is the canonical source of truth for application status. Slash commands
mutate it via these helpers so the file shape stays stable.

Run from repo root.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml

REPO = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO / "applications.yaml"

Status = Literal["open", "applied", "declined", "closed", "rejected"]
VALID_STATUSES = {"open", "applied", "declined", "closed", "rejected"}

Stage = Literal["screen", "tech", "hiring_manager", "final", "offer"]
STAGES = ("screen", "tech", "hiring_manager", "final", "offer")
VALID_STAGES = set(STAGES)

FollowUpKind = Literal["nudge", "reply"]
VALID_FOLLOW_UP_KINDS = {"nudge", "reply"}

EmailActivityType = Literal[
    "confirmation",
    "additional_questions",
    "interview_invitation",
    "interview_scheduled",
    "rejection",
    "offer",
    "withdrawn",
    "other",
]
VALID_EMAIL_TYPES = {
    "confirmation",
    "additional_questions",
    "interview_invitation",
    "interview_scheduled",
    "rejection",
    "offer",
    "withdrawn",
    "other",
}

_HEADER = (
    "# applications.yaml - canonical state spine for job-seeker.\n"
    "# Edit me to flip status (open / applied / declined / closed).\n"
    "# Detailed per-posting analysis lives in postings/{slug}/application_review.json.\n\n"
)


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load() -> dict:
    if not INDEX_PATH.exists():
        return {"metadata": {"schema_version": 1}, "applications": []}
    data = yaml.safe_load(INDEX_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("metadata", {"schema_version": 1})
    data.setdefault("applications", [])
    return data


def save(data: dict) -> None:
    INDEX_PATH.write_text(
        _HEADER
        + yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=120,
        ),
        encoding="utf-8",
    )


def find(data: dict, slug: str) -> dict | None:
    for entry in data["applications"]:
        if entry["slug"] == slug:
            return entry
    return None


def upsert(
    data: dict,
    *,
    slug: str,
    company: str,
    title: str,
    location: str | None = None,
    posting_url: str | None = None,
    discovered_via: str = "manual",
    match_score: float | None = None,
    verdict: str | None = None,
    engagement: str = "permanent",
) -> dict:
    """Insert a new entry, or update the analytical fields on an existing one.

    Status / status_changed_at / cv_built_at / notes are never overwritten on
    update - those are user-owned. Returns the entry.
    """
    existing = find(data, slug)
    today = _today_utc()
    if existing is None:
        entry = {
            "slug": slug,
            "company": company,
            "title": title,
            "location": location,
            "posting_url": posting_url,
            "discovered": today,
            "discovered_via": discovered_via,
            "match_score": match_score,
            "verdict": verdict,
            "engagement": engagement,
            "status": "open",
            "status_changed_at": today,
            "cv_built_at": None,
            "notes": "",
        }
        data["applications"].append(entry)
        return entry

    for key, value in (
        ("company", company),
        ("title", title),
        ("location", location),
        ("posting_url", posting_url),
        ("discovered_via", discovered_via),
        ("match_score", match_score),
        ("verdict", verdict),
    ):
        if value is not None:
            existing[key] = value
    if engagement != "permanent" or "engagement" not in existing:
        existing["engagement"] = engagement
    return existing


def set_status(data: dict, slug: str, status: Status, notes: str | None = None) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(VALID_STATUSES)}")
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    entry["status"] = status
    entry["status_changed_at"] = _today_utc()
    if notes is not None:
        entry["notes"] = notes
    return entry


def set_stage(data: dict, slug: str, stage: Stage, notes: str | None = None) -> dict:
    if stage not in VALID_STAGES:
        raise ValueError(f"invalid stage {stage!r}; expected one of {sorted(VALID_STAGES)}")
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    entry["stage"] = stage
    entry["stage_changed_at"] = _today_utc()
    if notes is not None:
        entry["stage_notes"] = notes
    return entry


def set_follow_up(data: dict, slug: str, date: str, kind: FollowUpKind) -> dict:
    if kind not in VALID_FOLLOW_UP_KINDS:
        raise ValueError(f"invalid follow-up kind {kind!r}; expected one of {sorted(VALID_FOLLOW_UP_KINDS)}")
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    entry["follow_up"] = {"due": date, "kind": kind, "done": False}
    return entry


def clear_follow_up(data: dict, slug: str) -> dict:
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    entry.pop("follow_up", None)
    return entry


def mark_cv_built(data: dict, slug: str) -> dict:
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    entry["cv_built_at"] = _today_utc()
    return entry


def set_last_run(
    data: dict, routine: Literal["scan_indeed", "scan_companies", "check_email", "prune_open", "briefing"]
) -> None:
    key = f"last_{routine}_run"
    data["metadata"][key] = _now_utc()


def append_email_activity(
    data: dict,
    slug: str,
    *,
    date: str,
    type: EmailActivityType,
    subject: str,
    sender: str,
    link: str,
    summary: str | None = None,
) -> dict:
    """Append an email_activity entry to a posting. Idempotent on (date, link).

    Returns the entry. Does NOT auto-flip status - that's the caller's call
    (see /check-email docs for the policy).
    """
    if type not in VALID_EMAIL_TYPES:
        raise ValueError(f"invalid email type {type!r}; expected one of {sorted(VALID_EMAIL_TYPES)}")
    entry = find(data, slug)
    if entry is None:
        raise KeyError(f"no entry for slug {slug!r}")
    activity = entry.setdefault("email_activity", [])
    for existing in activity:
        if existing.get("link") == link:
            return entry
    record = {
        "date": date,
        "type": type,
        "subject": subject,
        "from": sender,
        "link": link,
    }
    if summary is not None:
        record["summary"] = summary
    activity.append(record)
    return entry
