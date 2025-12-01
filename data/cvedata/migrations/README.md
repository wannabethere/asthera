# Enum Metadata Tables Migration - Optimized for Pipeline Processing

This directory contains SQL migrations to convert Python enum classes into PostgreSQL metadata tables optimized for pipeline processing and enrichment.

## Key Features

### 1. **Combined Related Enums**
Related enums are grouped into domain-based tables for efficient querying and processing:
- `risk_impact_metadata` - Combines risk levels, impact classes, propagation classes, and vulnerability levels
- `breach_method_metadata` - Combines breach methods and prefixes
- `security_strength_metadata` - Combines all strength enums (certificate, cipher, encryption, credential)
- `asset_classification_metadata` - Combines all asset classification enums
- `vulnerability_metadata` - Combines vulnerability types, subtypes, states, and tags
- `software_metadata` - Combines software-related enums
- `state_status_metadata` - Combines all state and status enums
- `cvss_metadata` - Combines all CVSS v2 and v3 enums

### 2. **Numeric Prioritization & Scoring**
Each enum value includes numeric fields for pipeline enrichment:
- `priority_order` - For sorting/ordering (1 = highest priority)
- `numeric_score` - For calculations (typically 0-100 scale)
- `severity_level` - Numeric severity (1-10 scale)
- `risk_score` - Risk contribution score (0-100)
- `weight` - Weight for weighted calculations (0-1 scale)
- `criticality_score` - Asset/role criticality (0-100)
- `exploitability_score` - How easily exploitable (0-100)
- `impact_score` - Potential impact (0-100)

### 3. **Pipeline-Ready**
All tables are designed for efficient use in data pipelines:
- Indexed on commonly queried fields
- Numeric fields ready for calculations
- Relationships maintained via foreign keys
- Metadata fields for categorization and filtering

## Running the Migration

### Using psql

```bash
psql -U your_username -d your_database -f migrations/create_enum_metadata_tables.sql
```

### Using Python (psycopg2)

```python
import psycopg2

conn = psycopg2.connect(
    host="your_host",
    database="your_database",
    user="your_user",
    password="your_password"
)

with open('migrations/create_enum_metadata_tables.sql', 'r') as f:
    sql = f.read()
    
with conn.cursor() as cur:
    cur.execute(sql)
    
conn.commit()
conn.close()
```

## Table Structure

### Core Metadata Tables

#### 1. Risk & Impact Metadata (`risk_impact_metadata`)
Combines: risk_issue_levels, impact_class, propagation_class, vuln_level

**Fields:**
- `enum_type` - 'risk_level', 'impact_class', 'propagation_class', 'vuln_level'
- `code` - Enum code
- `priority_order` - Sorting order (1 = highest)
- `numeric_score` - Score for calculations (0-100)
- `severity_level` - Severity (1-10)
- `weight` - Weight for calculations

**Example Query:**
```sql
-- Get all risk levels ordered by priority
SELECT code, description, numeric_score, severity_level
FROM risk_impact_metadata
WHERE enum_type = 'risk_level'
ORDER BY priority_order;
```

#### 2. Breach Method Metadata (`breach_method_metadata`)
Combines: breach_methods, bmm_prefix

**Fields:**
- `code` - Breach method code
- `prefix` - Short-hand prefix
- `priority_order` - Attack vector priority
- `risk_score` - Base risk score (0-100)
- `exploitability_score` - How easily exploitable (0-100)
- `impact_score` - Potential impact (0-100)
- `weight` - Weight for calculations

**Example Query:**
```sql
-- Get breach methods ordered by risk score
SELECT code, description, risk_score, exploitability_score, impact_score
FROM breach_method_metadata
ORDER BY risk_score DESC;
```

#### 3. Security Strength Metadata (`security_strength_metadata`)
Combines: certificate_strength, cipher_strength, encryption_strength, cred_strength

**Fields:**
- `enum_type` - 'certificate', 'cipher', 'encryption', 'credential'
- `code` - Strength code (WEAK, MODERATE, STRONG)
- `strength_order` - 1 = weakest, higher = stronger
- `numeric_score` - Strength score (0-100)
- `security_level` - Security level (1-5)

**Example Query:**
```sql
-- Get all credential strength levels
SELECT code, description, numeric_score, security_level
FROM security_strength_metadata
WHERE enum_type = 'credential'
ORDER BY strength_order;
```

