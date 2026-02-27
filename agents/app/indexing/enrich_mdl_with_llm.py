#!/usr/bin/env python3
"""
LLM-powered enrichment for MDL files.
Enriches column descriptions, fixes incorrect types, and generates SQL examples.

Supports processing by layer (bronze/silver/gold) with priority assignment:
- gold: priority 1 (highest)
- silver: priority 2
- bronze: priority 3 (lowest)

Usage:
  # Process all MDL files in a directory
  python enrich_mdl_with_llm.py --mdl-dir /path/to/mdl/files

  # Process by layer from models directory structure
  python enrich_mdl_with_llm.py --by-layer --models-dir /path/to/dbt/models --mdl-dir /path/to/mdl/output

  # Process specific layer
  python enrich_mdl_with_llm.py --by-layer --layer silver --models-dir /path/to/models --mdl-dir /path/to/mdl

  # Process specific connector
  python enrich_mdl_with_llm.py --by-layer --connector qualys --models-dir /path/to/models --mdl-dir /path/to/mdl
"""

import json
import re
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers.string import StrOutputParser
    from langchain_openai import ChatOpenAI
except ImportError:
    print("Error: Required packages not found. Install with: pip install langchain langchain-openai")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Warning: PyYAML not found. YAML-based enrichment will be skipped.")
    yaml = None


from app.settings import get_settings
settings = get_settings()
api_key = settings.OPENAI_API_KEY
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Try to import DbtToMdlConverter for generating MDL files from dbt models
HAS_DBT_CONVERTER = False
DbtToMdlConverter = None

try:
    import sys
    script_dir = Path(__file__).parent
    # The converter is at: genieml/data/dbt_to_mdl/convert_dbt_to_mdl.py
    # From: genieml/agents/app/indexing/enrich_mdl_with_llm.py
    # Path: script_dir.parent.parent.parent / "data" / "dbt_to_mdl"
    converter_path = script_dir.parent.parent.parent / "data" / "dbt_to_mdl"
    
    if converter_path.exists() and (converter_path / "convert_dbt_to_mdl.py").exists():
        sys.path.insert(0, str(converter_path.parent))
        from dbt_to_mdl.convert_dbt_to_mdl import DbtToMdlConverter  # type: ignore
        HAS_DBT_CONVERTER = True
    else:
        # Try absolute path as fallback
        abs_path = Path("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/dbt_to_mdl")
        if abs_path.exists() and (abs_path / "convert_dbt_to_mdl.py").exists():
            sys.path.insert(0, str(abs_path.parent))
            from dbt_to_mdl.convert_dbt_to_mdl import DbtToMdlConverter  # type: ignore
            HAS_DBT_CONVERTER = True
        else:
            print("Warning: DbtToMdlConverter not found. MDL generation from dbt models will be skipped.")
            print(f"  Expected path: {converter_path}")
except ImportError as e:
    HAS_DBT_CONVERTER = False
    print(f"Warning: Could not import DbtToMdlConverter: {e}. MDL generation from dbt models will be skipped.")
except Exception as e:
    HAS_DBT_CONVERTER = False
    print(f"Warning: Error setting up DbtToMdlConverter: {e}. MDL generation from dbt models will be skipped.")
    
# Try to import get_llm, fallback to direct ChatOpenAI if not available
try:
    import os
    import sys
    # Add parent directories to path to find app.core
    script_dir = Path(__file__).parent
    dataservices_dir = script_dir.parent.parent.parent / "dataservices"
    if dataservices_dir.exists():
        sys.path.insert(0, str(dataservices_dir))
    from app.core.dependencies import get_llm
    USE_APP_LLM = True
