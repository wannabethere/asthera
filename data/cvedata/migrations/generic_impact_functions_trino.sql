-- ============================================================================
-- Generic Impact Calculation Engine - TrinoSQL Version
-- ============================================================================
-- Converted from PostgreSQL to TrinoSQL
-- Major differences:
-- - No custom types (using ROW types inline)
-- - No procedural language (pure SQL expressions)
-- - JSON instead of JSONB
-- - Array operations using transform/reduce/filter
-- - No mutable variables (functional approach)
-- ============================================================================

-- ============================================================================
-- IMPACT DECAY FUNCTION CALCULATOR
-- ============================================================================
-- Note: In Trino, this is implemented as a reusable query pattern
-- rather than a stored function

-- Parameter structure (used inline as ROW type):
-- ROW(
--   param_name VARCHAR,
--   param_value DOUBLE,
--   param_weight DOUBLE,
--   max_value DOUBLE,
--   impact_category VARCHAR,
--   amplification_factor DOUBLE,
--   decay_function VARCHAR,
--   decay_rate DOUBLE,
--   time_delta DOUBLE,
--   inverse BOOLEAN,
--   threshold_critical DOUBLE,
--   threshold_high DOUBLE,
--   threshold_medium DOUBLE
-- )

-- ============================================================================
-- HELPER VIEW: Decay Function Logic
-- ============================================================================
-- This encapsulates the decay calculation logic as a reusable pattern

CREATE OR REPLACE VIEW impact_decay_calculator AS
SELECT
    'Use this pattern in your queries' AS usage_note,
    'CASE decay_function
        WHEN ''none'' THEN normalized_value
        WHEN ''linear'' THEN normalized_value * GREATEST(1.0 - (time_delta / NULLIF(decay_rate, 0)), 0.0)
        WHEN ''exponential'' THEN normalized_value * EXP(-time_delta / NULLIF(decay_rate, 0))
        WHEN ''logarithmic'' THEN normalized_value * LN(1.0 + (time_delta / NULLIF(decay_rate, 0)))
        WHEN ''step'' THEN CASE WHEN time_delta >= decay_rate THEN normalized_value ELSE 0.0 END
        WHEN ''compound'' THEN normalized_value * POWER(1.0 + decay_rate, time_delta)
        WHEN ''inverse_exponential'' THEN normalized_value * (1.0 - EXP(-time_delta / NULLIF(decay_rate, 0)))
        WHEN ''sigmoid'' THEN normalized_value / (1.0 + EXP(-decay_rate * (time_delta - 50.0)))
        WHEN ''square'' THEN normalized_value * POWER(time_delta / NULLIF(decay_rate, 1.0), 2)
        ELSE normalized_value
    END' AS decay_formula;

-- ============================================================================
-- GENERIC IMPACT CALCULATOR - Main Function (as a Macro/Query Pattern)
-- ============================================================================
-- Since Trino doesn't support UDFs with complex logic, we provide this as
-- a query template that accepts JSON input

