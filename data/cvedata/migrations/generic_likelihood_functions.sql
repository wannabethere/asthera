-- ============================================================================
-- Generic Likelihood Calculation Engine
-- ============================================================================
-- Fully configurable likelihood calculator that accepts:
-- - Any list of parameters with their values and metrics
-- - Decay functions per parameter
-- - Multiple aggregation methods (weighted sum, least, max, geometric mean)
-- - Normalization and scaling options
-- ============================================================================

-- ============================================================================
-- CORE DATA TYPES
-- ============================================================================

-- Parameter definition type
CREATE TYPE likelihood_parameter AS (
    param_name TEXT,              -- Name of the parameter (e.g., 'critical_vuln_count')
    param_value DECIMAL(10,2),    -- Current value of the parameter
    param_weight DECIMAL(5,3),    -- Weight in final calculation (0-1)
    max_value DECIMAL(10,2),      -- Maximum expected value for normalization
    decay_function TEXT,          -- 'none', 'linear', 'exponential', 'logarithmic', 'step'
    decay_rate DECIMAL(5,3),      -- Decay rate parameter (tau for exponential, etc.)
    time_delta DECIMAL(10,2),     -- Time elapsed (days, hours, etc.) for decay calculation
    inverse BOOLEAN,              -- If true, higher value = lower likelihood (e.g., patch_compliance)
    threshold_low DECIMAL(10,2),  -- Lower threshold for step function
    threshold_high DECIMAL(10,2)  -- Upper threshold for step function
);

-- Aggregation result type
CREATE TYPE likelihood_result AS (
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    calculation_details JSONB
);

-- ============================================================================
-- DECAY FUNCTION CALCULATOR
-- ============================================================================

CREATE OR REPLACE FUNCTION apply_decay_function(
    p_value DECIMAL(10,2),
    p_decay_function TEXT,
    p_decay_rate DECIMAL(5,3),
    p_time_delta DECIMAL(10,2),
    p_max_value DECIMAL(10,2)
) RETURNS DECIMAL(10,2) AS $$
DECLARE
    v_normalized_value DECIMAL(10,2);
    v_decayed_value DECIMAL(10,2);
