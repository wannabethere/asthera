"""
MDL Transformers
Convert MDL schema to target formats: Cube.js, dbt, etc.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from .mdl_schema_generator import MDLSchema, MDLModel, MDLRelationship, MDLMetric, MDLView


# ============================================================================
# MDL TO CUBE.JS TRANSFORMER
# ============================================================================

class MDLToCubeJsTransformer:
    """Transforms MDL schema to Cube.js definitions"""
    
    def __init__(self):
        self.layer_prefixes = {
            "raw": "raw_",
            "silver": "silver_",
            "gold": "gold_"
        }
    
    def transform_model_to_cube(self, model: MDLModel) -> Dict[str, Any]:
        """Convert MDL model to Cube.js cube definition"""
        cube = {
            "name": model.name,
            "description": model.properties.get("description", ""),
            "dimensions": [],
            "measures": [],
            "preAggregations": []
        }
        
        # Convert columns to dimensions and measures
        for col in model.columns:
            if col.properties.get("category") == "dimension":
                dimension = {
                    "name": col.name,
                    "type": self._map_mdl_type_to_cube_type(col.type),
                    "sql": col.properties.get("sql", f"${{{model.name}.{col.name}}}"),
                    "description": col.properties.get("description", "")
                }
                cube["dimensions"].append(dimension)
            
            elif col.properties.get("category") == "measure" or col.isCalculated:
                measure = {
                    "name": col.name,
                    "type": self._map_mdl_type_to_cube_type(col.type),
                    "sql": col.expression or col.properties.get("sql", f"${{{model.name}.{col.name}}}"),
                    "description": col.properties.get("description", "")
                }
                
                # Add aggregation if specified
                aggregation = col.properties.get("aggregation", "sum")
                if aggregation:
                    measure["type"] = aggregation
                
                cube["measures"].append(measure)
        
        # Add pre-aggregations if available
        pre_agg_str = model.properties.get("pre_aggregations", "")
        if pre_agg_str:
            try:
                cube["preAggregations"] = json.loads(pre_agg_str)
            except:
                pass
        
        return cube
    
    def transform_relationship_to_joins(self, relationship: MDLRelationship) -> Dict[str, Any]:
        """Convert MDL relationship to Cube.js join definition"""
        return {
            "name": relationship.name,
            "sql": relationship.condition,
            "relationship": relationship.joinType.lower()
        }
    
    def transform_view_to_cube_view(self, view: MDLView) -> Dict[str, Any]:
        """Convert MDL view to Cube.js view definition"""
        return {
            "name": view.name,
            "sql": view.statement,
            "description": view.properties.get("description", "")
        }
    
    def generate_cubejs_files(
        self,
        mdl_schema: MDLSchema,
        output_dir: Path,
        layer: Optional[str] = None
    ) -> List[str]:
        """
        Generate Cube.js files from MDL schema.
        
        Args:
            mdl_schema: MDL schema to transform
            output_dir: Output directory for Cube.js files
            layer: Optional layer filter (raw, silver, gold)
            
        Returns:
            List of generated file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = []
        
        # Filter models by layer if specified
        models = mdl_schema.models
        if layer:
            models = [m for m in models if m.layer == layer]
        
        # Generate cube files for each model
        for model in models:
            cube = self.transform_model_to_cube(model)
            
            # JSON format
            json_path = output_dir / f"{model.name}.json"
            with open(json_path, 'w') as f:
                json.dump(cube, f, indent=2)
            generated_files.append(str(json_path))
            
            # JavaScript format
            js_path = output_dir / f"{model.name}.js"
            with open(js_path, 'w') as f:
                f.write(self._cube_to_javascript(cube, model.name))
            generated_files.append(str(js_path))
        
        return generated_files
    
    def _cube_to_javascript(self, cube: Dict[str, Any], cube_name: str) -> str:
        """Convert cube definition to JavaScript format"""
        lines = [f"cube(`{cube_name}`, {{"]
        
        if cube.get("description"):
            lines.append(f'  description: `{cube["description"]}`,')
        
        # Dimensions
        if cube.get("dimensions"):
            lines.append("  dimensions: {")
            for dim in cube["dimensions"]:
                lines.append(f"    {dim['name']}: {{")
                lines.append(f"      type: `{dim['type']}`,",)
                lines.append(f"      sql: `{dim['sql']}`,",)
                if dim.get("description"):
                    lines.append(f"      description: `{dim['description']}`,",)
                lines.append("    },")
            lines.append("  },")
        
        # Measures
        if cube.get("measures"):
            lines.append("  measures: {")
            for measure in cube["measures"]:
                lines.append(f"    {measure['name']}: {{")
                lines.append(f"      type: `{measure['type']}`,",)
                lines.append(f"      sql: `{measure['sql']}`,",)
                if measure.get("description"):
                    lines.append(f"      description: `{measure['description']}`,",)
                lines.append("    },")
            lines.append("  },")
        
        # Pre-aggregations
        if cube.get("preAggregations"):
            lines.append("  preAggregations: {")
            lines.append("    // Pre-aggregation definitions")
            lines.append("  },")
        
        lines.append("});")
        
        return "\n".join(lines)
    
    def _map_mdl_type_to_cube_type(self, mdl_type: str) -> str:
        """Map MDL types to Cube.js types"""
        type_mapping = {
            "VARCHAR": "string",
            "STRING": "string",
            "TEXT": "string",
            "DOUBLE": "number",
            "FLOAT": "number",
            "INTEGER": "number",
            "BIGINT": "number",
            "BOOLEAN": "boolean",
            "TIMESTAMP": "time",
            "DATE": "time"
        }
        return type_mapping.get(mdl_type.upper(), "string")


