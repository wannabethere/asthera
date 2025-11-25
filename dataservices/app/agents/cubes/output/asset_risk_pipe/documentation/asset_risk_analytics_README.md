# asset_risk_analytics - Data Model Documentation

**Generated**: 2025-11-24 09:20:55

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
  - Analysis Types: descriptive, predictive, diagnostic, exploratory, comparative
  - Business Goals: 5 goals
- **vulnerabilities**:
  - Analysis Types: descriptive, diagnostic, predictive, prescriptive, exploratory, comparative, trend, segmentation
  - Business Goals: 6 goals
- **misconfigurations**:
  - Analysis Types: descriptive, diagnostic, exploratory, trend
  - Business Goals: 5 goals
- **external_exposure**:
  - Analysis Types: descriptive, predictive, diagnostic, exploratory
  - Business Goals: 5 goals
- **identity_exposure**:
  - Analysis Types: descriptive, diagnostic, exploratory, prescriptive
  - Business Goals: 5 goals
- ... and 1 more tables

### Gold Layer
Business-level aggregations and metrics

## Data Marts

Planned 4 data mart(s):

### Data Mart 1: Create Attack Surface Index (ASI) datamart by business unit with top 5 rankings

**Complexity**: medium

**Marts**:
- **attack_surface_index_by_business_unit**: This mart contains the Attack Surface Index (ASI) by business unit, summarizing the total vulnerabilities, misconfigurations, external exposures, and identity exposures.
  - Question: Which business units have the highest number of vulnerabilities and exposures?
  - Grain: One row per business unit
- **software_asset_management_summary**: This mart contains a summary of software assets by department, including total software assets, total licenses, and average usage hours.
  - Question: Which departments have the highest number of software assets and how are they utilizing them?
  - Grain: One row per department
- **vulnerability_risk_assessment**: This mart contains a risk assessment of vulnerabilities based on their severity, including total vulnerabilities and average time to remediate.
  - Question: What are the most common vulnerabilities by severity and how quickly can they be remediated?
  - Grain: One row per vulnerability severity level

### Data Mart 2: Show attack surface breakdown by OS/software stack, business unit, and environment

**Complexity**: medium

**Marts**:
- **attack_surface_summary_by_os_software**: This mart contains a summary of the attack surface categorized by operating system, software stack, business unit, and environment.
  - Question: What is the breakdown of the attack surface by OS/software stack, business unit, and environment?
  - Grain: One row per combination of business unit, environment, OS, and software stack.
- **external_exposure_summary**: This mart summarizes external exposures categorized by business unit, environment, and type of exposure.
  - Question: What are the total external exposures categorized by business unit and environment?
  - Grain: One row per combination of business unit, environment, and exposure type.
- **identity_exposure_summary**: This mart summarizes identity exposures by business unit and environment.
  - Question: How many identity exposures are there by business unit and environment?
  - Grain: One row per combination of business unit and environment.

### Data Mart 3: Generate 12-month trend analysis for likelihood and breach risk

**Complexity**: medium

**Marts**:
- **asset_performance_trend_analysis**: This mart contains a 12-month trend analysis of asset performance, including vulnerabilities, misconfigurations, and external exposures.
  - Question: What is the trend of vulnerabilities, misconfigurations, and external exposures for each asset over the past 12 months?
  - Grain: One row per asset per month
- **identity_exposure_risk_analysis**: This mart contains a 12-month trend analysis of identity exposures, focusing on the number of exposures and their severity.
  - Question: What is the trend of identity exposures and their severity over the past 12 months?
  - Grain: One row per identity per month
- **software_inventory_compliance_analysis**: This mart contains a 12-month trend analysis of software inventory compliance, focusing on the number of licenses and compliance status.
  - Question: What is the trend of software compliance and license management over the past 12 months?
  - Grain: One row per software per month

### Data Mart 4: Create exposure score aggregations for dashboard visualizations

**Complexity**: medium

**Marts**:
- **asset_exposure_summary**: This mart aggregates exposure scores related to assets by counting vulnerabilities, misconfigurations, and external exposures.
  - Question: What is the total number of vulnerabilities, misconfigurations, and external exposures for each asset?
  - Grain: One row per asset
- **identity_exposure_summary**: This mart summarizes the exposure of sensitive identity information by counting instances of exposure per identity.
  - Question: How many instances of sensitive identity information exposure are there for each identity?
  - Grain: One row per identity
- **software_inventory_summary**: This mart aggregates software inventory data by counting licenses and summing usage hours for each software.
  - Question: What is the total number of licenses and usage hours for each software asset?
  - Grain: One row per software asset

## MDL Schema (Single Source of Truth)

