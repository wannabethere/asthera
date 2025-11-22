"""
Natural Language Question Generator
Generates structured natural language questions for:
- Raw to Silver transformations
- Silver to Gold transformations
- Cube building (raw, silver, gold)
- SQL generation

Each question is a JSON structure that can be used by SQL agents and code generation agents.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import json
from datetime import datetime

from .cube_generation_agent import (
    TableMetadataSummary,
    CubeDefinition,
    TransformationStep,
    RelationshipMapping
)


# ============================================================================
# QUESTION MODELS
# ============================================================================

class NLQuestion(BaseModel):
    """Natural language question structure"""
    question_id: str
    question: str
    context: Dict[str, Any] = Field(default_factory=dict)
    expected_output_type: str  # "sql", "cube", "transformation", "dbt_model"
    steps: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)  # Question IDs this depends on


class TransformationQuestion(NLQuestion):
    """Question for generating transformations"""
    source_layer: str
    target_layer: str
    source_table: str
    target_table: str
    transformation_type: str  # "raw_to_silver", "silver_to_gold"
    lod_config: Optional[Dict[str, Any]] = None
    data_quality_requirements: List[str] = Field(default_factory=list)


class CubeQuestion(NLQuestion):
    """Question for generating cubes"""
    layer: str  # "raw", "silver", "gold"
    table_name: str
    cube_name: str
    dimensions: List[Dict[str, Any]] = Field(default_factory=list)
    measures: List[Dict[str, Any]] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)


class SQLQuestion(NLQuestion):
    """Question for generating SQL"""
    sql_type: str  # "create_table", "view", "transformation", "data_mart"
    target_object: str
    source_tables: List[str] = Field(default_factory=list)
    business_requirements: List[str] = Field(default_factory=list)


# ============================================================================
# NATURAL LANGUAGE QUESTION GENERATOR
# ============================================================================

class NLQuestionGenerator:
    """Generates natural language questions for all components"""
    
    def __init__(self):
        self.questions: List[NLQuestion] = []
    
    def generate_transformation_questions(
        self,
        transformation_steps: List[TransformationStep],
        source_layer: str,
        target_layer: str,
        table_metadata: Optional[TableMetadataSummary] = None,
        lod_config: Optional[Dict[str, Any]] = None
    ) -> List[TransformationQuestion]:
        """Generate natural language questions for transformations"""
        questions = []
        
        # Group steps by table
        steps_by_table = {}
        for step in transformation_steps:
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
            steps_by_table[table_name].append({
                "step_name": step_name,
                "step_type": step_type,
                "sql_logic": sql_logic,
                "description": description
            })
        
        # Generate question for each table transformation
        for table_name, steps in steps_by_table.items():
            # Build context
            context = {
                "source_layer": source_layer,
                "target_layer": target_layer,
                "source_table": table_name,
                "target_table": f"{target_layer}_{table_name}",
                "transformation_steps": steps
            }
            
            if table_metadata:
                context["table_metadata"] = {
                    "table_name": table_metadata.table_name,
                    "description": table_metadata.description,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.data_type,
                            "description": col.description
                        }
                        for col in table_metadata.columns
                    ]
                }
            
            if lod_config:
                context["lod_config"] = lod_config
            
            # Build steps description
            steps_description = []
            for i, step in enumerate(steps, 1):
                steps_description.append(
                    f"Step {i}: {step['step_name']} - {step['description']}"
                )
            
            # Generate question
            question_text = f"""Generate a SQL transformation to convert the {source_layer} table '{table_name}' to the {target_layer} table '{target_layer}_{table_name}'.

The transformation should:
{chr(10).join([f"- {desc}" for desc in steps_description])}

{f"Apply LOD (Level of Detail) configuration: {lod_config}" if lod_config else ""}

{f"Include data quality checks based on: {table_metadata.description if table_metadata else ''}" if table_metadata else ""}

