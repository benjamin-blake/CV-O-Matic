"""
CV Data Loader Module
Handles loading and merging of CV data from multiple YAML files,
achievement filtering, and posting-specific configuration.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class CVDataLoader:
    """Loads and manages CV data from split YAML files."""
    
    def __init__(self, base_dir: Path):
        """
        Initialize the CV data loader.
        
        Args:
            base_dir: Base directory containing CV YAML files
        """
        self.base_dir = Path(base_dir)
        self.core_data_file = self.base_dir / "cv_core_data.yaml"
        self.achievements_file = self.base_dir / "cv_achievements.yaml"
        self.config_file = self.base_dir / "cv_config.yaml"
        
        # Validate required files exist
        self._validate_files()
    
    def _validate_files(self) -> None:
        """Validate that all required YAML files exist."""
        missing_files = []
        for file_path in [self.core_data_file, self.achievements_file, self.config_file]:
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        if missing_files:
            raise FileNotFoundError(
                f"Missing required CV data files:\n" + "\n".join(missing_files)
            )
    
    def load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Load a YAML file and return its contents.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            Dictionary containing YAML data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load {file_path}: {str(e)}")
    
    def load_all_data(self) -> Dict[str, Any]:
        """
        Load all CV data files and merge into single dictionary.
        
        Returns:
            Merged dictionary containing all CV data
        """
        core_data = self.load_yaml_file(self.core_data_file)
        achievements_data = self.load_yaml_file(self.achievements_file)
        config_data = self.load_yaml_file(self.config_file)
        
        # Merge into single structure
        merged_data = {
            **core_data,
            'achievements': achievements_data.get('achievements', []),
            'tag_taxonomy': achievements_data.get('tag_taxonomy', {}),
            'all_tags': achievements_data.get('all_tags', []),
            'cv_config': config_data,
        }
        
        return merged_data
    
    def get_achievement_by_id(self, achievement_id: str, achievements: List[Dict]) -> Optional[Dict]:
        """
        Get a single achievement by its ID.
        
        Args:
            achievement_id: Achievement ID to find
            achievements: List of all achievements
            
        Returns:
            Achievement dictionary or None if not found
        """
        for achievement in achievements:
            if achievement.get('id') == achievement_id:
                return achievement
        return None
    
    def get_achievements_by_ids(self, achievement_ids: List[str], achievements: List[Dict]) -> List[Dict]:
        """
        Get multiple achievements by their IDs, maintaining order.
        
        Args:
            achievement_ids: List of achievement IDs to retrieve
            achievements: List of all achievements
            
        Returns:
            List of achievement dictionaries in the order specified
        """
        result = []
        for aid in achievement_ids:
            achievement = self.get_achievement_by_id(aid, achievements)
            if achievement:
                result.append(achievement)
            else:
                print(f"Warning: Achievement ID '{aid}' not found in library")
        return result
    
    def filter_experience_by_achievement_ids(
        self,
        roles: List[Dict],
        achievement_ids: List[str],
        achievements: List[Dict]
    ) -> List[Dict]:
        """
        Replace ALL role highlights with selected achievements.
        Each role gets only achievements that match its role_id.
        
        Args:
            roles: List of role dictionaries from core data
            achievement_ids: List of selected achievement IDs
            achievements: Full achievement library
            
        Returns:
            List of roles with highlights replaced by selected achievements
        """
        # Get selected achievements
        selected_achievements = self.get_achievements_by_ids(achievement_ids, achievements)
        
        # Create mapping of role_id to achievements
        role_achievements = {}
        for achievement in selected_achievements:
            role_id = achievement.get('role_id')
            if role_id:
                if role_id not in role_achievements:
                    role_achievements[role_id] = []
                # Convert achievement to highlight format
                highlight = achievement['description']
                if achievement.get('impact'):
                    highlight += f" - {achievement['impact']}"
                role_achievements[role_id].append(highlight)
        
        # Replace highlights for each role
        filtered_roles = []
        for role in roles:
            role_copy = role.copy()
            role_id = role_copy.get('id')
            
            # Replace ALL highlights with selected achievements for this role
            role_copy['highlights'] = role_achievements.get(role_id, [])
            
            filtered_roles.append(role_copy)
        
        return filtered_roles
    
    def load_posting_config(self, posting_path: Path) -> Dict[str, Any]:
        """
        Load posting-specific configuration file.
        FAIL if config.yaml doesn't exist or is missing required fields.
        
        Args:
            posting_path: Path to posting directory
            
        Returns:
            Posting configuration dictionary
            
        Raises:
            FileNotFoundError: If config.yaml doesn't exist
            ValueError: If required fields are missing
        """
        config_file = posting_path / "config.yaml"
        
        if not config_file.exists():
            raise FileNotFoundError(
                f"Posting configuration not found: {config_file}\n"
                f"Create config.yaml with required fields:\n"
                f"  color_scheme: <scheme_name>\n"
                f"  selected_achievement_ids: [...]"
            )
        
        config = self.load_yaml_file(config_file)
        
        # Validate required fields - FAIL FAST
        required_fields = ['color_scheme', 'selected_achievement_ids']
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(
                f"Posting config missing required fields: {', '.join(missing_fields)}\n"
                f"File: {config_file}\n"
                f"Required structure:\n"
                f"  color_scheme: <scheme_name>\n"
                f"  selected_achievement_ids: [...]"
            )
        
        # Validate color_scheme exists in cv_config
        cv_config = self.load_yaml_file(self.config_file)
        available_schemes = list(cv_config.get('color_schemes', {}).keys())
        
        if config['color_scheme'] not in available_schemes:
            raise ValueError(
                f"Invalid color_scheme '{config['color_scheme']}' in {config_file}\n"
                f"Available schemes: {', '.join(available_schemes)}"
            )
        
        # Validate selected_achievement_ids is a list (can be empty)
        if not isinstance(config['selected_achievement_ids'], list):
            raise ValueError(
                f"selected_achievement_ids must be a list in {config_file}"
            )
        
        return config
    
    def merge_posting_data(
        self,
        posting_path: Path,
        core_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Load posting config and merge with core CV data.
        Apply achievement filtering and color scheme selection.
        
        Args:
            posting_path: Path to posting directory
            core_data: Pre-loaded core data (optional, will load if not provided)
            
        Returns:
            Complete CV data dictionary ready for generation
        """
        if core_data is None:
            core_data = self.load_all_data()
        
        # Load posting configuration (FAIL if invalid)
        posting_config = self.load_posting_config(posting_path)
        
        # Filter experience by selected achievements
        filtered_roles = self.filter_experience_by_achievement_ids(
            roles=core_data['roles'],
            achievement_ids=posting_config['selected_achievement_ids'],
            achievements=core_data['achievements']
        )
        
        # Build final data structure
        merged_data = {
            **core_data,
            'roles': filtered_roles,
            'selected_color_scheme': posting_config['color_scheme'],
            'posting_config': posting_config,
        }
        
        return merged_data
