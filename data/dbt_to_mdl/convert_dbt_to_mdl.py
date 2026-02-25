#!/usr/bin/env python3
"""
Convert dbt models to MDL (Model Definition Language) format.

This script scans dbt model directories, parses YAML and SQL files,
and generates MDL JSON files following the MDL schema specification.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install it with: pip install pyyaml")
    sys.exit(1)


@dataclass
class ColumnInfo:
    """Information about a column."""
    name: str
    type: str = "VARCHAR"
    not_null: bool = False
    description: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class ModelInfo:
    """Information about a dbt model."""
    name: str
    description: Optional[str] = None
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key: Optional[str] = None
    sql: Optional[str] = None
    table_reference: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)


class DbtToMdlConverter:
    """Converts dbt models to MDL format."""
    
    # SQL type to MDL type mapping
    TYPE_MAPPING = {
        "STRING": "VARCHAR",
        "VARCHAR": "VARCHAR",
        "TEXT": "VARCHAR",
        "CHAR": "VARCHAR",
        "INTEGER": "BIGINT",
        "INT": "BIGINT",
        "BIGINT": "BIGINT",
        "SMALLINT": "BIGINT",
        "TINYINT": "BIGINT",
        "DOUBLE": "DOUBLE",
        "FLOAT": "DOUBLE",
        "REAL": "DOUBLE",
        "DECIMAL": "DOUBLE",
        "NUMERIC": "DOUBLE",
        "BOOLEAN": "BOOLEAN",
        "BOOL": "BOOLEAN",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP",
        "TIMESTAMP_NTZ": "TIMESTAMP",
        "TIMESTAMP_LTZ": "TIMESTAMP",
        "ARRAY": "VARCHAR",  # Arrays stored as JSON strings
        "STRUCT": "VARCHAR",  # Structs stored as JSON strings
        "VARIANT": "VARCHAR",  # Variants stored as JSON strings
        "OBJECT": "VARCHAR",  # Objects stored as JSON strings
    }
    
    def __init__(self, models_dir: Path, output_dir: Path):
        """
        Initialize the converter.
        
        Args:
            models_dir: Directory containing dbt models
            output_dir: Directory to write MDL files
        """
        self.models_dir = Path(models_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def parse_yaml_file(self, yaml_path: Path) -> List[ModelInfo]:
        """Parse a dbt YAML file and extract model information."""
        models = []
        
        try:
            with open(yaml_path, 'r') as f:
                content = yaml.safe_load(f)
            
            if not content or 'models' not in content:
                return models
            
            for model_def in content['models']:
                model_name = model_def.get('name')
                if not model_name:
                    continue
                
                model = ModelInfo(
                    name=model_name,
                    description=model_def.get('description', '').strip() or None
                )
                
                # Extract columns from YAML if available
                if 'columns' in model_def:
                    for col_def in model_def['columns']:
                        col_name = col_def.get('name')
                        if not col_name:
                            continue
                        
                        col_type = col_def.get('data_type', 'VARCHAR')
                        mdl_type = self._map_sql_type_to_mdl(col_type)
                        
                        column = ColumnInfo(
                            name=col_name,
                            type=mdl_type,
                            not_null=col_def.get('not_null', False),
                            description=col_def.get('description', '').strip() or None
                        )
                        
                        if column.description:
                            column.properties['displayName'] = self._to_display_name(col_name)
                            column.properties['description'] = column.description
                        
                        model.columns.append(column)
                
                # Extract primary key from config or columns
                if 'config' in model_def:
                    config = model_def['config']
                    if 'unique_key' in config:
                        model.primary_key = config['unique_key']
                
                models.append(model)
        
        except Exception as e:
            print(f"Error parsing YAML file {yaml_path}: {e}")
        
        return models
    
    def extract_columns_from_sql(self, sql_path: Path) -> List[ColumnInfo]:
        """Extract column information from SQL SELECT statement."""
        columns = []
        
        try:
            with open(sql_path, 'r') as f:
                sql_content = f.read()
            
            # Find the final SELECT statement (after all CTEs)
            # Look for the last SELECT that's not in a CTE
            # Try multiple patterns
            patterns = [
                r'select\s+(.*?)\s+from\s+cte\s*$',  # SELECT ... FROM cte
                r'select\s+(.*?)\s+from\s+[a-zA-Z_][a-zA-Z0-9_]*\s*$',  # SELECT ... FROM table
                r'select\s+(.*?)\s+from\s+[^\s]+',  # Any SELECT ... FROM
            ]
            
            match = None
            for pattern in patterns:
                match = re.search(pattern, sql_content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                if match:
                    break
            
            if match:
                select_clause = match.group(1)
                
                # Split by comma, but be careful with nested structures
                parts = self._split_select_clause(select_clause)
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # Skip dbt macros like {{ ... }}
                    if '{{' in part and '}}' in part:
                        continue
                    
                    # Extract column name and alias
                    # Handle: column_name, column_name as alias, expression as alias
                    alias_match = re.search(r'\s+as\s+(\w+)', part, re.IGNORECASE)
                    if alias_match:
                        col_name = alias_match.group(1)
                    else:
                        # Try to extract the last identifier (before any function call)
                        # Remove function calls and get the identifier
                        cleaned = re.sub(r'\w+\s*\([^)]*\)', '', part)
                        identifiers = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', cleaned)
                        if identifiers:
                            col_name = identifiers[-1]
                        else:
                            continue
                    
                    # Skip if it's a dbt function
                    if col_name.startswith('_') and 'dbt' in part.lower():
                        continue
                    
                    # Infer type from column name or expression
                    col_type = self._infer_column_type(part, col_name)
                    
                    column = ColumnInfo(
                        name=col_name,
                        type=col_type,
                        not_null=False
                    )
                    
                    # Check if it's a primary key (will be set in process_model)
                    if '_surrogate_key' in col_name.lower():
                        column.not_null = True
                    elif col_name.lower().endswith('_id') and not col_name.startswith('_'):
                        column.not_null = True
                    
                    columns.append(column)
        
        except Exception as e:
            print(f"Error extracting columns from SQL {sql_path}: {e}")
        
        return columns
    
    def _split_select_clause(self, clause: str) -> List[str]:
        """Split SELECT clause by comma, handling nested parentheses."""
        parts = []
        current = ""
        depth = 0
        
        for char in clause:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                if current.strip():
                    parts.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            parts.append(current.strip())
        
        return parts
    
    def _infer_column_type(self, expression: str, col_name: str) -> str:
        """Infer MDL type from SQL expression or column name."""
        expression_upper = expression.upper()
        col_name_lower = col_name.lower()
        
        # Check for type hints in expression
        if any(t in expression_upper for t in ['TIMESTAMP', 'DATE']):
            if 'TIMESTAMP' in expression_upper:
                return "TIMESTAMP"
            return "DATE"
        
        if any(t in expression_upper for t in ['INT', 'BIGINT', 'SMALLINT']):
            return "BIGINT"
        
        if any(t in expression_upper for t in ['DOUBLE', 'FLOAT', 'DECIMAL', 'NUMERIC']):
            return "DOUBLE"
        
        if any(t in expression_upper for t in ['BOOLEAN', 'BOOL']):
            return "BOOLEAN"
        
        # Infer from column name patterns
        if any(pattern in col_name_lower for pattern in ['_id', '_key']):
            return "VARCHAR"
        
        if any(pattern in col_name_lower for pattern in ['_timestamp', '_at', '_date', '_time']):
            if '_date' in col_name_lower:
                return "DATE"
            return "TIMESTAMP"
        
        if any(pattern in col_name_lower for pattern in ['_count', '_num', '_size', '_age', '_days']):
            return "BIGINT"
        
        if any(pattern in col_name_lower for pattern in ['_score', '_rate', '_ratio', '_percent']):
            return "DOUBLE"
        
        if any(pattern in col_name_lower for pattern in ['_is_', 'is_', 'has_', '_flag']):
            return "BOOLEAN"
        
        # Default to VARCHAR
        return "VARCHAR"
    
    def _map_sql_type_to_mdl(self, sql_type: str) -> str:
        """Map SQL type to MDL type."""
        sql_type_upper = sql_type.upper().strip()
        
        # Remove size/precision info
        sql_type_upper = re.sub(r'\([^)]*\)', '', sql_type_upper)
        sql_type_upper = sql_type_upper.strip()
        
        return self.TYPE_MAPPING.get(sql_type_upper, "VARCHAR")
    
    def _to_display_name(self, name: str) -> str:
        """Convert snake_case to Display Name."""
        return ' '.join(word.capitalize() for word in name.split('_'))
    
    def find_model_files(self, base_path: Path) -> List[Tuple[Path, Path]]:
        """
        Find all model YAML and SQL file pairs.
        
        Returns:
            List of (yaml_path, sql_path) tuples
        """
        model_pairs = []
        
        # Find all YAML files
        for yaml_path in base_path.rglob('*.yaml'):
            if yaml_path.name.startswith('.'):
                continue
            
            # Look for corresponding SQL file
            sql_path = yaml_path.parent / yaml_path.stem.replace('.yaml', '.sql')
            if not sql_path.exists():
                # Try with model name from YAML
                try:
                    with open(yaml_path, 'r') as f:
                        content = yaml.safe_load(f)
                    if content and 'models' in content:
                        for model in content.get('models', []):
                            model_name = model.get('name')
                            if model_name:
                                sql_path = yaml_path.parent / f"{model_name}.sql"
                                if sql_path.exists():
                                    model_pairs.append((yaml_path, sql_path))
                                    break
                except:
                    pass
            else:
                model_pairs.append((yaml_path, sql_path))
        
        # Also find SQL files without YAML
        for sql_path in base_path.rglob('*.sql'):
            if sql_path.name.startswith('.'):
                continue
            
            yaml_path = sql_path.parent / f"{sql_path.stem}.yaml"
            if not yaml_path.exists():
                # Create a minimal model info from SQL
                model_pairs.append((None, sql_path))
        
        return model_pairs
    
    def process_model(self, yaml_path: Optional[Path], sql_path: Path) -> Optional[ModelInfo]:
        """Process a single model from YAML and SQL files."""
        model = None
        
        # Parse YAML if available
        if yaml_path and yaml_path.exists():
            models = self.parse_yaml_file(yaml_path)
            if models:
                model = models[0]  # Take first model from YAML
        
        # If no YAML or no model found, create from SQL
        if not model:
            # Extract model name from SQL file
            model_name = sql_path.stem
            model = ModelInfo(name=model_name)
        
        # Read SQL file
        if sql_path.exists():
            with open(sql_path, 'r') as f:
                model.sql = f.read()
            
            # Extract columns from SQL if not already in YAML
            if not model.columns:
                model.columns = self.extract_columns_from_sql(sql_path)
            
            # Try to find primary key in SQL or columns
            if not model.primary_key:
                # Look for _surrogate_key first (most common)
                for col in model.columns:
                    if '_surrogate_key' in col.name.lower():
                        model.primary_key = col.name
                        break
                
                # If no surrogate key, look for id fields
                if not model.primary_key:
                    for col in model.columns:
                        col_lower = col.name.lower()
                        # Prefer non-prefixed id fields (e.g., 'id' over 'connection_id')
                        if col_lower == 'id':
                            model.primary_key = col.name
                            break
                        elif col_lower.endswith('_id') and not col_lower.startswith('_'):
                            model.primary_key = col.name
                            break
        
        return model
    
    def determine_table_reference(self, model: ModelInfo) -> Optional[Dict[str, str]]:
        """Determine table reference from model name or SQL."""
        # For silver/gold models, they typically reference bronze/silver tables
        # We'll use the model name as the table name
        table_name = model.name
        
        return {
            "table": table_name
        }
    
    def convert_to_mdl(self, models: List[ModelInfo], catalog: str, schema: str) -> Dict[str, Any]:
        """Convert model information to MDL format."""
        mdl_models = []
        
        for model in models:
            mdl_model = {
                "name": model.name,
            }
            
            # Add description to properties
            if model.description:
                mdl_model["properties"] = {
                    "description": model.description,
                    "displayName": self._to_display_name(model.name)
                }
            
            # Determine if we use tableReference or refSql
            # If SQL is complex (has CTEs, transformations), use refSql
            # Otherwise, use tableReference
            if model.sql and self._is_complex_sql(model.sql):
                mdl_model["refSql"] = model.sql
            else:
                table_ref = self.determine_table_reference(model)
                if table_ref:
                    mdl_model["tableReference"] = table_ref
            
            # Add primary key if available
            if model.primary_key:
                mdl_model["primaryKey"] = model.primary_key
            
            # Add columns
            if model.columns:
                mdl_model["columns"] = []
                for col in model.columns:
                    col_def = {
                        "name": col.name,
                        "type": col.type
                    }
                    
                    if col.not_null:
                        col_def["notNull"] = col.not_null
                    
                    if col.properties or col.description:
                        col_def["properties"] = {}
                        if col.description:
                            col_def["properties"]["description"] = col.description
                        if "displayName" in col.properties:
                            col_def["properties"]["displayName"] = col.properties["displayName"]
                        else:
                            col_def["properties"]["displayName"] = self._to_display_name(col.name)
                    
                    mdl_model["columns"].append(col_def)
            
            mdl_models.append(mdl_model)
        
        return {
            "$schema": "https://github.com/Canner/AsteraAI/tree/main/astera-mdl/mdl.schema.json",
            "catalog": catalog,
            "schema": schema,
            "models": mdl_models
        }
    
    def _is_complex_sql(self, sql: str) -> bool:
        """Check if SQL is complex (has CTEs, transformations, etc.)."""
        sql_upper = sql.upper()
        # Check for CTEs, window functions, aggregations, etc.
        complex_patterns = [
            r'\bWITH\s+\w+',  # CTEs
            r'\bROW_NUMBER\(\)',  # Window functions
            r'\bGROUP\s+BY',  # Aggregations
            r'\bJOIN\s+',  # Joins
            r'\bUNION\s+',  # Unions
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, sql_upper):
                return True
        
        return False
    
    def convert_directory(self, subdirectory: str, catalog: str, schema: str):
        """Convert all models in a subdirectory to MDL."""
        dir_path = self.models_dir / subdirectory
        
        if not dir_path.exists():
            print(f"Directory not found: {dir_path}")
            return
        
        print(f"Processing directory: {dir_path}")
        
        # Find all model files
        model_pairs = self.find_model_files(dir_path)
        
        if not model_pairs:
            print(f"No model files found in {dir_path}")
            return
        
        # Process each model
        models = []
        for yaml_path, sql_path in model_pairs:
            if sql_path:
                model = self.process_model(yaml_path, sql_path)
                if model:
                    models.append(model)
                    print(f"  Processed: {model.name}")
        
        if not models:
            print(f"No models found in {dir_path}")
            return
        
        # Convert to MDL
        mdl_schema = self.convert_to_mdl(models, catalog, schema)
        
        # Write MDL file
        output_file = self.output_dir / f"{schema}.mdl.json"
        with open(output_file, 'w') as f:
            json.dump(mdl_schema, f, indent=2)
        
        print(f"Generated MDL file: {output_file} ({len(models)} models)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert dbt models to MDL format')
    parser.add_argument('--models-dir', type=str, required=True,
                       help='Directory containing dbt models')
    parser.add_argument('--output-dir', type=str, required=True,
                       help='Output directory for MDL files')
    parser.add_argument('--subdirectory', type=str, required=True,
                       help='Subdirectory to process (e.g., aws/guardduty/silver)')
    parser.add_argument('--catalog', type=str, default='product_knowledge',
                       help='MDL catalog name')
    parser.add_argument('--schema', type=str, required=True,
                       help='MDL schema name (e.g., aws_guardduty)')
    
    args = parser.parse_args()
    
    converter = DbtToMdlConverter(
        models_dir=Path(args.models_dir),
        output_dir=Path(args.output_dir)
    )
    
    converter.convert_directory(
        subdirectory=args.subdirectory,
        catalog=args.catalog,
        schema=args.schema
    )


if __name__ == '__main__':
    main()