The complete MDL schema is available at: `mdl/asset_risk_analytics_schema.json`

This schema contains:
- **Models**: 6 models across raw, silver, and gold layers
- **Relationships**: 5 relationships
- **Metrics**: 11 metrics
- **Views**: 0 views
- **Transformations**: 47 transformations
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
- `transformations/silver_to_gold/gold_attack_surface_index_per_asset.sql`
- `transformations/silver_to_gold/gold_attack_surface_index_per_asset.json`
- `transformations/silver_to_gold/gold_distribution_of_attack_surface_index.sql`
- `transformations/silver_to_gold/gold_distribution_of_attack_surface_index.json`
- `transformations/silver_to_gold/gold_top_10_highest_risk_assets.sql`
- `transformations/silver_to_gold/gold_top_10_highest_risk_assets.json`
- `transformations/silver_to_gold/gold_total_external_exposure_score.sql`
- `transformations/silver_to_gold/gold_total_external_exposure_score.json`
- `transformations/silver_to_gold/gold_external_exposure_score_by_environment.sql`
- `transformations/silver_to_gold/gold_external_exposure_score_by_environment.json`
- `transformations/silver_to_gold/gold_vulnerability_exposure_score.sql`
- `transformations/silver_to_gold/gold_vulnerability_exposure_score.json`
- `transformations/silver_to_gold/gold_assets_above_threshold.sql`
- `transformations/silver_to_gold/gold_assets_above_threshold.json`
- `transformations/silver_to_gold/gold_misconfiguration_exposure_score.sql`
- `transformations/silver_to_gold/gold_misconfiguration_exposure_score.json`
- `transformations/silver_to_gold/gold_misconfiguration_exposure_score_trend.sql`
- `transformations/silver_to_gold/gold_misconfiguration_exposure_score_trend.json`
- `transformations/silver_to_gold/gold_identity_exposure_score_per_asset.sql`
- `transformations/silver_to_gold/gold_identity_exposure_score_per_asset.json`
- `transformations/silver_to_gold/gold_count_high_identity_risk_assets.sql`
- `transformations/silver_to_gold/gold_count_high_identity_risk_assets.json`
- `transformations/silver_to_gold/gold_admin_account_count.sql`
- `transformations/silver_to_gold/gold_admin_account_count.json`
- `transformations/silver_to_gold/gold_stale_account_count.sql`
- `transformations/silver_to_gold/gold_stale_account_count.json`
- `transformations/silver_to_gold/gold_mfa_status_percentage.sql`
- `transformations/silver_to_gold/gold_mfa_status_percentage.json`
- `transformations/silver_to_gold/gold_software_exposure_score_per_asset.sql`
- `transformations/silver_to_gold/gold_software_exposure_score_per_asset.json`
- `transformations/silver_to_gold/gold_count_of_assets_with_eol_or_unsupported_software.sql`
- `transformations/silver_to_gold/gold_count_of_assets_with_eol_or_unsupported_software.json`
- `transformations/silver_to_gold/gold_exploitability_likelihood_per_asset.sql`
- `transformations/silver_to_gold/gold_exploitability_likelihood_per_asset.json`
- `transformations/silver_to_gold/gold_exploitability_trend_over_12_months.sql`
- `transformations/silver_to_gold/gold_exploitability_trend_over_12_months.json`
- `transformations/silver_to_gold/gold_increasing_risk_assets.sql`
- `transformations/silver_to_gold/gold_increasing_risk_assets.json`
- `transformations/silver_to_gold/gold_attack_surface_index.sql`
- `transformations/silver_to_gold/gold_attack_surface_index.json`
- `transformations/silver_to_gold/gold_weighted_component_value.sql`
- `transformations/silver_to_gold/gold_weighted_component_value.json`
- `transformations/silver_to_gold/gold_component_weight.sql`
- `transformations/silver_to_gold/gold_component_weight.json`
- `transformations/silver_to_gold/gold_total_attack_surface_contribution.sql`
- `transformations/silver_to_gold/gold_total_attack_surface_contribution.json`
- `transformations/silver_to_gold/gold_overall_risk_by_stack.sql`
- `transformations/silver_to_gold/gold_overall_risk_by_stack.json`
- `transformations/silver_to_gold/gold_percentage_contribution_to_risk.sql`
- `transformations/silver_to_gold/gold_percentage_contribution_to_risk.json`
- `transformations/silver_to_gold/gold_top_contributing_stacks.sql`
- `transformations/silver_to_gold/gold_top_contributing_stacks.json`
- `transformations/silver_to_gold/gold_exposure_score_weekly_average.sql`
- `transformations/silver_to_gold/gold_exposure_score_weekly_average.json`
- `transformations/silver_to_gold/gold_exposure_score_week_over_week_change.sql`
- `transformations/silver_to_gold/gold_exposure_score_week_over_week_change.json`
- `transformations/silver_to_gold/gold_significant_increase_assets.sql`
- `transformations/silver_to_gold/gold_significant_increase_assets.json`
- `transformations/silver_to_gold/gold_breach_risk_likelihood.sql`
- `transformations/silver_to_gold/gold_breach_risk_likelihood.json`
- `transformations/silver_to_gold/gold_quarterly_trend_breach_risk_likelihood.sql`
- `transformations/silver_to_gold/gold_quarterly_trend_breach_risk_likelihood.json`
- `transformations/silver_to_gold/gold_total_attack_surface.sql`
- `transformations/silver_to_gold/gold_total_attack_surface.json`
- `transformations/silver_to_gold/gold_vulnerability_score.sql`
- `transformations/silver_to_gold/gold_vulnerability_score.json`
- `transformations/silver_to_gold/gold_average_vulnerability_score.sql`
- `transformations/silver_to_gold/gold_average_vulnerability_score.json`
- `transformations/silver_to_gold/gold_top_5_business_units_by_attack_surface.sql`
- `transformations/silver_to_gold/gold_top_5_business_units_by_attack_surface.json`
- `transformations/silver_to_gold/gold_attack_surface_count.sql`
- `transformations/silver_to_gold/gold_attack_surface_count.json`
- `transformations/silver_to_gold/gold_attack_surface_by_os_software_stack.sql`
- `transformations/silver_to_gold/gold_attack_surface_by_os_software_stack.json`
- `transformations/silver_to_gold/gold_attack_surface_by_business_unit.sql`
- `transformations/silver_to_gold/gold_attack_surface_by_business_unit.json`
- `transformations/silver_to_gold/gold_attack_surface_by_environment.sql`
- `transformations/silver_to_gold/gold_attack_surface_by_environment.json`
- `transformations/silver_to_gold/gold_attack_surface_breakdown_combined.sql`
- `transformations/silver_to_gold/gold_attack_surface_breakdown_combined.json`
- `transformations/silver_to_gold/gold_likelihood_trend.sql`
- `transformations/silver_to_gold/gold_likelihood_trend.json`
- `transformations/silver_to_gold/gold_breach_risk_trend.sql`
- `transformations/silver_to_gold/gold_breach_risk_trend.json`
- `transformations/silver_to_gold/gold_exposure_score_sum.sql`
- `transformations/silver_to_gold/gold_exposure_score_sum.json`
- `transformations/silver_to_gold/gold_exposure_score_avg.sql`
- `transformations/silver_to_gold/gold_exposure_score_avg.json`
- `transformations/silver_to_gold/gold_exposure_score_count.sql`
- `transformations/silver_to_gold/gold_exposure_score_count.json`
- `transformations/silver_to_gold/gold_exposure_score_trend.sql`
- `transformations/silver_to_gold/gold_exposure_score_trend.json`
- `transformations/silver_to_gold/gold_exposure_score_comparison_by_category.sql`
- `transformations/silver_to_gold/gold_exposure_score_comparison_by_category.json`

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
- `data_marts/attack_surface_index_by_business_unit.sql`
- `data_marts/software_asset_management_summary.sql`
- `data_marts/vulnerability_risk_assessment.sql`
- `data_marts/attack_surface_summary_by_os_software.sql`
- `data_marts/external_exposure_summary.sql`
- `data_marts/identity_exposure_summary.sql`
- `data_marts/asset_performance_trend_analysis.sql`
- `data_marts/identity_exposure_risk_analysis.sql`
- `data_marts/software_inventory_compliance_analysis.sql`
- `data_marts/asset_exposure_summary.sql`
- `data_marts/identity_exposure_summary.sql`
- `data_marts/software_inventory_summary.sql`
- `data_marts/attack_surface_index_by_business_unit_enhanced.sql`
- `data_marts/software_asset_management_summary_enhanced.sql`
- `data_marts/vulnerability_risk_assessment_enhanced.sql`
- `data_marts/attack_surface_summary_by_os_software_enhanced.sql`
- `data_marts/external_exposure_summary_enhanced.sql`
- `data_marts/identity_exposure_summary_enhanced.sql`
- `data_marts/asset_performance_trend_analysis_enhanced.sql`
- `data_marts/identity_exposure_risk_analysis_enhanced.sql`
- `data_marts/software_inventory_compliance_analysis_enhanced.sql`
- `data_marts/asset_exposure_summary_enhanced.sql`
- `data_marts/identity_exposure_summary_enhanced.sql`
- `data_marts/software_inventory_summary_enhanced.sql`

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
