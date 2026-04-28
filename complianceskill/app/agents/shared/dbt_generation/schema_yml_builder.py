"""
Schema YML Builder — renders gold_cube_schema.yml.j2.

Produces the dbt schema.yml file with column definitions and tests.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .models import DbtGenerateRequest

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def build_schema_yml(req: DbtGenerateRequest) -> str:
    """Render the dbt schema.yml for the given request."""
    description = req.description or f"Gold cube for dashboard {req.dashboard_id}"
    template = _env.get_template("gold_cube_schema.yml.j2")
    return template.render(
        model_name=req.model_name,
        description=description,
        dashboard_id=req.dashboard_id,
        grain=req.grain.value,
        dimensions=req.dimensions,
        metrics=req.metrics,
    )