Generate a complete CREATE TABLE statement with all necessary transformations, data cleaning, and validations."""

            transformation_question = TransformationQuestion(
                question_id=f"trans_{source_layer}_to_{target_layer}_{table_name}",
                question=question_text,
                context=context,
                expected_output_type="sql",
                steps=steps_description,
                source_layer=source_layer,
                target_layer=target_layer,
                source_table=table_name,
                target_table=f"{target_layer}_{table_name}",
                transformation_type=f"{source_layer}_to_{target_layer}",
                lod_config=lod_config,
                data_quality_requirements=[
                    "Handle null values appropriately",
                    "Validate data types",
                    "Ensure referential integrity"
                ],
                metadata={
                    "step_count": len(steps),
                    "generated_at": datetime.now().isoformat()
                }
            )
            
            questions.append(transformation_question)
        
        return questions
    
    def generate_cube_questions(
        self,
        cubes: List[CubeDefinition],
        layer: str,
        table_metadata: Optional[TableMetadataSummary] = None,
        relationships: Optional[List[RelationshipMapping]] = None
    ) -> List[CubeQuestion]:
        """Generate natural language questions for cube building"""
        questions = []
        
        for cube in cubes:
            # Handle both dict and object formats
            if isinstance(cube, dict):
                cube_name = cube.get("name", "")
                dimensions = cube.get("dimensions", [])
                measures = cube.get("measures", [])
                description = cube.get("description", "")
                sql = cube.get("sql", "")
            else:
                cube_name = getattr(cube, "name", "")
                dimensions = getattr(cube, "dimensions", [])
                measures = getattr(cube, "measures", [])
                description = getattr(cube, "description", "")
                sql = getattr(cube, "sql", "")
            
            # Extract table name from cube name
            table_name = cube_name.replace(f"{layer}_", "").replace("raw_", "").replace("silver_", "").replace("gold_", "")
            
            # Build context
            context = {
                "layer": layer,
                "table_name": table_name,
                "cube_name": cube_name,
                "description": description
            }
            
            if table_metadata:
                context["table_metadata"] = {
                    "table_name": table_metadata.table_name,
                    "description": table_metadata.description
                }
            
            # Build steps for cube building
            steps = [
                f"1. Define dimensions: {', '.join([d.get('name', d.name) if isinstance(d, dict) else getattr(d, 'name', '') for d in dimensions[:5]])}",
                f"2. Define measures: {', '.join([m.get('name', m.name) if isinstance(m, dict) else getattr(m, 'name', '') for m in measures[:5]])}",
                f"3. Configure pre-aggregations for performance",
                f"4. Set up joins with related tables" if relationships else "4. Configure cube properties"
            ]
            
            # Generate question
            dimensions_list = [d.get('name', d.name) if isinstance(d, dict) else getattr(d, 'name', '') for d in dimensions]
            measures_list = [m.get('name', m.name) if isinstance(m, dict) else getattr(m, 'name', '') for m in measures]
            
            question_text = f"""Build a Cube.js cube definition for the {layer} layer table '{table_name}' (cube name: '{cube_name}').

The cube should include:

Dimensions:
{chr(10).join([f"- {dim}" for dim in dimensions_list[:10]])}

Measures:
{chr(10).join([f"- {measure}" for measure in measures_list[:10]])}

{f"Relationships to other tables: {', '.join([r.child_table if isinstance(r, dict) else getattr(r, 'child_table', '') for r in (relationships or [])[:5]])}" if relationships else ""}

Steps to build:
{chr(10).join([f"- {step}" for step in steps])}