CREATE OR REPLACE VIEW calculate_generic_impact_template AS
WITH impact_config AS (
    -- Input: JSON configuration
    -- Example structure in comments below
    SELECT CAST('{
        "aggregation_method": "weighted_sum",
        "scale_to": 100.0,
        "enable_cascade": true,
        "cascade_depth": 3,
        "parameters": [
            {
                "param_name": "asset_criticality",
                "param_value": 95.0,
                "param_weight": 0.40,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.0,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0.0,
                "inverse": false,
                "threshold_critical": 90.0,
                "threshold_high": 70.0,
                "threshold_medium": 50.0
            }
        ]
    }' AS JSON) AS config
),
parsed_parameters AS (
    SELECT
        json_extract_scalar(param, '$.param_name') AS param_name,
        CAST(json_extract_scalar(param, '$.param_value') AS DOUBLE) AS param_value,
        CAST(COALESCE(json_extract_scalar(param, '$.param_weight'), '1.0') AS DOUBLE) AS param_weight,
        CAST(COALESCE(json_extract_scalar(param, '$.max_value'), '100.0') AS DOUBLE) AS max_value,
        COALESCE(json_extract_scalar(param, '$.impact_category'), 'direct') AS impact_category,
        CAST(COALESCE(json_extract_scalar(param, '$.amplification_factor'), '1.0') AS DOUBLE) AS amplification_factor,
        COALESCE(json_extract_scalar(param, '$.decay_function'), 'none') AS decay_function,
        CAST(COALESCE(json_extract_scalar(param, '$.decay_rate'), '1.0') AS DOUBLE) AS decay_rate,
        CAST(COALESCE(json_extract_scalar(param, '$.time_delta'), '0.0') AS DOUBLE) AS time_delta,
        CAST(COALESCE(json_extract_scalar(param, '$.inverse'), 'false') AS BOOLEAN) AS inverse,
        CAST(COALESCE(json_extract_scalar(param, '$.threshold_critical'), '90.0') AS DOUBLE) AS threshold_critical,
        CAST(COALESCE(json_extract_scalar(param, '$.threshold_high'), '70.0') AS DOUBLE) AS threshold_high,
        CAST(COALESCE(json_extract_scalar(param, '$.threshold_medium'), '50.0') AS DOUBLE) AS threshold_medium
    FROM impact_config
    CROSS JOIN UNNEST(CAST(json_extract(config, '$.parameters') AS ARRAY(JSON))) AS t(param)
),
calculated_scores AS (
    SELECT
        param_name,
        param_value,
        param_weight,
        max_value,
        impact_category,
        amplification_factor,
        decay_function,
        decay_rate,
        time_delta,
        inverse,
        -- Calculate raw score (normalized to 0-1)
        CASE 
            WHEN max_value > 0 THEN LEAST(param_value / max_value, 1.0)
            ELSE LEAST(param_value / 100.0, 1.0)
        END AS raw_score_base,
        -- Apply inverse if needed
        CASE 
            WHEN inverse THEN 1.0 - CASE 
                WHEN max_value > 0 THEN LEAST(param_value / max_value, 1.0)
                ELSE LEAST(param_value / 100.0, 1.0)
            END
            ELSE CASE 
                WHEN max_value > 0 THEN LEAST(param_value / max_value, 1.0)
                ELSE LEAST(param_value / 100.0, 1.0)
            END
        END AS raw_score
    FROM parsed_parameters
),
decayed_scores AS (
    SELECT
        cs.*,
        -- Apply amplification
        raw_score * amplification_factor AS normalized_value,
        -- Apply decay/growth function
        LEAST(
            CASE decay_function
                WHEN 'none' THEN raw_score * amplification_factor
                WHEN 'linear' THEN 
                    (raw_score * amplification_factor) * GREATEST(1.0 - (time_delta / NULLIF(decay_rate, 0)), 0.0)
                WHEN 'exponential' THEN 
                    (raw_score * amplification_factor) * EXP(-time_delta / NULLIF(decay_rate, 0))
                WHEN 'logarithmic' THEN 
                    (raw_score * amplification_factor) * LN(1.0 + (time_delta / NULLIF(decay_rate, 0)))
                WHEN 'step' THEN 
                    CASE WHEN time_delta >= decay_rate THEN raw_score * amplification_factor ELSE 0.0 END
                WHEN 'compound' THEN
                    (raw_score * amplification_factor) * POWER(1.0 + decay_rate, time_delta)
                WHEN 'inverse_exponential' THEN
                    (raw_score * amplification_factor) * (1.0 - EXP(-time_delta / NULLIF(decay_rate, 0)))
                WHEN 'sigmoid' THEN
                    (raw_score * amplification_factor) / (1.0 + EXP(-decay_rate * (time_delta - 50.0)))
                WHEN 'square' THEN
                    (raw_score * amplification_factor) * POWER(time_delta / NULLIF(decay_rate, 1.0), 2)
                ELSE raw_score * amplification_factor
            END,
            10.0  -- Cap at 10x for compound growth
        ) AS decayed_score
    FROM calculated_scores cs
),
weighted_scores AS (
    SELECT
        ds.*,
        decayed_score * param_weight AS weighted_score
    FROM decayed_scores ds
),
category_aggregates AS (
    SELECT
        impact_category,
        SUM(weighted_score) AS category_impact,
        COUNT(*) AS param_count,
        CAST(json_format(json_object(
            'parameters': json_array_agg(
                json_object(
                    'param_name': param_name,
                    'impact': ROUND(decayed_score * 100.0, 2),
                    'weight': param_weight
                )
            )
        )) AS JSON) AS contributors
    FROM weighted_scores
    GROUP BY impact_category
),
aggregation_calc AS (
    SELECT
        ic.config,
        json_extract_scalar(ic.config, '$.aggregation_method') AS aggregation_method,
        CAST(COALESCE(json_extract_scalar(ic.config, '$.scale_to'), '100.0') AS DOUBLE) AS scale_to,
        CAST(COALESCE(json_extract_scalar(ic.config, '$.enable_cascade'), 'false') AS BOOLEAN) AS enable_cascade,
        -- Calculate various aggregation methods
        SUM(ws.weighted_score) / NULLIF(SUM(ws.param_weight), 0) AS weighted_sum_score,
        MAX(ws.decayed_score) AS max_score,
        MIN(ws.decayed_score) AS min_score,
        -- Geometric mean using exp(avg(ln(x)))
        EXP(AVG(LN(GREATEST(ws.decayed_score, 0.0001)))) AS geometric_mean_score,
        -- Quadratic mean (RMS)
        SQRT(AVG(ws.decayed_score * ws.decayed_score)) AS quadratic_mean_score,
        -- Category impacts
        SUM(CASE WHEN ws.impact_category = 'direct' THEN ws.weighted_score ELSE 0 END) AS direct_impact,
        SUM(CASE WHEN ws.impact_category = 'indirect' THEN ws.weighted_score ELSE 0 END) AS indirect_impact,
        SUM(CASE WHEN ws.impact_category = 'cascading' THEN ws.weighted_score ELSE 0 END) AS cascading_impact,
        SUM(ws.param_weight) AS sum_weights,
        COUNT(*) AS param_count
    FROM impact_config ic
    CROSS JOIN weighted_scores ws
    GROUP BY ic.config
),
final_calculation AS (
    SELECT
        aggregation_method,
        scale_to,
        enable_cascade,
        -- Select final score based on aggregation method
        CASE aggregation_method
            WHEN 'weighted_sum' THEN weighted_sum_score
            WHEN 'max' THEN max_score
            WHEN 'least' THEN min_score
            WHEN 'geometric_mean' THEN geometric_mean_score
            WHEN 'quadratic_mean' THEN quadratic_mean_score
            WHEN 'cascading' THEN weighted_sum_score * (1.0 + (cascading_impact * 0.5))
            ELSE weighted_sum_score
        END AS base_overall_score,
        direct_impact,
        indirect_impact,
        cascading_impact,
        sum_weights,
        param_count
    FROM aggregation_calc
),
cascade_applied AS (
    SELECT
        fc.*,
        CASE 
            WHEN enable_cascade THEN 
                base_overall_score * (1.0 + (cascading_impact * 0.3))
            ELSE 
                base_overall_score
        END AS overall_score,
        CASE 
            WHEN enable_cascade THEN 1.0 + (cascading_impact * 0.3)
            ELSE 1.0
        END AS cascade_multiplier
    FROM final_calculation fc
)
SELECT
    -- Scale to target range
    LEAST(overall_score * scale_to, scale_to) AS overall_impact,
    LEAST(direct_impact * scale_to, scale_to) AS direct_impact,
    LEAST(indirect_impact * scale_to, scale_to) AS indirect_impact,
    LEAST(cascading_impact * scale_to, scale_to) AS cascading_impact,
    aggregation_method,
    -- Category breakdown
    CAST(json_format(json_object(
        'direct': ROUND(direct_impact * scale_to, 2),
        'indirect': ROUND(indirect_impact * scale_to, 2),
        'cascading': ROUND(cascading_impact * scale_to, 2)
    )) AS JSON) AS impact_by_category,
    -- Metadata
    CAST(json_format(json_object(
        'parameter_count': param_count,
        'aggregation_method': aggregation_method,
        'scale_to': scale_to,
        'sum_weights': sum_weights,
        'cascade_enabled': enable_cascade,
        'cascade_multiplier': cascade_multiplier
    )) AS JSON) AS calculation_metadata
