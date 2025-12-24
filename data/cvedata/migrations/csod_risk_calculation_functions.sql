-- ============================================================================
-- Generic Risk Calculation Functions
-- ============================================================================
-- Bridge functions that connect metadata tables to generic calculation functions
-- Calculates impact and likelihood scores from source data rows using metadata
-- 
-- KEY FEATURES:
-- - Fully generic: Accepts metadata table names as parameters
-- - Works with any risk model following the standard metadata pattern
-- - Backward compatible: CSOD-specific wrapper functions included
-- - Dynamic SQL: Queries metadata tables specified at runtime
--
-- METADATA TABLE REQUIREMENTS:
-- All metadata tables must follow this structure:
-- - model_metadata: model_code, risk_formula, score_min, score_max
-- - factor_metadata: model_code, dimension, factor_code, weight, scoring_type, source_columns, is_active
-- - lookup_metadata: model_code, dimension, factor_code, input_value, score, priority_order
-- - bucket_metadata: model_code, dimension, factor_code, min_value, max_value, min_inclusive, max_inclusive, score, priority_order
-- - band_metadata: model_code, band_code, min_score, max_score, priority_order
-- ============================================================================

-- ============================================================================
-- HELPER: Get factor score from source value (GENERIC VERSION)
-- ============================================================================

CREATE OR REPLACE FUNCTION get_factor_score(
    p_model_code VARCHAR(50),
    p_dimension VARCHAR(20),
    p_factor_code VARCHAR(100),
    p_source_value TEXT,  -- Can be numeric or categorical
    p_source_numeric_value DECIMAL(18,6) DEFAULT NULL,
    p_factor_metadata_table TEXT,  -- e.g., 'csod_risk_factor_metadata'
    p_lookup_metadata_table TEXT,  -- e.g., 'csod_risk_factor_lookup_metadata'
    p_bucket_metadata_table TEXT   -- e.g., 'csod_risk_factor_bucket_metadata'
) RETURNS DECIMAL(10,2) AS $$
DECLARE
    v_scoring_type VARCHAR(30);
    v_default_score DECIMAL(10,2);
    v_score DECIMAL(10,2);
    v_lookup_score DECIMAL(10,2);
    v_bucket_score DECIMAL(10,2);
    v_sql TEXT;