# ============================================================================
# MDL TO DBT TRANSFORMER
# ============================================================================

class MDLToDbtTransformer:
    """Transforms MDL schema to dbt models and schema.yml"""
    
    def __init__(self):
        self.models_dir = Path("models")
        self.schema_file = Path("schema.yml")
    
    def transform_model_to_dbt_sql(
        self,
        model: MDLModel,
        transformations: Optional[List[Any]] = None
    ) -> str:
        """Convert MDL model to dbt SQL model"""
        # Find transformation SQL if available
        transformation_sql = None
        if transformations:
            for trans in transformations:
                if trans.target_model == model.name:
                    transformation_sql = trans.sql
                    break
        
        # Use refSql if available, otherwise use transformation SQL
        sql = model.refSql or transformation_sql or f"SELECT * FROM {model.name}"
        
        # Convert to dbt format
        dbt_sql = f"""-- dbt model: {model.name}
{{{{ config(materialized='table') }}}}

{sql}"""
        
        return dbt_sql
    
    def generate_dbt_schema_yml(
        self,
        mdl_schema: MDLSchema,
        models: Optional[List[MDLModel]] = None
    ) -> str:
        """Generate dbt schema.yml from MDL schema"""
        if models is None:
            models = mdl_schema.models
        
        lines = ["version: 2", "", "models:"]
        
        for model in models:
            lines.append(f"  - name: {model.name}")
            if model.properties.get("description"):
                lines.append(f"    description: \"{model.properties['description']}\"")
            lines.append("    columns:")
            
            for col in model.columns:
                lines.append(f"      - name: {col.name}")
                if col.properties.get("description"):
                    lines.append(f"        description: \"{col.properties['description']}\"")
                lines.append(f"        data_type: {col.type}")
                
                # Add tests
                if col.notNull:
                    lines.append("        tests:")
                    lines.append("          - not_null")
            
            lines.append("")
        
        # Add metrics if available
        if mdl_schema.metrics:
            lines.append("metrics:")
            for metric in mdl_schema.metrics:
                lines.append(f"  - name: {metric.name}")
                lines.append(f"    model: {metric.baseObject}")
                if metric.dimension:
                    lines.append("    dimensions:")
                    for dim in metric.dimension:
                        lines.append(f"      - {dim.name}")
                if metric.measure:
                    lines.append("    measures:")
                    for measure in metric.measure:
                        lines.append(f"      - name: {measure.name}")
                        lines.append(f"        expression: {measure.expression or measure.name}")
                lines.append("")
        
        return "\n".join(lines)
    
    def generate_dbt_files(
        self,
        mdl_schema: MDLSchema,
        output_dir: Path,
        layer: Optional[str] = None
    ) -> List[str]:
        """
        Generate dbt files from MDL schema.
        
        Args:
            mdl_schema: MDL schema to transform
            output_dir: Output directory for dbt files
            layer: Optional layer filter (raw, silver, gold)
            
        Returns:
            List of generated file paths
        """
        generated_files = []
        
        # Filter models by layer if specified
        models = mdl_schema.models
        if layer:
            models = [m for m in models if m.layer == layer]
        
        # Create models directory
        models_dir = output_dir / "models" / (layer or "all")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate SQL files for each model
        for model in models:
            dbt_sql = self.transform_model_to_dbt_sql(
                model,
                mdl_schema.transformations
            )
            
            sql_path = models_dir / f"{model.name}.sql"
            with open(sql_path, 'w') as f:
                f.write(dbt_sql)
            generated_files.append(str(sql_path))
        
        # Generate schema.yml
        schema_yml = self.generate_dbt_schema_yml(mdl_schema, models)
        schema_path = output_dir / "schema.yml"
        with open(schema_path, 'w') as f:
            f.write(schema_yml)
        generated_files.append(str(schema_path))
        
        return generated_files


# ============================================================================
# MDL TO TRANSFORMATIONS EXPORTER
# ============================================================================

class MDLToTransformationsExporter:
    """Exports transformations from MDL schema to SQL files"""
    
    def export_transformations(
        self,
        mdl_schema: MDLSchema,
        output_dir: Path
    ) -> List[str]:
        """Export transformations to SQL files"""
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = []
        
        for transformation in mdl_schema.transformations:
            # Create directory structure: transformations/{source_layer}_to_{target_layer}/
            trans_dir = output_dir / f"{transformation.source_layer}_to_{transformation.target_layer}"
            trans_dir.mkdir(parents=True, exist_ok=True)
            
            # Write SQL file
            sql_path = trans_dir / f"{transformation.source_model}.sql"
            with open(sql_path, 'w') as f:
                f.write(f"-- Transformation: {transformation.name}\n")
                f.write(f"-- Source: {transformation.source_layer}.{transformation.source_model}\n")
                f.write(f"-- Target: {transformation.target_layer}.{transformation.target_model}\n")
                if transformation.description:
                    f.write(f"-- Description: {transformation.description}\n")
                f.write("\n")
                f.write(transformation.sql or "")
            
            generated_files.append(str(sql_path))
            
            # Write transformation metadata JSON
            metadata_path = trans_dir / f"{transformation.source_model}.json"
            with open(metadata_path, 'w') as f:
                json.dump({
                    "name": transformation.name,
                    "source_layer": transformation.source_layer,
                    "target_layer": transformation.target_layer,
                    "source_model": transformation.source_model,
                    "target_model": transformation.target_model,
                    "steps": transformation.steps,
                    "description": transformation.description,
                    "properties": transformation.properties
                }, f, indent=2)
            
            generated_files.append(str(metadata_path))
        
        return generated_files