BEGIN
    -- Normalize value to 0-1 range
    v_normalized_value := CASE 
        WHEN p_max_value > 0 THEN LEAST(p_value / p_max_value, 1.0)
        ELSE LEAST(p_value / 100.0, 1.0)
    END;
    
    -- Apply decay function
    v_decayed_value := CASE p_decay_function
        
        -- No decay - value as-is
        WHEN 'none' THEN v_normalized_value
        
        -- Linear decay: value * (1 - time_delta / decay_rate)
        WHEN 'linear' THEN 
            v_normalized_value * GREATEST(1.0 - (p_time_delta / NULLIF(p_decay_rate, 0)), 0.0)
        
        -- Exponential decay: value * exp(-time_delta / decay_rate)
        WHEN 'exponential' THEN 
            v_normalized_value * EXP(-p_time_delta / NULLIF(p_decay_rate, 0))
        
        -- Logarithmic growth: value * log(1 + time_delta / decay_rate)
        WHEN 'logarithmic' THEN 
            v_normalized_value * LN(1.0 + (p_time_delta / NULLIF(p_decay_rate, 0)))
        
        -- Step function: 0 if time_delta < decay_rate, else value
        WHEN 'step' THEN 
            CASE WHEN p_time_delta >= p_decay_rate THEN v_normalized_value ELSE 0.0 END
        
        -- Inverse exponential growth: value * (1 - exp(-time_delta / decay_rate))
        WHEN 'inverse_exponential' THEN
            v_normalized_value * (1.0 - EXP(-p_time_delta / NULLIF(p_decay_rate, 0)))
        
        -- Sigmoid: value / (1 + exp(-decay_rate * (time_delta - threshold)))
        WHEN 'sigmoid' THEN
            v_normalized_value / (1.0 + EXP(-p_decay_rate * (p_time_delta - 50.0)))
        
        ELSE v_normalized_value
    END;
    
    RETURN LEAST(v_decayed_value, 1.0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- GENERIC LIKELIHOOD CALCULATOR
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_generic_likelihood(
    p_parameters likelihood_parameter[],
    p_aggregation_method TEXT DEFAULT 'weighted_sum',  -- 'weighted_sum', 'least', 'max', 'geometric_mean', 'harmonic_mean', 'quadratic_mean'
    p_scale_to DECIMAL(10,2) DEFAULT 100.0,            -- Scale final result to this value
    p_normalization_method TEXT DEFAULT 'none'         -- 'none', 'min_max', 'z_score', 'sigmoid'
) RETURNS TABLE (
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    raw_scores JSONB,
    decayed_scores JSONB,
    weighted_scores JSONB,
    calculation_metadata JSONB
) AS $$
DECLARE
    v_param likelihood_parameter;
    v_raw_score DECIMAL(10,2);
    v_decayed_score DECIMAL(10,2);
    v_weighted_score DECIMAL(10,2);
    v_overall_score DECIMAL(10,2) := 0;
    
    v_raw_scores JSONB := '{}'::JSONB;
    v_decayed_scores JSONB := '{}'::JSONB;
    v_weighted_scores JSONB := '{}'::JSONB;
    v_parameter_scores JSONB := '{}'::JSONB;
    
    v_sum_weights DECIMAL(10,2) := 0;
    v_product DECIMAL(10,2) := 1.0;
    v_sum_reciprocals DECIMAL(10,2) := 0;
    v_sum_squares DECIMAL(10,2) := 0;
    v_count INTEGER := 0;
    v_min_score DECIMAL(10,2) := 999999;
    v_max_score DECIMAL(10,2) := -999999;
    
    v_metadata JSONB;
BEGIN
    -- Process each parameter
    FOREACH v_param IN ARRAY p_parameters
    LOOP
        v_count := v_count + 1;
        
        -- Calculate raw score (normalized to 0-1)
        v_raw_score := CASE 
            WHEN v_param.max_value > 0 THEN 
                LEAST(v_param.param_value / v_param.max_value, 1.0)
            ELSE 
                LEAST(v_param.param_value / 100.0, 1.0)
        END;
        
        -- Apply inverse if specified (e.g., for compliance where high = good)
        IF v_param.inverse THEN
            v_raw_score := 1.0 - v_raw_score;
        END IF;
        
        -- Apply decay function
        v_decayed_score := apply_decay_function(
            v_param.param_value,
            COALESCE(v_param.decay_function, 'none'),
            COALESCE(v_param.decay_rate, 1.0),
            COALESCE(v_param.time_delta, 0),
            v_param.max_value
        );
        
        -- Apply inverse to decayed score if needed
        IF v_param.inverse THEN
            v_decayed_score := 1.0 - v_decayed_score;
        END IF;
        
        -- Apply weight
        v_weighted_score := v_decayed_score * COALESCE(v_param.param_weight, 1.0);
        
        -- Store scores in JSONB
        v_raw_scores := jsonb_set(
            v_raw_scores, 
            ARRAY[v_param.param_name], 
            to_jsonb(ROUND(v_raw_score * p_scale_to, 2))
        );
        
        v_decayed_scores := jsonb_set(
            v_decayed_scores, 
            ARRAY[v_param.param_name], 
            to_jsonb(ROUND(v_decayed_score * p_scale_to, 2))
        );
        
        v_weighted_scores := jsonb_set(
            v_weighted_scores, 
            ARRAY[v_param.param_name], 
            to_jsonb(ROUND(v_weighted_score * p_scale_to, 2))
        );
        
        v_parameter_scores := jsonb_set(
            v_parameter_scores,
            ARRAY[v_param.param_name],
            jsonb_build_object(
                'raw_value', v_param.param_value,
                'raw_score', ROUND(v_raw_score * p_scale_to, 2),
                'decayed_score', ROUND(v_decayed_score * p_scale_to, 2),
                'weighted_score', ROUND(v_weighted_score * p_scale_to, 2),
                'weight', v_param.param_weight,
                'decay_function', v_param.decay_function,
                'time_delta', v_param.time_delta,
                'inverse', v_param.inverse
            )
        );
        
        -- Accumulate for different aggregation methods
        v_sum_weights := v_sum_weights + COALESCE(v_param.param_weight, 1.0);
        
        CASE p_aggregation_method
            WHEN 'weighted_sum' THEN
                v_overall_score := v_overall_score + v_weighted_score;
                
            WHEN 'least' THEN
                v_min_score := LEAST(v_min_score, v_decayed_score);
                
            WHEN 'max' THEN
                v_max_score := GREATEST(v_max_score, v_decayed_score);
                
            WHEN 'geometric_mean' THEN
                v_product := v_product * GREATEST(v_decayed_score, 0.0001); -- Avoid zero
                
            WHEN 'harmonic_mean' THEN
                v_sum_reciprocals := v_sum_reciprocals + (1.0 / NULLIF(v_decayed_score, 0));
                
            WHEN 'quadratic_mean' THEN
                v_sum_squares := v_sum_squares + (v_decayed_score * v_decayed_score);
                
            ELSE
                v_overall_score := v_overall_score + v_weighted_score;
        END CASE;
    END LOOP;
    
    -- Calculate final aggregated score based on method
    v_overall_score := CASE p_aggregation_method
        WHEN 'weighted_sum' THEN
            CASE WHEN v_sum_weights > 0 THEN v_overall_score / v_sum_weights ELSE 0 END
            
        WHEN 'least' THEN
            v_min_score
            
        WHEN 'max' THEN
            v_max_score
            
        WHEN 'geometric_mean' THEN
            POWER(v_product, 1.0 / NULLIF(v_count, 0))
            
        WHEN 'harmonic_mean' THEN
            v_count / NULLIF(v_sum_reciprocals, 0)
            
        WHEN 'quadratic_mean' THEN
            SQRT(v_sum_squares / NULLIF(v_count, 0))
            
        ELSE
            CASE WHEN v_sum_weights > 0 THEN v_overall_score / v_sum_weights ELSE 0 END
    END;
    
    -- Scale to target range
    v_overall_score := LEAST(v_overall_score * p_scale_to, p_scale_to);
    
    -- Build metadata
    v_metadata := jsonb_build_object(
        'parameter_count', v_count,
        'aggregation_method', p_aggregation_method,
        'scale_to', p_scale_to,
        'sum_weights', v_sum_weights,
        'normalization_method', p_normalization_method
    );
    
    RETURN QUERY SELECT
        v_overall_score,
        p_aggregation_method,
        v_parameter_scores,
        v_raw_scores,
        v_decayed_scores,
        v_weighted_scores,
        v_metadata;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SIMPLIFIED JSON-BASED INTERFACE
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_likelihood_from_json(
    p_config JSONB
) RETURNS TABLE (
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    calculation_summary JSONB
) AS $$
DECLARE
    v_parameters likelihood_parameter[];
    v_param JSONB;
    v_param_struct likelihood_parameter;
    v_aggregation TEXT;
    v_scale DECIMAL(10,2);
    v_normalization TEXT;
BEGIN
    -- Extract configuration
    v_aggregation := COALESCE(p_config->>'aggregation_method', 'weighted_sum');
    v_scale := COALESCE((p_config->>'scale_to')::DECIMAL, 100.0);
    v_normalization := COALESCE(p_config->>'normalization_method', 'none');
    
    -- Build parameter array from JSON
    FOR v_param IN SELECT * FROM jsonb_array_elements(p_config->'parameters')
    LOOP
        v_param_struct := ROW(
            v_param->>'param_name',
            COALESCE((v_param->>'param_value')::DECIMAL, 0),
            COALESCE((v_param->>'param_weight')::DECIMAL, 1.0),
            COALESCE((v_param->>'max_value')::DECIMAL, 100.0),
            COALESCE(v_param->>'decay_function', 'none'),
            COALESCE((v_param->>'decay_rate')::DECIMAL, 1.0),
            COALESCE((v_param->>'time_delta')::DECIMAL, 0),
            COALESCE((v_param->>'inverse')::BOOLEAN, FALSE),
            COALESCE((v_param->>'threshold_low')::DECIMAL, 0),
            COALESCE((v_param->>'threshold_high')::DECIMAL, 100.0)
        )::likelihood_parameter;
        
        v_parameters := array_append(v_parameters, v_param_struct);
    END LOOP;
    
    -- Calculate using generic function
    RETURN QUERY
    SELECT 
        l.overall_likelihood,
        l.aggregation_method,
        l.parameter_scores,
        jsonb_build_object(
            'raw_scores', l.raw_scores,
            'decayed_scores', l.decayed_scores,
            'weighted_scores', l.weighted_scores,
            'metadata', l.calculation_metadata
        ) AS calculation_summary
    FROM calculate_generic_likelihood(
        v_parameters,
        v_aggregation,
        v_scale,
        v_normalization
    ) l;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- BATCH CALCULATION FOR MULTIPLE ASSETS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_likelihood_batch(
    p_asset_configs JSONB  -- Array of {asset_id, parameters, config}
) RETURNS TABLE (
    asset_id TEXT,
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    rank_overall INTEGER,
    percentile DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    WITH asset_calculations AS (
        SELECT 
            config->>'asset_id' AS asset_id,
            (calculate_likelihood_from_json(config)).overall_likelihood,
            (calculate_likelihood_from_json(config)).aggregation_method,
            (calculate_likelihood_from_json(config)).parameter_scores
        FROM jsonb_array_elements(p_asset_configs) AS config
    ),
    ranked_assets AS (
        SELECT
            *,
            RANK() OVER (ORDER BY overall_likelihood DESC) AS rank_overall,
            PERCENT_RANK() OVER (ORDER BY overall_likelihood) * 100 AS percentile
        FROM asset_calculations
    )
    SELECT * FROM ranked_assets;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- LIKELIHOOD COMPARISON FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION compare_likelihood_methods(
    p_parameters likelihood_parameter[]
) RETURNS TABLE (
    method_name TEXT,
    likelihood_score DECIMAL(10,2),
    score_difference DECIMAL(10,2),
    rank INTEGER
) AS $$
DECLARE
    v_methods TEXT[] := ARRAY['weighted_sum', 'least', 'max', 'geometric_mean', 'harmonic_mean', 'quadratic_mean'];
    v_method TEXT;
    v_baseline DECIMAL(10,2);
BEGIN
    -- Calculate for each method
    CREATE TEMP TABLE IF NOT EXISTS method_comparison (
        method_name TEXT,
        likelihood_score DECIMAL(10,2)
    ) ON COMMIT DROP;
    
    FOREACH v_method IN ARRAY v_methods
    LOOP
        INSERT INTO method_comparison
        SELECT 
            v_method,
            l.overall_likelihood
        FROM calculate_generic_likelihood(
            p_parameters,
            v_method,
            100.0,
            'none'
        ) l;
    END LOOP;
    
    -- Get baseline (weighted_sum)
    SELECT likelihood_score INTO v_baseline
    FROM method_comparison
    WHERE method_name = 'weighted_sum';
    
    -- Return comparison
    RETURN QUERY
    SELECT 
        mc.method_name,
        mc.likelihood_score,
        mc.likelihood_score - v_baseline AS score_difference,
        RANK() OVER (ORDER BY mc.likelihood_score DESC)::INTEGER AS rank
    FROM method_comparison mc
    ORDER BY mc.likelihood_score DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HELPER FUNCTION: CREATE PARAMETER FROM JSON
-- ============================================================================

CREATE OR REPLACE FUNCTION build_parameter(
    p_name TEXT,
    p_value DECIMAL(10,2),
    p_weight DECIMAL(5,3) DEFAULT 1.0,
    p_max_value DECIMAL(10,2) DEFAULT 100.0,
    p_decay_function TEXT DEFAULT 'none',
    p_decay_rate DECIMAL(5,3) DEFAULT 1.0,
    p_time_delta DECIMAL(10,2) DEFAULT 0,
    p_inverse BOOLEAN DEFAULT FALSE
) RETURNS likelihood_parameter AS $$
BEGIN
    RETURN ROW(
        p_name,
        p_value,
        p_weight,
        p_max_value,
        p_decay_function,
        p_decay_rate,
        p_time_delta,
        p_inverse,
        0,
        100.0
    )::likelihood_parameter;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_generic_likelihood IS
'Generic likelihood calculator accepting array of parameters with:
- param_name: Name of parameter
- param_value: Current value
- param_weight: Weight in aggregation (0-1)
- max_value: Maximum value for normalization
- decay_function: none, linear, exponential, logarithmic, step, inverse_exponential, sigmoid
- decay_rate: Rate parameter for decay function (tau for exponential)
- time_delta: Time elapsed for decay calculation
- inverse: If TRUE, higher value = lower likelihood

Aggregation methods:
- weighted_sum: Weighted average (default)
- least: Minimum of all scores (conservative)
- max: Maximum of all scores (optimistic)
- geometric_mean: Product root
- harmonic_mean: Harmonic average
- quadratic_mean: Root mean square

Returns overall likelihood plus detailed breakdowns.';

COMMENT ON FUNCTION calculate_likelihood_from_json IS
'Simplified JSON interface for likelihood calculation.
Input format:
{
  "aggregation_method": "weighted_sum",
  "scale_to": 100.0,
  "normalization_method": "none",
  "parameters": [
    {
      "param_name": "critical_vulns",
      "param_value": 5,
      "param_weight": 0.4,
      "max_value": 20,
      "decay_function": "exponential",
      "decay_rate": 30.0,
      "time_delta": 45,
      "inverse": false
    },
    ...
  ]
}';

COMMENT ON FUNCTION calculate_likelihood_batch IS
'Batch calculation for multiple assets/entities.
Input: Array of asset configurations with parameters.
Returns: Ranked results with percentiles.';

COMMENT ON FUNCTION compare_likelihood_methods IS
'Compares all aggregation methods for same parameter set.
Useful for understanding sensitivity to aggregation method.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Using likelihood_parameter array directly
SELECT * FROM calculate_generic_likelihood(
    ARRAY[
        ROW('critical_vulns', 5, 0.40, 20, 'exponential', 30.0, 45, FALSE, 0, 100)::likelihood_parameter,
        ROW('high_vulns', 10, 0.30, 50, 'exponential', 30.0, 45, FALSE, 0, 100)::likelihood_parameter,
        ROW('patch_compliance', 75, 0.20, 100, 'none', 1.0, 0, TRUE, 0, 100)::likelihood_parameter,
        ROW('dwell_time', 60, 0.10, 90, 'linear', 90.0, 60, FALSE, 0, 100)::likelihood_parameter
    ],
    'weighted_sum',  -- aggregation method
    100.0,          -- scale to 100
    'none'          -- normalization
);

-- Example 2: Using JSON interface (most flexible)
SELECT * FROM calculate_likelihood_from_json(
    '{
        "aggregation_method": "weighted_sum",
        "scale_to": 100.0,
        "parameters": [
            {
                "param_name": "critical_vulnerabilities",
                "param_value": 5,
                "param_weight": 0.40,
                "max_value": 20,
                "decay_function": "exponential",
                "decay_rate": 30.0,
                "time_delta": 45,
                "inverse": false
            },
            {
                "param_name": "high_vulnerabilities",
                "param_value": 10,
                "param_weight": 0.30,
                "max_value": 50,
                "decay_function": "exponential",
                "decay_rate": 30.0,
                "time_delta": 45,
                "inverse": false
            },
            {
                "param_name": "patch_compliance_rate",
                "param_value": 75,
                "param_weight": 0.20,
                "max_value": 100,
                "decay_function": "none",
                "inverse": true
            },
            {
                "param_name": "user_behavior_risk",
                "param_value": 45,
                "param_weight": 0.10,
                "max_value": 100,
                "decay_function": "sigmoid",
                "decay_rate": 0.1,
                "time_delta": 30
            }
        ]
    }'::JSONB
);

-- Example 3: Batch calculation for multiple assets
SELECT * FROM calculate_likelihood_batch(
    '[
        {
            "asset_id": "asset_001",
            "aggregation_method": "weighted_sum",
            "scale_to": 100,
            "parameters": [
                {"param_name": "vulns", "param_value": 5, "param_weight": 0.5, "max_value": 20},
                {"param_name": "compliance", "param_value": 80, "param_weight": 0.5, "max_value": 100, "inverse": true}
            ]
        },
        {
            "asset_id": "asset_002",
            "aggregation_method": "weighted_sum",
            "scale_to": 100,
            "parameters": [
                {"param_name": "vulns", "param_value": 12, "param_weight": 0.5, "max_value": 20},
                {"param_name": "compliance", "param_value": 60, "param_weight": 0.5, "max_value": 100, "inverse": true}
            ]
        },
        {
            "asset_id": "asset_003",
            "aggregation_method": "weighted_sum",
            "scale_to": 100,
            "parameters": [
                {"param_name": "vulns", "param_value": 2, "param_weight": 0.5, "max_value": 20},
                {"param_name": "compliance", "param_value": 95, "param_weight": 0.5, "max_value": 100, "inverse": true}
            ]
        }
    ]'::JSONB
);