#### 4. Asset Classification Metadata (`asset_classification_metadata`)
Combines: asset_os_type, asset_device_type, asset_canonical_device_type, asset_device_subtype, asset_platform

**Fields:**
- `classification_type` - 'os_type', 'device_type', 'canonical_type', 'subtype', 'platform'
- `code` - Classification code
- `priority_order` - For prioritization
- `risk_weight` - Risk weight for this asset type
- `criticality_score` - Criticality score (0-100)

**Example Query:**
```sql
-- Get canonical device types by criticality
SELECT code, description, criticality_score, risk_weight
FROM asset_classification_metadata
WHERE classification_type = 'canonical_type'
ORDER BY criticality_score DESC;
```

#### 5. Vulnerability Metadata (`vulnerability_metadata`)
Combines: vulnerability_type, vulnerability_subtype, vuln_states, vuln_tags

**Fields:**
- `enum_type` - 'type', 'subtype', 'state', 'tag'
- `code` - Vulnerability code
- `parent_code` - For subtypes, references type code
- `priority_order` - Priority order
- `risk_score` - Risk contribution score
- `remediation_priority` - 1 = highest priority for remediation

**Example Query:**
```sql
-- Get vulnerability subtypes with their parent types
SELECT v.code, v.description, v.risk_score, p.code as parent_type
FROM vulnerability_metadata v
LEFT JOIN vulnerability_metadata p ON v.parent_code = p.code AND p.enum_type = 'type'
WHERE v.enum_type = 'subtype'
ORDER BY v.remediation_priority;
```

#### 6. Software Metadata (`software_metadata`)
Combines: product_category, os_enum, sw_part, product_state, patch_state, vuln_state

**Fields:**
- `enum_type` - 'category', 'os', 'part', 'product_state', 'patch_state', 'vuln_state'
- `code` - Software code
- `priority_order` - Priority order
- `risk_score` - Risk score
- `maintenance_priority` - Priority for maintenance/updates

#### 7. Roles Metadata (`roles_metadata`)
Service and system roles with criticality scoring

**Fields:**
- `code` - Role code
- `role_category` - 'admin', 'service', 'cloud', 'cmdb'
- `is_admin_role` - Boolean flag
- `is_proxy_role` - Boolean flag
- `criticality_score` - Criticality (0-100)
- `risk_weight` - Risk weight

**Example Query:**
```sql
-- Get all admin roles
SELECT code, description, criticality_score
FROM roles_metadata
WHERE is_admin_role = TRUE
ORDER BY criticality_score DESC;
```

#### 8. CVSS Metadata (`cvss_metadata`)
Combines all CVSS v2 and v3 enums

**Fields:**
- `cvss_version` - 'v2' or 'v3'
- `metric_type` - Metric type (base_metric, access_vector, etc.)
- `code` - CVSS code
- `numeric_value` - Numeric value for calculations
- `weight` - Weight for calculations

### Supporting Tables

- `data_source_metadata` - Data source types with confidence scores
- `state_status_metadata` - Combined state and status enums
- `pipeline_metadata` - Pipeline module and processing metadata
- `ops_metrics_metadata` - Operations metrics types
- `protocol_port_metadata` - Protocol and port mappings with security risk scores
- `ssl_tls_version_metadata` - SSL/TLS protocol versions with security scores
- `cred_usage_category_metadata` - Credential usage categories with risk scores
- `sw_source_metadata` - Software source metadata with confidence scores
- `search_tag_metadata` - Search tags with risk scores
- `likelihood_vuln_attributes_metadata` - Likelihood vulnerability attributes with weights
- `cpe_metadata` - CPE portion and version range specifiers
- `cloud_connector_vuln_metadata` - Cloud connector vulnerabilities with risk scores
- `int_strength_level_metadata` - Integer-based strength levels

## Usage Examples

### Calculate Weighted Risk Score

```sql
-- Calculate weighted risk score for a breach method
SELECT 
    bm.code,
    bm.description,
    (bm.risk_score * bm.weight) as weighted_risk_score,
    (bm.exploitability_score * bm.weight) as weighted_exploitability,
    (bm.impact_score * bm.weight) as weighted_impact
FROM breach_method_metadata bm
ORDER BY weighted_risk_score DESC;
```

### Get Assets by Criticality