BEGIN
    -- Get factor metadata using dynamic SQL
    v_sql := format('
        SELECT scoring_type, default_score
        FROM %I
        WHERE model_code = $1
          AND dimension = $2
          AND factor_code = $3
          AND is_active = TRUE
    ', p_factor_metadata_table);
    
    EXECUTE v_sql
    INTO v_scoring_type, v_default_score
    USING p_model_code, p_dimension, p_factor_code;
    
    -- If factor not found or inactive, return NULL
    IF v_scoring_type IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- Handle NULL source value
    IF p_source_value IS NULL AND p_source_numeric_value IS NULL THEN
        RETURN v_default_score;
    END IF;
    
    -- Apply scoring based on type
    CASE v_scoring_type
        WHEN 'lookup' THEN
            -- Lookup categorical value using dynamic SQL
            v_sql := format('
                SELECT score
                FROM %I
                WHERE model_code = $1
                  AND dimension = $2
                  AND factor_code = $3
                  AND input_value = $4
                ORDER BY priority_order ASC
                LIMIT 1
            ', p_lookup_metadata_table);
            
            EXECUTE v_sql
            INTO v_lookup_score
            USING p_model_code, p_dimension, p_factor_code, p_source_value;
            
            RETURN COALESCE(v_lookup_score, v_default_score);
            
        WHEN 'bucket' THEN
            -- Bucket numeric value using dynamic SQL
            v_sql := format('
                SELECT score
                FROM %I
                WHERE model_code = $1
                  AND dimension = $2
                  AND factor_code = $3
                  AND (
                    (min_value IS NULL OR 
                     (COALESCE(min_inclusive, TRUE) = TRUE AND $4 >= min_value) OR
                     (COALESCE(min_inclusive, TRUE) = FALSE AND $4 > min_value))
                    AND
                    (max_value IS NULL OR 
                     (COALESCE(max_inclusive, FALSE) = TRUE AND $4 <= max_value) OR
                     (COALESCE(max_inclusive, FALSE) = FALSE AND $4 < max_value))
                  )
                ORDER BY priority_order ASC
                LIMIT 1
            ', p_bucket_metadata_table);
            
            EXECUTE v_sql
            INTO v_bucket_score
            USING p_model_code, p_dimension, p_factor_code, p_source_numeric_value;
            
            RETURN COALESCE(v_bucket_score, v_default_score);
            
        WHEN 'linear' THEN
            -- Linear scaling (0-100 based on max_value from factor metadata)
            IF p_source_numeric_value IS NOT NULL THEN
                RETURN LEAST((p_source_numeric_value / 100.0) * 100.0, 100.0);
            ELSE
                RETURN v_default_score;
            END IF;
            
        ELSE
            -- Unknown scoring type, return default
            RETURN v_default_score;
    END CASE;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- CALCULATE LIKELIHOOD FROM SOURCE ROW (GENERIC VERSION)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_risk_likelihood(
    p_model_code VARCHAR(50),
    p_source_data JSONB,  -- Row data with all source columns
    p_factor_metadata_table TEXT DEFAULT 'csod_risk_factor_metadata',
    p_lookup_metadata_table TEXT DEFAULT 'csod_risk_factor_lookup_metadata',
    p_bucket_metadata_table TEXT DEFAULT 'csod_risk_factor_bucket_metadata'
) RETURNS TABLE (
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    calculation_summary JSONB
) AS $$
DECLARE
    v_factor RECORD;
    v_factor_score DECIMAL(10,2);
    v_source_value TEXT;
    v_source_numeric DECIMAL(18,6);
    v_config JSONB;
    v_parameters JSONB := '[]'::JSONB;
    v_param JSONB;
    v_sql TEXT;
BEGIN
    -- Build parameter array from metadata and source data using dynamic SQL
    v_sql := format('
        SELECT 
            factor_code,
            factor_name,
            weight,
            scoring_type,
            default_score,
            source_columns
        FROM %I
        WHERE model_code = $1
          AND dimension = ''likelihood''
          AND is_active = TRUE
        ORDER BY factor_code
    ', p_factor_metadata_table);
    
    FOR v_factor IN EXECUTE v_sql USING p_model_code
    LOOP
        -- Extract source value(s) from JSONB
        -- Try to get value from source_columns (comma-separated list)
        v_source_value := NULL;
        v_source_numeric := NULL;
        
        -- Try first column name from source_columns
        IF v_factor.source_columns IS NOT NULL THEN
            DECLARE
                v_first_col TEXT;
            BEGIN
                v_first_col := TRIM(SPLIT_PART(v_factor.source_columns, ',', 1));
                
                -- Try as text first (for lookups)
                IF p_source_data ? v_first_col THEN
                    v_source_value := p_source_data->>v_first_col;
                END IF;
                
                -- Try as numeric (for buckets)
                IF p_source_data ? v_first_col THEN
                    BEGIN
                        v_source_numeric := (p_source_data->>v_first_col)::DECIMAL;
                    EXCEPTION WHEN OTHERS THEN
                        v_source_numeric := NULL;
                    END;
                END IF;
            END;
        END IF;
        
        -- Get factor score using helper function
        v_factor_score := get_factor_score(
            p_model_code,
            'likelihood',
            v_factor.factor_code,
            v_source_value,
            v_source_numeric,
            p_factor_metadata_table,
            p_lookup_metadata_table,
            p_bucket_metadata_table
        );
        
        -- Skip if score is NULL
        IF v_factor_score IS NULL THEN
            CONTINUE;
        END IF;
        
        -- Build parameter JSON
        v_param := jsonb_build_object(
            'param_name', v_factor.factor_code,
            'param_value', v_factor_score,
            'param_weight', v_factor.weight,
            'max_value', 100.0,
            'decay_function', 'none',
            'inverse', false
        );
        
        v_parameters := v_parameters || v_param;
    END LOOP;
    
    -- Build config for generic likelihood function
    v_config := jsonb_build_object(
        'aggregation_method', 'weighted_sum',
        'scale_to', 100.0,
        'normalization_method', 'none',
        'parameters', v_parameters
    );
    
    -- Call generic likelihood function
    RETURN QUERY
    SELECT 
        l.overall_likelihood,
        l.aggregation_method,
        l.parameter_scores,
        l.calculation_summary
    FROM calculate_likelihood_from_json(v_config) l;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CALCULATE IMPACT FROM SOURCE ROW (GENERIC VERSION)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_risk_impact(
    p_model_code VARCHAR(50),
    p_source_data JSONB,  -- Row data with all source columns
    p_factor_metadata_table TEXT DEFAULT 'csod_risk_factor_metadata',
    p_lookup_metadata_table TEXT DEFAULT 'csod_risk_factor_lookup_metadata',
    p_bucket_metadata_table TEXT DEFAULT 'csod_risk_factor_bucket_metadata'
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
    v_factor RECORD;
    v_factor_score DECIMAL(10,2);
    v_source_value TEXT;
    v_source_numeric DECIMAL(18,6);
    v_config JSONB;
    v_parameters JSONB := '[]'::JSONB;
    v_param JSONB;
    v_sql TEXT;
BEGIN
    -- Build parameter array from metadata and source data using dynamic SQL
    v_sql := format('
        SELECT 
            factor_code,
            factor_name,
            weight,
            scoring_type,
            default_score,
            source_columns
        FROM %I
        WHERE model_code = $1
          AND dimension = ''impact''
          AND is_active = TRUE
        ORDER BY factor_code
    ', p_factor_metadata_table);
    
    FOR v_factor IN EXECUTE v_sql USING p_model_code
    LOOP
        -- Extract source value(s) from JSONB
        v_source_value := NULL;
        v_source_numeric := NULL;
        
        -- Try first column name from source_columns
        IF v_factor.source_columns IS NOT NULL THEN
            DECLARE
                v_first_col TEXT;
            BEGIN
                v_first_col := TRIM(SPLIT_PART(v_factor.source_columns, ',', 1));
                
                -- Try as text first (for lookups)
                IF p_source_data ? v_first_col THEN
                    v_source_value := p_source_data->>v_first_col;
                END IF;
                
                -- Try as numeric (for buckets)
                IF p_source_data ? v_first_col THEN
                    BEGIN
                        v_source_numeric := (p_source_data->>v_first_col)::DECIMAL;
                    EXCEPTION WHEN OTHERS THEN
                        v_source_numeric := NULL;
                    END;
                END IF;
            END;
        END IF;
        
        -- Get factor score using helper function
        v_factor_score := get_factor_score(
            p_model_code,
            'impact',
            v_factor.factor_code,
            v_source_value,
            v_source_numeric,
            p_factor_metadata_table,
            p_lookup_metadata_table,
            p_bucket_metadata_table
        );
        
        -- Skip if score is NULL
        IF v_factor_score IS NULL THEN
            CONTINUE;
        END IF;
        
        -- Build parameter JSON
        v_param := jsonb_build_object(
            'param_name', v_factor.factor_code,
            'param_value', v_factor_score,
            'param_weight', v_factor.weight,
            'max_value', 100.0,
            'impact_category', 'direct',
            'amplification_factor', 1.0,
            'decay_function', 'none',
            'inverse', false
        );
        
        v_parameters := v_parameters || v_param;
    END LOOP;
    
    -- Build config for generic impact function
    v_config := jsonb_build_object(
        'aggregation_method', 'weighted_sum',
        'scale_to', 100.0,
        'enable_cascade', false,
        'parameters', v_parameters
    );
    
    -- Call generic impact function
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
    FROM calculate_impact_from_json(v_config) i;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CALCULATE COMPLETE RISK SCORE (Impact + Likelihood + Risk) - GENERIC VERSION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_risk_score(
    p_model_code VARCHAR(50),
    p_source_data JSONB,
    p_model_metadata_table TEXT DEFAULT 'csod_risk_model_metadata',
    p_factor_metadata_table TEXT DEFAULT 'csod_risk_factor_metadata',
    p_lookup_metadata_table TEXT DEFAULT 'csod_risk_factor_lookup_metadata',
    p_bucket_metadata_table TEXT DEFAULT 'csod_risk_factor_bucket_metadata',
    p_band_metadata_table TEXT DEFAULT 'csod_risk_score_band_metadata'
) RETURNS TABLE (
    impact_score DECIMAL(10,2),
    likelihood_score DECIMAL(10,2),
    risk_score DECIMAL(10,2),
    risk_category TEXT,
    impact_details JSONB,
    likelihood_details JSONB,
    calculation_metadata JSONB
) AS $$
DECLARE
    v_impact_result RECORD;
    v_likelihood_result RECORD;
    v_risk_formula TEXT;
    v_risk_score DECIMAL(10,2);
    v_risk_category TEXT;
    v_sql TEXT;
BEGIN
    -- Get risk formula from model metadata using dynamic SQL
    v_sql := format('
        SELECT risk_formula
        FROM %I
        WHERE model_code = $1
    ', p_model_metadata_table);
    
    EXECUTE v_sql
    INTO v_risk_formula
    USING p_model_code;
    
    -- Calculate impact
    SELECT * INTO v_impact_result
    FROM calculate_risk_impact(
        p_model_code, 
        p_source_data,
        p_factor_metadata_table,
        p_lookup_metadata_table,
        p_bucket_metadata_table
    )
    LIMIT 1;
    
    -- Calculate likelihood
    SELECT * INTO v_likelihood_result
    FROM calculate_risk_likelihood(
        p_model_code, 
        p_source_data,
        p_factor_metadata_table,
        p_lookup_metadata_table,
        p_bucket_metadata_table
    )
    LIMIT 1;
    
    -- Calculate risk using formula (default: sqrt(impact * likelihood))
    IF v_risk_formula = 'sqrt(impact_score * likelihood_score)' THEN
        v_risk_score := SQRT(
            COALESCE(v_impact_result.overall_impact, 0) * 
            COALESCE(v_likelihood_result.overall_likelihood, 0)
        );
    ELSE
        -- Fallback to simple formula
        v_risk_score := SQRT(
            COALESCE(v_impact_result.overall_impact, 0) * 
            COALESCE(v_likelihood_result.overall_likelihood, 0)
        );
    END IF;
    
    -- Determine risk category from bands using dynamic SQL
    v_sql := format('
        SELECT band_code
        FROM %I
        WHERE model_code = $1
          AND $2 >= min_score
          AND $2 < max_score
        ORDER BY priority_order ASC
        LIMIT 1
    ', p_band_metadata_table);
    
    EXECUTE v_sql
    INTO v_risk_category
    USING p_model_code, v_risk_score;
    
    RETURN QUERY SELECT
        COALESCE(v_impact_result.overall_impact, 0),
        COALESCE(v_likelihood_result.overall_likelihood, 0),
        v_risk_score,
        COALESCE(v_risk_category, 'Unknown'),
        jsonb_build_object(
            'overall_impact', v_impact_result.overall_impact,
            'direct_impact', v_impact_result.direct_impact,
            'parameter_scores', v_impact_result.parameter_scores,
            'calculation_summary', v_impact_result.calculation_summary
        ),
        jsonb_build_object(
            'overall_likelihood', v_likelihood_result.overall_likelihood,
            'parameter_scores', v_likelihood_result.parameter_scores,
            'calculation_summary', v_likelihood_result.calculation_summary
        ),
        jsonb_build_object(
            'model_code', p_model_code,
            'risk_formula', v_risk_formula,
            'calculation_timestamp', CURRENT_TIMESTAMP
        );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- BATCH CALCULATION FROM TABLE (GENERIC VERSION)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_risk_batch(
    p_model_code VARCHAR(50),
    p_table_name TEXT,  -- Source table name
    p_row_id_column TEXT DEFAULT 'id',  -- Column to identify rows
    p_limit INTEGER DEFAULT 100,
    p_model_metadata_table TEXT DEFAULT 'csod_risk_model_metadata',
    p_factor_metadata_table TEXT DEFAULT 'csod_risk_factor_metadata',
    p_lookup_metadata_table TEXT DEFAULT 'csod_risk_factor_lookup_metadata',
    p_bucket_metadata_table TEXT DEFAULT 'csod_risk_factor_bucket_metadata',
    p_band_metadata_table TEXT DEFAULT 'csod_risk_score_band_metadata'
) RETURNS TABLE (
    row_id TEXT,
    impact_score DECIMAL(10,2),
    likelihood_score DECIMAL(10,2),
    risk_score DECIMAL(10,2),
    risk_category TEXT,
    calculation_metadata JSONB
) AS $$
DECLARE
    v_sql TEXT;
    v_row_data JSONB;
    v_row_id TEXT;
BEGIN
    -- Build dynamic SQL to process rows
    v_sql := format('
        SELECT 
            %I::TEXT AS row_id,
            row_to_json(t.*)::JSONB AS row_data
        FROM %I t
        LIMIT %s
    ', p_row_id_column, p_table_name, p_limit);
    
    -- Process each row
    FOR v_row_id, v_row_data IN EXECUTE v_sql
    LOOP
        RETURN QUERY
        SELECT 
            v_row_id,
            r.impact_score,
            r.likelihood_score,
            r.risk_score,
            r.risk_category,
            r.calculation_metadata
        FROM calculate_risk_score(
            p_model_code, 
            v_row_data,
            p_model_metadata_table,
            p_factor_metadata_table,
            p_lookup_metadata_table,
            p_bucket_metadata_table,
            p_band_metadata_table
        ) r;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CSOD-SPECIFIC WRAPPER FUNCTIONS (for backward compatibility)
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_csod_likelihood(
    p_model_code VARCHAR(50),
    p_source_data JSONB
) RETURNS TABLE (
    overall_likelihood DECIMAL(10,2),
    aggregation_method TEXT,
    parameter_scores JSONB,
    calculation_summary JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM calculate_risk_likelihood(
        p_model_code,
        p_source_data,
        'csod_risk_factor_metadata',
        'csod_risk_factor_lookup_metadata',
        'csod_risk_factor_bucket_metadata'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_csod_impact(
    p_model_code VARCHAR(50),
    p_source_data JSONB
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
BEGIN
    RETURN QUERY
    SELECT * FROM calculate_risk_impact(
        p_model_code,
        p_source_data,
        'csod_risk_factor_metadata',
        'csod_risk_factor_lookup_metadata',
        'csod_risk_factor_bucket_metadata'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_csod_risk(
    p_model_code VARCHAR(50),
    p_source_data JSONB
) RETURNS TABLE (
    impact_score DECIMAL(10,2),
    likelihood_score DECIMAL(10,2),
    risk_score DECIMAL(10,2),
    risk_category TEXT,
    impact_details JSONB,
    likelihood_details JSONB,
    calculation_metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM calculate_risk_score(
        p_model_code,
        p_source_data,
        'csod_risk_model_metadata',
        'csod_risk_factor_metadata',
        'csod_risk_factor_lookup_metadata',
        'csod_risk_factor_bucket_metadata',
        'csod_risk_score_band_metadata'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION calculate_csod_risk_batch(
    p_model_code VARCHAR(50),
    p_table_name TEXT,
    p_row_id_column TEXT DEFAULT 'id',
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    row_id TEXT,
    impact_score DECIMAL(10,2),
    likelihood_score DECIMAL(10,2),
    risk_score DECIMAL(10,2),
    risk_category TEXT,
    calculation_metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM calculate_risk_batch(
        p_model_code,
        p_table_name,
        p_row_id_column,
        p_limit,
        'csod_risk_model_metadata',
        'csod_risk_factor_metadata',
        'csod_risk_factor_lookup_metadata',
        'csod_risk_factor_bucket_metadata',
        'csod_risk_score_band_metadata'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DOCUMENTATION
-- ============================================================================

COMMENT ON FUNCTION get_factor_score IS
'Generic helper function that maps source values to factor scores using metadata tables.
Supports lookup (categorical), bucket (numeric ranges), and linear scoring types.
Accepts metadata table names as parameters for maximum flexibility.';

COMMENT ON FUNCTION calculate_risk_likelihood IS
'Generic function that calculates likelihood score from source data row using metadata tables.
Input: model_code, JSONB row data, and metadata table names.
Output: overall likelihood score with detailed breakdown.
Works with any metadata tables following the standard risk scoring pattern.';

COMMENT ON FUNCTION calculate_risk_impact IS
'Generic function that calculates impact score from source data row using metadata tables.
Input: model_code, JSONB row data, and metadata table names.
Output: overall impact score with category breakdown.
Works with any metadata tables following the standard risk scoring pattern.';

COMMENT ON FUNCTION calculate_risk_score IS
'Generic function that calculates complete risk score (impact + likelihood + risk) from source data.
Uses metadata tables (specified as parameters) to determine factors, weights, and scoring rules.
Returns risk score, category, and detailed calculation metadata.
Fully configurable via metadata table names.';

COMMENT ON FUNCTION calculate_risk_batch IS
'Generic batch processing function for multiple rows from a table.
Accepts metadata table names as parameters.
Useful for bulk calculations on any risk scoring tables.';

COMMENT ON FUNCTION calculate_csod_likelihood IS
'CSOD-specific wrapper for calculate_risk_likelihood.
Maintains backward compatibility with existing CSOD code.
Uses csod_risk_* metadata tables by default.';

COMMENT ON FUNCTION calculate_csod_impact IS
'CSOD-specific wrapper for calculate_risk_impact.
Maintains backward compatibility with existing CSOD code.
Uses csod_risk_* metadata tables by default.';

COMMENT ON FUNCTION calculate_csod_risk IS
'CSOD-specific wrapper for calculate_risk_score.
Maintains backward compatibility with existing CSOD code.
Uses csod_risk_* metadata tables by default.';

COMMENT ON FUNCTION calculate_csod_risk_batch IS
'CSOD-specific wrapper for calculate_risk_batch.
Maintains backward compatibility with existing CSOD code.
Uses csod_risk_* metadata tables by default.';

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

/*
-- ============================================================================
-- GENERIC FUNCTIONS (with custom metadata tables)
-- ============================================================================

-- Example 1: Calculate risk using custom metadata tables
SELECT * FROM calculate_risk_score(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress",
        "positionLevel": "Senior Management",
        "activityType": "Compliance"
    }'::JSONB,
    'my_custom_model_metadata',      -- Custom model metadata table
    'my_custom_factor_metadata',      -- Custom factor metadata table
    'my_custom_lookup_metadata',      -- Custom lookup metadata table
    'my_custom_bucket_metadata',      -- Custom bucket metadata table
    'my_custom_band_metadata'         -- Custom band metadata table
);

-- Example 2: Calculate likelihood with custom metadata
SELECT * FROM calculate_risk_likelihood(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress"
    }'::JSONB,
    'my_custom_factor_metadata',
    'my_custom_lookup_metadata',
    'my_custom_bucket_metadata'
);

-- Example 3: Calculate impact with custom metadata
SELECT * FROM calculate_risk_impact(
    'compliance',
    '{
        "positionLevel": "Senior Management",
        "activityType": "Compliance"
    }'::JSONB,
    'my_custom_factor_metadata',
    'my_custom_lookup_metadata',
    'my_custom_bucket_metadata'
);

-- Example 4: Batch calculation with custom metadata
SELECT * FROM calculate_risk_batch(
    'compliance',
    'my_source_table',
    'id',
    100,
    'my_custom_model_metadata',
    'my_custom_factor_metadata',
    'my_custom_lookup_metadata',
    'my_custom_bucket_metadata',
    'my_custom_band_metadata'
);

-- ============================================================================
-- CSOD-SPECIFIC FUNCTIONS (backward compatibility - uses default CSOD tables)
-- ============================================================================

-- Example 5: Calculate compliance risk (CSOD wrapper)
SELECT * FROM calculate_csod_risk(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress",
        "lastLoginDays": 10,
        "userCompletionRate": 65.0,
        "positionLevel": "Senior Management",
        "activityType": "Compliance",
        "estimatedDuration": 90,
        "cost": 500
    }'::JSONB
);

-- Example 6: Calculate only likelihood (CSOD wrapper)
SELECT * FROM calculate_csod_likelihood(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress",
        "lastLoginDays": 10,
        "userCompletionRate": 65.0
    }'::JSONB
);

-- Example 7: Calculate only impact (CSOD wrapper)
SELECT * FROM calculate_csod_impact(
    'compliance',
    '{
        "positionLevel": "Senior Management",
        "activityType": "Compliance",
        "estimatedDuration": 90,
        "cost": 500
    }'::JSONB
);

-- Example 8: Batch calculation (CSOD wrapper)
SELECT * FROM calculate_csod_risk_batch(
    'compliance',
    'compliance_risk_silver',
    'id',
    100
);

-- Example 9: Calculate attrition risk (CSOD wrapper)
SELECT * FROM calculate_csod_risk(
    'attrition',
    '{
        "tenureRiskBand": "New Hire Critical (0-6mo)",
        "learningEngagementScore": 35.0,
        "complianceCompletionRate": 70.0,
        "lastLoginDays": 15,
        "overdueCourseCount": 2,
        "positionLevel": "Executive",
        "directReportCount": 10,
        "trainingInvestment": 5000
    }'::JSONB
);

-- ============================================================================
-- USING GENERIC FUNCTIONS WITH CSOD TABLES (explicit table names)
-- ============================================================================

-- Example 10: Same as CSOD wrapper but explicitly specifying table names
SELECT * FROM calculate_risk_score(
    'compliance',
    '{
        "daysUntilDue": -5,
        "completionPercentage": 45.0,
        "trainingStatus": "In Progress"
    }'::JSONB,
    'csod_risk_model_metadata',
    'csod_risk_factor_metadata',
    'csod_risk_factor_lookup_metadata',
    'csod_risk_factor_bucket_metadata',
    'csod_risk_score_band_metadata'
);
*/

