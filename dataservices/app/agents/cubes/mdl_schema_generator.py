"""
MDL Schema Generator
Converts agent outputs (cubes, transformations, metadata) to MDL (Model Definition Language) format.

MDL serves as the single source of truth for:
- Models (raw, silver, gold layers)
- Relationships
- Metrics
- Views
- Transformations
- Governance metadata
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import json
from datetime import datetime

from .cube_generation_agent import (
    TableMetadataSummary,
    CubeDefinition,
    ViewDefinition,
    TransformationStep,
    RelationshipMapping,
    LODConfig
)


# ============================================================================
# MDL SCHEMA MODELS
# ============================================================================

class MDLColumn(BaseModel):
    """MDL column definition"""
    name: str
    type: str
    relationship: Optional[str] = None
    isCalculated: Optional[bool] = False
    notNull: Optional[bool] = False
    expression: Optional[str] = None
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class MDLModel(BaseModel):
    """MDL model definition"""
    name: str
    refSql: Optional[str] = None
    baseObject: Optional[str] = None
    tableReference: Optional[Dict[str, str]] = None
    columns: List[MDLColumn] = Field(default_factory=list)
    primaryKey: Optional[str] = None
    cached: Optional[bool] = False
    refreshTime: Optional[str] = None
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)
    layer: Optional[str] = None  # raw, silver, gold - custom property


class MDLRelationship(BaseModel):
    """MDL relationship definition"""
    name: str
    models: List[str]  # Exactly 2 model names
    joinType: str  # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
    condition: str
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)
    layer: Optional[str] = None  # raw, silver, gold - custom property


class MDLMetric(BaseModel):
    """MDL metric definition"""
    name: str
    baseObject: str  # Model name
    dimension: List[MDLColumn] = Field(default_factory=list)
    measure: List[MDLColumn] = Field(default_factory=list)
    timeGrain: Optional[List[Dict[str, Any]]] = None
    cached: Optional[bool] = False
    refreshTime: Optional[str] = None
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class MDLView(BaseModel):
    """MDL view definition"""
    name: str
    statement: str
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class MDLTransformation(BaseModel):
    """Transformation definition (custom extension to MDL)"""
    name: str
    source_layer: str  # raw, silver
    target_layer: str  # silver, gold
    source_model: str
    target_model: str
    steps: List[Dict[str, Any]]  # Transformation steps
    sql: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class MDLGovernance(BaseModel):
    """Governance metadata (custom extension to MDL)"""
    data_quality_rules: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_requirements: List[str] = Field(default_factory=list)
    data_lineage: Dict[str, List[str]] = Field(default_factory=dict)
    access_controls: Dict[str, List[str]] = Field(default_factory=dict)
    retention_policies: Dict[str, str] = Field(default_factory=dict)
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class MDLSchema(BaseModel):
    """Complete MDL schema with all components"""
    catalog: str
    schema: str
    models: List[MDLModel] = Field(default_factory=list)
    relationships: List[MDLRelationship] = Field(default_factory=list)
    metrics: List[MDLMetric] = Field(default_factory=list)
    views: List[MDLView] = Field(default_factory=list)
    transformations: List[MDLTransformation] = Field(default_factory=list)  # Custom extension
    governance: Optional[MDLGovernance] = None  # Custom extension
    enumDefinitions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    macros: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


# ============================================================================
# MDL SCHEMA GENERATOR
# ============================================================================

class MDLSchemaGenerator:
    """Generates MDL schema from agent outputs"""
    
    def __init__(self, catalog: str = "default_catalog", schema: str = "public"):
        self.catalog = catalog
        self.schema = schema
    
    def generate_mdl_schema(
        self,
        table_metadata: List[TableMetadataSummary],
        raw_cubes: List[CubeDefinition],
        silver_cubes: List[CubeDefinition],
        gold_cubes: List[CubeDefinition],
        views: List[ViewDefinition],
        raw_to_silver_steps: List[TransformationStep],
        silver_to_gold_steps: List[TransformationStep],
        relationships: List[RelationshipMapping],
        lod_configs: List[LODConfig],
        data_mart_plans: Optional[List[Dict[str, Any]]] = None,
        gold_metrics: Optional[Dict[str, Any]] = None
    ) -> MDLSchema:
        """
        Generate complete MDL schema from all agent outputs.
        
        Args:
            table_metadata: Enriched table metadata
            raw_cubes: Raw layer cube definitions
            silver_cubes: Silver layer cube definitions
            gold_cubes: Gold layer cube definitions
            views: View definitions
            raw_to_silver_steps: Raw to silver transformation steps
            silver_to_gold_steps: Silver to gold transformation steps
            relationships: Relationship mappings
            lod_configs: LOD configurations
            data_mart_plans: Data mart plans (optional)
            gold_metrics: Gold metrics (optional)
            
        Returns:
            Complete MDL schema
        """
        mdl = MDLSchema(
            catalog=self.catalog,
            schema=self.schema,
            properties={
                "generated_at": datetime.now().isoformat(),
                "architecture": "medallion",
                "layers": "raw,silver,gold"
            }
        )
        
        # Generate models for each layer
        mdl.models.extend(self._generate_models_from_cubes(raw_cubes, "raw", table_metadata))
        mdl.models.extend(self._generate_models_from_cubes(silver_cubes, "silver", table_metadata))
        mdl.models.extend(self._generate_models_from_cubes(gold_cubes, "gold", table_metadata))
        
        # Generate relationships
        mdl.relationships.extend(self._generate_relationships(relationships))
        
        # Generate views
        mdl.views.extend(self._generate_views(views))
        
        # Generate transformations
        mdl.transformations.extend(
            self._generate_transformations(raw_to_silver_steps, "raw", "silver")
        )
        mdl.transformations.extend(
            self._generate_transformations(silver_to_gold_steps, "silver", "gold")
        )
        
        # Generate metrics from gold metrics
        if gold_metrics:
            mdl.metrics.extend(self._generate_metrics_from_gold_metrics(gold_metrics))
        
        # Generate governance metadata
        mdl.governance = self._generate_governance(
            table_metadata,
            lod_configs,
            relationships
        )
        
        return mdl
    
    def _generate_models_from_cubes(
        self,
        cubes: List[CubeDefinition],
        layer: str,
        table_metadata: List[TableMetadataSummary]
    ) -> List[MDLModel]:
        """Convert cube definitions to MDL models"""
        models = []
        
        for cube in cubes:
            # Find corresponding table metadata
            table_meta = next(
                (t for t in table_metadata if t.table_name in cube.name),
                None
            )
            
            # Extract table name (remove layer prefix if present)
            model_name = cube.name.replace(f"{layer}_", "").replace("raw_", "").replace("silver_", "").replace("gold_", "")
            
            # Build columns from cube dimensions and measures
            columns = []
            
            # Add dimensions as columns
            for dim in cube.dimensions:
                # Handle both dict and object formats
                if isinstance(dim, dict):
                    dim_name = dim.get("name", "")
                    dim_type = dim.get("type", "string")
                    dim_sql = dim.get("sql", f"${{{model_name}.{dim_name}}}")
                    dim_desc = dim.get("description", "")
                else:
                    dim_name = getattr(dim, "name", "")
                    dim_type = getattr(dim, "type", "string")
                    dim_sql = getattr(dim, "sql", f"${{{model_name}.{dim_name}}}")
                    dim_desc = getattr(dim, "description", "")
                
                columns.append(MDLColumn(
                    name=dim_name,
                    type=self._map_cube_type_to_mdl_type(dim_type),
                    properties={
                        "description": dim_desc or "",
                        "category": "dimension",
                        "sql": dim_sql
                    }
                ))
            
            # Add measures as calculated columns
            for measure in cube.measures:
                # Handle both dict and object formats
                if isinstance(measure, dict):
                    measure_name = measure.get("name", "")
                    measure_type = measure.get("type", "number")
                    measure_sql = measure.get("sql", f"${{{model_name}.{measure_name}}}")
                    measure_desc = measure.get("description", "")
                    measure_agg = measure.get("aggregation", "sum")
                else:
                    measure_name = getattr(measure, "name", "")
                    measure_type = getattr(measure, "type", "number")
                    measure_sql = getattr(measure, "sql", f"${{{model_name}.{measure_name}}}")
                    measure_desc = getattr(measure, "description", "")
                    measure_agg = getattr(measure, "aggregation", "sum")
                
                columns.append(MDLColumn(
                    name=measure_name,
                    type=self._map_cube_type_to_mdl_type(measure_type),
                    isCalculated=True,
                    expression=measure_sql,
                    properties={
                        "description": measure_desc or "",
                        "category": "measure",
                        "aggregation": measure_agg
                    }
                ))
            
            # Determine primary key
            primary_key = None
            if table_meta:
                # Look for primary key columns
                pk_cols = [col.name for col in table_meta.columns if col.is_primary_key]
                if pk_cols:
                    primary_key = pk_cols[0]
            
            # Build model
            model = MDLModel(
                name=model_name,
                refSql=self._generate_ref_sql(cube, layer),
                columns=columns,
                primaryKey=primary_key,
                layer=layer,
                properties={
                    "description": cube.description or "",
                    "cube_name": cube.name,
                    "pre_aggregations": json.dumps(cube.pre_aggregations) if cube.pre_aggregations else ""
                }
            )
            
            models.append(model)
        
        return models
    
    def _generate_ref_sql(self, cube: CubeDefinition, layer: str) -> str:
        """Generate refSql for MDL model from cube definition"""
        # For now, generate a simple SELECT statement
        # In production, this would use the actual table reference
        table_name = cube.name.replace(f"{layer}_", "")
        return f"SELECT * FROM {self.schema}.{table_name}"
    
    def _map_cube_type_to_mdl_type(self, cube_type: str) -> str:
        """Map Cube.js types to MDL types"""
        type_mapping = {
            "string": "VARCHAR",
            "number": "DOUBLE",
            "boolean": "BOOLEAN",
            "time": "TIMESTAMP",
            "date": "DATE"
        }
        return type_mapping.get(cube_type.lower(), "VARCHAR")
    
    def _generate_relationships(
        self,
        relationships: List[RelationshipMapping]
    ) -> List[MDLRelationship]:
        """Convert relationship mappings to MDL relationships"""
        mdl_relationships = []
        
        for rel in relationships:
            # Map join types
            join_type_map = {
                "MANY_TO_ONE": "MANY_TO_ONE",
                "ONE_TO_MANY": "ONE_TO_MANY",
                "ONE_TO_ONE": "ONE_TO_ONE",
                "MANY_TO_MANY": "MANY_TO_MANY"
            }
            
            mdl_rel = MDLRelationship(
                name=f"{rel.child_table}_to_{rel.parent_table}",
                models=[rel.child_table, rel.parent_table],
                joinType=join_type_map.get(rel.join_type, "MANY_TO_ONE"),
                condition=rel.join_condition,
                layer=rel.layer,
                properties={
                    "description": f"Relationship from {rel.child_table} to {rel.parent_table}"
                }
            )
            
            mdl_relationships.append(mdl_rel)
        
        return mdl_relationships
    
    def _generate_views(self, views: List[ViewDefinition]) -> List[MDLView]:
        """Convert view definitions to MDL views"""
        mdl_views = []
        
        for view in views:
            mdl_view = MDLView(
                name=view.name,
                statement=view.sql,
                properties={
                    "description": view.description or ""
                }
            )
            mdl_views.append(mdl_view)
        
        return mdl_views
    
    def _generate_transformations(
        self,
        steps: List[TransformationStep],
        source_layer: str,
        target_layer: str
    ) -> List[MDLTransformation]:
        """Convert transformation steps to MDL transformations"""
        transformations = []
        
        # Group steps by output table
        steps_by_table = {}
        for step in steps:
            # Handle both dict and object formats
            if isinstance(step, dict):
                table_name = step.get("output_table", step.get("table_name", "unknown"))
                step_name = step.get("step_name", "")
                step_type = step.get("step_type", step.get("transformation_type", ""))
                sql_logic = step.get("sql_logic", "")
                description = step.get("description", "")
            else:
                table_name = getattr(step, "output_table", getattr(step, "table_name", "unknown"))
                step_name = getattr(step, "step_name", "")
                step_type = getattr(step, "step_type", getattr(step, "transformation_type", ""))
                sql_logic = getattr(step, "sql_logic", "")
                description = getattr(step, "description", "")
            
            if table_name not in steps_by_table:
                steps_by_table[table_name] = []
            steps_by_table[table_name].append(step)
        
        # Create transformation for each table
        for table_name, table_steps in steps_by_table.items():
            # Combine SQL from all steps
            combined_sql_parts = []
            step_dicts = []
            
            for step in table_steps:
                if isinstance(step, dict):
                    step_name = step.get("step_name", "")
                    step_type = step.get("step_type", step.get("transformation_type", ""))
                    sql_logic = step.get("sql_logic", "")
                    description = step.get("description", "")
                    step_dicts.append(step)
                else:
                    step_name = getattr(step, "step_name", "")
                    step_type = getattr(step, "step_type", getattr(step, "transformation_type", ""))
                    sql_logic = getattr(step, "sql_logic", "")
                    description = getattr(step, "description", "")
                    step_dicts.append(step.dict() if hasattr(step, 'dict') else {
                        "step_name": step_name,
                        "step_type": step_type,
                        "sql_logic": sql_logic,
                        "description": description
                    })
                
                combined_sql_parts.append(f"-- {step_name}: {description}\n{sql_logic}")
            
            combined_sql = "\n\n".join(combined_sql_parts)
            
            # Extract transformation types
            trans_types = set()
            for step in table_steps:
                if isinstance(step, dict):
                    trans_types.add(step.get("step_type", step.get("transformation_type", "")))
                else:
                    trans_types.add(getattr(step, "step_type", getattr(step, "transformation_type", "")))
            
            transformation = MDLTransformation(
                name=f"{source_layer}_to_{target_layer}_{table_name}",
                source_layer=source_layer,
                target_layer=target_layer,
                source_model=table_name,
                target_model=f"{target_layer}_{table_name}",
                steps=step_dicts,
                sql=combined_sql,
                description=f"Transform {table_name} from {source_layer} to {target_layer}",
                properties={
                    "step_count": str(len(table_steps)),
                    "transformation_types": ",".join([t for t in trans_types if t])
                }
            )
            
            transformations.append(transformation)
        
        return transformations
    
    def _generate_metrics_from_gold_metrics(
        self,
        gold_metrics: Dict[str, Any]
    ) -> List[MDLMetric]:
        """Generate MDL metrics from gold metrics configuration"""
        metrics = []
        
        # Extract dimensions
        dimensions = gold_metrics.get("dimensions", [])
        # Extract measures
        measures = gold_metrics.get("measures", [])
        # Extract metrics
        metric_defs = gold_metrics.get("metrics", [])
        
        # Group by mart_name if available
        marts = {}
        for dim in dimensions:
            mart_name = dim.get("mart_name", "default")
            if mart_name not in marts:
                marts[mart_name] = {"dimensions": [], "measures": []}
            marts[mart_name]["dimensions"].append(dim)
        
        for measure in measures:
            mart_name = measure.get("mart_name", "default")
            if mart_name not in marts:
                marts[mart_name] = {"dimensions": [], "measures": []}
            marts[mart_name]["measures"].append(measure)
        
        # Create metrics for each mart
        for mart_name, mart_data in marts.items():
            if not mart_data["measures"]:
                continue
            
            # Convert dimensions to MDL columns
            mdl_dimensions = [
                MDLColumn(
                    name=dim.get("name", ""),
                    type=dim.get("type", "VARCHAR"),
                    properties={"description": dim.get("description", "")}
                )
                for dim in mart_data["dimensions"]
            ]
            
            # Convert measures to MDL columns
            mdl_measures = [
                MDLColumn(
                    name=measure.get("name", ""),
                    type=measure.get("type", "DOUBLE"),
                    isCalculated=True,
                    expression=measure.get("formula", f"${{model.{measure.get('name', '')}}}"),
                    properties={
                        "description": measure.get("description", ""),
                        "aggregation": measure.get("type", "sum")
                    }
                )
                for measure in mart_data["measures"]
            ]
            
            metric = MDLMetric(
                name=f"{mart_name}_metrics",
                baseObject=mart_name,
                dimension=mdl_dimensions,
                measure=mdl_measures,
                properties={
                    "description": f"Metrics for {mart_name} data mart"
                }
            )
            
            metrics.append(metric)
        
        return metrics
    
    def _generate_governance(
        self,
        table_metadata: List[TableMetadataSummary],
        lod_configs: List[LODConfig],
        relationships: List[RelationshipMapping]
    ) -> MDLGovernance:
        """Generate governance metadata"""
        governance = MDLGovernance()
        
        # Extract data quality rules from table metadata
        for table in table_metadata:
            if hasattr(table, 'data_quality_rules') and table.data_quality_rules:
                governance.data_quality_rules.extend(table.data_quality_rules)
        
        # Extract compliance requirements
        # This would come from table_analysis_configs in production
        governance.compliance_requirements = ["GDPR", "SOX"]  # Placeholder
        
        # Build data lineage from relationships
        for rel in relationships:
            if rel.child_table not in governance.data_lineage:
                governance.data_lineage[rel.child_table] = []
            governance.data_lineage[rel.child_table].append(rel.parent_table)
        
        return governance
    
    def to_dict(self, mdl_schema: MDLSchema) -> Dict[str, Any]:
        """Convert MDL schema to dictionary (JSON-serializable)"""
        # Convert to dict, handling custom extensions
        result = {
            "catalog": mdl_schema.catalog,
            "schema": mdl_schema.schema,
            "models": [model.dict(exclude_none=True) for model in mdl_schema.models],
            "relationships": [rel.dict(exclude_none=True) for rel in mdl_schema.relationships],
            "metrics": [metric.dict(exclude_none=True) for metric in mdl_schema.metrics],
            "views": [view.dict(exclude_none=True) for view in mdl_schema.views],
            "properties": mdl_schema.properties
        }
        
        # Add custom extensions
        if mdl_schema.transformations:
            result["transformations"] = [t.dict(exclude_none=True) for t in mdl_schema.transformations]
        
        if mdl_schema.governance:
            result["governance"] = mdl_schema.governance.dict(exclude_none=True)
        
        if mdl_schema.enumDefinitions:
            result["enumDefinitions"] = mdl_schema.enumDefinitions
        
        if mdl_schema.macros:
            result["macros"] = mdl_schema.macros
        
        return result
    
    def save_to_file(self, mdl_schema: MDLSchema, file_path: str):
        """Save MDL schema to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(mdl_schema), f, indent=2)

