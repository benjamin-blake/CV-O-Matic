#!/usr/bin/env python3
"""
Unified CV Generator
Generates HTML and PDF CVs from YAML data with posting-specific customization.

Usage:
    python generate_cv.py --posting postings/2026-01-15_acme_senior_data_analyst
    python generate_cv.py --posting postings/2026-01-15_acme_senior_data_analyst --html-only
    python generate_cv.py --posting postings/... --allow-example   # smoke-test on the example profile

The script will:
1. Load cv_core_data.yaml, cv_achievements.yaml, cv_config.yaml
2. Load posting-specific config.yaml (REQUIRED - fails if missing)
3. Replace ALL role highlights with selected achievements
4. Generate CSS from selected color scheme
5. Generate HTML and optionally PDF
6. Output to posting folder as {name_slug}_cv.html and {name_slug}_cv.pdf
   (name_slug is derived from personal_info.name; see models/profile.py)

Refuses to run (exit 3) while the fictional example profile is active, unless
--allow-example is passed. Run /onboard to replace the example profile.
"""

import argparse
import sys
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Make the repo root importable (this script runs from inside cv/ with the cv venv).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.profile import name_slug as profile_name_slug, require_real_profile  # noqa: E402

# Import shared library modules
from lib import (
    CVDataLoader,
    generate_initials,
    prepare_experience_data,
    prepare_education_data,
    truncate_text,
    generate_css_from_scheme,
    get_color_scheme,
)

# PDF generation uses Playwright (bundled Chromium) for pixel-perfect browser parity


# ============================================================================
# Configuration
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
TEMPLATE_FILE = SCRIPT_DIR / "cv_template.html"
CSS_TEMPLATE_FILE = SCRIPT_DIR / "cv_styles.css"


def load_yaml(posting_path: Path, filename: str, key: str = None, fallback=None):
    """Load YAML config from posting's config/ directory with optional key extraction."""
    import yaml
    config_file = posting_path / 'config' / filename
    if not config_file.exists():
        return fallback if fallback is not None else {}
    try:
        data = yaml.safe_load(open(config_file, 'r', encoding='utf-8'))
        return data.get(key, fallback if fallback is not None else {}) if key else data
    except Exception as e:
        print(f"  ⚠ Warning: Could not load {filename}: {str(e)}")
        return fallback if fallback is not None else {}


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate customized CV for specific job posting')
    parser.add_argument('--posting', type=str, required=True, help='Path to posting directory')
    parser.add_argument('--allow-example', action='store_true', help='Render even while the fictional example profile is active (template smoke tests only)')
    parser.add_argument('--html-only', action='store_true', help='Generate HTML only (skip PDF generation)')
    return parser.parse_args()


def validate_environment(html_only: bool):
    """Validate that required files and dependencies are available. FAIL FAST if requirements not met."""
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Template file not found: {TEMPLATE_FILE}")
    if not CSS_TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"CSS template not found: {CSS_TEMPLATE_FILE}")
    if not html_only:
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Playwright not installed for PDF generation.\n"
                "Options:\n"
                "  1. Use --html-only flag to generate HTML preview only\n"
                "  2. pip install playwright && playwright install chromium"
            )


def load_and_merge_cv_data(posting_path: Path, loader: CVDataLoader) -> dict:
    """Load all YAML configs and apply posting-specific overrides."""
    print("Loading CV data and posting configuration...")
    try:
        cv_data = loader.merge_posting_data(posting_path)
        print(f"  ✓ Core data, config, {len(cv_data['posting_config']['selected_achievement_ids'])} achievements")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n[ERROR] {str(e)}\n")
        sys.exit(1)
    
    # Load color scheme and custom overrides
    color_scheme_config = load_yaml(posting_path, 'color_scheme.yaml', key='color_scheme')
    cv_data['selected_color_scheme'] = color_scheme_config or cv_data['selected_color_scheme']
    
    custom_summary = load_yaml(posting_path, 'summary.yaml', key='summary')
    if custom_summary and 'statement' in custom_summary:
        cv_data['custom_summary'] = custom_summary['statement']
    
    custom_skills = load_yaml(posting_path, 'skills.yaml', key='skills_matrix')
    if custom_skills:
        cv_data['custom_skills'] = custom_skills
    
    custom_experience = load_yaml(posting_path, 'experience.yaml', key='experience')
    if custom_experience:
        cv_data['custom_experience'] = custom_experience

    custom_education = load_yaml(posting_path, 'education.yaml', key='education')
    if custom_education:
        cv_data['custom_education'] = custom_education
    
    projects_data = load_yaml(posting_path, 'projects.yaml', key='projects', fallback=[])
    cv_data['relevant_projects'] = [p.get('title', p) if isinstance(p, dict) else p for p in projects_data]
    return cv_data


def render_cv_files(posting_path: Path, template_data: dict, output_files: dict, html_only: bool):
    """Generate CSS, HTML, and optionally PDF files."""
    print("\nGenerating HTML...")
    env = Environment(loader=FileSystemLoader(SCRIPT_DIR))
    template = env.get_template(TEMPLATE_FILE.name)
    html_output = posting_path / output_files['html']
    open(html_output, 'w', encoding='utf-8').write(template.render(**template_data))
    print(f"  ✓ HTML: {html_output}")
    
    if not html_only:
        print("\nGenerating PDF (Playwright/Chromium)...")
        pdf_path = posting_path / output_files['pdf']
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(html_output.absolute().as_uri(), wait_until="networkidle")
                page.pdf(path=str(pdf_path.absolute()), format="A4", print_background=True)
                browser.close()
            if pdf_path.exists():
                print(f"  ✓ PDF: {pdf_path}")
            else:
                print("\n[ERROR] PDF not created.")
                sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] PDF failed: {e}. Try --html-only flag.\n")
            sys.exit(1)