Generate a complete Cube.js cube definition with all dimensions, measures, joins, and pre-aggregations."""

            cube_question = CubeQuestion(
                question_id=f"cube_{layer}_{table_name}",
                question=question_text,
                context=context,
                expected_output_type="cube",
                steps=steps,
                layer=layer,
                table_name=table_name,
                cube_name=cube_name,
                dimensions=[d if isinstance(d, dict) else d.dict() if hasattr(d, 'dict') else {"name": str(d)} for d in dimensions],
                measures=[m if isinstance(m, dict) else m.dict() if hasattr(m, 'dict') else {"name": str(m)} for m in measures],
                relationships=[r if isinstance(r, dict) else r.dict() if hasattr(r, 'dict') else {} for r in (relationships or [])],
                metadata={
                    "dimension_count": len(dimensions),
                    "measure_count": len(measures),
                    "generated_at": datetime.now().isoformat()
                }
            )
            
            questions.append(cube_question)
        
        return questions
    
    def generate_sql_questions(
        self,
        sql_type: str,
        target_object: str,
        source_tables: List[str],
        business_requirements: List[str],
        sql_content: Optional[str] = None,
        description: Optional[str] = None
    ) -> SQLQuestion:
        """Generate natural language question for SQL generation"""
        
        # Build context
        context = {
            "sql_type": sql_type,
            "target_object": target_object,
            "source_tables": source_tables,
            "business_requirements": business_requirements
        }
        
        if sql_content:
            context["existing_sql"] = sql_content[:500]  # Truncate for context
        
        # Generate question based on SQL type
        if sql_type == "create_table":
            question_text = f"""Generate a SQL CREATE TABLE statement for '{target_object}' using data from: {', '.join(source_tables)}.

Business Requirements:
{chr(10).join([f"- {req}" for req in business_requirements])}

The SQL should:
- Create a well-structured table with appropriate data types
- Include all necessary columns from source tables
- Apply any required transformations or calculations
- Include proper indexes for performance
- Add data quality constraints where appropriate"""
        
        elif sql_type == "view":
            question_text = f"""Generate a SQL CREATE VIEW statement for '{target_object}' using data from: {', '.join(source_tables)}.

Business Requirements:
{chr(10).join([f"- {req}" for req in business_requirements])}

The view should:
- Combine data from source tables appropriately
- Apply business logic and calculations
- Be optimized for query performance
- Include proper filtering and aggregation"""
        
        elif sql_type == "transformation":
            question_text = f"""Generate SQL transformation code to create '{target_object}' from: {', '.join(source_tables)}.

Business Requirements:
{chr(10).join([f"- {req}" for req in business_requirements])}

The transformation should:
- Clean and validate input data
- Apply business rules and calculations
- Handle data quality issues
- Optimize for performance"""
        
        elif sql_type == "data_mart":
            question_text = f"""Generate SQL to create a data mart '{target_object}' from: {', '.join(source_tables)}.

Business Requirements:
{chr(10).join([f"- {req}" for req in business_requirements])}

The data mart should:
- Aggregate data appropriately for analytics
- Include calculated metrics and KPIs
- Support common analytical queries
- Be optimized for reporting and dashboards"""
        
        else:
            question_text = f"""Generate SQL for '{target_object}' using: {', '.join(source_tables)}.

Business Requirements:
{chr(10).join([f"- {req}" for req in business_requirements])}"""
        
        sql_question = SQLQuestion(
            question_id=f"sql_{sql_type}_{target_object}",
            question=question_text,
            context=context,
            expected_output_type="sql",
            steps=[
                "1. Analyze source tables and requirements",
                "2. Design table/view structure",
                "3. Write SQL CREATE statement",
                "4. Add indexes and constraints",
                "5. Validate SQL syntax and logic"
            ],
            sql_type=sql_type,
            target_object=target_object,
            source_tables=source_tables,
            business_requirements=business_requirements,
            metadata={
                "generated_at": datetime.now().isoformat(),
                "source_table_count": len(source_tables)
            }
        )
        
        return sql_question
    
    def save_questions(
        self,
        questions: List[NLQuestion],
        output_dir: str,
        category: str = "questions"
    ) -> List[str]:
        """Save questions to JSON files"""
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        # Save individual question files
        for question in questions:
            question_file = output_path / f"{category}_{question.question_id}.json"
            with open(question_file, 'w') as f:
                json.dump(question.dict(), f, indent=2)
            saved_files.append(str(question_file))
        
        # Save combined questions file
        combined_file = output_path / f"{category}_all.json"
        with open(combined_file, 'w') as f:
            json.dump([q.dict() for q in questions], f, indent=2)
        saved_files.append(str(combined_file))
        
        return saved_files

