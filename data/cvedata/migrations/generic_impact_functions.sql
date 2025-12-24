-- ============================================================================
-- Generic Impact Calculation Engine
-- ============================================================================
-- Fully configurable impact calculator that accepts:
-- - Any list of parameters with their values and metrics
-- - Decay functions per parameter
-- - Multiple aggregation methods (weighted sum, max, least, geometric mean)
-- - Cascade multipliers for compound impact
-- - Normalization and scaling options
-- ============================================================================

-- ============================================================================
-- CORE DATA TYPES
-- ============================================================================

-- Impact parameter definition type
CREATE TYPE impact_parameter AS (
    param_name TEXT,                  -- Name of the parameter (e.g., 'asset_criticality')
    param_value DECIMAL(10,2),        -- Current value of the parameter
    param_weight DECIMAL(5,3),        -- Weight in final calculation (0-1)
    max_value DECIMAL(10,2),          -- Maximum expected value for normalization
    impact_category TEXT,             -- 'direct', 'indirect', 'cascading', 'reputational', 'financial', 'operational', 'compliance'
    amplification_factor DECIMAL(5,3), -- Multiplier for cascading impacts (default 1.0)
    decay_function TEXT,              -- 'none', 'linear', 'exponential', 'logarithmic', 'step', 'compound'
    decay_rate DECIMAL(5,3),          -- Decay rate parameter
    time_delta DECIMAL(10,2),         -- Time elapsed for decay calculation
    inverse BOOLEAN,                  -- If true, higher value = lower impact
    threshold_critical DECIMAL(10,2), -- Critical threshold
    threshold_high DECIMAL(10,2),     -- High threshold
    threshold_medium DECIMAL(10,2)    -- Medium threshold
);

-- Impact cascade type for compound calculations
CREATE TYPE impact_cascade AS (
    primary_impact DECIMAL(10,2),
    secondary_impact DECIMAL(10,2),
    tertiary_impact DECIMAL(10,2),
    cascade_multiplier DECIMAL(5,3)
);

-- ============================================================================
-- IMPACT DECAY FUNCTION CALCULATOR (includes compound growth)
-- ============================================================================

