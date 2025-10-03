"""
Utility module for handling project-specific instructions.
"""
import json
import os
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ProjectInstructionsManager:
    """Manages project-specific instructions for SQL generation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the ProjectInstructionsManager.
        
        Args:
            config_path: Path to the project instructions JSON file.
                        If None, uses default path.
        """
        if config_path is None:
            # Default path relative to this file
            current_dir = Path(__file__).parent
            config_path = current_dir.parent / "config" / "project_instructions.json"
        
        self.config_path = Path(config_path)
        self._instructions_cache: Optional[Dict] = None
    
    def _load_instructions(self) -> Dict:
        """Load instructions from the JSON file."""
        if self._instructions_cache is not None:
            return self._instructions_cache
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._instructions_cache = json.load(f)
        except FileNotFoundError:
            # No fallback to default - return empty config
            logger.warning(f"Project instructions file not found: {self.config_path}")
            self._instructions_cache = {}
        except json.JSONDecodeError as e:
            # No fallback to default - return empty config
            logger.error(f"Invalid JSON in project instructions file: {e}")
            self._instructions_cache = {}
        
        return self._instructions_cache
    
    def get_instructions(self, project_id: str) -> str:
        """
        Get project-specific instructions for a given project ID.
        
        Args:
            project_id: The project identifier
            
        Returns:
            String containing the project-specific instructions
        """
        if not project_id:
            raise ValueError("project_id is required and cannot be empty or None")
            
        instructions_config = self._load_instructions()
        
        # Check if project-specific instructions exist
        if project_id in instructions_config:
            return instructions_config[project_id].get("instructions", "")
        
        # If no project-specific instructions found, return empty string
        # This ensures we don't fall back to "default" when project_id is always provided
        logger.warning(f"No instructions found for project_id: {project_id}")
        return ""
    
    def append_instructions_to_query(self, query: str, project_id: str) -> str:
        """
        Append project-specific instructions to the user query.
        
        Args:
            query: The original user query
            project_id: The project identifier
            
        Returns:
            The query with appended instructions
        """
        instructions = self.get_instructions(project_id)
        
        if not instructions:
            return query
        
        # Append instructions to the query
        return f"{query}\n\n{instructions}"

# Global instance for easy access
project_instructions_manager = ProjectInstructionsManager()