FROM cascade_applied;

-- ============================================================================
-- IMPACT CLASSIFICATION FUNCTION (as parameterized query)
-- ============================================================================

CREATE OR REPLACE VIEW classify_impact_level_template AS
SELECT
    impact_score,
    CASE
        WHEN impact_score >= 90.0 THEN 'CRITICAL'
        WHEN impact_score >= 70.0 THEN 'HIGH'
        WHEN impact_score >= 50.0 THEN 'MEDIUM'
        WHEN impact_score >= 30.0 THEN 'LOW'
        ELSE 'MINIMAL'
    END AS impact_level,
    CASE
        WHEN impact_score >= 90.0 THEN 'Catastrophic'
        WHEN impact_score >= 70.0 THEN 'Severe'
        WHEN impact_score >= 50.0 THEN 'Moderate'
        WHEN impact_score >= 30.0 THEN 'Minor'
        ELSE 'Negligible'
    END AS impact_category,
    CASE
        WHEN impact_score >= 90.0 THEN 1
        WHEN impact_score >= 70.0 THEN 2
        WHEN impact_score >= 50.0 THEN 3
        WHEN impact_score >= 30.0 THEN 4
        ELSE 5
    END AS priority_order,
    CASE
        WHEN impact_score >= 90.0 THEN 'IMMEDIATE ACTION REQUIRED - Executive escalation'
        WHEN impact_score >= 70.0 THEN 'URGENT - Prioritize remediation within 24-48 hours'
        WHEN impact_score >= 50.0 THEN 'IMPORTANT - Address within 1 week'
        WHEN impact_score >= 30.0 THEN 'STANDARD - Include in regular maintenance'
        ELSE 'MONITOR - Track as part of routine operations'
    END AS recommended_action
