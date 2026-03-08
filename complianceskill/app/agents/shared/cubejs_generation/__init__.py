"""
CubeJS Schema Generation — shared node for CSOD and DT workflows.

Generates Cube.js schema files from gold SQL models and metric recommendations.
"""
from .node import cubejs_schema_generation_node
from .parser import parse_cube_js_response, validate_cube_schema
from .example_loader import load_examples_for_domain

__all__ = [
    "cubejs_schema_generation_node",
    "parse_cube_js_response",
    "validate_cube_schema",
    "load_examples_for_domain",
]
