#!/usr/bin/env python3
"""
LLM-powered enrichment for MDL files.
Enriches column descriptions, fixes incorrect types, and generates SQL examples.
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


from app.settings import get_settings
settings = get_settings()
api_key = settings.OPENAI_API_KEY
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")
    
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
    
    async def enrich_mdl_file(self, mdl_path: Path, models_dir: Optional[Path] = None):
        """Enrich a single MDL file."""
        print(f"\n{'='*60}")
        print(f"Processing: {mdl_path.name}")
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
            
            table_desc = model.get('properties', {}).get('description', '')
            columns = model.get('columns', [])
            other_col_names = [col.get('name', '') for col in columns]
            
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
            
            # Second pass: enrich descriptions (only for columns that need it)
            print("  Enriching column descriptions...")
            columns_to_enrich = []
            for i, col in enumerate(columns):
                col_name = col.get('name', '')
                current_desc = col.get('properties', {}).get('description', '')
                
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
    parser.add_argument('--mdl-dir', type=str, required=True,
                       help='Directory containing MDL files')
    parser.add_argument('--models-dir', type=str, required=False,
                       help='Directory containing dbt models (optional, for reference)')
    parser.add_argument('--file', type=str, required=False,
                       help='Process single file instead of all files')
    
    args = parser.parse_args()
    
    mdl_dir = Path(args.mdl_dir)
    models_dir = Path(args.models_dir) if args.models_dir else None
    
    if not mdl_dir.exists():
        print(f"Error: MDL directory not found: {mdl_dir}")
        sys.exit(1)
    
    if models_dir and not models_dir.exists():
        print(f"Warning: Models directory not found: {models_dir}")
        models_dir = None
    
    # Initialize enricher
    enricher = MDLEnricher()
    
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
