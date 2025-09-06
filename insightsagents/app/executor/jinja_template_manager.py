"""
Enhanced template manager for data source executors with Jinja2 support.
This module provides functionality to discover, load, and manage data source templates
using Jinja2 templating engine.
"""

import importlib
import inspect
from pathlib import Path
from typing import Dict, Type, List, Optional, Any
import jinja2
from app.executor.base_template import BaseTemplate
from app.executor.templates.trino_jinja_template import TrinoTemplate
from app.executor.templates.postgres_jinja_template import PostgreSQLTemplate

# Template Manager
class TemplateManager:
    """Template manager with built-in templates."""
    
    def __init__(self):
        self.templates: Dict[str, Type[BaseTemplate]] = {}
        self.template_instances: Dict[str, BaseTemplate] = {}
        
        # Register built-in templates
        self._register_builtin_templates()
    
    def _register_builtin_templates(self):
        """Register built-in templates."""
        self.templates["trino"] = TrinoTemplate
        self.templates["postgresql"] = PostgreSQLTemplate
        print("✅ Registered built-in templates: trino, postgresql")
    
    def register_template(self, name: str, template_class: Type[BaseTemplate]):
        """Register a custom template class."""
        if not issubclass(template_class, BaseTemplate):
            raise ValueError(f"Template class must inherit from BaseTemplate")
        
        self.templates[name] = template_class
        
        # Clear cached instance if it exists
        if name in self.template_instances:
            del self.template_instances[name]
        
        print(f"✅ Registered custom template: {name}")
    
    def get_template(self, name: str) -> Optional[BaseTemplate]:
        """Get a template instance by name."""
        if name not in self.templates:
            return None
        
        if name not in self.template_instances:
            template_class = self.templates[name]
            self.template_instances[name] = template_class()
        
        return self.template_instances[name]
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def create_executable(self, name: str, query: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Create executable Python code from a template."""
        template = self.get_template(name)
        if not template:
            return None
        
        # Merge with default configuration
        final_config = template.get_default_config().copy()
        if config:
            final_config.update(config)
        
        # Validate configuration
        if not template.validate_config(final_config):
            raise ValueError(f"Invalid configuration for template {name}")
        
        # Generate executable code
        try:
            return template.generate_executable(query, final_config)
        except Exception as e:
            raise RuntimeError(f"Failed to generate executable for template {name}: {e}")
    
    def get_template_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a template."""
        template = self.get_template(name)
        if not template:
            return None
        
        return {
            "name": template.data_source_name,
            "dependencies": template.required_dependencies,
            "connection_parameters": template.connection_parameters,
            "config_schema": template.get_config_schema(),
            "default_config": template.get_default_config(),
            "query_placeholder": template.query_placeholder
        }
    
    def get_requirements(self, name: str) -> List[str]:
        """Get required dependencies for a template."""
        template = self.get_template(name)
        if not template:
            return []
        
        return template.required_dependencies
    
    def get_config_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for template configuration."""
        template = self.get_template(name)
        if not template:
            return None
        
        return template.get_config_schema()
    
    def preview_template(self, name: str, query: str = "SELECT 1", config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate a preview of the executable code without executing it."""
        return self.create_executable(name, query, config)
    
    def export_template(self, name: str, file_path: Path, query: str, config: Dict[str, Any]):
        """Export generated code to a Python file."""
        code = self.create_executable(name, query, config)
        if code is None:
            raise ValueError(f"Template {name} not found")
        
        file_path.write_text(code)
        print(f"✅ Exported {name} template to {file_path}")
    
    def get_requirements(self, name: str) -> List[str]:
        """Get required dependencies for a template."""
        template = self.get_template(name)
        if not template:
            return []
        
        return template.required_dependencies
    
    def get_config_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for template configuration."""
        template = self.get_template(name)
        if not template:
            return None
        
        return template.get_config_schema()
    
    def preview_template(self, name: str, query: str = "SELECT 1", config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate a preview of the executable code without executing it."""
        return self.create_executable(name, query, config)
    
    def validate_template(self, name: str) -> bool:
        """Validate that a template is properly implemented."""
        try:
            template = self.get_template(name)
            if not template:
                return False
            
            # Check required properties
            required_properties = [
                'data_source_name',
                'required_dependencies', 
                'connection_parameters',
                'query_placeholder',
                'jinja_template_content'
            ]
            
            for prop in required_properties:
                if not hasattr(template, prop):
                    return False
            
            # Try to compile Jinja template
            try:
                template.get_jinja_template()
            except Exception:
                return False
            
            return True
            
        except Exception:
            return False
    def get_template_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded templates."""
        stats = {
            "total_templates": len(self.templates),
            "template_names": list(self.templates.keys()),
            "instantiated_templates": len(self.template_instances),
            "templates_by_type": {},
            "templates_by_dependency": {}
        }
        
        # Categorize templates by their dependencies
        for name, template_class in self.templates.items():
            template_instance = template_class()
            deps = template_instance.required_dependencies
            
            # Group by each dependency
            for dep in deps:
                if dep not in stats["templates_by_dependency"]:
                    stats["templates_by_dependency"][dep] = []
                stats["templates_by_dependency"][dep].append(name)
            
            # Group by data source type
            data_source = template_instance.data_source_name
            if data_source not in stats["templates_by_type"]:
                stats["templates_by_type"][data_source] = []
            stats["templates_by_type"][data_source].append(name)
        
        return stats


# Global template manager instance
template_manager = TemplateManager()


# Convenience functions for backward compatibility and ease of use
def create_executable(template_name: str, query: str, config: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to create executable code."""
    result = template_manager.create_executable(template_name, query, config)
    if result is None:
        raise ValueError(f"Template '{template_name}' not found")
    return result


def list_available_templates() -> List[str]:
    """Convenience function to list available templates."""
    return template_manager.list_templates()


def get_template_requirements(template_name: str) -> List[str]:
    """Convenience function to get template requirements."""
    return template_manager.get_requirements(template_name)


def preview_template(template_name: str, sample_query: str = "SELECT 1") -> str:
    """Convenience function to preview a template."""
    result = template_manager.preview_template(template_name, sample_query)
    if result is None:
        raise ValueError(f"Template '{template_name}' not found")
    return result


def get_template_info(template_name: str) -> Dict[str, Any]:
    """Convenience function to get template information."""
    result = template_manager.get_template_info(template_name)
    if result is None:
        raise ValueError(f"Template '{template_name}' not found")
    return result


def validate_template(template_name: str) -> bool:
    """Convenience function to validate a template."""
    return template_manager.validate_template(template_name)


def export_template(template_name: str, file_path: Path, query: str, config: Dict[str, Any]):
    """Convenience function to export a template."""
    template_manager.export_template(template_name, file_path, query, config)

def get_template_stats() -> Dict[str, Any]:
    """Convenience function to get template statistics."""
    return template_manager.get_template_stats()