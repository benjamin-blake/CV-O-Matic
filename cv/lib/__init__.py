"""
CV Generation Library
Shared modules for CV generation system.
"""

from .cv_data_loader import CVDataLoader
from .cv_processors import (
    generate_initials,
    format_date_range,
    truncate_text,
    prepare_experience_data,
    prepare_education_data,
)
from .cv_css_generator import generate_css_from_scheme, get_color_scheme

__all__ = [
    'CVDataLoader',
    'generate_initials',
    'format_date_range',
    'truncate_text',
    'prepare_experience_data',
    'prepare_education_data',
    'generate_css_from_scheme',
    'get_color_scheme',
]
