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
        schema_name: str
    ) -> List[str]:
        """Generate SQL example queries for a model."""
        
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
        
        system_prompt = """You are an expert SQL query writer specializing in security and compliance data analysis.
Generate practical SQL example queries that demonstrate common use cases for the given table.
Return ONLY valid JSON array without any markdown formatting, comments, or additional text."""

        # Build user prompt - need to escape braces for LangChain template
        user_prompt_template = """Generate 3-5 practical SQL example queries for this table:

Table: {table_name}
Schema: {schema_name}
Description: {table_desc}

Columns:
{columns_info}

Generate a JSON array of query objects:
[
    {{
        "title": "Query purpose/title",
        "sql": "SELECT ... FROM ... WHERE ...",
        "description": "What this query demonstrates"
    }},
    ...
]

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
                "table_desc": table_desc,
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
            
            return examples
            
        except Exception as e:
            print(f"  Error generating SQL examples: {e}")
            return []
    
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
            
            # First pass: fix types
            print("  Fixing column types...")
            for col in columns:
                col_name = col.get('name', '')
                current_type = col.get('type', 'VARCHAR')
                current_desc = col.get('properties', {}).get('description', '')
                
                correct_type = infer_correct_type(col_name, current_type, current_desc)
                if correct_type != current_type:
                    print(f"    {col_name}: {current_type} -> {correct_type}")
                    col['type'] = correct_type
                    updated = True
            
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
            
            # Generate SQL examples
            print("  Generating SQL examples...")
            sql_examples = await self.generate_sql_examples(model, schema_name)
            
            if sql_examples:
                if 'properties' not in model:
                    model['properties'] = {}
                model['properties']['sql_examples'] = sql_examples
                updated = True
                print(f"    Generated {len(sql_examples)} SQL examples")
        
        # Write updated file
        if updated:
            with open(mdl_path, 'w') as f:
                json.dump(mdl_data, f, indent=2)
            print(f"\n✓ Updated {mdl_path.name}")
        else:
            print(f"\n- No updates needed for {mdl_path.name}")


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
