# asset_risk_analytics - Data Model Documentation

**Generated**: 2025-11-20 11:49:06

## Overview

Comprehensive asset risk quantification dashboard with Attack Surface Index (ASI), exposure scoring, and non-financial risk metrics

## Architecture

This data model follows the medallion architecture:

```
Raw Layer → Silver Layer → Gold Layer
```

### Raw Layer
Source tables with minimal transformation:

- `assets`
- `vulnerabilities`
- `misconfigurations`
- `external_exposure`
- `identity_exposure`
- `software_inventory`

### Silver Layer
Cleaned, deduplicated, and conformed data

#### Silver Table Analysis
Collected requirements for 6 tables:

- **assets**:
  - Analysis Types: descriptive, diagnostic, prescriptive, exploratory
  - Business Goals: 5 goals
- **vulnerabilities**:
  - Analysis Types: descriptive, diagnostic, trend, exploratory, prescriptive
  - Business Goals: 7 goals
- **misconfigurations**:
  - Analysis Types: descriptive, diagnostic, exploratory, prescriptive
  - Business Goals: 5 goals
- **external_exposure**:
  - Analysis Types: descriptive, diagnostic, exploratory, comparative
  - Business Goals: 5 goals
- **identity_exposure**:
  - Analysis Types: descriptive, diagnostic, predictive, prescriptive, exploratory, comparative
  - Business Goals: 7 goals
- ... and 1 more tables

### Gold Layer
Business-level aggregations and metrics

## Data Marts

Planned 4 data mart(s):

### Data Mart 1: Create Attack Surface Index (ASI) datamart by business unit with top 5 rankings

**Complexity**: low

**Marts**:

### Data Mart 2: Show attack surface breakdown by OS/software stack, business unit, and environment

**Complexity**: medium

**Marts**:
- **attack_surface_summary_by_os_software**: This mart contains a summary of the attack surface categorized by operating system, software stack, business unit, and environment.
  - Question: What is the breakdown of the attack surface by OS/software stack, business unit, and environment?
  - Grain: One row per business unit, environment, OS, and software stack.
- **software_asset_management_summary**: This mart provides a summary of software assets, including their usage and associated vulnerabilities and misconfigurations.
  - Question: How many devices are using each software application, and what are the associated vulnerabilities and misconfigurations?
  - Grain: One row per software application and version.
- **external_exposure_risk_summary**: This mart summarizes external exposure risks categorized by risk type, including the total number of exposures and their potential impact.
  - Question: What are the total external exposures categorized by risk type, and what is their potential impact?
  - Grain: One row per risk category.

### Data Mart 3: Generate 12-month trend analysis for likelihood and breach risk

**Complexity**: high

**Marts**:
- **asset_management_trend_analysis**: This mart contains a 12-month trend analysis of asset management, including risk scores, vulnerabilities, misconfigurations, and exposures related to each asset.
  - Question: What is the 12-month trend of risk scores and vulnerabilities for each asset?
  - Grain: One row per asset per month over the last 12 months.
- **software_asset_management_trend_analysis**: This mart contains a 12-month trend analysis of software asset management, including device counts, misconfigurations, and external exposures related to each software application.
  - Question: What is the 12-month trend of software usage and compliance across devices?
  - Grain: One row per software application per month over the last 12 months.

### Data Mart 4: Create exposure score aggregations for dashboard visualizations

**Complexity**: medium

**Marts**:
- **asset_exposure_summary**: This mart contains aggregated exposure scores for each asset, including vulnerabilities, misconfigurations, and external risks.
  - Question: What is the total vulnerability score and count of vulnerabilities for each asset?
  - Grain: One row per asset
- **identity_exposure_summary**: This mart contains aggregated data on identity exposure incidents, including total incidents and average severity levels.
  - Question: How many identity exposure incidents have occurred for each identity, and what is the average severity of these incidents?
  - Grain: One row per identity
- **software_asset_usage_summary**: This mart contains aggregated usage data for software assets, including the number of devices using each software and total usage hours.
  - Question: What is the total number of devices using each software and how many hours it has been used?
  - Grain: One row per software application