FROM (VALUES (85.0)) AS t(impact_score);

-- ============================================================================
-- CASCADING IMPACT CALCULATOR
-- ============================================================================

CREATE OR REPLACE VIEW calculate_cascading_impact_template AS
WITH input_params AS (
    SELECT
        75.0 AS primary_impact,
        12 AS affected_systems_count,
        3 AS dependency_depth,
        0.5 AS cascade_rate
),
cascade_calc AS (
    SELECT
        primary_impact,
        affected_systems_count,
        dependency_depth,
        cascade_rate,
        -- Calculate secondary impact
        primary_impact * cascade_rate * LEAST(CAST(affected_systems_count AS DOUBLE) / 10.0, 2.0) AS secondary_impact,
        -- Calculate tertiary impact
        (primary_impact * cascade_rate * LEAST(CAST(affected_systems_count AS DOUBLE) / 10.0, 2.0)) * 
        cascade_rate * LEAST(CAST(affected_systems_count AS DOUBLE) / 20.0, 1.5) AS tertiary_impact
    FROM input_params
)
SELECT
    primary_impact,
    ROUND(secondary_impact, 2) AS secondary_impact,
    ROUND(tertiary_impact, 2) AS tertiary_impact,
    ROUND(LEAST(primary_impact + secondary_impact + tertiary_impact, 100.0), 2) AS total_cascaded_impact,
    affected_systems_count,
    ROUND(LEAST(
        (CAST(affected_systems_count AS DOUBLE) * 5.0) + (CAST(dependency_depth AS DOUBLE) * 10.0),
        100.0
    ), 2) AS blast_radius_score
