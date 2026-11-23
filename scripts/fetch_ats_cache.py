"""Fetch ATS list endpoints + filtered job bodies for the watchlist.

Runs on a GitHub Actions runner (open egress) and writes:

 - ``data/ats-cache/manifest.json`` - index of filtered candidates per company.
 - ``data/ats-cache/bodies/{YYYY-MM-DD}/{slug}.md`` - one markdown per
   filtered candidate, with title / location / URL frontmatter and the raw
   ATS body. The body is HTML for Greenhouse/Lever/Ashby/SmartRecruiters
   and markdown for Workable; Claude reads either fine.

The Anthropic scheduled-agent container is behind an egress allow-list that
rejects every ATS host (probed 2026-05-15). The skill reads these on-disk
artefacts so Tier 1 needs no network in the container.

Usage:
    python scripts/fetch_ats_cache.py                    # full watchlist
    python scripts/fetch_ats_cache.py --only Anthropic   # one company

Exit codes:
    0 - manifest written (or nothing changed)
    1 - > 50% of companies returned ``status == error`` (upstream-wide breakage)
    2 - usage / config error
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add repo root to sys.path so `models.slug` resolves when invoked from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import requests  # noqa: E402
import yaml  # noqa: E402

from models.slug import mint_slug  # noqa: E402


CACHE_DIR = REPO_ROOT / "data" / "ats-cache"
BODIES_DIR = CACHE_DIR / "bodies"
MANIFEST_PATH = CACHE_DIR / "manifest.json"
WATCHLIST_PATH = REPO_ROOT / "config" / "company_watchlist.yaml"
JOB_SEEKER_PATH = REPO_ROOT / "config" / "job_seeker.yaml"

REQUEST_TIMEOUT_S = 20
BODY_FETCH_SPACING_S = 0.2
BODY_FETCH_CAP_PER_COMPANY = 50
BODY_RETENTION_DAYS = 7
ERROR_RATIO_FAIL = 0.5


# ----------------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_body_markdown(path: Path, title: str, location: str, url: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = (
        f"# {title}\n\n"
        f"- **Location:** {location}\n"
        f"- **URL:** {url}\n\n"
        f"---\n\n"
        f"{body.strip()}\n"
    )
    path.write_text(out, encoding="utf-8")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------------

@dataclass
class FilterConfig:
    primary_location: str
    acceptable_uk_cities: list[str]
    remote_ok: bool
    onsite_ok: bool
    international: bool


def build_filter_config(job_seeker: dict) -> FilterConfig:
    loc = job_seeker.get("location") or {}
    return FilterConfig(
        primary_location=(loc.get("primary") or "").lower(),
        acceptable_uk_cities=[c.lower() for c in (loc.get("acceptable_uk_cities") or [])],
        remote_ok=bool(loc.get("remote_ok")),
        onsite_ok=bool(loc.get("onsite_ok")),
        international=bool(loc.get("international")),
    )


# Topic tokens - match if any appears as substring of the (lowercased) title.
# Deliberately broad: bare "data engineer" catches Anthropic's "Data Engineer,
# Safeguards", "member of technical staff" catches the AI-labs naming
# convention, "head of data" / "head of ai" catches leadership variants.
# Seniority and must-have coverage are enforced downstream by the job-matcher
# subagent, not here - the fetcher's job is to cast a wide enough net that
# the agent gets to use its judgement on borderline cases.
TITLE_TOPIC_TOKENS = (
    "data engineer", "data engineering", "data platform",
    "data architect", "data infrastructure", "data services", "data intelligence",
    "analytics engineer", "analytics engineering", "analytics platform",
    "ai engineer", "ai lead", "ai technical", "ai infrastructure",
    "machine learning engineer", "ml engineer",
    "head of data", "head of ai", "head of analytics",
    "enterprise architect", "solution architect",
    "member of technical staff",
    "software engineer, data", "software engineer (data)", "software engineer - data",
)

# Sub-Senior hints - reject regardless of topic match. The trailing space on
# "intern " avoids dropping "international" / "internal".
_JUNIOR_HINTS = ("junior", "graduate", "intern ", "apprentice", "trainee")

_INTERNATIONAL_HINTS = (
    "san francisco", "new york", "remote - us", "remote (us)", "us-based",
    "remote, us", "remote us", "boston", "seattle", "austin", "berlin",
    "paris", "amsterdam", "remote eu", "remote, eu", "apac",
    "singapore", "tokyo", "sydney", "tel aviv", "toronto",
)
_REMOTE_HINTS = ("remote", "anywhere", "distributed", "work from home", "hybrid")
_LONDON_HINTS = ("london", "uk", "united kingdom")


def passes_filters(title: str, location: str, cfg: FilterConfig) -> bool:
    """Broad topic-token title filter + location filter.

    Mirror of the semantics in scan-companies.md Step 3. The title check is
    intentionally broad (topic only); seniority and must-have evaluation belong
    to the job-matcher subagent downstream.
    """
    title_l = (title or "").lower()
    if not title_l:
        return False
    if any(j in title_l for j in _JUNIOR_HINTS):
        return False
    if not any(t in title_l for t in TITLE_TOPIC_TOKENS):
        return False

    loc_l = (location or "").lower()
    if not loc_l:
        # Missing location text - let it through; skill can filter further.
        return True

    is_remote_mention = any(h in loc_l for h in _REMOTE_HINTS)
    matches_primary = cfg.primary_location and cfg.primary_location in loc_l
    matches_uk_city = any(city and city in loc_l for city in cfg.acceptable_uk_cities)
    matches_uk_hint = any(h in loc_l for h in _LONDON_HINTS)
    matches_international = any(h in loc_l for h in _INTERNATIONAL_HINTS)

    if not cfg.international and matches_international and not (matches_primary or matches_uk_city or matches_uk_hint):
        return False

    if matches_primary or matches_uk_city or matches_uk_hint:
        return True
    if is_remote_mention and cfg.remote_ok:
        return True
    return False


# ----------------------------------------------------------------------------
# HTTP with retry
# ----------------------------------------------------------------------------

@dataclass
class FetchResult:
    http_status: int | None
    body: str | None
    error: str | None = None
    json_payload: dict | list | None = None


def _is_retryable_status(code: int) -> bool:
    return code in (408, 429) or 500 <= code < 600


def http_request(
    session: requests.Session,
    method: str,
    url: str,
    json_body: dict | None = None,
    timeout: int = REQUEST_TIMEOUT_S,
) -> FetchResult:
    """One retry on timeout / 5xx / 408 / 429. No retry on other 4xx."""
    last_error: str | None = None
    last_status: int | None = None
    for attempt in (1, 2):
        try:
            r = session.request(method, url, json=json_body, timeout=timeout)
            last_status = r.status_code
            if r.status_code >= 400:
                last_error = f"HTTP {r.status_code}"
                if attempt == 1 and _is_retryable_status(r.status_code):
                    time.sleep(1)
                    continue
                return FetchResult(http_status=r.status_code, body=None, error=last_error)
            try:
                payload = r.json()
            except ValueError:
                payload = None
            return FetchResult(http_status=r.status_code, body=r.text, json_payload=payload)
        except requests.Timeout:
            last_error = f"timeout after {timeout}s"
            if attempt == 1:
                continue
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt == 1:
                continue
    return FetchResult(http_status=last_status, body=None, error=last_error)


# ----------------------------------------------------------------------------
# ATS adapters - each returns a list of dicts with: title, location, url, body
# ----------------------------------------------------------------------------

@dataclass
class CompanyResult:
    name: str
    ats_type: str
    slug: str
    status: str  # "ok" | "ok_partial" | "error"
    http_status: int | None
    error: str | None = None
    jobs_total: int = 0
    jobs_after_filter: int = 0
    filtered_jobs: list[dict] = field(default_factory=list)


def _greenhouse(session, slug: str, cfg: FilterConfig) -> tuple[list[dict], int, FetchResult]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    res = http_request(session, "GET", url)
    if res.json_payload is None:
        return [], 0, res
    jobs = res.json_payload.get("jobs", []) if isinstance(res.json_payload, dict) else []
    total = len(jobs)
    out: list[dict] = []
    for j in jobs:
        title = j.get("title", "")
        location = ((j.get("location") or {}).get("name") or "")
        if not passes_filters(title, location, cfg):
            continue
        # Greenhouse `content` is HTML-entity-encoded HTML (`&lt;p&gt;...`).
        # Unescape once so the on-disk body is standard HTML that Claude reads natively.
        content = html.unescape(j.get("content", "") or "")
        out.append({
            "title": title,
            "location": location,
            "url": j.get("absolute_url", ""),
            "body": content,
        })
    return out, total, res


def _lever(session, slug: str, cfg: FilterConfig) -> tuple[list[dict], int, FetchResult]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    res = http_request(session, "GET", url)
    if res.json_payload is None:
        return [], 0, res
    postings = res.json_payload if isinstance(res.json_payload, list) else []
    total = len(postings)
    out: list[dict] = []
    for p in postings:
        title = p.get("text", "")
        location = ((p.get("categories") or {}).get("location") or "")
        if not passes_filters(title, location, cfg):
            continue
        body = p.get("descriptionPlain") or p.get("description") or ""
        # Append the requirement lists if present so the skill has the bullets too.
        for lst in p.get("lists") or []:
            heading = lst.get("text") or "Requirements"
            content = lst.get("content") or ""
            body += f"\n\n### {heading}\n\n{content}"
        out.append({
            "title": title,
            "location": location,
            "url": p.get("hostedUrl", ""),
            "body": body,
        })
    return out, total, res


def _ashby(session, slug: str, cfg: FilterConfig) -> tuple[list[dict], int, FetchResult]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    res = http_request(session, "GET", url, timeout=30)  # Ashby can be slow
    if res.json_payload is None:
        return [], 0, res
    jobs = res.json_payload.get("jobs", []) if isinstance(res.json_payload, dict) else []
    total = len(jobs)
    out: list[dict] = []
    for j in jobs:
        title = j.get("title", "")
        location = j.get("location", "") or ""
        if not passes_filters(title, location, cfg):
            continue
        out.append({
            "title": title,
            "location": location,
            "url": j.get("jobUrl", ""),
            "body": j.get("descriptionHtml", "") or "",
        })
    return out, total, res


def _smartrecruiters(session, slug: str, cfg: FilterConfig) -> tuple[list[dict], int, FetchResult, bool]:
    # SmartRecruiters list endpoint paginates: ?limit=100&offset=N. Walk pages
    # until offset >= totalFound or a page returns no content. Hard cap of 10
    # pages (1000 jobs) to bound runtime on pathological responses.
    first_res: FetchResult | None = None
    items: list[dict] = []
    total = 0
    offset = 0
    PAGE_LIMIT = 100
    for _page in range(10):
        page_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit={PAGE_LIMIT}&offset={offset}"
        res = http_request(session, "GET", page_url)
        if first_res is None:
            first_res = res
        if not isinstance(res.json_payload, dict):
            break
        page_items = res.json_payload.get("content") or []
        if not page_items:
            break
        items.extend(page_items)
        total = res.json_payload.get("totalFound") or len(items)
        offset += len(page_items)
        if offset >= total:
            break
    res = first_res or FetchResult(http_status=None, body=None, error="no response")
    if res.json_payload is None and not items:
        return [], 0, res, False
    filtered: list[dict] = []
    for it in items:
        title = it.get("name", "")
        loc = it.get("location") or {}
        location_parts = [loc.get("city"), loc.get("country")]
        if loc.get("remote"):
            location_parts.append("Remote")
        location = ", ".join(p for p in location_parts if p)
        if not passes_filters(title, location, cfg):
            continue
        filtered.append({
            "title": title,
            "location": location,
            "url": it.get("ref", ""),
            "id": it.get("id", ""),
        })
    # Fetch bodies, capped at BODY_FETCH_CAP_PER_COMPANY
    truncated = False
    if len(filtered) > BODY_FETCH_CAP_PER_COMPANY:
        truncated = True
        filtered = filtered[:BODY_FETCH_CAP_PER_COMPANY]
    out: list[dict] = []
    for f in filtered:
        body_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{f['id']}"
        body_res = http_request(session, "GET", body_url)
        if body_res.json_payload is None:
            body = ""
        else:
            sections = ((body_res.json_payload.get("jobAd") or {}).get("sections") or {})
            parts = []
            for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
                section = sections.get(key) or {}
                text = section.get("text") or ""
                if text:
                    title_h = section.get("title") or key
                    parts.append(f"### {title_h}\n\n{text}")
            body = "\n\n".join(parts)
        out.append({
            "title": f["title"],
            "location": f["location"],
            "url": f["url"],
            "body": body,
        })
        time.sleep(BODY_FETCH_SPACING_S)
    return out, total, res, truncated


def _workable(session, slug: str, cfg: FilterConfig) -> tuple[list[dict], int, FetchResult, bool]:
    # Workable's POST endpoint returns pages of ~10 with a `nextPage` token.
    # Re-POST with `{"token": "<nextPage>"}` until exhausted. Hard cap 20 pages.
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    body_req: dict = {"query": "", "department": [], "location": []}
    first_res: FetchResult | None = None
    items: list[dict] = []
    total = 0
    for page_idx in range(20):
        res = http_request(session, "POST", url, json_body=body_req)
        if first_res is None:
            first_res = res
        if not isinstance(res.json_payload, dict):
            break
        page_items = res.json_payload.get("results") or []
        if page_idx == 0:
            total = res.json_payload.get("total", len(page_items))
        items.extend(page_items)
        next_token = res.json_payload.get("nextPage")
        if not next_token or not page_items:
            break
        body_req = {"token": next_token}
    res = first_res or FetchResult(http_status=None, body=None, error="no response")
    if res.json_payload is None and not items:
        return [], 0, res, False
    if not total:
        total = len(items)
    filtered: list[dict] = []
    for it in items:
        title = it.get("title", "")
        loc = it.get("location") or {}
        location_parts = [loc.get("city"), loc.get("country")]
        if it.get("remote") or it.get("workplace") == "remote":
            location_parts.append("Remote")
        location = ", ".join(p for p in location_parts if p)
        if not passes_filters(title, location, cfg):
            continue
        filtered.append({
            "title": title,
            "location": location,
            "shortcode": it.get("shortcode", ""),
        })
    truncated = False
    if len(filtered) > BODY_FETCH_CAP_PER_COMPANY:
        truncated = True
        filtered = filtered[:BODY_FETCH_CAP_PER_COMPANY]
    out: list[dict] = []
    for f in filtered:
        body_url = f"https://apply.workable.com/{slug}/jobs/view/{f['shortcode']}.md"
        body_res = http_request(session, "GET", body_url)
        body = body_res.body or ""
        out.append({
            "title": f["title"],
            "location": f["location"],
            "url": f"https://apply.workable.com/{slug}/j/{f['shortcode']}/",
            "body": body,
        })
        time.sleep(BODY_FETCH_SPACING_S)
    return out, total, res, truncated


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def process_company(session, company: dict, cfg: FilterConfig, bodies_today_dir: Path, today: datetime) -> CompanyResult:
    name = company.get("name", "?")
    ats = company.get("ats") or {}
    ats_type = ats.get("type", "")
    slug = ats.get("slug", "")
    result = CompanyResult(name=name, ats_type=ats_type, slug=slug, status="error", http_status=None)
    if not ats_type or not slug:
        result.error = "missing ats.type or ats.slug"
        return result
    try:
        if ats_type == "greenhouse":
            jobs, total, fetch = _greenhouse(session, slug, cfg)
            truncated = False
        elif ats_type == "lever":
            jobs, total, fetch = _lever(session, slug, cfg)
            truncated = False
        elif ats_type == "ashby":
            jobs, total, fetch = _ashby(session, slug, cfg)
            truncated = False
        elif ats_type == "smartrecruiters":
            jobs, total, fetch, truncated = _smartrecruiters(session, slug, cfg)
        elif ats_type == "workable":
            jobs, total, fetch, truncated = _workable(session, slug, cfg)
        else:
            result.error = f"unknown ats.type {ats_type!r}"
            return result
    except Exception as exc:  # noqa: BLE001 - last-resort isolation
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.http_status = fetch.http_status
    if fetch.body is None and fetch.error:
        result.error = fetch.error
        return result

    result.jobs_total = total
    result.jobs_after_filter = len(jobs)
    result.status = "ok_partial" if truncated else "ok"

    # Per-job isolation: a single malformed posting (e.g. empty title triggering
    # a ValueError in mint_slug) must not drop the company's other valid jobs.
    filtered_payload: list[dict] = []
    for j in jobs:
        try:
            candidate_slug = mint_slug(name, j["title"], today=today)
        except ValueError as exc:
            print(f"  skipping job with invalid title: {exc}", file=sys.stderr)
            continue
        body_path = bodies_today_dir / f"{candidate_slug}.md"
        try:
            write_body_markdown(
                body_path,
                title=j["title"],
                location=j["location"],
                url=j["url"],
                body=j["body"],
            )
        except OSError as exc:
            print(f"  failed to write body for {candidate_slug}: {exc}", file=sys.stderr)
            continue
        rel = body_path.relative_to(REPO_ROOT).as_posix()
        filtered_payload.append({
            "title": j["title"],
            "location": j["location"],
            "url": j["url"],
            "candidate_slug": candidate_slug,
            "body_path": rel,
            "body_source": "bundle",
        })
    result.filtered_jobs = filtered_payload
    result.jobs_after_filter = len(filtered_payload)
    return result


def prune_old_bodies(retain_days: int) -> list[str]:
    """Remove body directories older than retain_days. Returns pruned dir names."""
    if not BODIES_DIR.exists():
        return []
    cutoff = today_utc().date() - timedelta(days=retain_days)
    pruned = []
    for child in BODIES_DIR.iterdir():
        if not child.is_dir():
            continue
        try:
            child_date = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if child_date < cutoff:
            for f in child.rglob("*"):
                if f.is_file():
                    f.unlink()
            child.rmdir()
            pruned.append(child.name)
    return pruned


def compute_watchlist_diff(companies: list[dict], prev_manifest: dict | None) -> dict:
    def key_set(items: list[dict]) -> set[tuple[str, str]]:
        out = set()
        for c in items:
            ats = (c.get("ats") or {}) if isinstance(c, dict) else {}
            slug = ats.get("slug") or c.get("slug") or ""
            out.add((c.get("name", ""), slug))
        return out

    current = key_set(companies)
    previous = key_set((prev_manifest or {}).get("companies") or []) if prev_manifest else set()
    added = sorted(f"{n} ({s})" for n, s in current - previous)
    removed = sorted(f"{n} ({s})" for n, s in previous - current)
    return {"added": added, "removed": removed}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fetch ATS list endpoints and body bundle for the watchlist.")
    parser.add_argument("--only", metavar="COMPANY", help="Fetch a single company by exact name match.")
    args = parser.parse_args(argv)

    if not WATCHLIST_PATH.exists():
        print(f"error: {WATCHLIST_PATH} not found", file=sys.stderr)
        return 2
    if not JOB_SEEKER_PATH.exists():
        print(f"error: {JOB_SEEKER_PATH} not found", file=sys.stderr)
        return 2

    watchlist = load_yaml(WATCHLIST_PATH)
    job_seeker = load_yaml(JOB_SEEKER_PATH)
    cfg = build_filter_config(job_seeker)

    companies = watchlist.get("companies") or []
    if args.only:
        wanted = args.only.lower()
        companies = [c for c in companies if (c.get("name") or "").lower() == wanted]
        if not companies:
            print(f"error: no company matches --only={args.only!r}", file=sys.stderr)
            return 2

    prev_manifest = None
    if MANIFEST_PATH.exists():
        try:
            prev_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except ValueError:
            prev_manifest = None

    today = today_utc()
    bodies_today_dir = BODIES_DIR / today.strftime("%Y-%m-%d")
    bodies_today_dir.mkdir(parents=True, exist_ok=True)

    pruned = prune_old_bodies(BODY_RETENTION_DAYS)
    if pruned:
        print(f"pruned old body dirs: {', '.join(pruned)}", file=sys.stderr)

    session = requests.Session()
    session.headers.update({"User-Agent": "cv-o-matic-ats-cache/1.0"})

    results: list[CompanyResult] = []
    for company in companies:
        name = company.get("name", "?")
        print(f"fetching {name} ({(company.get('ats') or {}).get('type', '?')})", file=sys.stderr)
        r = process_company(session, company, cfg, bodies_today_dir, today)
        results.append(r)
        print(
            f"  -> {r.status} (http={r.http_status}, total={r.jobs_total}, "
            f"matched={r.jobs_after_filter})"
            + (f", error={r.error}" if r.error else ""),
            file=sys.stderr,
        )

    error_count = sum(1 for r in results if r.status == "error")
    error_ratio = error_count / max(1, len(results))

    def company_entry(r: CompanyResult) -> dict:
        return {
            "name": r.name,
            "ats_type": r.ats_type,
            "slug": r.slug,
            "status": r.status,
            "http_status": r.http_status,
            "error": r.error,
            "jobs_total": r.jobs_total,
            "jobs_after_filter": r.jobs_after_filter,
            "filtered_jobs": r.filtered_jobs,
        }

    if args.only:
        # Merge into the existing manifest: replace the matching company entry,
        # leave everything else untouched. The watchlist diff is undefined for a
        # partial run, so preserve whatever the previous full run computed.
        if prev_manifest:
            manifest = json.loads(json.dumps(prev_manifest))
        else:
            manifest = {
                "fetched_at_utc": utcnow_iso(),
                "watchlist_diff_since_last": {"added": [], "removed": []},
                "companies": [],
            }
        existing = manifest.get("companies") or []
        new_entries = [company_entry(r) for r in results]
        keep = [c for c in existing if c.get("name") not in {r.name for r in results}]
        manifest["companies"] = keep + new_entries
        manifest["fetched_at_utc"] = utcnow_iso()
    else:
        manifest = {
            "fetched_at_utc": utcnow_iso(),
            "watchlist_diff_since_last": compute_watchlist_diff(companies, prev_manifest),
            "companies": [company_entry(r) for r in results],
        }
    write_json_atomic(MANIFEST_PATH, manifest)
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT).as_posix()} (error_ratio={error_ratio:.0%})", file=sys.stderr)

    if error_ratio > ERROR_RATIO_FAIL:
        print(f"error: error_ratio {error_ratio:.0%} > {ERROR_RATIO_FAIL:.0%} threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
