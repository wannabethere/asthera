"""
Utility module for handling project-specific instructions.
"""
import json
import os
from typing import Dict, Optional
from pathlib import Path

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
            # Fallback to default instructions if file not found
            self._instructions_cache = {
                "default": {
                    "instructions": "Please generate accurate SQL queries based on the provided schema and requirements."
                }
            }
        except json.JSONDecodeError as e:
            # Fallback to default instructions if JSON is malformed
            self._instructions_cache = {
                "default": {
                    "instructions": "Please generate accurate SQL queries based on the provided schema and requirements."
                }
            }
        
        return self._instructions_cache
    
    def get_instructions(self, project_id: str) -> str:
        """
        Get project-specific instructions for a given project ID.
        
        Args:
            project_id: The project identifier
            
        Returns:
            String containing the project-specific instructions
        """
        instructions_config = self._load_instructions()
        
        # Check if project-specific instructions exist
        if project_id in instructions_config:
            return instructions_config[project_id].get("instructions", "")
        
        # Fallback to default instructions
        return instructions_config.get("default", {}).get("instructions", "")
    
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
