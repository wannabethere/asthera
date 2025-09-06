"""
Templates package for data source executors.
This package contains template implementations for various data sources.
"""

from .postgres_jinja_template import PostgreSQLTemplate
from .trino_jinja_template import TrinoTemplate

# Registry of available templates
TEMPLATE_REGISTRY = {
    "postgresql": PostgreSQLTemplate,
    "trino": TrinoTemplate
}

__all__ = ["PostgreSQLTemplate", "TrinoTemplate", "TEMPLATE_REGISTRY"]
