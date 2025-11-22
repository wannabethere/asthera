# Asset Risk Analytics Workflow

This workflow generates a comprehensive asset risk quantification dashboard using non-financial measures (exposure, exploitability, criticality) to compute an Attack Surface Index (ASI) per asset and business unit.

## Overview

The workflow processes 6 raw tables:
- `raw.assets` - Asset inventory with criticality
- `raw.vulnerabilities` - CVE data with CVSS, EPSS, KEV flags
- `raw.misconfigurations` - Configuration findings
- `raw.external_exposure` - Internet-facing exposure data
- `raw.identity_exposure` - IAM and access exposure
- `raw.software_inventory` - Software stack with EOL/unsupported flags

## Attack Surface Index (ASI) Formula

ASI is computed as a weighted sum of 5 exposure components (0-100 scale):

```
ASI = External Exposure (0-30) 
    + Vulnerability Exposure (0-25)
    + Misconfiguration Exposure (0-20)
    + Identity Exposure (0-15)
    + Software Exposure (0-10)
```

### Component Scoring

1. **External Exposure (0-30 points)**
   - Public IP: 10 points
   - Open ports >10: 10 points, >5: 5 points, >0: 2 points
   - Weak TLS: 5 points
   - Geo-risky: 5 points

2. **Vulnerability Exposure (0-25 points)**
   - KEV present: 10 points
   - CVSS × EPSS × Internet-facing multiplier: 0-10 points
   - Vulnerability count: 0-5 points

3. **Misconfiguration Exposure (0-20 points)**
   - Critical: 5 points each
   - High: 3 points each
   - Medium: 2 points each
   - Low: 1 point each

4. **Identity Exposure (0-15 points)**
   - Admin accounts >10: 5 points, >5: 3 points, >0: 1 point
   - Stale accounts >20: 4 points, >10: 2 points, >0: 1 point
   - Password reuse: 3 points
   - MFA disabled: 3 points

5. **Software Exposure (0-10 points)**
   - EOL software count: 0-5 points
   - Unsupported software count: 0-5 points

## Generated Artifacts

### SQL Transformations

1. **`attack_surface_index.sql`** - Core ASI calculation per asset
2. **`attack_surface_by_bu.sql`** - Business unit aggregations with top 5 rankings
3. **`attack_surface_by_env_os.sql`** - Environment and OS breakdown
4. **`exploitability_likelihood.sql`** - Likelihood calculation based on EPSS, CVSS, KEV
5. **`exposure_trends_monthly.sql`** - 12-month time-series snapshots

### dbt Models

Located in `output/dbt/models/gold/`:
- `attack_surface_index.sql`
- `attack_surface_by_bu.sql`

Schema definitions in `output/dbt/schema.yml` with:
- Column descriptions
- Data quality tests
- Metric definitions

### Semantic Layer (Lexy)

`output/semantic_layer/lexy_metrics.yaml` defines:
- **Entities**: asset, business_unit, vulnerability
- **Metrics**: attack_surface_index, exploitability_likelihood, breach_risk_count, etc.
- **Dimensions**: business_unit, env, os_category, snapshot_month
- **Natural Language Aliases**: Enables queries like "top 5 business units by attack surface"
- **Query Templates**: Pre-built SQL patterns for common questions

### Vega-Lite Visualizations

Located in `output/visualizations/`:

1. **`attack_surface_by_bu_stacked.json`** - Stacked bar chart showing ASI components by business unit (top 5)
2. **`attack_surface_by_bu_contribution.json`** - Donut chart showing risk contribution percentages
3. **`attack_surface_by_env_os.json`** - Grouped bar chart by environment and OS category
4. **`likelihood_trend_12month.json`** - Time-series line chart for exploitability likelihood
5. **`breach_risk_trend_12month.json`** - Area chart for high breach risk assets over time
6. **`asi_heatmap_bu_env.json`** - Heatmap showing ASI intensity across BU × Environment

## Data Marts

### 1. Attack Surface by Business Unit
- **Purpose**: Dashboard showing top 5 business units by exposure
- **Metrics**: avg_asi, total_risk_exposure, risk_contribution_pct
- **Visualizations**: Stacked bar, contribution chart

### 2. Attack Surface by Environment/OS
- **Purpose**: Drill-down analysis by environment and software stack
- **Metrics**: avg_asi, asset_count, risk_contribution_pct
- **Visualizations**: Grouped bar chart

### 3. Exploitability Likelihood
- **Purpose**: Probability-based risk assessment
- **Metrics**: asset_exploitability_likelihood (0-1 scale)
- **Formula**: `EPSS × Exposure Multiplier × KEV Boost × CVSS Multiplier`

### 4. Monthly Exposure Trends
- **Purpose**: 12-month trend analysis for likelihood and breach risk
- **Metrics**: avg_asi, avg_likelihood, high_breach_risk_assets
- **Visualizations**: Time-series line and area charts

## Usage

### Running the Workflow

```python
from app.agents.cubes.workflow_executor import WorkflowExecutor
import json

# Load workflow configuration
with open('asset_risk_workflow.json', 'r') as f:
    workflow_config = json.load(f)

# Execute workflow
executor = WorkflowExecutor(output_dir="./output")
result = executor.execute_workflow_sync(workflow_config)
```

### Querying with Lexy

Using the semantic layer YAML, natural language queries are supported:

- "What is the attack surface index for Finance?"
- "Show me top 5 business units by risk exposure"
- "What is the likelihood of exploitation for Production assets?"
- "Show me breach risk trends over 12 months"
- "Attack surface by OS category and environment"

### Using Vega-Lite Visualizations

Load the JSON specs into any Vega-Lite compatible tool:
- Observable
- Apache Superset
- Redash
- Custom dashboard frameworks

Example:
```javascript
import { vegaLite } from 'vega-lite';

const spec = await fetch('attack_surface_by_bu_stacked.json').then(r => r.json());
vegaLite(spec, { data: attackSurfaceData });
```

## Key Metrics

### Attack Surface Index (ASI)
- **Range**: 0-100
- **Interpretation**: Higher = greater attack surface exposure
- **Thresholds**: 
  - High Risk: ASI >= 70
  - Medium Risk: ASI 50-69
  - Low Risk: ASI < 50

### Exploitability Likelihood
- **Range**: 0-1
- **Interpretation**: Probability of exploitation
- **Thresholds**:
  - Very High: >= 0.7
  - High: 0.5-0.7
  - Medium: 0.3-0.5
  - Low: 0.1-0.3
  - Very Low: < 0.1

### Breach Risk
- **Definition**: Assets with ASI >= 70 AND likelihood >= 0.5
- **Use Case**: Identifies highest priority remediation targets

## Time-Series Analysis

The `exposure_trends_monthly` table supports:
- 12-month trend lines for likelihood
- 12-month trend lines for breach risk
- Month-over-month change indicators
- Snapshot comparisons

## Next Steps

1. Execute SQL transformations in order (raw → silver → gold)
2. Load dbt models into your data warehouse
3. Configure Lexy agent with `lexy_metrics.yaml`
4. Deploy Vega-Lite visualizations to dashboard
5. Set up automated refresh schedules for monthly snapshots
6. Configure alerts for high breach risk assets

## References

- Asset Risk Pipelines documentation: `asset_risk_pipelines.md`
- Workflow executor: `workflow_executor.py`
- Network device workflow example: `network_device_workflow.json`