CREATE OR REPLACE FUNCTION apply_impact_decay_function(
    p_value DECIMAL(10,2),
    p_decay_function TEXT,
    p_decay_rate DECIMAL(5,3),
    p_time_delta DECIMAL(10,2),
    p_max_value DECIMAL(10,2),
    p_amplification_factor DECIMAL(5,3) DEFAULT 1.0
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
    
    -- Apply amplification factor first
    v_normalized_value := v_normalized_value * p_amplification_factor;
    
    -- Apply decay/growth function
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
        
        -- Compound growth: value * (1 + decay_rate)^time_delta
        -- Useful for cascading impacts that grow over time
        WHEN 'compound' THEN
            v_normalized_value * POWER(1.0 + p_decay_rate, p_time_delta)
        
        -- Inverse exponential growth: value * (1 - exp(-time_delta / decay_rate))
        WHEN 'inverse_exponential' THEN
            v_normalized_value * (1.0 - EXP(-p_time_delta / NULLIF(p_decay_rate, 0)))
        
        -- Sigmoid: value / (1 + exp(-decay_rate * (time_delta - 50)))
        WHEN 'sigmoid' THEN
            v_normalized_value / (1.0 + EXP(-p_decay_rate * (p_time_delta - 50.0)))
        
        -- Square growth: value * (time_delta / decay_rate)^2
        -- Useful for impacts that accelerate
        WHEN 'square' THEN
            v_normalized_value * POWER(p_time_delta / NULLIF(p_decay_rate, 1.0), 2)
        
        ELSE v_normalized_value
    END;
    
    RETURN LEAST(v_decayed_value, 10.0); -- Cap at 10x for compound growth
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- IMPACT CATEGORY AGGREGATION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_category_impact(
    p_parameters impact_parameter[],
    p_category TEXT
) RETURNS TABLE (
    category TEXT,
    category_impact DECIMAL(10,2),
    parameter_count INTEGER,
    top_contributors JSONB
) AS $$
DECLARE
    v_param impact_parameter;
    v_category_impact DECIMAL(10,2) := 0;
    v_count INTEGER := 0;
    v_contributors JSONB := '[]'::JSONB;
BEGIN
    -- Aggregate parameters for this category
    FOREACH v_param IN ARRAY p_parameters
    LOOP
        IF v_param.impact_category = p_category THEN
            v_count := v_count + 1;
            
            -- Calculate parameter impact
            DECLARE
                v_impact DECIMAL(10,2);
            BEGIN
                v_impact := apply_impact_decay_function(
                    v_param.param_value,
                    COALESCE(v_param.decay_function, 'none'),
                    COALESCE(v_param.decay_rate, 1.0),
                    COALESCE(v_param.time_delta, 0),
                    v_param.max_value,
                    COALESCE(v_param.amplification_factor, 1.0)
                );
                
                v_category_impact := v_category_impact + (v_impact * v_param.param_weight * 100.0);
                
                v_contributors := v_contributors || jsonb_build_object(
                    'param_name', v_param.param_name,
                    'impact', ROUND(v_impact * 100.0, 2),
                    'weight', v_param.param_weight
                );
            END;
        END IF;
    END LOOP;
    
    RETURN QUERY SELECT 
        p_category,
        LEAST(v_category_impact, 100.0),
        v_count,
        v_contributors;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GENERIC IMPACT CALCULATOR
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_generic_impact(
    p_parameters impact_parameter[],
    p_aggregation_method TEXT DEFAULT 'weighted_sum',  -- 'weighted_sum', 'max', 'least', 'geometric_mean', 'cascading', 'quadratic_mean'
    p_scale_to DECIMAL(10,2) DEFAULT 100.0,            -- Scale final result to this value
    p_enable_cascade BOOLEAN DEFAULT FALSE,            -- Enable cascading impact calculation
    p_cascade_depth INTEGER DEFAULT 3                  -- Depth of cascade (1=primary only, 2=secondary, 3=tertiary)
) RETURNS TABLE (
    overall_impact DECIMAL(10,2),
    direct_impact DECIMAL(10,2),
    indirect_impact DECIMAL(10,2),
    cascading_impact DECIMAL(10,2),
    aggregation_method TEXT,
    impact_by_category JSONB,
    parameter_scores JSONB,
    raw_scores JSONB,
    decayed_scores JSONB,
    weighted_scores JSONB,
    cascade_breakdown JSONB,
    calculation_metadata JSONB
) AS $$
DECLARE
    v_param impact_parameter;
    v_raw_score DECIMAL(10,2);
    v_decayed_score DECIMAL(10,2);
    v_weighted_score DECIMAL(10,2);
    v_overall_score DECIMAL(10,2) := 0;
    v_direct_impact DECIMAL(10,2) := 0;
    v_indirect_impact DECIMAL(10,2) := 0;
    v_cascading_impact DECIMAL(10,2) := 0;
    
    v_raw_scores JSONB := '{}'::JSONB;
    v_decayed_scores JSONB := '{}'::JSONB;
    v_weighted_scores JSONB := '{}'::JSONB;
    v_parameter_scores JSONB := '{}'::JSONB;
    v_category_impacts JSONB := '{}'::JSONB;
    v_cascade_breakdown JSONB := '{}'::JSONB;
    
    v_sum_weights DECIMAL(10,2) := 0;
    v_product DECIMAL(10,2) := 1.0;
    v_sum_squares DECIMAL(10,2) := 0;
    v_count INTEGER := 0;
    v_max_score DECIMAL(10,2) := -999999;
    v_min_score DECIMAL(10,2) := 999999;
    
    v_cascade_multiplier DECIMAL(5,3) := 1.0;
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
        
        -- Apply inverse if specified
        IF v_param.inverse THEN
            v_raw_score := 1.0 - v_raw_score;
        END IF;
        
        -- Apply decay/growth function with amplification
        v_decayed_score := apply_impact_decay_function(
            v_param.param_value,
            COALESCE(v_param.decay_function, 'none'),
            COALESCE(v_param.decay_rate, 1.0),
            COALESCE(v_param.time_delta, 0),
            v_param.max_value,
            COALESCE(v_param.amplification_factor, 1.0)
        );
        
        -- Apply inverse to decayed score if needed
        IF v_param.inverse THEN
            v_decayed_score := LEAST(1.0 - v_decayed_score, 1.0);
        END IF;
        
        -- Apply weight
        v_weighted_score := v_decayed_score * COALESCE(v_param.param_weight, 1.0);
        
        -- Categorize impact
        CASE v_param.impact_category
            WHEN 'direct' THEN
                v_direct_impact := v_direct_impact + v_weighted_score;
            WHEN 'indirect' THEN
                v_indirect_impact := v_indirect_impact + v_weighted_score;
            WHEN 'cascading' THEN
                v_cascading_impact := v_cascading_impact + v_weighted_score;
            ELSE
                v_direct_impact := v_direct_impact + v_weighted_score;
        END CASE;
        
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
                'category', v_param.impact_category,
                'amplification_factor', v_param.amplification_factor,
                'decay_function', v_param.decay_function,
                'time_delta', v_param.time_delta
            )
        );
        
        -- Accumulate for different aggregation methods
        v_sum_weights := v_sum_weights + COALESCE(v_param.param_weight, 1.0);
        
        CASE p_aggregation_method
            WHEN 'weighted_sum' THEN
                v_overall_score := v_overall_score + v_weighted_score;
                
            WHEN 'max' THEN
                v_max_score := GREATEST(v_max_score, v_decayed_score);
                
            WHEN 'least' THEN
                v_min_score := LEAST(v_min_score, v_decayed_score);
                
            WHEN 'geometric_mean' THEN
                v_product := v_product * GREATEST(v_decayed_score, 0.0001);
                
            WHEN 'quadratic_mean' THEN
                v_sum_squares := v_sum_squares + (v_decayed_score * v_decayed_score);
                
            WHEN 'cascading' THEN
                -- Cascading uses compound multiplication
                v_overall_score := v_overall_score + v_weighted_score;
                
            ELSE
                v_overall_score := v_overall_score + v_weighted_score;
        END CASE;
    END LOOP;
    
    -- Calculate final aggregated score based on method
    v_overall_score := CASE p_aggregation_method
        WHEN 'weighted_sum' THEN
            CASE WHEN v_sum_weights > 0 THEN v_overall_score / v_sum_weights ELSE 0 END
            
        WHEN 'max' THEN
            v_max_score
            
        WHEN 'least' THEN
            v_min_score
            
        WHEN 'geometric_mean' THEN
            POWER(v_product, 1.0 / NULLIF(v_count, 0))
            
        WHEN 'quadratic_mean' THEN
            SQRT(v_sum_squares / NULLIF(v_count, 0))
            
        WHEN 'cascading' THEN
            -- For cascading, apply compound multiplier
            CASE WHEN v_sum_weights > 0 THEN v_overall_score / v_sum_weights ELSE 0 END *
            (1.0 + (v_cascading_impact * 0.5))  -- Cascade adds up to 50% more impact
            
        ELSE
            CASE WHEN v_sum_weights > 0 THEN v_overall_score / v_sum_weights ELSE 0 END
    END;
    
    -- Apply cascade calculation if enabled
    IF p_enable_cascade THEN
        v_cascade_multiplier := 1.0 + (v_cascading_impact * 0.3);
        v_overall_score := v_overall_score * v_cascade_multiplier;
        
        v_cascade_breakdown := jsonb_build_object(
            'primary_impact', ROUND(v_direct_impact * p_scale_to, 2),
            'secondary_impact', ROUND(v_indirect_impact * p_scale_to, 2),
            'tertiary_impact', ROUND(v_cascading_impact * p_scale_to, 2),
            'cascade_multiplier', v_cascade_multiplier,
            'cascade_depth', p_cascade_depth
        );
    ELSE
        v_cascade_breakdown := jsonb_build_object(
            'cascade_enabled', false
        );
    END IF;
    
    -- Scale to target range
    v_overall_score := LEAST(v_overall_score * p_scale_to, p_scale_to);
    v_direct_impact := LEAST(v_direct_impact * p_scale_to, p_scale_to);
    v_indirect_impact := LEAST(v_indirect_impact * p_scale_to, p_scale_to);
    v_cascading_impact := LEAST(v_cascading_impact * p_scale_to, p_scale_to);
    
    -- Get impact by category
    v_category_impacts := jsonb_build_object(
        'direct', ROUND(v_direct_impact, 2),
        'indirect', ROUND(v_indirect_impact, 2),
        'cascading', ROUND(v_cascading_impact, 2)
    );
    
    -- Build metadata
    v_metadata := jsonb_build_object(
        'parameter_count', v_count,
        'aggregation_method', p_aggregation_method,
        'scale_to', p_scale_to,
        'sum_weights', v_sum_weights,
        'cascade_enabled', p_enable_cascade,
        'cascade_depth', p_cascade_depth
    );
    
    RETURN QUERY SELECT
        v_overall_score,
        v_direct_impact,
        v_indirect_impact,
        v_cascading_impact,
        p_aggregation_method,
        v_category_impacts,
        v_parameter_scores,
        v_raw_scores,
        v_decayed_scores,
        v_weighted_scores,
        v_cascade_breakdown,
        v_metadata;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SIMPLIFIED JSON-BASED INTERFACE
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_impact_from_json(
    p_config JSONB
) RETURNS TABLE (
    overall_impact DECIMAL(10,2),
    direct_impact DECIMAL(10,2),
    indirect_impact DECIMAL(10,2),
    cascading_impact DECIMAL(10,2),
    aggregation_method TEXT,
    impact_by_category JSONB,
    parameter_scores JSONB,
    calculation_summary JSONB
) AS $$
DECLARE
    v_parameters impact_parameter[];
    v_param JSONB;
    v_param_struct impact_parameter;
    v_aggregation TEXT;
    v_scale DECIMAL(10,2);
    v_enable_cascade BOOLEAN;
    v_cascade_depth INTEGER;