except ImportError:
    USE_APP_LLM = False
    print("Warning: Could not import app.core.dependencies. Using direct ChatOpenAI.")
    
    def get_llm():
        """Fallback LLM getter using environment variables."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            openai_api_key=api_key
        )


# Type inference mapping
TYPE_PATTERNS = {
    'TIMESTAMP': ['_timestamp', '_at', 'created_at', 'updated_at', 'last_seen', 'first_seen'],
    'DATE': ['_date', 'date_'],
    'BIGINT': ['_id', '_count', '_num', '_size'],
    'DOUBLE': ['_score', '_rate', '_ratio', '_percent', 'severity'],
    'BOOLEAN': ['is_', 'has_', 'enabled', 'hidden', 'deleted'],
    'VARCHAR': []  # Default
}


def infer_correct_type(column_name: str, current_type: str, existing_description: str = "") -> str:
    """Infer correct type from column name and context."""
    col_lower = column_name.lower()
    desc_lower = existing_description.lower()
    
    # Special cases: struct/object fields should be VARCHAR
    if any(word in desc_lower for word in ['struct', 'array', 'object', 'context', 'details', 'info']):
        if current_type in ['TIMESTAMP', 'DATE', 'BIGINT', 'DOUBLE', 'BOOLEAN']:
            return 'VARCHAR'
    
    # Special case: severity is numeric
    if col_lower == 'severity' and 'numeric' in desc_lower or 'score' in desc_lower:
        if current_type == 'VARCHAR':
            return 'DOUBLE'
    
    # Check patterns
    for target_type, patterns in TYPE_PATTERNS.items():
        if any(pattern in col_lower for pattern in patterns):
            # Special handling for VARCHAR fields that might be misclassified
            if target_type in ['TIMESTAMP', 'DATE'] and current_type == 'VARCHAR':
                # Check if description suggests it's actually a timestamp/date
                if any(word in desc_lower for word in ['timestamp', 'date', 'time', 'when']):
                    return target_type
            # Don't override if it's clearly a struct/object
            if target_type in ['TIMESTAMP', 'DATE'] and any(word in desc_lower for word in ['struct', 'array', 'object']):
                continue
            return target_type
    
    # Fix common misclassifications
    if current_type == 'TIMESTAMP' and not any(p in col_lower for p in ['_at', '_timestamp', 'time', 'date', 'seen']):
        # Check if description suggests timestamp
        if not any(word in desc_lower for word in ['timestamp', 'date', 'time', 'when']):
            return 'VARCHAR'
    
    if current_type == 'DATE' and '_date' not in col_lower:
        # Check if description suggests date
        if not any(word in desc_lower for word in ['date', 'when']):
            return 'VARCHAR'
    
    if current_type == 'BIGINT' and not any(p in col_lower for p in ['_id', '_count', '_num', '_size']):
        # Check if description suggests it's not numeric
        if any(word in desc_lower for word in ['struct', 'array', 'object', 'string', 'text']):
            return 'VARCHAR'
    
    return current_type


def to_display_name(name: str) -> str:
    """Convert snake_case to Display Name."""
    return ' '.join(word.capitalize() for word in name.split('_'))


# Layer priority mapping
LAYER_PRIORITY = {
    'gold': 1,
    'silver': 2,
    'bronze': 3
}


def discover_layer_directories(models_dir: Path) -> List[Dict[str, Any]]:
    """
    Discover all layer directories (bronze, silver, gold) and generate metadata.
    
    Returns:
        List of dicts with: subdirectory, schema_name, layer, priority
    """
    discoveries = []
    models_path = Path(models_dir)
    
    # Find all directories containing bronze, silver, or gold
    for layer in ['bronze', 'silver', 'gold']:
        for layer_dir in models_path.rglob(layer):
            if not layer_dir.is_dir():
                continue
            
            # Get relative path from models directory
            rel_path = layer_dir.relative_to(models_path)
            subdirectory = str(rel_path)
            
            # Generate schema name from path
            # e.g., "aws/guardduty/silver" -> "aws_guardduty"
            # e.g., "crowdstrike/vms/gold" -> "crowdstrike_vms"
            parts = rel_path.parts[:-1]  # Remove layer name
            schema_name = "_".join(parts)
            
            # Check if there are any SQL or YAML files in this directory
            has_models = any(layer_dir.glob("*.sql")) or any(layer_dir.glob("*.yaml")) or any(layer_dir.glob("*.yml"))
            
            if has_models:
                discoveries.append({
                    'subdirectory': subdirectory,
                    'schema_name': schema_name,
                    'layer': layer,
                    'priority': LAYER_PRIORITY[layer],
                    'path': layer_dir
                })
    
    # Sort for consistent output
    discoveries.sort(key=lambda x: (x['schema_name'], x['priority']))
    
    return discoveries


def find_yaml_file_for_model(model_name: str, layer_dir: Path) -> Optional[Path]:
    """
    Find YAML file for a model in a layer directory.
    
    Args:
        model_name: Name of the model
        layer_dir: Path to the layer directory (e.g., models/aws/guardduty/silver)
    
    Returns:
        Path to YAML file if found, None otherwise
    """
    # Try exact match: {model_name}.yaml
    yaml_file = layer_dir / f"{model_name}.yaml"
    if yaml_file.exists():
        return yaml_file
    
    # Try .yml extension
    yml_file = layer_dir / f"{model_name}.yml"
    if yml_file.exists():
        return yml_file
    
    # Try to find in all YAML files in the directory
    for yaml_path in layer_dir.glob("*.yaml"):
        try:
            if yaml:
                with open(yaml_path, 'r') as f:
                    content = yaml.safe_load(f)
                if content and 'models' in content:
                    for model_def in content.get('models', []):
                        if model_def.get('name') == model_name:
                            return yaml_path
        except:
            continue
    
    for yml_path in layer_dir.glob("*.yml"):
        try:
            if yaml:
                with open(yml_path, 'r') as f:
                    content = yaml.safe_load(f)
                if content and 'models' in content:
                    for model_def in content.get('models', []):
                        if model_def.get('name') == model_name:
                            return yml_path
        except:
            continue
    
    return None


def find_sql_file_for_model(model_name: str, layer_dir: Path) -> Optional[Path]:
    """Find SQL file for a model in the layer directory."""
    # Try exact match first
    sql_file = layer_dir / f"{model_name}.sql"
    if sql_file.exists():
        return sql_file
    
    # Try with schema prefix removed
    if '_' in model_name:
        parts = model_name.split('_', 1)
        if len(parts) > 1:
            short_name = parts[1]
            sql_file = layer_dir / f"{short_name}.sql"
            if sql_file.exists():
                return sql_file
    
    return None


def parse_struct_definition(struct_str: str) -> Dict[str, Any]:
    """
    Parse a STRUCT definition string into a nested column structure.
    
    Example input:
    'STRUCT<AccessKeyDetails: STRUCT<AccessKeyId: STRING, PrincipalId: STRING>, ResourceType: STRING>'
    
    Returns:
    {
        'type': 'STRUCT',
        'fields': [
            {'name': 'AccessKeyDetails', 'type': 'STRUCT', 'fields': [...]},
            {'name': 'ResourceType', 'type': 'STRING', 'fields': []}
        ]
    }
    """
    def parse_struct_inner(s: str, start: int = 0) -> tuple[Dict[str, Any], int]:
        """Recursively parse STRUCT definition."""
        fields = []
        i = start
        depth = 0
        current_token = ''
        current_name = ''
        expecting_name = True
        
        while i < len(s):
            char = s[i]
            
            if char == '<':
                # Start of nested STRUCT
                depth += 1
                if current_name and current_token.strip().upper().startswith('STRUCT'):
                    # We have a field name and STRUCT type, start nested parsing
                    nested_struct, new_i = parse_struct_inner(s, i + 1)
                    nested_struct['name'] = current_name.strip()
                    nested_struct['type'] = 'STRUCT'
                    fields.append(nested_struct)
                    current_name = ''
                    current_token = ''
                    expecting_name = True
                    i = new_i
                    continue
                i += 1
            elif char == '>':
                # End of nested STRUCT
                depth -= 1
                if depth == 0:
                    # End of current STRUCT - handle last field
                    if current_name and current_token:
                        field_type = current_token.strip()
                        if field_type.upper().startswith('STRUCT'):
                            # This shouldn't happen here, but handle it
                            field_type = 'STRUCT'
                        fields.append({
                            'name': current_name.strip(),
                            'type': field_type,
                            'fields': []
                        })
                    return {'type': 'STRUCT', 'fields': fields}, i + 1
                i += 1
            elif char == ',' and depth == 0:
                # Field separator at top level
                if current_name and current_token:
                    field_type = current_token.strip()
                    if field_type.upper().startswith('STRUCT'):
                        field_type = 'STRUCT'
                    fields.append({
                        'name': current_name.strip(),
                        'type': field_type,
                        'fields': []
                    })
                    current_name = ''
                    current_token = ''
                    expecting_name = True
                i += 1
            elif char == ':' and depth == 0:
                # Separator between field name and type
                if expecting_name and current_token:
                    current_name = current_token.strip()
                    current_token = ''
                    expecting_name = False
                i += 1
            else:
                # Accumulate token
                current_token += char
                i += 1
        
        # Handle last field if any
        if current_name and current_token:
            field_type = current_token.strip()
            if field_type.upper().startswith('STRUCT'):
                field_type = 'STRUCT'
            fields.append({
                'name': current_name.strip(),
                'type': field_type,
                'fields': []
            })
        
        return {'type': 'STRUCT', 'fields': fields}, i
    
    # Remove 'STRUCT<' prefix and '>' suffix if present
    s = struct_str.strip()
    if s.upper().startswith('STRUCT<'):
        s = s[7:]  # Remove 'STRUCT<'
    if s.endswith('>'):
        s = s[:-1]  # Remove trailing '>'
    
    result, _ = parse_struct_inner(s)
    return result


def extract_struct_definition_string(sql_content: str, start_pos: int) -> tuple[Optional[str], int]:
    """
    Extract a complete STRUCT definition string, handling nested STRUCTs.
    
    Args:
        sql_content: SQL content to search
        start_pos: Position where 'STRUCT<' starts
    
    Returns:
        Tuple of (struct_string, end_position) or (None, start_pos) if not found
    """
    if not sql_content[start_pos:start_pos+7].upper().startswith('STRUCT'):
        return None, start_pos
    
    # Find the opening '<'
    i = start_pos + 6  # After 'STRUCT'
    while i < len(sql_content) and sql_content[i] in ' \t':
        i += 1
    
    if i >= len(sql_content) or sql_content[i] != '<':
        return None, start_pos
    
    # Now find the matching '>', accounting for nested '<' and '>'
    depth = 1
    i += 1
    start = i
    
    while i < len(sql_content) and depth > 0:
        if sql_content[i] == '<':
            depth += 1
        elif sql_content[i] == '>':
            depth -= 1
        i += 1
    
    if depth == 0:
        # Found matching '>'
        struct_str = 'STRUCT<' + sql_content[start:i-1] + '>'
        return struct_str, i
    else:
        # Unmatched brackets
        return None, start_pos


def extract_struct_definitions_from_sql(sql_file: Path) -> Dict[str, Dict[str, Any]]:
    """
    Extract STRUCT definitions from SQL file.
    
    Looks for patterns like:
    variant_get(parse_json(column_name), '$', 'STRUCT<...>') as column_name
    
    Handles multiple STRUCT definitions and nested STRUCTs.
    
    Returns:
    Dictionary mapping column_name -> parsed STRUCT definition
    """
    struct_defs = {}
    
    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Pattern to match variant_get with STRUCT definition
        # variant_get(parse_json(column_name), '$', 'STRUCT<...>') as column_name
        # We'll find the variant_get pattern, then extract the STRUCT definition properly
        variant_pattern = r'variant_get\s*\(\s*parse_json\s*\(\s*(\w+)\s*\)\s*,\s*[\'"]?\$[\'"]?\s*,\s*[\'"]?'
        
        matches = re.finditer(variant_pattern, sql_content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            source_col = match.group(1)
            struct_start = match.end()
            
            # Extract the complete STRUCT definition (handling nested STRUCTs)
            struct_str, struct_end = extract_struct_definition_string(sql_content, struct_start)
            
            if not struct_str:
                continue
            
            # Find the 'as column_name' part
            remaining = sql_content[struct_end:]
            as_match = re.search(r'\)\s+as\s+(\w+)', remaining, re.IGNORECASE)
            
            if as_match:
                target_col = as_match.group(1)
                
                # Parse the STRUCT definition
                try:
                    parsed_struct = parse_struct_definition(struct_str)
                    struct_defs[target_col] = parsed_struct
                    print(f"    Found STRUCT definition for {target_col}: {len(parsed_struct.get('fields', []))} top-level fields")
                except Exception as e:
                    print(f"    Error parsing STRUCT for {target_col}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        # Also look for direct STRUCT casts
        # column_name::STRUCT<...> or CAST(column_name AS STRUCT<...>)
        # First, find CAST patterns
        cast_pattern = r'CAST\s*\(\s*(\w+)\s+AS\s+STRUCT'
        cast_matches = re.finditer(cast_pattern, sql_content, re.IGNORECASE)
        
        for match in cast_matches:
            col_name = match.group(1)
            struct_start = match.end() - 5  # Back to 'STRUCT'
            
            struct_str, struct_end = extract_struct_definition_string(sql_content, struct_start)
            
            if struct_str:
                try:
                    parsed_struct = parse_struct_definition(struct_str)
                    struct_defs[col_name] = parsed_struct
                    print(f"    Found STRUCT CAST for {col_name}: {len(parsed_struct.get('fields', []))} top-level fields")
                except Exception as e:
                    print(f"    Error parsing STRUCT CAST for {col_name}: {e}")
                    continue
        
        # Also look for ::STRUCT<...> patterns
        colon_cast_pattern = r'(\w+)\s*::\s*STRUCT'
        colon_matches = re.finditer(colon_cast_pattern, sql_content, re.IGNORECASE)
        
        for match in colon_matches:
            col_name = match.group(1)
            struct_start = match.end() - 6  # Back to 'STRUCT'
            
            struct_str, struct_end = extract_struct_definition_string(sql_content, struct_start)
            
            if struct_str:
                try:
                    parsed_struct = parse_struct_definition(struct_str)
                    struct_defs[col_name] = parsed_struct
                    print(f"    Found STRUCT :: cast for {col_name}: {len(parsed_struct.get('fields', []))} top-level fields")
                except Exception as e:
                    print(f"    Error parsing STRUCT :: cast for {col_name}: {e}")
                    continue
        
    except Exception as e:
        print(f"    Error reading SQL file {sql_file}: {e}")
        import traceback
        traceback.print_exc()
    
    return struct_defs


def struct_to_mdl_columns(struct_def: Dict[str, Any], parent_name: str = '') -> List[Dict[str, Any]]:
    """
    Convert a parsed STRUCT definition into MDL column definitions.
    
    Args:
        struct_def: Parsed STRUCT definition from parse_struct_definition
        parent_name: Parent column name (for nested structures)
    
    Returns:
        List of MDL column definitions
    """
    columns = []
    fields = struct_def.get('fields', [])
    
    for field in fields:
        field_name = field.get('name', '')
        field_type = field.get('type', 'VARCHAR')
        nested_fields = field.get('fields', [])
        
        # Build full column name
        if parent_name:
            full_name = f"{parent_name}.{field_name}"
        else:
            full_name = field_name
        
        # If it's a nested STRUCT, recursively convert
        if nested_fields or field_type.upper() == 'STRUCT':
            # Create a column for the STRUCT itself
            col = {
                'name': full_name,
                'type': 'VARCHAR',  # STRUCTs are typically stored as JSON/VARCHAR
                'properties': {
                    'description': f"Nested structure containing {len(nested_fields)} fields",
                    'displayName': to_display_name(field_name),
                    'isStruct': True
                }
            }
            columns.append(col)
            
            # Add nested columns
            if nested_fields:
                nested_cols = struct_to_mdl_columns({'fields': nested_fields}, full_name)
                columns.extend(nested_cols)
        else:
            # Regular field
            col = {
                'name': full_name,
                'type': field_type.upper(),
                'properties': {
                    'description': f"Field from {parent_name if parent_name else 'struct'}",
                    'displayName': to_display_name(field_name)
                }
            }
            columns.append(col)
    
    return columns


def extract_yaml_descriptions(yaml_file: Path, model_name: str) -> Dict[str, Any]:
    """
    Extract model and column descriptions from YAML file.
    
    Returns:
        Dict with keys:
        - 'model_description': str
        - 'column_descriptions': Dict[str, str] mapping column name to description
    """
    if not yaml or not yaml_file.exists():
        return {'model_description': '', 'column_descriptions': {}}
    
    try:
        with open(yaml_file, 'r') as f:
            content = yaml.safe_load(f)
        
        if not content or 'models' not in content:
            return {'model_description': '', 'column_descriptions': {}}
        
        # Find the model definition
        model_def = None
        for m in content.get('models', []):
            if m.get('name') == model_name:
                model_def = m
                break
        
        if not model_def:
            return {'model_description': '', 'column_descriptions': {}}
        
        # Extract model description
        model_description = model_def.get('description', '').strip()
        
        # Extract column descriptions
        column_descriptions = {}
        
        # First, try to extract from model description text (markdown format)
        # Pattern: **field_name**: description
        if model_description:
            pattern = r'\*\*(\w+)\*\*[:\s—–-]+([^\n]+?)(?=\n|$)'
            for match in re.finditer(pattern, model_description, re.MULTILINE):
                field_name = match.group(1).lower()
                field_desc = match.group(2).strip()
                # Remove trailing period if present
                field_desc = re.sub(r'\.$', '', field_desc)
                if field_desc and field_name not in column_descriptions:
                    column_descriptions[field_name] = field_desc
        
        # Also check explicit column definitions in YAML
        if 'columns' in model_def:
            for col_def in model_def.get('columns', []):
                col_name = col_def.get('name', '').lower()
                col_desc = col_def.get('description', '').strip()
                if col_desc:
                    column_descriptions[col_name] = col_desc
        
        return {
            'model_description': model_description,
            'column_descriptions': column_descriptions
        }
        
    except Exception as e:
        print(f"  Warning: Error reading YAML file {yaml_file}: {e}")
        return {'model_description': '', 'column_descriptions': {}}


def generate_mdl_from_dbt(
    models_dir: Path,
    subdirectory: str,
    schema_name: str,
    layer: str,
    output_dir: Path,
    catalog: str = "product_knowledge"
) -> Optional[Path]:
    """
    Generate MDL file from dbt models in a subdirectory.
    
    Args:
        models_dir: Base directory containing dbt models
        subdirectory: Relative path to layer directory (e.g., "aws/guardduty/silver")
        schema_name: Schema name for MDL (e.g., "aws_guardduty")
        layer: Layer name (bronze, silver, gold)
        output_dir: Directory to write MDL file
        catalog: MDL catalog name
    
    Returns:
        Path to generated MDL file, or None if generation failed
    """
    if not HAS_DBT_CONVERTER:
        print(f"  Cannot generate MDL: DbtToMdlConverter not available")
        return None
    
    try:
        # Create a temporary output directory to avoid conflicts
        temp_output = output_dir / ".temp"
        temp_output.mkdir(parents=True, exist_ok=True)
        
        converter = DbtToMdlConverter(models_dir=models_dir, output_dir=temp_output)
        converter.convert_directory(
            subdirectory=subdirectory,
            catalog=catalog,
            schema=schema_name
        )
        
        # The converter creates {schema_name}.mdl.json
        original_file = temp_output / f"{schema_name}.mdl.json"
        
        if not original_file.exists():
            print(f"  Warning: MDL file was not created at {original_file}")
            return None
        
        # Target file with layer: {schema_name}_{layer}.mdl.json
        target_file = output_dir / f"{schema_name}_{layer}.mdl.json"
        
        # Move/rename to target location
        original_file.rename(target_file)
        
        # Clean up temp directory if empty
        try:
            temp_output.rmdir()
        except:
            pass
        
        return target_file
            
    except Exception as e:
        print(f"  Error generating MDL from dbt: {e}")
        import traceback
        traceback.print_exc()
        return None


class MDLEnricher:
    """LLM-powered MDL file enricher"""
    
    def __init__(self, llm=None):
        self.llm = llm or get_llm()
    
    async def enrich_column_description(
        self,
        column: Dict[str, Any],
        table_name: str,
        table_description: str,
        other_columns: List[str],
        schema_name: str
    ) -> Dict[str, Any]:
        """Enrich a single column with LLM-generated description."""
        
        col_name = column.get('name', '')
        current_desc = column.get('properties', {}).get('description', '')
        col_type = column.get('type', 'VARCHAR')
        
        # Skip if already has a good description (not generic)
        # Only enrich if description is missing, too short, or generic
        should_enrich = True
        if current_desc:
            desc_lower = current_desc.lower()
            # Skip if description is substantial and not generic
            if len(current_desc) > 30 and not any(
                generic in desc_lower 
                for generic in ['unique identifier for', 'timestamp when', 'boolean flag indicating', 
                               'unique identifier for', 'flag indicating if']
            ):
                should_enrich = False
        
        if not should_enrich:
            # Still ensure displayName exists
            if 'properties' not in column:
                column['properties'] = {}
            if 'displayName' not in column['properties']:
                column['properties']['displayName'] = to_display_name(col_name)
            return column
        
        system_prompt = """You are an expert data analyst specializing in security and compliance data models.
