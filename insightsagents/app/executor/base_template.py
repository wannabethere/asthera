"""
Base template class for data source executors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
import jinja2

# Base Template Class
class BaseTemplate(ABC):
    """Abstract base class for data source templates."""
    
    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = template_path
        self._jinja_env = None
        self._jinja_template = None
    
    @property
    @abstractmethod
    def data_source_name(self) -> str:
        """Return the name of the data source."""
        pass
    
    @property
    @abstractmethod
    def required_dependencies(self) -> List[str]:
        """Return list of required Python packages."""
        pass
    
    @property
    @abstractmethod
    def connection_parameters(self) -> List[str]:
        """Return list of required connection parameters."""
        pass
    
    @property
    @abstractmethod
    def query_placeholder(self) -> str:
        """Return the placeholder string for SQL queries in templates."""
        pass
    
    @property
    @abstractmethod
    def jinja_template_content(self) -> str:
        """Return the Jinja template content as a string."""
        pass
    
    def _setup_jinja_environment(self):
        """Setup Jinja2 environment with custom filters."""
        if self._jinja_env is None:
            self._jinja_env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # Add custom filters
            self._jinja_env.filters['quote_string'] = lambda x: f'"{x}"' if x else '""'
            self._jinja_env.filters['default_port'] = self._default_port_filter
    
    def _default_port_filter(self, value, default_port):
        """Custom Jinja filter for handling default ports."""
        return value if value is not None else default_port
    
    def get_jinja_template(self) -> jinja2.Template:
        """Get the compiled Jinja template."""
        if self._jinja_template is None:
            self._setup_jinja_environment()
            self._jinja_template = self._jinja_env.from_string(self.jinja_template_content)
        return self._jinja_template
    
    def generate_executable(self, query: str, config: Optional[Dict[str, Any]] = None) -> str:
        """Generate executable Python code from the template."""
        template = self.get_jinja_template()
        
        # Prepare template context
        context = {
            'query': query,
            'config': config or {},
        }
        
        # Add default configuration values
        context.update(self.get_default_config())
        
        # Override with provided config
        if config:
            context.update(config)
        
        return template.render(**context)
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values for the template."""
        return {}
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate the provided configuration."""
        required_params = self.connection_parameters
        for param in required_params:
            if param not in config or config[param] is None:
                return False
        return True
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get JSON schema for the configuration."""
        properties = {}
        required = []
        
        for param in self.connection_parameters:
            properties[param] = {
                "type": "string",
                "description": f"{param} for {self.data_source_name} connection"
            }
            required.append(param)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": True
        }