BEGIN
    -- Extract configuration
    v_aggregation := COALESCE(p_config->>'aggregation_method', 'weighted_sum');
    v_scale := COALESCE((p_config->>'scale_to')::DECIMAL, 100.0);
    v_enable_cascade := COALESCE((p_config->>'enable_cascade')::BOOLEAN, FALSE);
    v_cascade_depth := COALESCE((p_config->>'cascade_depth')::INTEGER, 3);
    
    -- Build parameter array from JSON
    FOR v_param IN SELECT * FROM jsonb_array_elements(p_config->'parameters')
    LOOP
        v_param_struct := ROW(
            v_param->>'param_name',
            COALESCE((v_param->>'param_value')::DECIMAL, 0),
            COALESCE((v_param->>'param_weight')::DECIMAL, 1.0),
            COALESCE((v_param->>'max_value')::DECIMAL, 100.0),
            COALESCE(v_param->>'impact_category', 'direct'),
            COALESCE((v_param->>'amplification_factor')::DECIMAL, 1.0),
            COALESCE(v_param->>'decay_function', 'none'),
            COALESCE((v_param->>'decay_rate')::DECIMAL, 1.0),
            COALESCE((v_param->>'time_delta')::DECIMAL, 0),
            COALESCE((v_param->>'inverse')::BOOLEAN, FALSE),
            COALESCE((v_param->>'threshold_critical')::DECIMAL, 90.0),
            COALESCE((v_param->>'threshold_high')::DECIMAL, 70.0),
            COALESCE((v_param->>'threshold_medium')::DECIMAL, 50.0)
        )::impact_parameter;
        
        v_parameters := array_append(v_parameters, v_param_struct);
    END LOOP;
    
    -- Calculate using generic function
    RETURN QUERY
    SELECT 
        i.overall_impact,
        i.direct_impact,
        i.indirect_impact,
        i.cascading_impact,
        i.aggregation_method,
        i.impact_by_category,
        i.parameter_scores,
        jsonb_build_object(
            'raw_scores', i.raw_scores,
            'decayed_scores', i.decayed_scores,
            'weighted_scores', i.weighted_scores,
            'cascade_breakdown', i.cascade_breakdown,
            'metadata', i.calculation_metadata
        ) AS calculation_summary
    FROM calculate_generic_impact(
        v_parameters,
        v_aggregation,
        v_scale,
        v_enable_cascade,
        v_cascade_depth
    ) i;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- IMPACT CLASSIFICATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION classify_impact_level(
    p_impact_score DECIMAL(10,2),
    p_threshold_critical DECIMAL(10,2) DEFAULT 90.0,
    p_threshold_high DECIMAL(10,2) DEFAULT 70.0,
    p_threshold_medium DECIMAL(10,2) DEFAULT 50.0,
    p_threshold_low DECIMAL(10,2) DEFAULT 30.0
) RETURNS TABLE (
    impact_score DECIMAL(10,2),
    impact_level TEXT,
    impact_category TEXT,
    priority_order INTEGER,
    recommended_action TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p_impact_score,
        CASE
            WHEN p_impact_score >= p_threshold_critical THEN 'CRITICAL'
            WHEN p_impact_score >= p_threshold_high THEN 'HIGH'
            WHEN p_impact_score >= p_threshold_medium THEN 'MEDIUM'
            WHEN p_impact_score >= p_threshold_low THEN 'LOW'
            ELSE 'MINIMAL'
        END AS impact_level,
        CASE
            WHEN p_impact_score >= p_threshold_critical THEN 'Catastrophic'
            WHEN p_impact_score >= p_threshold_high THEN 'Severe'
            WHEN p_impact_score >= p_threshold_medium THEN 'Moderate'
            WHEN p_impact_score >= p_threshold_low THEN 'Minor'
            ELSE 'Negligible'
        END AS impact_category,
        CASE
            WHEN p_impact_score >= p_threshold_critical THEN 1
            WHEN p_impact_score >= p_threshold_high THEN 2
            WHEN p_impact_score >= p_threshold_medium THEN 3
            WHEN p_impact_score >= p_threshold_low THEN 4
            ELSE 5
        END AS priority_order,
        CASE
            WHEN p_impact_score >= p_threshold_critical THEN 'IMMEDIATE ACTION REQUIRED - Executive escalation'
            WHEN p_impact_score >= p_threshold_high THEN 'URGENT - Prioritize remediation within 24-48 hours'
            WHEN p_impact_score >= p_threshold_medium THEN 'IMPORTANT - Address within 1 week'
            WHEN p_impact_score >= p_threshold_low THEN 'STANDARD - Include in regular maintenance'
            ELSE 'MONITOR - Track as part of routine operations'
        END AS recommended_action;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- CASCADING IMPACT CALCULATOR
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_cascading_impact(
    p_primary_impact DECIMAL(10,2),
    p_affected_systems_count INTEGER,
    p_dependency_depth INTEGER DEFAULT 3,
    p_cascade_rate DECIMAL(5,3) DEFAULT 0.5
) RETURNS TABLE (
    primary_impact DECIMAL(10,2),
    secondary_impact DECIMAL(10,2),
    tertiary_impact DECIMAL(10,2),
    total_cascaded_impact DECIMAL(10,2),
    affected_systems INTEGER,
    blast_radius_score DECIMAL(10,2)
) AS $$
DECLARE
    v_secondary DECIMAL(10,2);
    v_tertiary DECIMAL(10,2);
    v_total DECIMAL(10,2);
    v_blast_radius DECIMAL(10,2);
BEGIN
    -- Calculate cascading impacts with decay
    v_secondary := p_primary_impact * p_cascade_rate * LEAST(p_affected_systems_count / 10.0, 2.0);
    v_tertiary := v_secondary * p_cascade_rate * LEAST(p_affected_systems_count / 20.0, 1.5);
    
    -- Total impact including cascades
    v_total := LEAST(
        p_primary_impact + v_secondary + v_tertiary,
        100.0
    );
    
    -- Blast radius score based on affected systems
    v_blast_radius := LEAST(
        (p_affected_systems_count * 5.0) + (p_dependency_depth * 10.0),
        100.0
    );
    
    RETURN QUERY SELECT
        p_primary_impact,
        ROUND(v_secondary, 2),
        ROUND(v_tertiary, 2),
        ROUND(v_total, 2),
        p_affected_systems_count,
        ROUND(v_blast_radius, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- BATCH CALCULATION FOR MULTIPLE ASSETS
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_impact_batch(
    p_asset_configs JSONB
) RETURNS TABLE (
    asset_id TEXT,
    overall_impact DECIMAL(10,2),
    direct_impact DECIMAL(10,2),
    cascading_impact DECIMAL(10,2),
    impact_level TEXT,
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
            (calculate_impact_from_json(config)).overall_impact,
            (calculate_impact_from_json(config)).direct_impact,
            (calculate_impact_from_json(config)).cascading_impact,
            (calculate_impact_from_json(config)).aggregation_method,
            (calculate_impact_from_json(config)).parameter_scores
        FROM jsonb_array_elements(p_asset_configs) AS config
    ),
    classified_impacts AS (
        SELECT
            ac.*,
            (classify_impact_level(ac.overall_impact)).impact_level
        FROM asset_calculations ac
    ),
    ranked_assets AS (
        SELECT
            *,
            RANK() OVER (ORDER BY overall_impact DESC) AS rank_overall,
            PERCENT_RANK() OVER (ORDER BY overall_impact) * 100 AS percentile
        FROM classified_impacts
    )
    SELECT * FROM ranked_assets;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HELPER FUNCTION: CREATE PARAMETER FROM VALUES
-- ============================================================================

CREATE OR REPLACE FUNCTION build_impact_parameter(
    p_name TEXT,
    p_value DECIMAL(10,2),
    p_weight DECIMAL(5,3) DEFAULT 1.0,
    p_max_value DECIMAL(10,2) DEFAULT 100.0,
    p_category TEXT DEFAULT 'direct',
    p_amplification DECIMAL(5,3) DEFAULT 1.0,
    p_decay_function TEXT DEFAULT 'none',
    p_decay_rate DECIMAL(5,3) DEFAULT 1.0,
    p_time_delta DECIMAL(10,2) DEFAULT 0,
    p_inverse BOOLEAN DEFAULT FALSE
) RETURNS impact_parameter AS $$
BEGIN
    RETURN ROW(
        p_name,
        p_value,
        p_weight,
        p_max_value,
        p_category,
        p_amplification,
        p_decay_function,
        p_decay_rate,
        p_time_delta,
        p_inverse,
        90.0,  -- threshold_critical
        70.0,  -- threshold_high
        50.0   -- threshold_medium
    )::impact_parameter;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- IMPACT COMPARISON FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION compare_impact_methods(
    p_parameters impact_parameter[]
) RETURNS TABLE (
    method_name TEXT,
    impact_score DECIMAL(10,2),
    score_difference DECIMAL(10,2),
    rank INTEGER
) AS $$
DECLARE
    v_methods TEXT[] := ARRAY['weighted_sum', 'max', 'least', 'geometric_mean', 'cascading', 'quadratic_mean'];
    v_method TEXT;
    v_baseline DECIMAL(10,2);
BEGIN
    CREATE TEMP TABLE IF NOT EXISTS impact_method_comparison (
        method_name TEXT,
        impact_score DECIMAL(10,2)
    ) ON COMMIT DROP;
    
    FOREACH v_method IN ARRAY v_methods
    LOOP
        INSERT INTO impact_method_comparison
        SELECT 
            v_method,
            i.overall_impact
        FROM calculate_generic_impact(
            p_parameters,
            v_method,
            100.0,
            FALSE,
            3
        ) i;
    END LOOP;
    
    SELECT impact_score INTO v_baseline
    FROM impact_method_comparison
    WHERE method_name = 'weighted_sum';
    
    RETURN QUERY
    SELECT 
        imc.method_name,
        imc.impact_score,
        imc.impact_score - v_baseline AS score_difference,
        RANK() OVER (ORDER BY imc.impact_score DESC)::INTEGER AS rank
    FROM impact_method_comparison imc
    ORDER BY imc.impact_score DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_generic_impact IS
'Generic impact calculator accepting array of parameters with:
- param_name: Name of parameter
- param_value: Current value
- param_weight: Weight in aggregation (0-1)
- max_value: Maximum value for normalization
- impact_category: direct, indirect, cascading, reputational, financial, operational, compliance
- amplification_factor: Multiplier for impact (e.g., 2.0 doubles impact)
- decay_function: none, linear, exponential, logarithmic, step, compound, square
- decay_rate: Rate parameter for decay/growth function
- time_delta: Time elapsed for calculation
- inverse: If TRUE, higher value = lower impact

Aggregation methods:
- weighted_sum: Weighted average (default)
- max: Maximum impact (worst case)
- least: Minimum impact (best case)
- geometric_mean: Product root
- cascading: Includes cascade multiplier for compound effects
- quadratic_mean: Root mean square

Returns overall impact plus detailed breakdowns by category.';

COMMENT ON FUNCTION calculate_impact_from_json IS
'Simplified JSON interface for impact calculation.
Input format matches likelihood calculator with impact-specific fields.';

COMMENT ON FUNCTION classify_impact_level IS
'Classifies impact score into levels: CRITICAL, HIGH, MEDIUM, LOW, MINIMAL
with recommended actions for each level.';

COMMENT ON FUNCTION calculate_cascading_impact IS
'Calculates cascading/ripple effects when one system impacts others.
Accounts for affected systems count and dependency depth.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- Example 1: Basic impact calculation with direct and cascading parameters
SELECT * FROM calculate_impact_from_json(
    '{
        "aggregation_method": "weighted_sum",
        "scale_to": 100,
        "enable_cascade": true,
        "cascade_depth": 3,
        "parameters": [
            {
                "param_name": "asset_criticality",
                "param_value": 95,
                "param_weight": 0.40,
                "max_value": 100,
                "impact_category": "direct",
                "amplification_factor": 1.0
            },
            {
                "param_name": "data_sensitivity",
                "param_value": 85,
                "param_weight": 0.30,
                "max_value": 100,
                "impact_category": "direct",
                "amplification_factor": 1.2
            },
            {
                "param_name": "dependent_systems",
                "param_value": 15,
                "param_weight": 0.20,
                "max_value": 50,
                "impact_category": "cascading",
                "amplification_factor": 1.5,
                "decay_function": "compound",
                "decay_rate": 0.1,
                "time_delta": 3
            },
            {
                "param_name": "business_process_dependency",
                "param_value": 70,
                "param_weight": 0.10,
                "max_value": 100,
                "impact_category": "indirect"
            }
        ]
    }'::JSONB
);

-- Example 2: Mission Critical asset with high amplification
SELECT * FROM calculate_impact_from_json(
    '{
        "aggregation_method": "cascading",
        "scale_to": 100,
        "enable_cascade": true,
        "parameters": [
            {
                "param_name": "mission_critical_flag",
                "param_value": 100,
                "param_weight": 0.50,
                "max_value": 100,
                "impact_category": "direct",
                "amplification_factor": 1.5
            },
            {
                "param_name": "revenue_impact_per_hour",
                "param_value": 50000,
                "param_weight": 0.30,
                "max_value": 100000,
                "impact_category": "financial",
                "amplification_factor": 2.0
            },
            {
                "param_name": "user_count_affected",
                "param_value": 5000,
                "param_weight": 0.20,
                "max_value": 10000,
                "impact_category": "operational"
            }
        ]
    }'::JSONB
);