Generate clear, concise column descriptions that help analysts understand:
1. What the column represents in business/security terms
2. How it should be used in analysis
3. Important data characteristics

Be specific and use domain-appropriate terminology. Keep descriptions concise (1-2 sentences max).
Return ONLY valid JSON without any markdown formatting, comments, or additional text."""

        # Build user prompt - need to escape braces for LangChain template
        # Use format-style template with proper escaping
        user_prompt_template = """Generate a description for this database column:

Table Context:
- Table Name: {table_name}
- Schema: {schema_name}
- Table Description: {table_description}
- Column Name: {col_name}
- Column Type: {col_type}
- Current Description: {current_desc}
- Other Columns: {other_columns}

Generate a JSON response with:
{{
    "description": "Clear, concise description of what this column represents",
    "display_name": "Human-readable display name",
    "correct_type": "Correct data type (VARCHAR, TIMESTAMP, DATE, BIGINT, DOUBLE, BOOLEAN)"
}}

Focus on security/compliance context. Be specific about what the column contains."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt_template)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = await chain.ainvoke({
                "table_name": table_name,
                "schema_name": schema_name,
                "table_description": table_description,
                "col_name": col_name,
                "col_type": col_type,
                "current_desc": current_desc if current_desc else 'None',
                "other_columns": ', '.join(other_columns[:10])
            })
            
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = re.sub(r"^```json\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            elif response.startswith("```"):
                response = re.sub(r"^```\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = json.loads(response)
            
            # Update column
            if 'properties' not in column:
                column['properties'] = {}
            
            if result.get('description'):
                column['properties']['description'] = result['description']
            
            if result.get('display_name'):
                column['properties']['displayName'] = result['display_name']
            elif 'displayName' not in column['properties']:
                column['properties']['displayName'] = to_display_name(col_name)
            
            # Fix type if needed
            correct_type = result.get('correct_type', col_type)
            if correct_type != col_type:
                print(f"  Fixing type for {col_name}: {col_type} -> {correct_type}")
                column['type'] = correct_type
            
            return column
            
        except Exception as e:
            print(f"  Error enriching {col_name}: {e}")
            # Fallback: ensure displayName exists
            if 'properties' not in column:
                column['properties'] = {}
            if 'displayName' not in column['properties']:
                column['properties']['displayName'] = to_display_name(col_name)
            return column
    
    async def generate_sql_examples(
        self,
        model: Dict[str, Any],
        schema_name: str,
        layer: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate SQL example queries for a model in sql_pairs format."""
        
        table_name = model.get('name', '')
        table_desc = model.get('properties', {}).get('description', '')
        columns = model.get('columns', [])
        
        # Get column names and types
        col_info = []
        for col in columns:
            col_name = col.get('name', '')
            col_type = col.get('type', 'VARCHAR')
            col_desc = col.get('properties', {}).get('description', '')
            col_info.append(f"- {col_name} ({col_type}): {col_desc[:50]}")
        
        # Determine categories based on table name and description
        categories = self._infer_categories(table_name, table_desc, layer)
        
        system_prompt = """You are an expert SQL query writer specializing in security and compliance data analysis.
Generate practical SQL example queries in the sql_pairs format with natural language questions.
Return ONLY valid JSON array without any markdown formatting, comments, or additional text."""

        # Build user prompt - need to escape braces for LangChain template
        user_prompt_template = """Generate 3-5 practical SQL example queries for this table in sql_pairs format:

Table: {table_name}
Schema: {schema_name}
Layer: {layer}
Description: {table_desc}

Columns:
{columns_info}

Generate a JSON array of query objects in this exact format:
[
    {{
        "categories": ["category1", "category2"],
        "question": "Natural language question about what the query answers",
        "sql": "SELECT ... FROM {schema_name}.{table_name} WHERE ...",
        "context": "Visualization type and purpose (e.g., 'Direct Visualization - Bar Chart. Shows...')",
        "document": "{schema_name}_{layer}.mdl.json - {table_name}",
        "samples": [],
        "instructions": "Clear instructions on what the query calculates and why it's useful"
    }},
    ...
]

Categories should be relevant to security/compliance (e.g., vulnerability_management, asset_management, security_monitoring, etc.).
Questions should be natural language questions that the SQL answers.
Context should describe the visualization type and business purpose.
Document should reference the MDL file.
Instructions should explain what the query calculates and its business value.

Focus on:
1. Common filtering patterns
2. Aggregations and summaries
3. Time-based analysis
4. Security/compliance use cases
5. Joins with related tables (if applicable)

Make queries practical and realistic."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt_template)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = await chain.ainvoke({
                "table_name": table_name,
                "schema_name": schema_name,
                "layer": layer or "silver",
                "table_desc": table_desc[:500],  # Limit description length
                "columns_info": '\n'.join(col_info[:20])
            })
            
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = re.sub(r"^```json\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            elif response.startswith("```"):
                response = re.sub(r"^```\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                examples = json.loads(json_match.group(0))
            else:
                examples = json.loads(response)
            
            # Ensure all required fields are present and add schema/table context
            for example in examples:
                if 'categories' not in example:
                    example['categories'] = categories
                if 'document' not in example:
                    example['document'] = f"{schema_name}_{layer or 'silver'}.mdl.json - {table_name}"
                if 'samples' not in example:
                    example['samples'] = []
                # Ensure SQL uses full table name
                if 'sql' in example and f"{schema_name}.{table_name}" not in example['sql']:
                    example['sql'] = example['sql'].replace(table_name, f"{schema_name}.{table_name}")
            
            return examples
            
        except Exception as e:
            print(f"  Error generating SQL examples: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _infer_categories(self, table_name: str, description: str, layer: Optional[str] = None) -> List[str]:
        """Infer categories from table name and description."""
        categories = []
        name_lower = table_name.lower()
        desc_lower = description.lower()
        
        # Vulnerability-related
        if any(word in name_lower or word in desc_lower for word in ['vulnerability', 'vuln', 'cve', 'finding']):
            categories.append('vulnerability_management')
        
        # Asset-related
        if any(word in name_lower or word in desc_lower for word in ['asset', 'device', 'host', 'machine', 'endpoint']):
            categories.append('asset_management')
        
        # Software-related
        if any(word in name_lower or word in desc_lower for word in ['software', 'application', 'app', 'install']):
            categories.append('software_asset_management')
        
        # Security monitoring
        if any(word in name_lower or word in desc_lower for word in ['alert', 'threat', 'detection', 'agent', 'monitor']):
            categories.append('security_monitoring')
        
        # Compliance
        if any(word in name_lower or word in desc_lower for word in ['compliance', 'policy', 'standard', 'assessment']):
            categories.append('compliance_management')
        
        # Network
        if any(word in name_lower or word in desc_lower for word in ['network', 'interface', 'subnet', 'ip']):
            categories.append('network_infrastructure')
        
        # Default if no categories found
        if not categories:
            categories.append('security_analysis')
        
        return categories
    
    async def enrich_mdl_file(
        self, 
        mdl_path: Path, 
        models_dir: Optional[Path] = None,
        layer: Optional[str] = None,
        priority: Optional[int] = None,
        layer_dir: Optional[Path] = None
    ):
        """Enrich a single MDL file."""
        print(f"\n{'='*60}")
        print(f"Processing: {mdl_path.name}")
        if layer:
            print(f"Layer: {layer} (priority: {priority})")
        print(f"{'='*60}")
        
        with open(mdl_path, 'r') as f:
            mdl_data = json.load(f)
        
        if 'models' not in mdl_data:
            print("  No models found")
            return
        
        schema_name = mdl_data.get('schema', 'unknown')
        updated = False
        
        for model in mdl_data['models']:
            model_name = model.get('name', '')
            if not model_name:
                continue
            
            print(f"\n  Model: {model_name}")
            
            # Add priority property to model if provided
            if priority is not None:
                if 'properties' not in model:
                    model['properties'] = {}
                if model['properties'].get('priority') != priority:
                    model['properties']['priority'] = priority
                    updated = True
                    print(f"    Added priority: {priority}")
            
            # Add layer property if provided
            if layer:
                if 'properties' not in model:
                    model['properties'] = {}
                if model['properties'].get('layer') != layer:
                    model['properties']['layer'] = layer
                    updated = True
                    print(f"    Added layer: {layer}")
            
            # Try to find and use YAML file for enrichment
            yaml_descriptions = {'model_description': '', 'column_descriptions': {}}
            if layer_dir:
                yaml_file = find_yaml_file_for_model(model_name, layer_dir)
                if yaml_file:
                    print(f"    Found YAML file: {yaml_file.name}")
                    yaml_descriptions = extract_yaml_descriptions(yaml_file, model_name)
            
            # Try to find SQL file and extract STRUCT definitions
            struct_definitions = {}
            if layer_dir:
                sql_file = find_sql_file_for_model(model_name, layer_dir)
                if sql_file:
                    print(f"    Found SQL file: {sql_file.name}")
                    struct_definitions = extract_struct_definitions_from_sql(sql_file)
                    
                    # Use YAML model description if available and better than existing
                    yaml_model_desc = yaml_descriptions.get('model_description', '')
                    if yaml_model_desc:
                        if 'properties' not in model:
                            model['properties'] = {}
                        current_desc = model.get('properties', {}).get('description', '')
                        if not current_desc or len(yaml_model_desc) > len(current_desc):
                            model['properties']['description'] = yaml_model_desc
                            updated = True
                            print(f"    Updated model description from YAML ({len(yaml_model_desc)} chars)")
            
            table_desc = model.get('properties', {}).get('description', '')
            columns = model.get('columns', [])
            other_col_names = [col.get('name', '') for col in columns]
            
            # Apply YAML column descriptions
            yaml_col_descriptions = yaml_descriptions.get('column_descriptions', {})
            yaml_enriched_count = 0
            for col in columns:
                col_name = col.get('name', '').lower()
                if col_name in yaml_col_descriptions:
                    yaml_desc = yaml_col_descriptions[col_name]
                    if 'properties' not in col:
                        col['properties'] = {}
                    current_desc = col.get('properties', {}).get('description', '')
                    if not current_desc or len(yaml_desc) > len(current_desc):
                        col['properties']['description'] = yaml_desc
                        if 'displayName' not in col['properties']:
                            col['properties']['displayName'] = to_display_name(col.get('name', ''))
                        updated = True
                        yaml_enriched_count += 1
            
            if yaml_enriched_count > 0:
                print(f"    Enriched {yaml_enriched_count} columns from YAML")
            
            # First pass: expand STRUCT columns and fix types
            print("  Expanding STRUCT columns and fixing types...")
            columns_to_add = []
            columns_to_remove = []
            
            for i, col in enumerate(columns):
                col_name = col.get('name', '')
                current_type = col.get('type', 'VARCHAR')
                current_desc = col.get('properties', {}).get('description', '')
                
                # Check if this column has a STRUCT definition from SQL
                if col_name in struct_definitions:
                    struct_def = struct_definitions[col_name]
                    print(f"    Expanding STRUCT for {col_name}...")
                    
                    # Convert STRUCT to MDL columns
                    struct_columns = struct_to_mdl_columns(struct_def, col_name)
                    
                    # Update the original column to indicate it's a STRUCT
                    col['type'] = 'VARCHAR'  # STRUCTs are stored as JSON/VARCHAR
                    if 'properties' not in col:
                        col['properties'] = {}
                    col['properties']['isStruct'] = True
                    col['properties']['structFields'] = len(struct_def.get('fields', []))
                    if not col['properties'].get('description'):
                        col['properties']['description'] = f"Complex nested structure with {len(struct_def.get('fields', []))} top-level fields. Use dot notation to access nested fields (e.g., {col_name}.field_name)."
                    
                    # Add the nested columns
                    columns_to_add.extend(struct_columns)
                    updated = True
                    print(f"      Added {len(struct_columns)} nested columns")
                
                # Fix types for non-STRUCT columns
                correct_type = infer_correct_type(col_name, current_type, current_desc)
                if correct_type != current_type and col_name not in struct_definitions:
                    print(f"    {col_name}: {current_type} -> {correct_type}")
                    col['type'] = correct_type
                    updated = True
            
            # Add new STRUCT columns
            if columns_to_add:
                columns.extend(columns_to_add)
                print(f"  Added {len(columns_to_add)} STRUCT-derived columns")
            
            # Second pass: enrich descriptions with LLM (only for columns that still need it)
            print("  Enriching column descriptions with LLM...")
            columns_to_enrich = []
            for i, col in enumerate(columns):
                col_name = col.get('name', '')
                current_desc = col.get('properties', {}).get('description', '')
                
                # Skip if already has YAML description (already enriched above)
                col_name_lower = col_name.lower()
                if col_name_lower in yaml_col_descriptions:
                    continue
                
                # Check if needs enrichment
                needs_enrichment = True
                if current_desc and len(current_desc) > 30:
                    desc_lower = current_desc.lower()
                    if not any(generic in desc_lower for generic in [
                        'unique identifier for', 'timestamp when', 'boolean flag indicating'
                    ]):
                        needs_enrichment = False
                
                if needs_enrichment:
                    columns_to_enrich.append((i, col))
            
            if columns_to_enrich:
                print(f"    Enriching {len(columns_to_enrich)}/{len(columns)} columns...")
                for idx, (i, col) in enumerate(columns_to_enrich):
                    col_name = col.get('name', '')
                    print(f"    [{idx+1}/{len(columns_to_enrich)}] {col_name}...", end=' ', flush=True)
                    
                    enriched = await self.enrich_column_description(
                        col,
                        model_name,
                        table_desc,
                        [c for c in other_col_names if c != col_name],
                        schema_name
                    )
                    
                    if enriched != col:
                        columns[i] = enriched
                        updated = True
                        print("✓")
                    else:
                        print("-")
            else:
                print("    All columns already have good descriptions")
            
            # SQL examples are now stored in a separate file (sql_pairs.json)
            # Generate SQL examples in sql_pairs format
            print("  Generating SQL examples...")
            sql_examples = await self.generate_sql_examples(model, schema_name, layer=layer)
            if sql_examples:
                # Store in a way that can be extracted later
                # We'll collect these and write to sql_pairs.json separately
                if 'properties' not in model:
                    model['properties'] = {}
                model['properties']['_sql_examples'] = sql_examples  # Temporary storage
                updated = True
                print(f"    Generated {len(sql_examples)} SQL examples")
        
        # Write updated file
        if updated:
            with open(mdl_path, 'w') as f:
                json.dump(mdl_data, f, indent=2)
            print(f"\n✓ Updated {mdl_path.name}")
        else:
            print(f"\n- No updates needed for {mdl_path.name}")
    
    async def enrich_metrics_mdl(
        self,
        silver_mdl_path: Path,
        gold_mdl_path: Optional[Path] = None,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate metrics registry from silver and gold models.
        
        Args:
            silver_mdl_path: Path to silver layer MDL file
            gold_mdl_path: Optional path to gold layer MDL file
            output_path: Optional path to save metrics registry file
        
        Returns:
            Metrics registry dictionary (conforms to metric_registry_schema.json)
        """
        print(f"\n{'='*60}")
        print(f"Generating metrics registry from models")
        print(f"  Silver: {silver_mdl_path.name}")
        if gold_mdl_path:
            print(f"  Gold: {gold_mdl_path.name}")
        print(f"{'='*60}")
        
        # Load silver MDL
        with open(silver_mdl_path, 'r') as f:
            silver_mdl = json.load(f)
        
        silver_schema = silver_mdl.get('schema', 'unknown')
        silver_models = silver_mdl.get('models', [])
        
        # Load gold MDL if provided
        gold_models = []
        if gold_mdl_path and gold_mdl_path.exists():
            with open(gold_mdl_path, 'r') as f:
                gold_mdl = json.load(f)
            gold_models = gold_mdl.get('models', [])
        
        # Combine models (prefer gold over silver)
        all_models = {}
        for model in silver_models:
            model_name = model.get('name', '')
            if model_name:
                all_models[model_name] = {'layer': 'silver', 'model': model}
        
        for model in gold_models:
            model_name = model.get('name', '')
            if model_name:
                all_models[model_name] = {'layer': 'gold', 'model': model}
        
        print(f"\n  Found {len(all_models)} models ({len(silver_models)} silver, {len(gold_models)} gold)")
        
        # Generate metrics for each model
        metrics = []
        for model_name, model_info in all_models.items():
            model = model_info['model']
            layer = model_info['layer']
            
            print(f"\n  Generating metrics for: {model_name} ({layer})")
            
            model_metrics = await self._generate_metrics_for_model(
                model, silver_schema, layer
            )
            metrics.extend(model_metrics)
            print(f"    Generated {len(model_metrics)} metrics")
        
        # Create metrics registry structure (not MDL format)
        metrics_registry = {
            "version": "1.0.0",
            "metrics": metrics
        }
        
        # Save if output path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(metrics_registry, f, indent=2)
            print(f"\n{'='*60}")
            print(f"✓ Saved metrics registry to: {output_path}")
            print(f"  Total metrics: {len(metrics)}")
            print(f"{'='*60}")
        
        return metrics_registry
    
    async def _generate_metrics_for_model(
        self,
        model: Dict[str, Any],
        schema_name: str,
        layer: str
    ) -> List[Dict[str, Any]]:
        """Generate metrics for a single model using LLM in metric registry format."""
        
        model_name = model.get('name', '')
        model_desc = model.get('properties', {}).get('description', '')
        columns = model.get('columns', [])
        
        # Identify dimension and measure columns
        dimensions = []
        measures = []
        all_columns = []
        
        for col in columns:
            col_name = col.get('name', '')
            col_type = col.get('type', 'VARCHAR')
            col_desc = col.get('properties', {}).get('description', '')
            
            all_columns.append({
                'name': col_name,
                'type': col_type,
                'description': col_desc
            })
            
            # Dimensions are typically VARCHAR, DATE, TIMESTAMP, BOOLEAN
            if col_type in ['VARCHAR', 'DATE', 'TIMESTAMP', 'BOOLEAN']:
                dimensions.append(col_name)
            # Measures are typically numeric
            elif col_type in ['BIGINT', 'DOUBLE', 'INTEGER', 'DECIMAL']:
                measures.append(col_name)
        
        # Infer category from model name and description
        category = self._infer_metric_category(model_name, model_desc)
        
        system_prompt = """You are an expert data analyst specializing in security and compliance metrics.
Generate meaningful metrics in the metric registry format that can be derived from the given table.
Return ONLY valid JSON array without any markdown formatting, comments, or additional text."""

        user_prompt_template = """Generate 3-5 key metrics for this table in metric registry format:

Table: {table_name}
Schema: {schema_name}
Layer: {layer}
Description: {model_desc}

All Columns:
{columns_info}

Dimensions (for grouping): {dimensions}
Measures (for aggregation): {measures}

Generate a JSON array of metric objects in this exact format:
[
    {{
        "id": "unique_metric_id_snake_case",
        "name": "Human-readable metric name",
        "description": "What this metric measures and why it's important for security/compliance",
        "category": "{category}",
        "data_capability": ["temporal", "semantic"],
        "transformation_layer": "{layer}",
        "source_schemas": ["{schema_name}_{layer}_schema"],
        "source_capabilities": ["{schema_name}.{table_name}"],
        "data_filters": ["filter_column1", "filter_column2"],
        "data_groups": ["group_column1", "group_column2"],
        "kpis": ["KPI 1", "KPI 2"],
        "trends": ["Trend 1", "Trend 2"],
        "natural_language_question": "Natural language question this metric answers"
    }},
    ...
]

Required fields:
- id: unique snake_case identifier
- name: human-readable name
- description: detailed description
- category: one of: vulnerabilities, asset_management, application_security, identity_access_management
- data_capability: array of temporal, spatial, geo, semantic
- transformation_layer: bronze, silver, or gold
- source_schemas: array of schema names
- source_capabilities: array of schema.table references
- data_filters: array of column names that can be used for filtering
- data_groups: array of column names that can be used for grouping
- kpis: array of KPI strings this metric supports
- trends: array of trend analysis capabilities
- natural_language_question: natural language question

Focus on:
1. Security and compliance KPIs
2. Risk assessment metrics
3. Operational metrics
4. Trend analysis capabilities
5. Business value metrics

Make metrics practical and actionable."""

        columns_info = '\n'.join([f"- {c['name']} ({c['type']}): {c['description'][:50]}" for c in all_columns[:20]])

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt_template)
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            response = await chain.ainvoke({
                "table_name": model_name,
                "schema_name": schema_name,
                "layer": layer,
                "model_desc": model_desc[:500],
                "columns_info": columns_info,
                "dimensions": ', '.join(dimensions[:10]),
                "measures": ', '.join(measures[:10]),
                "category": category
            })
            
            # Clean response
            response = response.strip()
            if response.startswith("```json"):
                response = re.sub(r"^```json\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            elif response.startswith("```"):
                response = re.sub(r"^```\s*", "", response)
                response = re.sub(r"\s*```$", "", response)
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                metrics = json.loads(json_match.group(0))
            else:
                metrics = json.loads(response)
            
            # Ensure all metrics have required fields and validate
            validated_metrics = []
            for metric in metrics:
                # Ensure required fields
                if 'id' not in metric:
                    metric['id'] = f"{schema_name}_{model_name}_{len(validated_metrics)}"
                if 'name' not in metric:
                    metric['name'] = f"Metric for {model_name}"
                if 'description' not in metric:
                    metric['description'] = f"Metric derived from {model_name}"
                if 'category' not in metric:
                    metric['category'] = category
                
                # Ensure arrays exist
                if 'data_capability' not in metric:
                    metric['data_capability'] = ['temporal', 'semantic']
                if 'source_schemas' not in metric:
                    metric['source_schemas'] = [f"{schema_name}_{layer}_schema"]
                if 'source_capabilities' not in metric:
                    metric['source_capabilities'] = [f"{schema_name}.{model_name}"]
                if 'data_filters' not in metric:
                    metric['data_filters'] = []
                if 'data_groups' not in metric:
                    metric['data_groups'] = []
                if 'kpis' not in metric:
                    metric['kpis'] = []
                if 'trends' not in metric:
                    metric['trends'] = []
                if 'natural_language_question' not in metric:
                    metric['natural_language_question'] = f"What insights can we derive from {model_name}?"
                
                # Ensure transformation_layer
                if 'transformation_layer' not in metric:
                    metric['transformation_layer'] = layer
                
                validated_metrics.append(metric)
            
            return validated_metrics
            
        except Exception as e:
            print(f"    Error generating metrics: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _infer_metric_category(self, model_name: str, description: str) -> str:
        """Infer metric category from model name and description."""
        name_lower = model_name.lower()
        desc_lower = description.lower()
        
        # Check for vulnerabilities
        if any(word in name_lower or word in desc_lower for word in ['vulnerability', 'vuln', 'cve', 'finding']):
            return 'vulnerabilities'
        
        # Check for asset management
        if any(word in name_lower or word in desc_lower for word in ['asset', 'device', 'host', 'machine', 'endpoint']):
            return 'asset_management'
        
        # Check for application security
        if any(word in name_lower or word in desc_lower for word in ['application', 'app', 'code', 'repository', 'sast', 'dast']):
            return 'application_security'
        
        # Check for identity access management
        if any(word in name_lower or word in desc_lower for word in ['user', 'identity', 'access', 'iam', 'permission', 'role']):
            return 'identity_access_management'
        
        # Default to vulnerabilities for security data
        return 'vulnerabilities'


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich MDL files with LLM-generated descriptions and SQL examples')
    parser.add_argument('--mdl-dir', type=str, required=False,
                       help='Directory containing MDL files')
    parser.add_argument('--models-dir', type=str, required=False,
                       help='Directory containing dbt models (required if using --by-layer)')
    parser.add_argument('--file', type=str, required=False,
                       help='Process single file instead of all files')
    parser.add_argument('--by-layer', action='store_true',
                       help='Process models by layer (bronze/silver/gold) from models directory')
    parser.add_argument('--layer', type=str, choices=['bronze', 'silver', 'gold'],
                       help='Process only specific layer (requires --by-layer)')
    parser.add_argument('--connector', type=str, required=False,
                       help='Process only specific connector (e.g., qualys, crowdstrike)')
    parser.add_argument('--generate-metrics', action='store_true',
                       help='Generate metrics MDL from silver and gold models')
    parser.add_argument('--metrics-output-dir', type=str, required=False,
                       help='Output directory for metrics MDL files (used with --generate-metrics)')
    
    args = parser.parse_args()
    
    # Initialize enricher
    enricher = MDLEnricher()
    
    # Process by layer from models directory
    if args.by_layer:
        if not args.models_dir:
            print("Error: --models-dir is required when using --by-layer")
            sys.exit(1)
        
        models_dir = Path(args.models_dir)
        if not models_dir.exists():
            print(f"Error: Models directory not found: {models_dir}")
            sys.exit(1)
        
        # Discover layer directories
        print("Discovering layer directories...")
        layer_dirs = discover_layer_directories(models_dir)
        
        # Filter by layer if specified
        if args.layer:
            layer_dirs = [d for d in layer_dirs if d['layer'] == args.layer]
        
        # Filter by connector if specified
        if args.connector:
            layer_dirs = [d for d in layer_dirs if args.connector in d['schema_name'].lower()]
        
        if not layer_dirs:
            print("No layer directories found matching criteria")
            return
        
        print(f"Found {len(layer_dirs)} layer directories:")
        for layer_info in layer_dirs:
            print(f"  - {layer_info['subdirectory']} -> {layer_info['schema_name']} ({layer_info['layer']}, priority: {layer_info['priority']})")
        
        # Process each layer directory
        # We need to convert dbt models to MDL first, or work with existing MDL files
        # For now, we'll look for existing MDL files and enrich them with layer info
        if not args.mdl_dir:
            print("Error: --mdl-dir is required when using --by-layer")
            print("  Specify the directory where MDL files are stored/created")
            sys.exit(1)
        
        mdl_dir = Path(args.mdl_dir)
        mdl_dir.mkdir(parents=True, exist_ok=True)
        
        # Group by schema_name to process all layers for each connector
        schema_groups = {}
        for layer_info in layer_dirs:
            schema = layer_info['schema_name']
            if schema not in schema_groups:
                schema_groups[schema] = []
            schema_groups[schema].append(layer_info)
        
        # Process each schema group
        for schema_name, layer_infos in schema_groups.items():
            print(f"\n{'='*80}")
            print(f"Processing connector: {schema_name}")
            print(f"{'='*80}")
            
            # Process each layer for this schema
            for layer_info in sorted(layer_infos, key=lambda x: x['priority']):
                layer = layer_info['layer']
                priority = layer_info['priority']
                
                # MDL file name: {schema_name}_{layer}.mdl.json
                mdl_filename = f"{schema_name}_{layer}.mdl.json"
                mdl_path = mdl_dir / mdl_filename
                
                # Check if MDL file exists
                if not mdl_path.exists():
                    print(f"\nMDL file not found: {mdl_filename}")
                    print(f"  Generating from dbt models in: {layer_info['subdirectory']}")
                    
                    # Generate MDL file from dbt models
                    generated_file = generate_mdl_from_dbt(
                        models_dir=models_dir,
                        subdirectory=layer_info['subdirectory'],
                        schema_name=schema_name,
                        layer=layer,
                        output_dir=mdl_dir,
                        catalog="product_knowledge"
                    )
                    
                    if generated_file and generated_file.exists():
                        print(f"  ✓ Generated: {mdl_filename}")
                    else:
                        print(f"  ✗ Failed to generate MDL file")
                        continue
                
                # Enrich the MDL file
                print(f"\nEnriching MDL file: {mdl_filename}")
                await enricher.enrich_mdl_file(
                    mdl_path, 
                    models_dir, 
                    layer=layer, 
                    priority=priority,
                    layer_dir=layer_info['path']
                )
        
        print(f"\n{'='*80}")
        print(f"✓ Completed processing {len(layer_dirs)} layer directories")
        print(f"{'='*80}")
        
        # Generate metrics MDL if requested
        if args.generate_metrics:
            print(f"\n{'='*80}")
            print(f"Generating metrics MDL files...")
            print(f"{'='*80}")
            
            metrics_output_dir = Path(args.metrics_output_dir) if args.metrics_output_dir else mdl_dir
            metrics_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process each schema group to generate metrics
            for schema_name, layer_infos in schema_groups.items():
                silver_info = next((li for li in layer_infos if li['layer'] == 'silver'), None)
                gold_info = next((li for li in layer_infos if li['layer'] == 'gold'), None)
                
                if not silver_info:
                    print(f"\n  Skipping {schema_name}: No silver layer found")
                    continue
                
                silver_mdl_path = mdl_dir / f"{schema_name}_silver.mdl.json"
                gold_mdl_path = mdl_dir / f"{schema_name}_gold.mdl.json" if gold_info else None
                
                if not silver_mdl_path.exists():
                    print(f"\n  Skipping {schema_name}: Silver MDL file not found")
                    continue
                
                if gold_mdl_path and not gold_mdl_path.exists():
                    gold_mdl_path = None
                
                output_path = metrics_output_dir / f"{schema_name}_metrics.json"
                
                await enricher.enrich_metrics_mdl(
                    silver_mdl_path=silver_mdl_path,
                    gold_mdl_path=gold_mdl_path,
                    output_path=output_path
                )
            
            print(f"\n{'='*80}")
            print(f"✓ Completed metrics generation")
            print(f"{'='*80}")
        
        return
    
    # Original mode: process MDL files directly
    if not args.mdl_dir:
        print("Error: --mdl-dir is required")
        sys.exit(1)
    
    mdl_dir = Path(args.mdl_dir)
    models_dir = Path(args.models_dir) if args.models_dir else None
    
    if not mdl_dir.exists():
        print(f"Error: MDL directory not found: {mdl_dir}")
        sys.exit(1)
    
    if models_dir and not models_dir.exists():
        print(f"Warning: Models directory not found: {models_dir}")
        models_dir = None
    
    # Process files
    if args.file:
        mdl_files = [mdl_dir / args.file]
    else:
        mdl_files = list(mdl_dir.glob("*.mdl.json"))
    
    if not mdl_files:
        print(f"No MDL files found in {mdl_dir}")
        return
    
    print(f"Found {len(mdl_files)} MDL files\n")
    
    for mdl_file in sorted(mdl_files):
        await enricher.enrich_mdl_file(mdl_file, models_dir)
    
    print(f"\n{'='*60}")
    print(f"✓ Completed processing {len(mdl_files)} files")
    print(f"{'='*60}")


if __name__ == '__main__':
    asyncio.run(main())
