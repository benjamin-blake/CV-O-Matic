"""Canonical slug minting for posting directories.

Posting directories are named ``{YYYY-MM-DD}_{snake(company)}_{snake(title)}``
where the date is the discovery date in UTC. This module is the single source of
truth for that contract. Subagents must not generate slugs themselves - the
calling routine imports ``mint_slug`` and passes the result to the subagent.

Usage from a shell, e.g. inside a routine step:

    python -c "from models.slug import mint_slug; print(mint_slug('Baskerville & Co', 'Senior Data Analyst, Estates'))"
    # 2026-05-15_baskerville_co_senior_data_analyst_estates
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    """snake_case for slugs. Lowercase, [^a-z0-9] → underscore, collapse and trim."""
    s = s.lower()
    s = _NON_ALNUM.sub("_", s)
    return s.strip("_")


def mint_slug(company: str, title: str, today: datetime | None = None) -> str:
    """`{YYYY-MM-DD}_{snake(company)}_{snake(title)}`. UTC today by default.

    Raises ``ValueError`` if either component slugifies to an empty string - 
    catches all-non-Latin inputs (Cyrillic, emoji, etc.) rather than producing
    a malformed slug like ``2026-05-15__title``.
    """
    if today is None:
        today = datetime.now(timezone.utc)
    c = slugify(company)
    t = slugify(title)
    if not c or not t:
        raise ValueError(f"empty slug component: company={company!r} title={title!r}")
    return f"{today.strftime('%Y-%m-%d')}_{c}_{t}"