## MDL Schema (Single Source of Truth)

The complete MDL schema is available at: `mdl/asset_risk_analytics_schema.json`

This schema contains:
- **Models**: 6 models across raw, silver, and gold layers
- **Relationships**: 5 relationships
- **Metrics**: 8 metrics
- **Views**: 0 views
- **Transformations**: 0 transformations
- **Governance**: Data quality rules, compliance requirements, lineage

All target formats (Cube.js, dbt) are generated from this MDL schema.

## Generated Artifacts

### Cubes (Generated from MDL)
- `cubes/raw/assets.json`
- `cubes/raw/assets.js`
- `cubes/raw/vulnerabilities.json`
- `cubes/raw/vulnerabilities.js`
- `cubes/raw/misconfigurations.json`
- `cubes/raw/misconfigurations.js`
- `cubes/raw/external_exposure.json`
- `cubes/raw/external_exposure.js`
- `cubes/raw/identity_exposure.json`
- `cubes/raw/identity_exposure.js`
- ... and 26 more

### Transformations
- `transformations/raw_to_silver/assets.json`
- `transformations/raw_to_silver/vulnerabilities.json`
- `transformations/raw_to_silver/misconfigurations.json`
- `transformations/raw_to_silver/external_exposure.json`
- `transformations/raw_to_silver/identity_exposure.json`
- `transformations/raw_to_silver/software_inventory.json`
- `transformations/silver_to_gold/assets.json`
- `transformations/silver_to_gold/vulnerabilities.json`
- `transformations/silver_to_gold/misconfigurations.json`
- `transformations/silver_to_gold/external_exposure.json`
- `transformations/silver_to_gold/identity_exposure.json`
- `transformations/silver_to_gold/software_inventory.json`

### SQL Scripts
- `sql/raw_to_silver/assets.sql`
- `sql/raw_to_silver/vulnerabilities.sql`
- `sql/raw_to_silver/misconfigurations.sql`
- `sql/raw_to_silver/external_exposure.sql`
- `sql/raw_to_silver/identity_exposure.sql`
- `sql/raw_to_silver/software_inventory.sql`
- `sql/silver_to_gold/assets.sql`
- `sql/silver_to_gold/vulnerabilities.sql`
- `sql/silver_to_gold/misconfigurations.sql`
- `sql/silver_to_gold/external_exposure.sql`
- `sql/silver_to_gold/identity_exposure.sql`
- `sql/silver_to_gold/software_inventory.sql`
- `data_marts/attack_surface_summary_by_os_software.sql`
- `data_marts/software_asset_management_summary.sql`
- `data_marts/external_exposure_risk_summary.sql`
- `data_marts/asset_management_trend_analysis.sql`
- `data_marts/software_asset_management_trend_analysis.sql`
- `data_marts/asset_exposure_summary.sql`
- `data_marts/identity_exposure_summary.sql`
- `data_marts/software_asset_usage_summary.sql`
- `data_marts/attack_surface_summary_by_os_software_enhanced.sql`
- `data_marts/software_asset_management_summary_enhanced.sql`
- `data_marts/external_exposure_risk_summary_enhanced.sql`
- `data_marts/asset_management_trend_analysis_enhanced.sql`
- `data_marts/software_asset_management_trend_analysis_enhanced.sql`
- `data_marts/asset_exposure_summary_enhanced.sql`
- `data_marts/identity_exposure_summary_enhanced.sql`
- `data_marts/software_asset_usage_summary_enhanced.sql`

### Data Marts
- `data_marts/data_mart_plan_1.json`
- `data_marts/data_mart_plan_2.json`
- `data_marts/data_mart_plan_3.json`
- `data_marts/data_mart_plan_4.json`

## Usage

1. Review generated Cube.js definitions in `cubes/`
2. Execute transformation SQL in `sql/` in order
3. Review data mart SQL in `data_marts/`
4. Deploy cube definitions to your Cube.js instance
5. Configure pre-aggregations based on query patterns

## Next Steps

1. Validate SQL transformations
2. Test cube definitions
3. Execute data mart SQL queries
4. Configure refresh schedules
5. Set up data quality monitoring
