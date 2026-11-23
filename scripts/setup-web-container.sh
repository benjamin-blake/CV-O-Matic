#!/usr/bin/env bash
#
# Provision an ephemeral Claude Code on the web container for CV builds.
#
# Point the cloud environment's "Setup script" field at this file:
#
#     bash scripts/setup-web-container.sh
#
# It is a thin, idempotent wrapper around setup.py: it builds cv/.venv,
# installs the Python dependencies from requirements.txt, and downloads the
# Playwright Chromium browser that cv/generate_cv.py renders PDFs with. Safe to
# run repeatedly; the container caches the result so subsequent sessions are
# fast.
set -euo pipefail

# Resolve the repo root so the script works no matter where it is invoked from.
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

echo "==> Provisioning CV-build environment in $(pwd)"

# A previous run that was interrupted can leave a half-built venv with a dangling
# python symlink, which makes setup.py bail at its verification step. Detect that
# and start clean.
if [ -d cv/.venv ] && ! cv/.venv/bin/python -c '' 2>/dev/null; then
  echo "==> Removing broken cv/.venv from a prior run"
  rm -rf cv/.venv
fi

# Build the venv, install requirements.txt, download Chromium. Idempotent.
python3 setup.py

# Claude Code on the web containers ship a pre-installed Chromium at
# /opt/pw-browsers (see PLAYWRIGHT_BROWSERS_PATH) for browser-driven tools, but
# the system python has no `playwright` pip package by default, and an agent
# working outside cv/.venv (e.g. before setup.py has run, or in a fresh
# interactive session) can't reach the venv's copy. Installing it system-wide
# too means PDF generation works immediately, without depending on cv/.venv
# existing first.
echo "==> Installing playwright pip package system-wide (uses the container's pre-installed Chromium)"
pip install playwright --quiet

# The pip package and the pre-installed browser binary are both present at this
# point, but a bare container image is missing the OS-level shared libraries
# headless Chromium links against (libatk-1.0.so.0, libnss3, libxcomposite1,
# etc.) - without this, launch fails with "error while loading shared
# libraries" even though the binary itself downloaded fine.
echo "==> Installing OS-level Chromium runtime dependencies"
if command -v apt-get >/dev/null 2>&1; then
  python3 -m playwright install-deps chromium
else
  echo "    [!] apt-get not found; skipping OS dependency install (non-Debian base image?)"
fi

# Smoke-test the part that actually matters for /build-cv: that headless Chromium
# can launch and emit a PDF. Cheap insurance that the container is genuinely
# ready before the session starts.
#
# The pip package's bundled browser revision doesn't always match the
# pre-installed one at /opt/pw-browsers (version drift between Playwright
# releases), which makes the default browser resolution fail with an
# "Executable doesn't exist" error. Point explicitly at the pre-installed
# binary when present so this doesn't depend on the two versions lining up.
echo "==> Verifying headless Chromium can render a PDF"
python3 - <<'PY'
import os
from playwright.sync_api import sync_playwright

browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
prebuilt_chromium = os.path.join(browsers_path, "chromium") if browsers_path else None

with sync_playwright() as p:
    launch_kwargs = {}
    if prebuilt_chromium and os.path.exists(prebuilt_chromium):
        launch_kwargs["executable_path"] = prebuilt_chromium
    browser = p.chromium.launch(**launch_kwargs)
    page = browser.new_page()
    page.set_content("<h1>ok</h1>")
    assert len(page.pdf()) > 0
    browser.close()
print("    Chromium render OK")
PY

echo "==> CV-build environment ready. Run /build-cv {slug} to generate a CV (PDF included)."