-- Example 4: Compare aggregation methods
SELECT * FROM compare_likelihood_methods(
    ARRAY[
        ROW('critical_vulns', 5, 0.40, 20, 'none', 1.0, 0, FALSE, 0, 100)::likelihood_parameter,
        ROW('high_vulns', 10, 0.30, 50, 'none', 1.0, 0, FALSE, 0, 100)::likelihood_parameter,
        ROW('patch_compliance', 75, 0.20, 100, 'none', 1.0, 0, TRUE, 0, 100)::likelihood_parameter,
        ROW('dwell_time', 60, 0.10, 90, 'none', 1.0, 0, FALSE, 0, 100)::likelihood_parameter
    ]
);

-- Example 5: Using helper function to build parameters
SELECT * FROM calculate_generic_likelihood(
    ARRAY[
        build_parameter('critical_vulns', 8, 0.4, 20, 'exponential', 30.0, 45),
        build_parameter('compliance_rate', 70, 0.3, 100, 'none', 1.0, 0, TRUE),
        build_parameter('dwell_time', 60, 0.3, 90, 'linear', 90.0, 60)
    ],
    'weighted_sum',
    100.0
);

-- Example 6: Conservative approach using LEAST aggregation
SELECT * FROM calculate_likelihood_from_json(
    '{
        "aggregation_method": "least",
        "scale_to": 100.0,
        "parameters": [
            {"param_name": "security_controls", "param_value": 85, "param_weight": 1.0, "max_value": 100, "inverse": true},
            {"param_name": "vulnerability_score", "param_value": 45, "param_weight": 1.0, "max_value": 100},
            {"param_name": "exposure_level", "param_value": 70, "param_weight": 1.0, "max_value": 100}
        ]
    }'::JSONB
);
*/