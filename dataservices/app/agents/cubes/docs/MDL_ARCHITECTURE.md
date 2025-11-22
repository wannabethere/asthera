# MDL-Based Architecture

## Overview

The workflow executor now uses **MDL (Model Definition Language)** as the single source of truth for all data models, transformations, and governance metadata. This unified schema is then transformed to target formats like Cube.js and dbt.

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Workflows                           │
│  (Silver, Gold, Transformations, Data Marts, Metrics)        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    MDL Schema Generator                      │
│  • Models (raw, silver, gold)                                │
│  • Relationships                                             │
│  • Metrics                                                   │
│  • Views                                                     │
│  • Transformations                                           │
│  • Governance                                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
            ┌──────────┴──────────┐
            │   MDL Schema.json    │
            │  (Single Source of   │
            │       Truth)         │
            └──────────┬──────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Cube.js    │  │     dbt     │  │Transformations│
│ Transformer │  │ Transformer │  │   Exporter   │
└─────────────┘  └─────────────┘  └─────────────┘
        │              │              │
        ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Cube.js    │  │  dbt Models │  │   SQL Files │
│   Files     │  │ & schema.yml│  │   & Metadata│
└─────────────┘  └─────────────┘  └─────────────┘
```

## Key Components

### 1. MDL Schema Generator (`mdl_schema_generator.py`)

Converts all agent outputs to MDL format:

- **Models**: Raw, silver, and gold layer models with columns, types, and properties
- **Relationships**: Table relationships with join types and conditions
- **Metrics**: Business metrics with dimensions and measures
- **Views**: SQL view definitions
- **Transformations**: Raw→Silver and Silver→Gold transformation steps
- **Governance**: Data quality rules, compliance requirements, lineage

### 2. MDL Transformers (`mdl_transformers.py`)

#### MDLToCubeJsTransformer
- Converts MDL models to Cube.js cube definitions
- Generates both JSON and JavaScript formats
- Preserves dimensions, measures, and pre-aggregations

#### MDLToDbtTransformer
- Converts MDL models to dbt SQL models
- Generates `schema.yml` with models, columns, and metrics
- Supports materialization configurations

#### MDLToTransformationsExporter
- Exports transformations to SQL files
- Organizes by layer transitions (raw_to_silver, silver_to_gold)
- Includes transformation metadata JSON

## Benefits

### 1. Single Source of Truth
- All models, relationships, and transformations in one MDL schema
- Easy to version control and track changes
- Consistent across all target formats

### 2. Maintainability
- Update MDL schema once, regenerate all targets
- No need to maintain separate Cube.js and dbt definitions
- Changes propagate automatically

### 3. Governance
- Centralized data quality rules
- Compliance requirements in one place
- Data lineage tracking

### 4. Extensibility
- Easy to add new target formats (e.g., Looker, Tableau)
- Custom properties and metadata supported
- Layer-specific configurations

## File Structure

```
output/
├── mdl/
│   └── {workflow_name}_schema.json    # MDL schema (single source of truth)
├── cubes/
│   ├── raw/                            # Generated from MDL
│   ├── silver/                         # Generated from MDL
│   └── gold/                           # Generated from MDL
├── dbt/
│   ├── models/
│   │   ├── raw/                        # Generated from MDL
│   │   ├── silver/                     # Generated from MDL
│   │   └── gold/                       # Generated from MDL
│   └── schema.yml                      # Generated from MDL
└── transformations/
    ├── raw_to_silver/                   # Exported from MDL
    └── silver_to_gold/                  # Exported from MDL
```

## MDL Schema Structure

```json
{
  "catalog": "default_catalog",
  "schema": "public",
  "models": [
    {
      "name": "assets",
      "layer": "silver",
      "columns": [...],
      "primaryKey": "asset_id",
      "refSql": "SELECT * FROM public.assets"
    }
  ],
  "relationships": [
    {
      "name": "vulnerabilities_to_assets",
      "models": ["vulnerabilities", "assets"],
      "joinType": "MANY_TO_ONE",
      "condition": "vulnerabilities.asset_id = assets.asset_id"
    }
  ],
  "metrics": [...],
  "views": [...],
  "transformations": [
    {
      "name": "raw_to_silver_assets",
      "source_layer": "raw",
      "target_layer": "silver",
      "source_model": "assets",
      "target_model": "assets",
      "steps": [...],
      "sql": "..."
    }
  ],
  "governance": {
    "data_quality_rules": [...],
    "compliance_requirements": [...],
    "data_lineage": {...}
  }
}
```

## Usage

The workflow executor automatically:

1. **Generates MDL schema** from all agent outputs
2. **Saves MDL schema** to `mdl/{workflow_name}_schema.json`
3. **Transforms to targets** based on `output_formats` in workflow config:
   - `cubejs`: Generates Cube.js files
   - `dbt`: Generates dbt models (if `enable_dbt_generation: true`)

## Workflow Configuration

```json
{
  "workflow_name": "asset_risk_analytics",
  "catalog": "default_catalog",
  "schema": "public",
  "output_formats": ["cubejs", "dbt"],
  "enable_dbt_generation": true,
  ...
}
```

## Updating Models

To update models:

1. **Edit MDL schema** directly: `mdl/{workflow_name}_schema.json`
2. **Regenerate targets**: Run transformers on updated MDL
3. **Or**: Re-run workflow with updated configuration

## Future Enhancements

- MDL schema editor/validator
- Diff tool for MDL schema changes
- Additional transformers (Looker, Tableau, etc.)
- MDL schema versioning and migration tools
- Integration with data catalog tools