def generate_cv(posting_path: Path, html_only: bool = False):
    """Generate CV for specific posting."""
    from datetime import datetime
    
    print(f"\n{'='*70}\nCV Generator - {posting_path.name}\n{'='*70}\n")
    
    # Load data
    cv_data = load_and_merge_cv_data(posting_path, CVDataLoader(SCRIPT_DIR))
    personal_info = cv_data.get('personal_info', {})
    content_limits = cv_data['cv_config'].get('content_limits', {})
    
    # Get output file names
    name_slug = profile_name_slug(personal_info.get('name', 'cv'))
    output_templates = cv_data['cv_config'].get('output_files', {
        'html': '{name_slug}_cv.html', 'pdf': '{name_slug}_cv.pdf', 'css': '{name_slug}_cv_styles.css'
    })
    output_files = {k: v.format(name_slug=name_slug) for k, v in output_templates.items()}
    
    # Generate CSS
    print(f"\nGenerating CSS from '{cv_data['selected_color_scheme']}' scheme...")
    try:
        generate_css_from_scheme(
            get_color_scheme(cv_data['selected_color_scheme'], cv_data['cv_config']),
            CSS_TEMPLATE_FILE, posting_path / output_files['css']
        )
        print(f"  ✓ CSS: {posting_path / output_files['css']}")
    except ValueError as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)
    
    # Prepare template data
    print("\nPreparing template data...")
    summary_text = cv_data.get('custom_summary', cv_data.get('summary', {}).get('statement', ''))
    max_summary = content_limits.get('summary_section', 600)
    if len(summary_text) > max_summary:
        summary_text = truncate_text(summary_text, max_summary)
    
    # Process experience
    custom_experience = cv_data.get('custom_experience')
    if custom_experience:
        roles_by_id = {role['id']: role for role in cv_data.get('roles', [])}
        experience_data = [{
            'position': roles_by_id[r.get('role_id')].get('position', ''),
            'company': roles_by_id[r.get('role_id')].get('company', ''),
            'location': roles_by_id[r.get('role_id')].get('location', ''),
            'date_range': f"{roles_by_id[r.get('role_id')].get('end_date', '')} \u2013 {roles_by_id[r.get('role_id')].get('start_date', '')}",
            'highlights': r.get('highlights', [])
        } for r in custom_experience if r.get('role_id') in roles_by_id]
    else:
        experience_data = prepare_experience_data(cv_data.get('roles', []), content_limits.get('work_history_section', 2400))
    
    # Build template data
    current_date = datetime.now().strftime("%d %B %Y")
    posting_config = cv_data.get('posting_config', {})
    template_data = {
        'name': personal_info.get('name', ''), 'title': personal_info.get('title', ''),
        'initials': generate_initials(personal_info.get('name', '')),
        'location': personal_info.get('location', ''), 'phone': personal_info.get('phone', ''),
        'email': personal_info.get('email', ''), 'github': personal_info.get('github', ''),
        'birth_date': personal_info.get('birth_date', ''), 'nationality': personal_info.get('nationality', ''),
        'objective': summary_text, 'css_filename': output_files['css'],
        'current_date': current_date,
        'job_role': posting_config.get('job_title', personal_info.get('title', 'Role')),
        'company': posting_config.get('company', 'Company'),
        'relevant_projects': cv_data['relevant_projects'], 'green_tick_path': '../../green_tick.png',
        'skills_matrix': cv_data.get('custom_skills', cv_data.get('skills_matrix', [])),
        'experience': experience_data,
        'education': cv_data['custom_education'] if 'custom_education' in cv_data else prepare_education_data(cv_data.get('education', []), content_limits.get('education_section', 400)),
        'essential_criteria': load_yaml(posting_path, 'criteria_responses.yaml', key='criteria_responses', fallback=[]),
    }
    
    print(f"  ✓ {len(experience_data)} roles, {len(template_data['education'])} education, {len(template_data['essential_criteria'])} criteria")
    
    # Render files
    render_cv_files(posting_path, template_data, output_files, html_only)
    
    # Print summary
    print(f"\n{'='*70}\n✓ Complete! Output: {posting_path.absolute()}\n{'='*70}\n")


def main():
    """Main entry point."""
    args = parse_arguments()

    # Example-profile guard: exit 3 unless --allow-example was passed.
    require_real_profile(allow_example=args.allow_example)

    # Resolve posting path
    posting_path = Path(args.posting)
    if not posting_path.is_absolute():
        posting_path = SCRIPT_DIR / posting_path
    
    if not posting_path.exists():
        print(f"\n[ERROR] Posting directory not found: {posting_path}\n")
        sys.exit(1)
    
    # Validate environment
    try:
        validate_environment(args.html_only)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"\n[ERROR] {str(e)}\n")
        sys.exit(1)
    
    # Generate CV
    try:
        generate_cv(posting_path, args.html_only)
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] CV generation interrupted by user.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {str(e)}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
