#!/usr/bin/env python3
#
# CV Generator - Environment Setup
import subprocess, sys
from pathlib import Path
SCRIPT_DIR = Path(__file__).parent
# Single venv for the whole repo. Lives under cv/ because the CV pipeline (Playwright + Chromium)
# is the largest dependency and was historically the only thing that needed a venv. Slash commands
# and integrations import from this same venv via `cv/.venv/Scripts/python.exe` (Windows) or
# `cv/.venv/bin/python` (Unix).
VENV_PATH = SCRIPT_DIR / 'cv' / '.venv'
REQUIREMENTS = SCRIPT_DIR / 'requirements.txt'
def get_venv_python():
    win = VENV_PATH / 'Scripts' / 'python.exe'
    unix = VENV_PATH / 'bin' / 'python'
    return win if win.exists() else unix
def main():
    print('=' * 60)
    print('CV Generator - Environment Setup')
    print('=' * 60)
    print()
    print('[1/5] Checking Python installation...')
    print(f'  [OK] Found: Python {sys.version.split()[0]}')
    print()
    print('[2/5] Setting up virtual environment...')
    if VENV_PATH.exists():
        print('  [OK] Virtual environment exists')
    else:
        print('  > Creating virtual environment...')
        r = subprocess.run([sys.executable, '-m', 'venv', str(VENV_PATH)])
        if r.returncode != 0:
            print('  [X] Failed to create venv')
            sys.exit(1)
        print(f'  [OK] Created: {VENV_PATH}')
    print()
    print('[3/5] Verifying virtual environment...')
    venv_python = get_venv_python()
    if not venv_python.exists():
        print('  [X] Python not found in venv')
        sys.exit(1)
    print('  [OK] Virtual environment ready')
    print()
    print('[4/5] Upgrading pip...')
    subprocess.run([str(venv_python), '-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'])
    print('  [OK] pip upgraded')
    print()
    print('[5/5] Installing dependencies...')
    if not REQUIREMENTS.exists():
        print('  [X] requirements.txt not found')
        sys.exit(1)
    r = subprocess.run([str(venv_python), '-m', 'pip', 'install', '-r', str(REQUIREMENTS)])
    if r.returncode != 0:
        print('  [X] Installation failed'); sys.exit(1)
    print('  [OK] Dependencies installed')
    print()
    print('[5b/5] Installing Playwright Chromium browser...')
    r = subprocess.run([str(venv_python), '-m', 'playwright', 'install', 'chromium'])
    if r.returncode != 0:
        print('  [X] Playwright Chromium install failed'); sys.exit(1)
    print('  [OK] Chromium installed')
    print()
    r = subprocess.run([str(venv_python), '-c', 'import playwright; from playwright.sync_api import sync_playwright; print("ok")'], capture_output=True, text=True)
    if r.returncode == 0:
        print('  [OK] Playwright ready')
    else:
        print(f'  [X] Playwright check failed: {r.stderr.strip()}')
        sys.exit(1)
    print()
    print('[6/6] Checking environment configuration (.env)...')
    env_path = SCRIPT_DIR / '.env'
    env_example_path = SCRIPT_DIR / '.env.example'
    if not env_path.exists():
        if env_example_path.exists():
            import shutil
            shutil.copy(env_example_path, env_path)
            print('  [OK] Created .env from .env.example')
        else:
            print('  [!] No .env file found - create one with your API keys')
    else:
        print('  [OK] .env exists')
    # Warn about any empty GDrive credentials
    env_contents = env_path.read_text() if env_path.exists() else ''
    missing = []
    for key in ('GOOGLE_DRIVE_CLIENT_ID', 'GOOGLE_DRIVE_CLIENT_SECRET'):
        if f'{key}=' in env_contents and not env_contents.split(f'{key}=')[1].split('\n')[0].strip():
            missing.append(key)
    if missing:
        print()
        print('  [!] Fill in the following in your .env before running `python main.py sync`:')
        for k in missing:
            print(f'      {k}')
    print()
    print('  Setup complete!')
if __name__ == '__main__':
    main()
