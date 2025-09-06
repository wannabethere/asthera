"""
Base template class for data source executors.
This class defines the interface that all data source templates must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseTemplate(ABC):
    """
    Abstract base class for data source templates.
    
    All data source templates must inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, template_path: Path):
        """
        Initialize the template.
        
        Args:
            template_path: Path to the template file
        """
        self.template_path = template_path
        self.template_content = self._load_template()
    
    def _load_template(self) -> str:
        """Load the template content from file."""
        with open(self.template_path, 'r') as f:
            return f.read()
    
    @property
    @abstractmethod
    def data_source_name(self) -> str:
        """Return the name of the data source (e.g., 'postgres', 'trino', 'mysql')."""
        pass
    
    @property
    @abstractmethod
    def required_dependencies(self) -> list:
        """Return list of required Python packages for this data source."""
        pass
    
    @property
    @abstractmethod
    def connection_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Return connection parameter definitions.
        
        Returns:
            Dict mapping parameter names to their metadata:
            {
                "host": {"default": "localhost", "type": "str", "required": True},
                "port": {"default": 5432, "type": "int", "required": False},
                ...
            }
        """
        pass
    
    @property
    @abstractmethod
    def query_placeholder(self) -> str:
        """Return the placeholder string that should be replaced with the actual query."""
        pass
    
    @abstractmethod
    def apply_connection_config(self, content: str, config: Dict[str, Any]) -> str:
        """
        Apply connection configuration to the template content.
        
        Args:
            content: Template content
            config: Connection configuration dictionary
            
        Returns:
            Modified content with connection configuration applied
        """
        pass
    
    def generate_executable(self, query: str, config: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate executable code from the template.
        
        Args:
            query: SQL query to execute
            config: Optional connection configuration
            
        Returns:
            Generated executable code
        """
        content = self.template_content
        
        # Replace query placeholder
        content = content.replace(self.query_placeholder, f'query = """{query}"""')
        
        # Apply connection configuration if provided
        if config:
            content = self.apply_connection_config(content, config)
        
        return content
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate connection configuration.
        
        Args:
            config: Connection configuration dictionary
            
        Returns:
            True if configuration is valid, False otherwise
        """
        required_params = [
            param for param, meta in self.connection_parameters.items() 
            if meta.get("required", False)
        ]
        
        for param in required_params:
            if param not in config:
                return False
        
        return True
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default connection configuration values."""
        return {
            param: meta.get("default", None)
            for param, meta in self.connection_parameters.items()
        }
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get JSON schema for connection configuration validation."""
        properties = {}
        required = []
        
        for param, meta in self.connection_parameters.items():
            properties[param] = {
                "type": meta.get("type", "string"),
                "description": meta.get("description", f"{param} parameter"),
                "default": meta.get("default")
            }
            
            if meta.get("required", False):
                required.append(param)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
