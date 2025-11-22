# Natural Language Questions for Code Generation

## Overview

The workflow executor now generates structured natural language questions in JSON format for all components. These questions can be used by SQL agents and code generation agents to build:

- **Raw to Silver transformations** - SQL transformation questions
- **Silver to Gold transformations** - SQL transformation questions  
- **Cube building** - Questions with steps to build cubes (raw, silver, gold)
- **SQL generation** - Questions for creating tables, views, data marts

## Question Structure

Each question is a JSON object with the following structure:

```json
{
  "question_id": "trans_raw_to_silver_assets",
  "question": "Generate a SQL transformation to convert the raw table 'assets' to the silver table 'silver_assets'...",
  "context": {
    "source_layer": "raw",
    "target_layer": "silver",
    "source_table": "assets",
    "target_table": "silver_assets",
    "transformation_steps": [...]
  },
  "expected_output_type": "sql",
  "steps": [
    "Step 1: Clean data - Remove duplicates",
    "Step 2: Validate data types",
    ...
  ],
  "metadata": {
    "step_count": 3,
    "generated_at": "2024-01-01T12:00:00"
  },
  "dependencies": []
}
```

## Question Types

### 1. Transformation Questions

**File Location**: `nl_questions/transformations/`

**Structure**:
```json
{
  "question_id": "trans_raw_to_silver_assets",
  "question": "...",
  "source_layer": "raw",
  "target_layer": "silver",
  "source_table": "assets",
  "target_table": "silver_assets",
  "transformation_type": "raw_to_silver",
  "lod_config": {...},
  "data_quality_requirements": [...]
}
```

**Use Case**: Generate SQL transformations using SQL agents

### 2. Cube Questions

**File Location**: `nl_questions/cubes/`

**Structure**:
```json
{
  "question_id": "cube_silver_assets",
  "question": "Build a Cube.js cube definition for the silver layer table 'assets'...",
  "layer": "silver",
  "table_name": "assets",
  "cube_name": "silver_assets",
  "dimensions": [...],
  "measures": [...],
  "relationships": [...],
  "steps": [
    "1. Define dimensions: asset_id, business_unit, ...",
    "2. Define measures: total_assets, ...",
    "3. Configure pre-aggregations for performance",
    "4. Set up joins with related tables"
  ]
}
```

**Use Case**: Generate Cube.js definitions using code generation agents

### 3. SQL Questions

**File Location**: `nl_questions/sql/`

**Structure**:
```json
{
  "question_id": "sql_data_mart_attack_surface_index",
  "question": "Generate SQL to create a data mart 'attack_surface_index'...",
  "sql_type": "data_mart",
  "target_object": "attack_surface_index",
  "source_tables": ["assets", "vulnerabilities"],
  "business_requirements": [
    "Create Attack Surface Index (ASI) datamart",
    "Show top 5 business units by exposure"
  ],
  "steps": [
    "1. Analyze source tables and requirements",
    "2. Design table/view structure",
    "3. Write SQL CREATE statement",
    "4. Add indexes and constraints",
    "5. Validate SQL syntax and logic"
  ]
}
```

**Use Case**: Generate SQL using SQL agents

## Output Structure

```
output/
├── nl_questions/
│   ├── workflow_all.json                    # All questions combined
│   ├── workflow_trans_raw_to_silver_assets.json
│   ├── workflow_cube_silver_assets.json
│   ├── workflow_sql_data_mart_asi.json
│   ├── transformations/
│   │   ├── transformation_all.json
│   │   ├── transformation_trans_raw_to_silver_assets.json
│   │   └── ...
│   ├── cubes/
│   │   ├── cube_all.json
│   │   ├── cube_raw_assets.json
│   │   ├── cube_silver_assets.json
│   │   └── ...
│   └── sql/
│       ├── sql_all.json
│       ├── sql_transformation_silver_assets.json
│       └── ...
```

## Usage with Agents

### Example: Using SQL Agent

```python
import json
from your_sql_agent import SQLAgent

# Load transformation question
with open('nl_questions/transformations/transformation_trans_raw_to_silver_assets.json') as f:
    question = json.load(f)

# Use with SQL agent
sql_agent = SQLAgent()
sql_code = sql_agent.generate_sql(
    question=question['question'],
    context=question['context'],
    steps=question['steps']
)
```

### Example: Using Code Generation Agent

```python
import json
from your_code_agent import CodeGenerationAgent

# Load cube question
with open('nl_questions/cubes/cube_silver_assets.json') as f:
    question = json.load(f)

# Use with code generation agent
code_agent = CodeGenerationAgent()
cube_code = code_agent.generate_cube(
    question=question['question'],
    dimensions=question['dimensions'],
    measures=question['measures'],
    steps=question['steps']
)
```

## Question Generation

Questions are automatically generated during workflow execution:

1. **Transformation questions** - Generated from transformation steps and LOD configs
2. **Cube questions** - Generated from cube definitions and relationships
3. **SQL questions** - Generated for data marts and transformations

Each question includes:
- Natural language description
- Context (tables, layers, metadata)
- Step-by-step instructions
- Expected output type
- Dependencies (if any)

## Benefits

1. **Agent-Ready**: Questions are structured for direct use with SQL/code generation agents
2. **Context-Rich**: Includes all necessary context (metadata, relationships, requirements)
3. **Step-by-Step**: Provides clear steps for building the output
4. **Traceable**: Each question has a unique ID and metadata
5. **Categorized**: Questions are organized by type (transformations, cubes, SQL)

## Integration

The natural language questions complement the MDL schema:

- **MDL Schema**: Single source of truth for structure
- **NL Questions**: Natural language instructions for generation
- **Agents**: Use questions to generate code from MDL structure

This allows for:
- Human-readable requirements
- Agent-driven code generation
- Version control of requirements
- Iterative refinement of questions