```sql
-- Get asset classifications ordered by criticality
SELECT 
    classification_type,
    code,
    description,
    criticality_score,
    risk_weight
FROM asset_classification_metadata
WHERE classification_type IN ('canonical_type', 'os_type')
ORDER BY criticality_score DESC, risk_weight DESC;
```

### Calculate Composite Risk Score

```sql
-- Example: Calculate composite risk score combining multiple factors
SELECT 
    ri.code as risk_level,
    ri.numeric_score as risk_score,
    ic.numeric_score as impact_score,
    bm.risk_score as breach_method_score,
    (ri.numeric_score * 0.4 + ic.numeric_score * 0.3 + bm.risk_score * 0.3) as composite_score
FROM risk_impact_metadata ri
CROSS JOIN risk_impact_metadata ic
CROSS JOIN breach_method_metadata bm
WHERE ri.enum_type = 'risk_level'
  AND ic.enum_type = 'impact_class'
  AND ic.code = 'Mission Critical'
LIMIT 10;
```

### Get Vulnerability Remediation Priority

```sql
-- Get vulnerabilities ordered by remediation priority
SELECT 
    code,
    description,
    risk_score,
    remediation_priority,
    CASE 
        WHEN remediation_priority = 1 THEN 'CRITICAL'
        WHEN remediation_priority <= 2 THEN 'HIGH'
        WHEN remediation_priority <= 3 THEN 'MEDIUM'
        ELSE 'LOW'
    END as priority_category
FROM vulnerability_metadata
WHERE enum_type = 'subtype'
ORDER BY remediation_priority, risk_score DESC;
```

### Pipeline Enrichment Example

```sql
-- Enrich risk issues with metadata for pipeline processing
SELECT 
    ri.risk_issue_code,
    ri.breach_method_code,
    bm.risk_score,
    bm.exploitability_score,
    bm.impact_score,
    ic.numeric_score as impact_class_score,
    rl.numeric_score as risk_level_score,
    (bm.risk_score * 0.4 + ic.numeric_score * 0.3 + rl.numeric_score * 0.3) as enriched_risk_score
FROM your_risk_issues_table ri
JOIN breach_method_metadata bm ON ri.breach_method_code = bm.code
JOIN risk_impact_metadata ic ON ri.impact_class = ic.code AND ic.enum_type = 'impact_class'
JOIN risk_impact_metadata rl ON ri.risk_level = rl.code AND rl.enum_type = 'risk_level';
```

## Maintenance

### Adding New Enum Values

To add new enum values with scoring:

```sql
INSERT INTO breach_method_metadata (code, description, prefix, priority_order, risk_score, exploitability_score, impact_score, weight) 
VALUES ('new_method', 'New Method', 'nm', 12, 75.0, 70.0, 80.0, 0.8)
ON CONFLICT (code) DO NOTHING;
```

### Updating Scores

```sql
-- Update risk score for a breach method
UPDATE breach_method_metadata 
SET risk_score = 90.0,
    weight = 0.95
WHERE code = 'zero_day';
```

### Querying by Score Ranges

```sql
-- Find high-risk breach methods
SELECT code, description, risk_score
FROM breach_method_metadata
WHERE risk_score >= 80.0
ORDER BY risk_score DESC;
```

## Indexes

The migration creates indexes on:
- Foreign key columns for join performance
- Priority/order columns for sorting
- Score columns for range queries
- Type/category columns for filtering

## Notes on Excluded Content

The following Balbix-related entries have been excluded:
- `DataSourceType.BALBIX` from `data_source_metadata`
- `Roles.BALBIX_APPLIANCE` from `roles_metadata`
- `BalbixSensorVuln` enum (entire enum excluded as it's sensor-specific)

## Best Practices for Pipeline Usage

1. **Use Numeric Scores for Calculations**: Always use `numeric_score`, `risk_score`, etc. for calculations rather than string comparisons
2. **Leverage Weights**: Use `weight` fields for weighted aggregations
3. **Filter by Type**: Use `enum_type` or `classification_type` fields to filter related enums efficiently
4. **Join on Codes**: Use the `code` field for joins, but consider using the `id` for better performance in large datasets
5. **Cache Frequently Used Metadata**: Consider caching frequently accessed metadata in your application layer

## Future Enhancements

Consider adding:
- Audit columns (updated_at, updated_by) for tracking changes
- Soft delete support (is_active, deleted_at)
- Versioning for enum value changes
- Additional composite indexes based on query patterns
- Materialized views for common query patterns
- JSONB columns for flexible metadata storage
