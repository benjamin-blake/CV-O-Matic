"""
CV CSS Generator Module
Generates dynamic CSS from color scheme configuration.
"""

from typing import Dict, Any
from pathlib import Path


def generate_css_from_scheme(
    color_scheme: Dict[str, str],
    template_path: Path,
    output_path: Path
) -> None:
    """
    Generate CSS file from color scheme by replacing CSS variable values.
    
    Args:
        color_scheme: Dictionary with color values (primary, secondary, accent, text, light)
        template_path: Path to CSS template
        output_path: Path for generated CSS
    """
    import re
    
    with open(template_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Map scheme keys to CSS variable names and replace
    replacements = {
        '--primary-purple': color_scheme.get('primary', '#6B2C91'),
        '--secondary-purple': color_scheme.get('secondary', '#9B59B6'),
        '--accent-pink': color_scheme.get('accent', '#FF6B9D'),
        '--text-dark': color_scheme.get('text', '#2C3E50'),
        '--light-purple': color_scheme.get('light', '#E8EAF0')
    }
    
    for css_var, color_value in replacements.items():
        css_content = re.sub(
            f"{css_var}: #[0-9A-Fa-f]{{6}};",
            f"{css_var}: {color_value};",
            css_content
        )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(css_content)


def get_color_scheme(scheme_name: str, cv_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Get color scheme dictionary by name from cv_config.
    
    Args:
        scheme_name: Name of color scheme (e.g., "creative_purple")
        cv_config: CV configuration dictionary
        
    Returns:
        Color scheme dictionary
        
    Raises:
        ValueError: If scheme_name doesn't exist
    """
    color_schemes = cv_config.get('color_schemes', {})
    
    if scheme_name not in color_schemes:
        available = ', '.join(color_schemes.keys())
        raise ValueError(
            f"Color scheme '{scheme_name}' not found.\n"
            f"Available schemes: {available}"
        )
    
    return color_schemes[scheme_name]
