"""Render a generated CV to per-page PNG images for visual layout review.

Used by /build-cv Step 6.5: an agent Reads the PNGs to catch layout problems
that character-count checks cannot - content cut off (e.g. Education pushed off
the bottom of the left-hand column), overflow onto an unwanted extra page,
page-2 criteria/skills fit, or whitespace imbalance. This is the visual tier
that complements check_lengths.py (deterministic text budgets) and the
cv-reviewer subagent (semantic text review).

Usage:
    python cv/render_preview.py <posting_path> [output_dir]

Renders <posting_path>/{name_slug}_cv.html (see models.profile.cv_filenames()) to one PNG per A4 page, written to
<output_dir> (default: a system temp dir) as cv_preview_p{n}.png. Prints each
path, one per line, so the caller can Read them.

Exit codes:
    0  one or more preview PNGs written (paths printed to stdout)
    2  usage error / posting HTML missing
    3  Playwright or Chromium unavailable - NON-FATAL by contract: the /build-cv
       caller treats a missing preview like a missing PDF and proceeds with the
       text-only checks rather than blocking.
"""

from __future__ import annotations

import glob
import sys
import tempfile
from pathlib import Path

# Runs from inside cv/ with the cv venv: put the repo root on sys.path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.profile import cv_filenames  # noqa: E402

# A4 at 96 CSS px/in: 794 x 1123. The generator's print stylesheet targets A4,
# so slicing the rendered document into 1123-px bands approximates page breaks
# closely enough for a layout eyeball (it is not a substitute for the PDF's
# exact pagination, just a fast per-page view).
A4_W = 794
A4_H = 1123
MAX_PAGES = 4  # a CV over 4 pages is itself a defect; cap the render regardless


def _find_chromium() -> str | None:
    """Locate a Chromium executable. Prefer the container's pre-installed browser
    at /opt/pw-browsers (PLAYWRIGHT_BROWSERS_PATH), else let Playwright use its
    own resolution by returning None.
    """
    for pat in (
        "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
        "/opt/pw-browsers/chromium-*/chrome-linux/headless_shell",
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell",
    ):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


def render(posting: Path, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright  # imported late: ImportError -> exit 3

    html = (posting / cv_filenames()["html"]).resolve()
    if not html.exists():
        raise FileNotFoundError(html)

    exe = _find_chromium()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as p:
        launch_kwargs = {"executable_path": exe} if exe else {}
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": A4_W, "height": A4_H})
        page.goto(html.as_uri(), wait_until="networkidle")
        total_h = int(page.evaluate("document.body.scrollHeight"))
        pages = min(MAX_PAGES, max(1, -(-total_h // A4_H)))  # ceil div
        # Grow the viewport to the whole document so per-page clip regions all
        # fall inside the captured area (a viewport-height screenshot can only
        # clip within the viewport).
        page.set_viewport_size({"width": A4_W, "height": min(total_h, MAX_PAGES * A4_H)})
        for n in range(pages):
            y = n * A4_H
            h = min(A4_H, total_h - y)
            if h <= 0:
                break
            dest = out_dir / f"cv_preview_p{n + 1}.png"
            page.screenshot(path=str(dest), clip={"x": 0, "y": y, "width": A4_W, "height": h})
            written.append(dest)
        browser.close()
    return written


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Usage: python cv/render_preview.py <posting_path> [output_dir]", file=sys.stderr)
        return 2

    posting = Path(sys.argv[1])
    if not posting.is_dir():
        print(f"Error: {posting} is not a directory", file=sys.stderr)
        return 2

    out_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(tempfile.mkdtemp(prefix="cv_preview_"))

    try:
        written = render(posting, out_dir)
    except ImportError:
        print("Playwright not installed - skipping visual preview (non-fatal).", file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(f"Error: {exc} not found - run Step 6 (render) first.", file=sys.stderr)
        return 2
    except Exception as exc:  # Chromium missing / launch failure: non-fatal, same as no PDF
        print(f"Preview render failed ({exc}) - skipping visual preview (non-fatal).", file=sys.stderr)
        return 3

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