-- Example 3: Classify impact level
SELECT * FROM classify_impact_level(87.5);

-- Example 4: Calculate cascading impact
SELECT * FROM calculate_cascading_impact(
    75.0,  -- primary impact
    12,    -- affected systems
    3,     -- dependency depth
    0.5    -- cascade rate
);

-- Example 5: Batch calculation for multiple assets
SELECT * FROM calculate_impact_batch(
    '[
        {
            "asset_id": "db_prod_001",
            "aggregation_method": "weighted_sum",
            "enable_cascade": true,
            "parameters": [
                {"param_name": "criticality", "param_value": 95, "param_weight": 0.6, "impact_category": "direct"},
                {"param_name": "dependencies", "param_value": 20, "param_weight": 0.4, "max_value": 50, "impact_category": "cascading"}
            ]
        },
        {
            "asset_id": "web_app_001",
            "aggregation_method": "weighted_sum",
            "parameters": [
                {"param_name": "criticality", "param_value": 70, "param_weight": 0.7, "impact_category": "direct"},
                {"param_name": "dependencies", "param_value": 5, "param_weight": 0.3, "max_value": 50, "impact_category": "cascading"}
            ]
        }
    ]'::JSONB
);

-- Example 6: Compare aggregation methods
SELECT * FROM compare_impact_methods(
    ARRAY[
        build_impact_parameter('criticality', 90, 0.5, 100, 'direct', 1.0),
        build_impact_parameter('data_value', 85, 0.3, 100, 'direct', 1.2),
        build_impact_parameter('dependencies', 15, 0.2, 50, 'cascading', 1.5)
    ]
);

-- Example 7: Maximum impact approach (worst case)
SELECT * FROM calculate_impact_from_json(
    '{
        "aggregation_method": "max",
        "scale_to": 100,
        "parameters": [
            {"param_name": "data_breach_potential", "param_value": 90, "param_weight": 1.0, "impact_category": "direct"},
            {"param_name": "compliance_violation", "param_value": 85, "param_weight": 1.0, "impact_category": "compliance"},
            {"param_name": "reputation_damage", "param_value": 75, "param_weight": 1.0, "impact_category": "reputational"}
        ]
    }'::JSONB
);
*/