"""
Template manager for data source executors.
This module provides functionality to discover, load, and manage data source templates.
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, Type, List, Optional
from .base_template import BaseTemplate


class TemplateManager:
    """
    Manages data source templates and provides dynamic discovery capabilities.
    
    This class allows you to:
    - Discover available templates automatically
    - Load templates dynamically
    - Register custom templates
    - Validate template implementations
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the template manager.
        
        Args:
            template_dir: Directory containing template files. 
                         Defaults to the templates subdirectory.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = template_dir
        self.templates: Dict[str, Type[BaseTemplate]] = {}
        self.template_instances: Dict[str, BaseTemplate] = {}
        
        # Auto-discover templates
        self._discover_templates()
    
    def _discover_templates(self):
        """Automatically discover available templates in the templates directory."""
        if not self.template_dir.exists():
            return
        
        # Try to import from the templates package directly
        try:
            from .templates import TEMPLATE_REGISTRY
            for template_name, template_class in TEMPLATE_REGISTRY.items():
                self.templates[template_name] = template_class
                print(f"✅ Loaded template from registry: {template_name}")
        except ImportError as e:
            print(f"⚠️  Could not import from templates package: {e}")
            # Fallback to dynamic discovery
            self._discover_templates_dynamic()
    
    def _discover_templates_dynamic(self):
        """Fallback method for dynamic template discovery."""
        # Look for Python files in the templates directory
        for py_file in self.template_dir.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue
            
            try:
                # Import directly from the file path
                import importlib.util
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find template classes in the module
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BaseTemplate) and 
                        obj != BaseTemplate):
                        
                        template_name = obj().data_source_name
                        self.templates[template_name] = obj
                        print(f"✅ Discovered template: {template_name} (dynamic method)")
                        
            except Exception as e:
                print(f"⚠️  Dynamic discovery failed for {py_file}: {e}")
    
    def register_template(self, name: str, template_class: Type[BaseTemplate]):
        """
        Register a custom template.
        
        Args:
            name: Template name
            template_class: Template class that inherits from BaseTemplate
        """
        if not issubclass(template_class, BaseTemplate):
            raise ValueError(f"Template class must inherit from BaseTemplate")
        
        self.templates[name] = template_class
        print(f"✅ Registered custom template: {name}")
    
    def get_template(self, name: str) -> Optional[BaseTemplate]:
        """
        Get a template instance by name.
        
        Args:
            name: Template name
            
        Returns:
            Template instance or None if not found
        """
        if name not in self.templates:
            return None
        
        if name not in self.template_instances:
            # Create template instance
            template_class = self.templates[name]
            template_path = self.template_dir / f"{name}_template.py"
            
            # Check if the original template file exists
            if not template_path.exists():
                # Look for the template file in the parent directory
                parent_template_path = self.template_dir.parent / f"{name}_template.py"
                if parent_template_path.exists():
                    template_path = parent_template_path
                else:
                    raise FileNotFoundError(f"Template file not found for {name}")
            
            self.template_instances[name] = template_class(template_path)
        
        return self.template_instances[name]
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def get_template_info(self, name: str) -> Optional[Dict]:
        """
        Get information about a template.
        
        Args:
            name: Template name
            
        Returns:
            Dictionary with template information or None if not found
        """
        template = self.get_template(name)
        if not template:
            return None
        
        return {
            "name": template.data_source_name,
            "dependencies": template.required_dependencies,
            "connection_parameters": template.connection_parameters,
            "config_schema": template.get_config_schema()
        }
    
    def validate_template(self, name: str) -> bool:
        """
        Validate that a template is properly implemented.
        
        Args:
            name: Template name
            
        Returns:
            True if template is valid, False otherwise
        """
        try:
            template = self.get_template(name)
            if not template:
                return False
            
            # Check that all required methods are implemented
            required_methods = [
                'data_source_name',
                'required_dependencies', 
                'connection_parameters',
                'query_placeholder',
                'apply_connection_config'
            ]
            
            for method in required_methods:
                if not hasattr(template, method):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def create_template(self, name: str, query: str, config: Optional[Dict] = None) -> Optional[str]:
        """
        Create executable code from a template.
        
        Args:
            name: Template name
            query: SQL query to execute
            config: Optional connection configuration
            
        Returns:
            Generated executable code or None if template not found
        """
        template = self.get_template(name)
        if not template:
            return None
        
        # Validate configuration if provided
        if config and not template.validate_config(config):
            raise ValueError(f"Invalid configuration for template {name}")
        
        return template.generate_executable(query, config)
    
    def get_requirements(self, name: str) -> List[str]:
        """
        Get required dependencies for a template.
        
        Args:
            name: Template name
            
        Returns:
            List of required Python packages
        """
        template = self.get_template(name)
        if not template:
            return []
        
        return template.required_dependencies
    
    def get_config_schema(self, name: str) -> Optional[Dict]:
        """
        Get JSON schema for template configuration.
        
        Args:
            name: Template name
            
        Returns:
            JSON schema dictionary or None if template not found
        """
        template = self.get_template(name)
        if not template:
            return None
        
        return template.get_config_schema()


# Global template manager instance
template_manager = TemplateManager()