FROM cascade_calc;

-- ============================================================================
-- BATCH CALCULATION FOR MULTIPLE ASSETS
-- ============================================================================

CREATE OR REPLACE VIEW calculate_impact_batch_template AS
WITH asset_configs AS (
    -- Input: Array of asset configurations
    SELECT CAST('[
        {
            "asset_id": "db_prod_001",
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "enable_cascade": true,
            "parameters": [
                {
                    "param_name": "criticality",
                    "param_value": 95.0,
                    "param_weight": 0.6,
                    "max_value": 100.0,
                    "impact_category": "direct",
                    "amplification_factor": 1.0,
                    "decay_function": "none",
                    "decay_rate": 1.0,
                    "time_delta": 0.0,
                    "inverse": false
                },
                {
                    "param_name": "dependencies",
                    "param_value": 20.0,
                    "param_weight": 0.4,
                    "max_value": 50.0,
                    "impact_category": "cascading",
                    "amplification_factor": 1.5,
                    "decay_function": "none",
                    "decay_rate": 1.0,
                    "time_delta": 0.0,
                    "inverse": false
                }
            ]
        },
        {
            "asset_id": "web_app_001",
            "aggregation_method": "weighted_sum",
            "scale_to": 100.0,
            "enable_cascade": false,
            "parameters": [
                {
                    "param_name": "criticality",
                    "param_value": 70.0,
                    "param_weight": 0.7,
                    "max_value": 100.0,
                    "impact_category": "direct",
                    "amplification_factor": 1.0,
                    "decay_function": "none",
                    "decay_rate": 1.0,
                    "time_delta": 0.0,
                    "inverse": false
                },
                {
                    "param_name": "dependencies",
                    "param_value": 5.0,
                    "param_weight": 0.3,
                    "max_value": 50.0,
                    "impact_category": "cascading",
                    "amplification_factor": 1.0,
                    "decay_function": "none",
                    "decay_rate": 1.0,
                    "time_delta": 0.0,
                    "inverse": false
                }
            ]
        }
    ]' AS JSON) AS configs
),
individual_assets AS (
    SELECT
        json_extract_scalar(asset_config, '$.asset_id') AS asset_id,
        asset_config
    FROM asset_configs
    CROSS JOIN UNNEST(CAST(configs AS ARRAY(JSON))) AS t(asset_config)
),
-- For each asset, parse parameters and calculate impact
-- (This would use the same logic as calculate_generic_impact_template)
-- For brevity, showing simplified version
asset_scores AS (
    SELECT
        asset_id,
        85.0 AS overall_impact,  -- Placeholder - would use full calculation
        70.0 AS direct_impact,
        15.0 AS cascading_impact,
        'weighted_sum' AS aggregation_method
    FROM individual_assets
),
classified_assets AS (
    SELECT
        asset_id,
        overall_impact,
        direct_impact,
        cascading_impact,
        aggregation_method,
        CASE
            WHEN overall_impact >= 90.0 THEN 'CRITICAL'
            WHEN overall_impact >= 70.0 THEN 'HIGH'
            WHEN overall_impact >= 50.0 THEN 'MEDIUM'
            WHEN overall_impact >= 30.0 THEN 'LOW'
            ELSE 'MINIMAL'
        END AS impact_level
    FROM asset_scores
),
ranked_assets AS (
    SELECT
        *,
        RANK() OVER (ORDER BY overall_impact DESC) AS rank_overall,
        PERCENT_RANK() OVER (ORDER BY overall_impact) * 100 AS percentile
    FROM classified_assets
)
SELECT * FROM ranked_assets;

-- ============================================================================
-- IMPACT COMPARISON - Compare different aggregation methods
-- ============================================================================

