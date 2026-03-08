"""
CubeJS schema output parsing and validation.
"""
import re
import logging
from typing import List, TypedDict

logger = logging.getLogger(__name__)


class CubeSchemaFile(TypedDict, total=False):
    """Output schema for a generated Cube.js file."""

    cube_name: str
    filename: str
    content: str
    source_tables: List[str]
    measures: List[str]
    dimensions: List[str]


def parse_cube_js_response(raw: str) -> List[CubeSchemaFile]:
    """
    Split LLM output into individual cube files.

    Detection strategy:
      1. Look for `cube(` declarations — each is a separate cube
      2. Split on `// ───` comment separators (the LLM is prompted to emit these)
      3. Extract cube name from `cube(`CubeName` `
      4. Build filename as `{CubeName}.js`
    """
    # Strip markdown fences if present
    content = raw.strip()
    for fence in ("```js", "```javascript", "```"):
        if content.startswith(fence):
            content = content[len(fence) :].strip()
        if content.endswith("```"):
            content = content[:-3].strip()

    results: List[CubeSchemaFile] = []

    # Strategy 1: Split on comment separators
    parts = re.split(r"//\s*─{3,}", content)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        cubes = _extract_cubes_from_block(part)
        results.extend(cubes)

    # Strategy 2: If no separators, look for cube() declarations
    if not results:
        results = _extract_cubes_from_block(content)

    return results


def _extract_cubes_from_block(block: str) -> List[CubeSchemaFile]:
    """Extract cube definitions from a block of JS."""
    results: List[CubeSchemaFile] = []
    cube_pattern = re.compile(r"cube\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*\{", re.DOTALL)

    for match in cube_pattern.finditer(block):
        cube_name = match.group(1)
        # Find the matching closing brace (simplified: take from match to next cube or end)
        start = match.start()
        # Find end: next cube declaration or end of block
        next_match = cube_pattern.search(block, match.end())
        end = next_match.start() if next_match else len(block)
        cube_content = block[start:end].strip()

        # Extract source tables, measures, dimensions from content
        source_tables = _extract_sql_table(cube_content)
        measures = _extract_measure_names(cube_content)
        dimensions = _extract_dimension_names(cube_content)

        results.append(
            CubeSchemaFile(
                cube_name=cube_name,
                filename=f"{cube_name}.js",
                content=cube_content,
                source_tables=[source_tables] if source_tables else [],
                measures=measures,
                dimensions=dimensions,
            )
        )

    return results


def _extract_sql_table(content: str) -> str:
    """Extract sql_table value from cube content."""
    m = re.search(r"sql_table\s*:\s*['\"`]([^'\"`]+)['\"`]", content)
    return m.group(1) if m else ""


def _extract_measure_names(content: str) -> List[str]:
    """Extract measure names from measures block."""
    measures = []
    measures_block = re.search(r"measures\s*:\s*\[(.*?)\](?=\s*,?\s*(?:dimensions|joins|preAggregations|$))", content, re.DOTALL)
    if measures_block:
        for m in re.finditer(r"(\w+)\s*:\s*\{", measures_block.group(1)):
            measures.append(m.group(1))
    return measures


def _extract_dimension_names(content: str) -> List[str]:
    """Extract dimension names from dimensions block."""
    dimensions = []
    dims_block = re.search(r"dimensions\s*:\s*\[(.*?)\](?=\s*,?\s*(?:measures|joins|preAggregations|$))", content, re.DOTALL)
    if dims_block:
        for m in re.finditer(r"(\w+)\s*:\s*\{", dims_block.group(1)):
            dimensions.append(m.group(1))
    return dimensions


def validate_cube_schema(content: str, cube_name: str) -> List[str]:
    """
    Lightweight validation — returns list of error strings (empty = valid).

    Checks:
      - cube() declaration present
      - sql_table present
      - At least one measure
      - At least one time dimension
      - connectionId dimension present
      - No raw jsonb column in a measure sql (warn on jsonb without ->>'key')
    """
    errors: List[str] = []

    if "cube(" not in content:
        errors.append(f"{cube_name}: Missing cube() declaration")

    if "sql_table" not in content:
        errors.append(f"{cube_name}: Missing sql_table")

    if "measures" not in content or "measures:" not in content.lower():
        errors.append(f"{cube_name}: Missing measures block")
    elif not re.search(r"measures\s*:\s*\[\s*\w+", content):
        errors.append(f"{cube_name}: No measures defined")

    if "connectionId" not in content and "connection_id" not in content:
        errors.append(f"{cube_name}: Missing connectionId dimension (tenant isolation key)")

    # Check for time dimension
    if not re.search(r"type\s*:\s*['\"]time['\"]|timeDimension|weekStart|monthStart", content):
        errors.append(f"{cube_name}: No time dimension found")

    # Warn on raw jsonb in measure sql
    if re.search(r"measures.*?sql\s*:.*?jsonb(?!\s*->>)", content, re.DOTALL | re.IGNORECASE):
        errors.append(f"{cube_name}: Possible raw jsonb in measure — use ->>'key'::numeric for extraction")

    return errors
