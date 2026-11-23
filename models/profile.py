"""Candidate profile helpers: identity, CV file names, and the example-profile guard.

Identity (name, contact details, roles) lives in ``cv/cv_core_data.yaml``.
The guard flag lives in ``config/job_seeker.yaml -> profile.is_example_profile``.
The template ships with a fictional example profile and the flag set to true;
``/onboard`` replaces the example data and sets it to false.

Commands that act on real postings (``/build-cv``, the scan routines,
``/check-email`` ...) run the check first and stop if it fails:

    python3 -m models.profile --check      # exit 0 if onboarded, 3 if still the example
    python3 -m models.profile              # print name, CV file names, guard state

Importable from the repo root (``from models.profile import ...``) or from
inside ``cv/`` after adding the repo root to ``sys.path``. Needs only PyYAML.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CORE_DATA_PATH = REPO / "cv" / "cv_core_data.yaml"
JOB_SEEKER_PATH = REPO / "config" / "job_seeker.yaml"

EXIT_EXAMPLE_PROFILE = 3

GUARD_MESSAGE = (
    "This repo is still using the fictional example profile (Sherlock Holmes).\n"
    "Run /onboard in Claude Code to replace it with your own details first.\n"
    "(Guard: config/job_seeker.yaml -> profile.is_example_profile is true.)"
)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def candidate_name(core_data_path: Path = CORE_DATA_PATH) -> str:
    """Full name from ``cv_core_data.yaml -> personal_info.name``."""
    return str(_load_yaml(core_data_path).get("personal_info", {}).get("name", "")).strip()


def name_slug(name: str | None = None) -> str:
    """File-name stem derived from the candidate's name.

    Must stay identical to the derivation in ``cv/generate_cv.py`` so every
    consumer agrees on the generated file names.
    """
    name = candidate_name() if name is None else name
    return (name or "cv").lower().replace(" ", "_").replace("-", "_")


def cv_filenames(name: str | None = None) -> dict[str, str]:
    """Generated CV file names, e.g. ``{"html": "sherlock_holmes_cv.html", ...}``."""
    stem = name_slug(name)
    return {
        "html": f"{stem}_cv.html",
        "pdf": f"{stem}_cv.pdf",
        "css": f"{stem}_cv_styles.css",
    }


def is_example_profile(job_seeker_path: Path = JOB_SEEKER_PATH) -> bool:
    """True while the fictional example profile is still in place.

    A missing flag is treated as onboarded (older configs predate the guard).
    """
    profile = _load_yaml(job_seeker_path).get("profile", {}) or {}
    return bool(profile.get("is_example_profile", False))


def require_real_profile(allow_example: bool = False) -> None:
    """Exit with ``EXIT_EXAMPLE_PROFILE`` if the example profile is still active."""
    if is_example_profile() and not allow_example:
        print(GUARD_MESSAGE, file=sys.stderr)
        sys.exit(EXIT_EXAMPLE_PROFILE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help=f"Exit {EXIT_EXAMPLE_PROFILE} if the example profile is still active.")
    args = ap.parse_args(argv)

    if args.check:
        if is_example_profile():
            print(GUARD_MESSAGE, file=sys.stderr)
            return EXIT_EXAMPLE_PROFILE
        print("Profile OK: onboarded.")
        return 0

    files = cv_filenames()
    print(f"Candidate:        {candidate_name() or '(unset)'}")
    print(f"CV files:         {files['html']}, {files['pdf']}")
    print(f"Example profile:  {'YES - run /onboard' if is_example_profile() else 'no (onboarded)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