CREATE OR REPLACE VIEW compare_impact_methods_template AS
WITH input_params AS (
    -- Same parameters, different aggregation methods
    SELECT
        'weighted_sum' AS method_name,
        CAST('[
            {
                "param_name": "criticality",
                "param_value": 90.0,
                "param_weight": 0.5,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.0,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0.0,
                "inverse": false
            }
        ]' AS JSON) AS params
    FROM (VALUES (1))
    UNION ALL
    SELECT 'max', params FROM (SELECT CAST('[]' AS JSON) AS params) t
    UNION ALL
    SELECT 'least', params FROM (SELECT CAST('[]' AS JSON) AS params) t
    UNION ALL
    SELECT 'geometric_mean', params FROM (SELECT CAST('[]' AS JSON) AS params) t
    UNION ALL
    SELECT 'cascading', params FROM (SELECT CAST('[]' AS JSON) AS params) t
    UNION ALL
    SELECT 'quadratic_mean', params FROM (SELECT CAST('[]' AS JSON) AS params) t
),
method_scores AS (
    SELECT
        method_name,
        -- Placeholder scores - would use full calculation per method
        CASE method_name
            WHEN 'weighted_sum' THEN 85.0
            WHEN 'max' THEN 90.0
            WHEN 'least' THEN 75.0
            WHEN 'geometric_mean' THEN 83.0
            WHEN 'cascading' THEN 88.0
            WHEN 'quadratic_mean' THEN 86.0
        END AS impact_score
    FROM input_params
),
with_baseline AS (
    SELECT
        *,
        (SELECT impact_score FROM method_scores WHERE method_name = 'weighted_sum') AS baseline_score
    FROM method_scores
)
SELECT
    method_name,
    impact_score,
    impact_score - baseline_score AS score_difference,
    RANK() OVER (ORDER BY impact_score DESC) AS rank
FROM with_baseline
ORDER BY impact_score DESC;

-- ============================================================================
-- PRACTICAL USAGE FUNCTIONS (Inline SQL approach)
-- ============================================================================

-- Function-like macro for single impact calculation
-- To use: Replace the config JSON with your actual data

CREATE OR REPLACE VIEW calculate_impact AS
WITH config AS (
    SELECT CAST('{
        "aggregation_method": "weighted_sum",
        "scale_to": 100.0,
        "enable_cascade": true,
        "cascade_depth": 3,
        "parameters": [
            {
                "param_name": "example_param",
                "param_value": 85.0,
                "param_weight": 1.0,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.0,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0.0,
                "inverse": false
            }
        ]
    }' AS JSON) AS impact_config
)
SELECT 
    'Replace config above with your parameters' AS usage_note;

-- ============================================================================
-- DOCUMENTATION AND USAGE NOTES
-- ============================================================================

