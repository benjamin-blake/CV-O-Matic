"""
CV Processors Module
Contains all data processing functions extracted from original generators.
Handles date formatting, text truncation, skills extraction, and data preparation.
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime


def generate_initials(name: str) -> str:
    """
    Generate initials from a full name.
    
    Args:
        name: Full name (e.g., "Sherlock Holmes")
        
    Returns:
        Initials (e.g., "SH")
    """
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    elif len(parts) == 1:
        return parts[0][0].upper()
    return ""


def format_date_range(start_date: str, end_date: str) -> str:
    """
    Format a date range for display on CV.
    
    Args:
        start_date: Start date string (e.g., "Apr 2025")
        end_date: End date string (e.g., "present" or "May 2023")
        
    Returns:
        Formatted date range (e.g., "Apr 2025 - Present")
    """
    if end_date.lower() == "present":
        return f"{start_date} - Present"
    return f"{start_date} - {end_date}"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length, trying to break at word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating (default "...")
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    # Reserve space for suffix
    target_length = max_length - len(suffix)
    
    # Find the last space before target_length
    truncated = text[:target_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


def prepare_experience_data(
    roles: List[Dict],
    max_total_chars: int = 2400
) -> List[Dict[str, Any]]:
    """
    Prepare experience data for template with simple sequential truncation.
    Ensures all roles appear with at least one highlight (MANDATORY).
    
    Args:
        roles: List of role dictionaries
        max_total_chars: Maximum total characters across all highlights
        
    Returns:
        List of processed role dictionaries
    """
    # Sort roles by start_date in reverse chronological order (newest first)
    from datetime import datetime
    
    def parse_date(date_str: str) -> datetime:
        """Parse date string like 'Apr 2025' or 'present'."""
        if date_str.lower() == 'present':
            return datetime.now()
        try:
            return datetime.strptime(date_str, '%b %Y')
        except:
            return datetime.min
    
    sorted_roles = sorted(roles, key=lambda r: parse_date(r.get('start_date', '')), reverse=True)
    
    processed_roles = []
    remaining_chars = max_total_chars
    roles_without_highlights = []
    
    # First pass: Add highlights sequentially until running out of space
    for role in sorted_roles:
        processed_role = {
            'company': role.get('company', ''),
            'position': role.get('position', ''),
            'location': role.get('location', ''),
            'date_range': format_date_range(
                role.get('start_date', ''),
                role.get('end_date', '')
            ),
            'context': role.get('context', ''),
            'scale': role.get('scale', ''),
            'highlights': []
        }
        
        role_highlights = role.get('highlights', [])
        
        # Add highlights while space available
        for highlight in role_highlights:
            highlight_len = len(highlight)
            
            if remaining_chars >= highlight_len:
                processed_role['highlights'].append(highlight)
                remaining_chars -= highlight_len
            elif remaining_chars > 100:  # Truncate last one
                truncated = truncate_text(highlight, remaining_chars)
                processed_role['highlights'].append(truncated)
                remaining_chars = 0
                break
            else:
                break
        
        # Track roles without highlights for second pass
        if not processed_role['highlights'] and role_highlights:
            roles_without_highlights.append((processed_role, role_highlights[0]))
        
        processed_roles.append(processed_role)
    
    # Second pass: Ensure EVERY role has at least 1 highlight (MANDATORY)
    if roles_without_highlights:
        min_chars_per_role = 150
        chars_needed = len(roles_without_highlights) * min_chars_per_role
        
        # If not enough space, steal from roles with most highlights
        if remaining_chars < chars_needed:
            roles_by_highlights = sorted(
                [(i, r) for i, r in enumerate(processed_roles) if r['highlights']],
                key=lambda x: len(x[1]['highlights']),
                reverse=True
            )
            
            for role_idx, role_data in roles_by_highlights:
                if remaining_chars >= chars_needed:
                    break
                if len(role_data['highlights']) > 1:
                    removed = role_data['highlights'].pop()
                    remaining_chars += len(removed)
        
        # Add minimum highlight to roles that need it
        for processed_role, first_highlight in roles_without_highlights:
            if remaining_chars >= min_chars_per_role:
                truncated = truncate_text(first_highlight, min_chars_per_role)
                processed_role['highlights'].append(truncated)
                remaining_chars -= len(truncated)
            elif remaining_chars > 50:
                truncated = truncate_text(first_highlight, remaining_chars)
                processed_role['highlights'].append(truncated)
                remaining_chars = 0
    
    return processed_roles


def prepare_education_data(
    education: List[Dict],
    max_total_chars: int = 400
) -> List[Dict[str, Any]]:
    """
    Prepare education data for template, enforcing character limits.
    
    Args:
        education: List of education dictionaries
        max_total_chars: Maximum total characters for education section
        
    Returns:
        List of processed education dictionaries
    """
    processed_education = []
    total_chars = 0
    
    for edu in education:
        processed_edu = {
            'institution': edu.get('institution', ''),
            'degree': edu.get('degree', ''),
            'area': edu.get('area', ''),
            'classification': edu.get('classification', ''),
            'date_range': format_date_range(
                edu.get('start_date', ''),
                edu.get('end_date', '')
            ),
            'highlights': []
        }
        
        # Calculate base entry size (institution, degree, dates)
        base_text = f"{processed_edu['institution']} {processed_edu['degree']} {processed_edu['date_range']}"
        base_len = len(base_text)
        
        if total_chars + base_len > max_total_chars:
            break  # Skip this education entry
        
        total_chars += base_len
        
        # Add highlights if space permits
        for highlight in edu.get('highlights', []):
            highlight_len = len(highlight)
            if total_chars + highlight_len <= max_total_chars:
                processed_edu['highlights'].append(highlight)
                total_chars += highlight_len
            else:
                remaining = max_total_chars - total_chars
                if remaining > 50:
                    truncated = truncate_text(highlight, remaining)
                    processed_edu['highlights'].append(truncated)
                    total_chars += len(truncated)
                break
        
        processed_education.append(processed_edu)
    
    return processed_education