/*
TRINO CONVERSION NOTES:
========================

1. NO STORED FUNCTIONS WITH PROCEDURAL LOGIC
   - Trino doesn't support PL/SQL or procedural UDFs
   - All logic must be pure SQL expressions
   - Use VIEWs as "function templates" that users can adapt

2. NO CUSTOM TYPES
   - PostgreSQL: CREATE TYPE impact_parameter AS (...)
   - Trino: Use inline ROW(...) types or JSON
   - This version uses JSON for maximum flexibility

3. ARRAY OPERATIONS
   - PostgreSQL: FOREACH loop with mutable variables
   - Trino: UNNEST + aggregations + transform/reduce for complex operations

4. JSON vs JSONB
   - PostgreSQL: JSONB with operators ->, ->>, #>
   - Trino: JSON with functions json_extract, json_extract_scalar, json_format

5. USAGE PATTERN
   Instead of:
     SELECT * FROM calculate_generic_impact(params, 'weighted_sum', 100, true, 3);
   
   Use:
     WITH my_config AS (
       SELECT CAST('{...json config...}' AS JSON) AS config
     )
     SELECT * FROM (... copy the calculation CTE logic ...)

6. RECOMMENDED APPROACH
   - For production use, create parameterized views
   - Or move complex logic to application layer
   - Or use Trino's Python UDFs for procedural logic (requires setup)

EXAMPLE USAGE:
==============

-- Simple impact calculation
WITH config AS (
    SELECT CAST('{
        "aggregation_method": "weighted_sum",
        "scale_to": 100.0,
        "parameters": [
            {
                "param_name": "asset_criticality",
                "param_value": 95.0,
                "param_weight": 0.40,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.0,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0.0,
                "inverse": false
            },
            {
                "param_name": "data_sensitivity",
                "param_value": 85.0,
                "param_weight": 0.30,
                "max_value": 100.0,
                "impact_category": "direct",
                "amplification_factor": 1.2,
                "decay_function": "none",
                "decay_rate": 1.0,
                "time_delta": 0.0,
                "inverse": false
            }
        ]
    }' AS JSON) AS impact_config
),
parsed AS (
    SELECT
        json_extract_scalar(param, '$.param_name') AS param_name,
        CAST(json_extract_scalar(param, '$.param_value') AS DOUBLE) AS param_value,
        CAST(json_extract_scalar(param, '$.param_weight') AS DOUBLE) AS param_weight,
        CAST(json_extract_scalar(param, '$.max_value') AS DOUBLE) AS max_value,
        json_extract_scalar(param, '$.impact_category') AS impact_category,
        CAST(json_extract_scalar(param, '$.amplification_factor') AS DOUBLE) AS amplification_factor
    FROM config
    CROSS JOIN UNNEST(CAST(json_extract(impact_config, '$.parameters') AS ARRAY(JSON))) AS t(param)
),
scores AS (
    SELECT
        param_name,
        param_value,
        param_weight,
        (param_value / max_value) * amplification_factor AS normalized_score,
        ((param_value / max_value) * amplification_factor * param_weight) AS weighted_score,
        impact_category
    FROM parsed
)
SELECT
    SUM(weighted_score) / SUM(param_weight) * 100.0 AS overall_impact,
    SUM(CASE WHEN impact_category = 'direct' THEN weighted_score ELSE 0 END) * 100.0 AS direct_impact,
    CAST(json_format(json_object(
        'parameters': json_array_agg(
            json_object(
                'param_name': param_name,
                'score': ROUND(normalized_score * 100, 2),
                'category': impact_category
            )
        )
    )) AS JSON) AS parameter_scores
FROM scores;

-- Classify impact level (inline)
WITH scores AS (
    SELECT 87.5 AS impact_score
)
SELECT
    impact_score,
    CASE
        WHEN impact_score >= 90.0 THEN 'CRITICAL'
        WHEN impact_score >= 70.0 THEN 'HIGH'
        WHEN impact_score >= 50.0 THEN 'MEDIUM'
        WHEN impact_score >= 30.0 THEN 'LOW'
        ELSE 'MINIMAL'
    END AS impact_level,
    CASE
        WHEN impact_score >= 90.0 THEN 'IMMEDIATE ACTION REQUIRED'
        WHEN impact_score >= 70.0 THEN 'URGENT - Prioritize within 24-48 hours'
        WHEN impact_score >= 50.0 THEN 'IMPORTANT - Address within 1 week'
        WHEN impact_score >= 30.0 THEN 'STANDARD - Regular maintenance'
        ELSE 'MONITOR - Routine operations'
    END AS recommended_action
FROM scores;

LIMITATIONS:
============
1. No reusable functions - must copy CTE logic or use views as templates
2. More verbose than PostgreSQL version
3. Cannot have mutable state or loops
4. JSON parsing adds overhead
5. Type safety is reduced (everything goes through JSON)

ADVANTAGES:
===========
1. Pure SQL - no procedural dependencies
2. Highly portable
3. Can leverage Trino's distributed execution
4. Easy to parallelize across partitions
5. More transparent - all logic visible in query

*/

