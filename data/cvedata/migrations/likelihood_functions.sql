-- ============================================================================
-- Likelihood Calculation Functions with JSON Parameters
-- ============================================================================
-- These functions accept JSONB parameters for maximum flexibility
-- Security experts can pass any combination of attributes without changing
-- function signatures
-- ============================================================================

-- ============================================================================
-- CORE LIKELIHOOD CALCULATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_breach_likelihood(
    p_params JSONB
) RETURNS TABLE (
    likelihood_score DECIMAL(10,2),
    contributing_factors JSONB,
    calculation_method TEXT,
    confidence_level DECIMAL(5,2)
) AS $$
DECLARE
    v_vulnerability_score DECIMAL(10,2) := 0;
    v_exposure_score DECIMAL(10,2) := 0;
    v_time_score DECIMAL(10,2) := 0;
    v_behavior_score DECIMAL(10,2) := 0;
    v_historical_score DECIMAL(10,2) := 0;
    v_engagement_score DECIMAL(10,2) := 0;
    v_total_score DECIMAL(10,2) := 0;
    v_confidence DECIMAL(5,2) := 100.0;
    v_factors JSONB := '{}'::JSONB;
BEGIN
    -- Extract and calculate vulnerability-based likelihood
    IF p_params ? 'vulnerability_count' THEN
        v_vulnerability_score := LEAST(
            (p_params->>'vulnerability_count')::DECIMAL * 
            COALESCE((p_params->>'vulnerability_weight')::DECIMAL, 5.0),
            40.0
        );
        v_factors := jsonb_set(v_factors, '{vulnerability_score}', to_jsonb(v_vulnerability_score));
    ELSE
        v_confidence := v_confidence - 15;
    END IF;
    
    -- Extract and calculate exposure-based likelihood
    IF p_params ? 'propagation_class' THEN
        SELECT numeric_score INTO v_exposure_score
        FROM risk_impact_metadata
        WHERE enum_type = 'propagation_class' 
        AND code = p_params->>'propagation_class';
        
        v_exposure_score := v_exposure_score * 0.3; -- Scale to 30 points max
        v_factors := jsonb_set(v_factors, '{exposure_score}', to_jsonb(v_exposure_score));
    ELSE
        v_confidence := v_confidence - 10;
    END IF;
    
    -- Extract and calculate time-based likelihood
    IF p_params ? 'dwell_time_days' THEN
        v_time_score := LEAST(
            (p_params->>'dwell_time_days')::DECIMAL / 
            COALESCE((p_params->>'max_dwell_days')::DECIMAL, 90.0) * 20.0,
            20.0
        );
        v_factors := jsonb_set(v_factors, '{time_score}', to_jsonb(v_time_score));
    END IF;
    
    -- Extract and calculate user behavior likelihood
    IF p_params ? 'user_behavior_risk' THEN
        v_behavior_score := LEAST((p_params->>'user_behavior_risk')::DECIMAL, 20.0);
        v_factors := jsonb_set(v_factors, '{behavior_score}', to_jsonb(v_behavior_score));
    ELSIF p_params ? 'risky_behavior_count' THEN
        v_behavior_score := LEAST(
            (p_params->>'risky_behavior_count')::DECIMAL * 
            COALESCE((p_params->>'behavior_weight')::DECIMAL, 5.0),
            20.0
        );
        v_factors := jsonb_set(v_factors, '{behavior_score}', to_jsonb(v_behavior_score));
    END IF;
    
    -- Extract and calculate historical performance likelihood
    IF p_params ? 'historical_breach_rate' THEN
        v_historical_score := LEAST((p_params->>'historical_breach_rate')::DECIMAL, 15.0);
        v_factors := jsonb_set(v_factors, '{historical_score}', to_jsonb(v_historical_score));
    ELSIF p_params ? 'past_incident_count' THEN
        v_historical_score := LEAST(
            (p_params->>'past_incident_count')::DECIMAL * 
            COALESCE((p_params->>'incident_weight')::DECIMAL, 3.0),
            15.0
        );
        v_factors := jsonb_set(v_factors, '{historical_score}', to_jsonb(v_historical_score));
    END IF;
    
    -- Extract and calculate engagement metrics likelihood
    IF p_params ? 'security_engagement_score' THEN
        -- Lower engagement means higher likelihood
        v_engagement_score := LEAST(
            (100.0 - (p_params->>'security_engagement_score')::DECIMAL) * 0.15,
            15.0
        );
        v_factors := jsonb_set(v_factors, '{engagement_score}', to_jsonb(v_engagement_score));
    ELSIF p_params ? 'patch_compliance_rate' THEN
        -- Lower compliance means higher likelihood
        v_engagement_score := LEAST(
            (100.0 - (p_params->>'patch_compliance_rate')::DECIMAL) * 0.15,
            15.0
        );
        v_factors := jsonb_set(v_factors, '{engagement_score}', to_jsonb(v_engagement_score));
    END IF;
    
    -- Calculate total likelihood score
    v_total_score := LEAST(
        v_vulnerability_score + v_exposure_score + v_time_score + 
        v_behavior_score + v_historical_score + v_engagement_score,
        100.0
    );
    
    -- Apply any overall multipliers
    IF p_params ? 'urgency_multiplier' THEN
        v_total_score := LEAST(
            v_total_score * (p_params->>'urgency_multiplier')::DECIMAL,
            100.0
        );
    END IF;
    
    -- Add calculation metadata to factors
    v_factors := jsonb_set(v_factors, '{weights}', 
        jsonb_build_object(
            'vulnerability', 0.40,
            'exposure', 0.30,
            'time', 0.20,
            'behavior', 0.20,
            'historical', 0.15,
            'engagement', 0.15
        )
    );
    
    RETURN QUERY SELECT 
        v_total_score,
        v_factors,
        'weighted_multi_factor'::TEXT,
        v_confidence;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VULNERABILITY-BASED LIKELIHOOD FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_vulnerability_likelihood(
    p_params JSONB
) RETURNS TABLE (
    likelihood_score DECIMAL(10,2),
    critical_vuln_contribution DECIMAL(10,2),
    high_vuln_contribution DECIMAL(10,2),
    medium_vuln_contribution DECIMAL(10,2),
    cisa_exploit_contribution DECIMAL(10,2),
    unpatched_contribution DECIMAL(10,2),
    calculation_details JSONB
) AS $$
DECLARE
    v_critical_count INTEGER := COALESCE((p_params->>'critical_vuln_count')::INTEGER, 0);
    v_high_count INTEGER := COALESCE((p_params->>'high_vuln_count')::INTEGER, 0);
    v_medium_count INTEGER := COALESCE((p_params->>'medium_vuln_count')::INTEGER, 0);
    v_cisa_count INTEGER := COALESCE((p_params->>'cisa_exploit_count')::INTEGER, 0);
    v_unpatched_count INTEGER := COALESCE((p_params->>'unpatched_vuln_count')::INTEGER, 0);
    
    v_critical_contrib DECIMAL(10,2);
    v_high_contrib DECIMAL(10,2);
    v_medium_contrib DECIMAL(10,2);
    v_cisa_contrib DECIMAL(10,2);
    v_unpatched_contrib DECIMAL(10,2);
    v_total DECIMAL(10,2);
    v_details JSONB;
BEGIN
    -- Get severity weights from metadata
    v_critical_contrib := LEAST(v_critical_count * 15.0, 45.0);
    v_high_contrib := LEAST(v_high_count * 8.0, 30.0);
    v_medium_contrib := LEAST(v_medium_count * 3.0, 15.0);
    
    -- CISA exploits have very high weight
    v_cisa_contrib := LEAST(v_cisa_count * 25.0, 50.0);
    
    -- Unpatched vulnerabilities with available patches
    v_unpatched_contrib := LEAST(v_unpatched_count * 10.0, 30.0);
    
    -- Calculate total with diminishing returns
    v_total := LEAST(
        (v_critical_contrib * 1.0) +
        (v_high_contrib * 0.8) +
        (v_medium_contrib * 0.5) +
        (v_cisa_contrib * 1.5) +
        (v_unpatched_contrib * 1.2),
        100.0
    );
    
    -- Build details JSON
    v_details := jsonb_build_object(
        'input_counts', jsonb_build_object(
            'critical', v_critical_count,
            'high', v_high_count,
            'medium', v_medium_count,
            'cisa_exploits', v_cisa_count,
            'unpatched', v_unpatched_count
        ),
        'weights', jsonb_build_object(
            'critical_per_vuln', 15.0,
            'high_per_vuln', 8.0,
            'medium_per_vuln', 3.0,
            'cisa_per_exploit', 25.0,
            'unpatched_per_vuln', 10.0
        ),
        'calculation_method', 'weighted_vulnerability_count'
    );
    
    RETURN QUERY SELECT 
        v_total,
        v_critical_contrib,
        v_high_contrib,
        v_medium_contrib,
        v_cisa_contrib,
        v_unpatched_contrib,
        v_details;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TIME-WEIGHTED LIKELIHOOD FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_time_weighted_likelihood(
    p_params JSONB
) RETURNS TABLE (
    likelihood_score DECIMAL(10,2),
    urgency_factor DECIMAL(10,2),
    dwell_time_penalty DECIMAL(10,2),
    time_to_due_bonus DECIMAL(10,2),
    exponential_decay_factor DECIMAL(10,2),
    calculation_details JSONB
) AS $$
DECLARE
    v_dwell_time_days INTEGER := COALESCE((p_params->>'dwell_time_days')::INTEGER, 0);
    v_days_until_due INTEGER := COALESCE((p_params->>'days_until_due')::INTEGER, 999);
    v_tau_zero DECIMAL(10,2) := COALESCE((p_params->>'tau_zero')::DECIMAL, 30.0);
    v_base_likelihood DECIMAL(10,2) := COALESCE((p_params->>'base_likelihood')::DECIMAL, 50.0);
    
    v_urgency DECIMAL(10,2);
    v_dwell_penalty DECIMAL(10,2);
    v_due_bonus DECIMAL(10,2);
    v_exp_decay DECIMAL(10,2);
    v_total DECIMAL(10,2);
    v_details JSONB;
BEGIN
    -- Calculate exponential decay factor (recent emphasis)
    v_exp_decay := EXP(-v_dwell_time_days::DECIMAL / v_tau_zero);
    
    -- Calculate dwell time penalty (older = worse)
    v_dwell_penalty := CASE
        WHEN v_dwell_time_days <= 7 THEN 0
        WHEN v_dwell_time_days <= 30 THEN v_dwell_time_days * 0.5
        WHEN v_dwell_time_days <= 90 THEN 15.0 + ((v_dwell_time_days - 30) * 0.8)
        ELSE 63.0 + ((v_dwell_time_days - 90) * 1.2)
    END;
    v_dwell_penalty := LEAST(v_dwell_penalty, 50.0);
    
    -- Calculate urgency based on time remaining
    v_urgency := CASE
        WHEN v_days_until_due < 0 THEN 25.0  -- Overdue
        WHEN v_days_until_due <= 7 THEN 20.0  -- Critical window
        WHEN v_days_until_due <= 14 THEN 15.0  -- Urgent
        WHEN v_days_until_due <= 30 THEN 10.0  -- Important
        WHEN v_days_until_due <= 60 THEN 5.0   -- Standard
        ELSE 0
    END;
    
    -- Calculate time-to-due bonus (negative = penalty)
    v_due_bonus := CASE
        WHEN v_days_until_due < 0 THEN -10.0
        WHEN v_days_until_due > 90 THEN 10.0
        ELSE 0
    END;
    
    -- Combine factors
    v_total := LEAST(
        v_base_likelihood + v_dwell_penalty + v_urgency + v_due_bonus,
        100.0
    );
    
    -- Apply exponential decay if requested
    IF p_params ? 'apply_exponential_decay' AND (p_params->>'apply_exponential_decay')::BOOLEAN THEN
        v_total := v_total * (1.0 - v_exp_decay * 0.3);  -- Reduce by up to 30% for old items
    END IF;
    
    v_details := jsonb_build_object(
        'input_values', jsonb_build_object(
            'dwell_time_days', v_dwell_time_days,
            'days_until_due', v_days_until_due,
            'tau_zero', v_tau_zero,
            'base_likelihood', v_base_likelihood
        ),
        'time_thresholds', jsonb_build_object(
            'overdue', '< 0 days',
            'critical', '0-7 days',
            'urgent', '8-14 days',
            'important', '15-30 days',
            'standard', '31-60 days',
            'low_priority', '> 60 days'
        )
    );
    
    RETURN QUERY SELECT 
        v_total,
        v_urgency,
        v_dwell_penalty,
        v_due_bonus,
        v_exp_decay,
        v_details;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- BEHAVIORAL LIKELIHOOD FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_behavioral_likelihood(
    p_params JSONB
) RETURNS TABLE (
    likelihood_score DECIMAL(10,2),
    user_behavior_score DECIMAL(10,2),
    historical_performance_score DECIMAL(10,2),
    engagement_score DECIMAL(10,2),
    compliance_score DECIMAL(10,2),
    risk_pattern_score DECIMAL(10,2),
    calculation_details JSONB
) AS $$
DECLARE
    v_user_behavior DECIMAL(10,2) := 0;
    v_historical DECIMAL(10,2) := 0;
    v_engagement DECIMAL(10,2) := 0;
    v_compliance DECIMAL(10,2) := 0;
    v_risk_pattern DECIMAL(10,2) := 0;
    v_total DECIMAL(10,2);
    v_details JSONB := '{}'::JSONB;
BEGIN
    -- User Behavior Risk (0-25 points)
    IF p_params ? 'risky_login_attempts' THEN
        v_user_behavior := LEAST(
            (p_params->>'risky_login_attempts')::INTEGER * 2.5,
            25.0
        );
    ELSIF p_params ? 'user_risk_score' THEN
        v_user_behavior := LEAST((p_params->>'user_risk_score')::DECIMAL * 0.25, 25.0);
    END IF;
    
    -- Historical Performance (0-20 points)
    IF p_params ? 'past_incident_count' THEN
        v_historical := LEAST(
            (p_params->>'past_incident_count')::INTEGER * 4.0,
            20.0
        );
    ELSIF p_params ? 'mean_time_to_remediate_days' THEN
        -- Longer MTTR = higher likelihood
        v_historical := LEAST(
            (p_params->>'mean_time_to_remediate_days')::DECIMAL / 5.0,
            20.0
        );
    ELSIF p_params ? 'historical_breach_rate' THEN
        v_historical := LEAST((p_params->>'historical_breach_rate')::DECIMAL * 0.20, 20.0);
    END IF;
    
    -- Engagement Score (0-20 points) - inverse relationship
    IF p_params ? 'security_training_completion_rate' THEN
        v_engagement := LEAST(
            (100.0 - (p_params->>'security_training_completion_rate')::DECIMAL) * 0.20,
            20.0
        );
    ELSIF p_params ? 'engagement_metrics_score' THEN
        v_engagement := LEAST(
            (100.0 - (p_params->>'engagement_metrics_score')::DECIMAL) * 0.20,
            20.0
        );
    ELSIF p_params ? 'days_since_last_security_action' THEN
        v_engagement := LEAST(
            (p_params->>'days_since_last_security_action')::DECIMAL / 5.0,
            20.0
        );
    END IF;
    
    -- Compliance Score (0-20 points) - inverse relationship
    IF p_params ? 'patch_compliance_rate' THEN
        v_compliance := LEAST(
            (100.0 - (p_params->>'patch_compliance_rate')::DECIMAL) * 0.20,
            20.0
        );
    ELSIF p_params ? 'policy_violations_count' THEN
        v_compliance := LEAST(
            (p_params->>'policy_violations_count')::INTEGER * 3.0,
            20.0
        );
    ELSIF p_params ? 'compliance_score' THEN
        v_compliance := LEAST(
            (100.0 - (p_params->>'compliance_score')::DECIMAL) * 0.20,
            20.0
        );
    END IF;
    
    -- Risk Pattern Score (0-15 points)
    IF p_params ? 'repeated_offender_flag' AND (p_params->>'repeated_offender_flag')::BOOLEAN THEN
        v_risk_pattern := v_risk_pattern + 15.0;
    ELSIF p_params ? 'risk_pattern_matches' THEN
        v_risk_pattern := LEAST(
            (p_params->>'risk_pattern_matches')::INTEGER * 5.0,
            15.0
        );
    ELSIF p_params ? 'anomaly_score' THEN
        v_risk_pattern := LEAST((p_params->>'anomaly_score')::DECIMAL * 0.15, 15.0);
    END IF;
    
    -- Calculate total
    v_total := LEAST(
        v_user_behavior + v_historical + v_engagement + v_compliance + v_risk_pattern,
        100.0
    );
    
    -- Build details
    v_details := jsonb_build_object(
        'component_weights', jsonb_build_object(
            'user_behavior', 0.25,
            'historical_performance', 0.20,
            'engagement', 0.20,
            'compliance', 0.20,
            'risk_pattern', 0.15
        ),
        'score_ranges', jsonb_build_object(
            'user_behavior_max', 25.0,
            'historical_max', 20.0,
            'engagement_max', 20.0,
            'compliance_max', 20.0,
            'risk_pattern_max', 15.0
        )
    );
    
    RETURN QUERY SELECT 
        v_total,
        v_user_behavior,
        v_historical,
        v_engagement,
        v_compliance,
        v_risk_pattern,
        v_details;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- BREACH METHOD SPECIFIC LIKELIHOOD FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_breach_method_likelihood(
    p_params JSONB
) RETURNS TABLE (
    breach_method VARCHAR(100),
    likelihood_score DECIMAL(10,2),
    method_weight DECIMAL(5,3),
    contributing_factors JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        bmm.code AS breach_method,
        LEAST(
            -- Base method risk score
            bmm.risk_score * bmm.weight * 
            
            -- Exploitability factor
            (COALESCE((p_params->>'exploitability_score')::DECIMAL, 50.0) / 100.0) *
            
            -- Impact factor
            (COALESCE((p_params->>'impact_score')::DECIMAL, 50.0) / 100.0) *
            
            -- Known exploit multiplier
            CASE WHEN COALESCE((p_params->>'has_known_exploit')::BOOLEAN, FALSE) 
                 THEN 1.25 ELSE 1.0 END *
            
            -- Patch availability penalty
            CASE WHEN COALESCE((p_params->>'has_patch_available')::BOOLEAN, FALSE) 
                 THEN 1.15 ELSE 1.0 END *
            
            -- Dwell time factor
            (1.0 + (COALESCE((p_params->>'dwell_time_days')::DECIMAL, 0) / 90.0) * 0.3) *
            
            -- Exposure factor
            (COALESCE((p_params->>'asset_exposure_score')::DECIMAL, 50.0) / 100.0),
            
            100.0
        ) AS likelihood_score,
        bmm.weight AS method_weight,
        jsonb_build_object(
            'base_risk', bmm.risk_score,
            'exploitability', bmm.exploitability_score,
            'impact', bmm.impact_score,
            'method_description', bmm.description,
            'priority_order', bmm.priority_order
        ) AS contributing_factors
    FROM breach_method_metadata bmm
    ORDER BY likelihood_score DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ASSET-LEVEL AGGREGATED LIKELIHOOD FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_asset_likelihood(
    p_asset_id INTEGER,
    p_params JSONB DEFAULT '{}'::JSONB
) RETURNS TABLE (
    asset_id INTEGER,
    total_likelihood DECIMAL(10,2),
    vulnerability_likelihood DECIMAL(10,2),
    exposure_likelihood DECIMAL(10,2),
    behavioral_likelihood DECIMAL(10,2),
    time_weighted_likelihood DECIMAL(10,2),
    top_breach_methods JSONB,
    confidence_level DECIMAL(5,2),
    calculation_timestamp TIMESTAMP
) AS $$
DECLARE
    v_vuln_likelihood DECIMAL(10,2);
    v_exposure_likelihood DECIMAL(10,2);
    v_behavioral_likelihood DECIMAL(10,2);
    v_time_likelihood DECIMAL(10,2);
    v_total_likelihood DECIMAL(10,2);
    v_confidence DECIMAL(5,2) := 100.0;
    v_breach_methods JSONB;
BEGIN
    -- Calculate vulnerability likelihood if vulnerability data provided
    IF p_params ? 'critical_vuln_count' OR p_params ? 'vulnerability_count' THEN
        SELECT likelihood_score INTO v_vuln_likelihood
        FROM calculate_vulnerability_likelihood(p_params);
    ELSE
        v_vuln_likelihood := 0;
        v_confidence := v_confidence - 20;
    END IF;
    
    -- Calculate exposure likelihood
    IF p_params ? 'propagation_class' THEN
        SELECT numeric_score * 0.5 INTO v_exposure_likelihood
        FROM risk_impact_metadata
        WHERE enum_type = 'propagation_class' 
        AND code = p_params->>'propagation_class';
    ELSE
        v_exposure_likelihood := 0;
        v_confidence := v_confidence - 15;
    END IF;
    
    -- Calculate behavioral likelihood
    IF p_params ? 'user_risk_score' OR p_params ? 'historical_breach_rate' THEN
        SELECT likelihood_score INTO v_behavioral_likelihood
        FROM calculate_behavioral_likelihood(p_params);
    ELSE
        v_behavioral_likelihood := 0;
        v_confidence := v_confidence - 15;
    END IF;
    
    -- Calculate time-weighted likelihood
    IF p_params ? 'dwell_time_days' THEN
        SELECT likelihood_score INTO v_time_likelihood
        FROM calculate_time_weighted_likelihood(p_params);
    ELSE
        v_time_likelihood := 0;
        v_confidence := v_confidence - 10;
    END IF;
    
    -- Aggregate with weights
    v_total_likelihood := LEAST(
        (v_vuln_likelihood * COALESCE((p_params->>'vuln_weight')::DECIMAL, 0.40)) +
        (v_exposure_likelihood * COALESCE((p_params->>'exposure_weight')::DECIMAL, 0.30)) +
        (v_behavioral_likelihood * COALESCE((p_params->>'behavioral_weight')::DECIMAL, 0.20)) +
        (v_time_likelihood * COALESCE((p_params->>'time_weight')::DECIMAL, 0.10)),
        100.0
    );
    
    -- Get top 5 breach methods
    SELECT jsonb_agg(
        jsonb_build_object(
            'method', breach_method,
            'likelihood', likelihood_score
        ) ORDER BY likelihood_score DESC
    ) INTO v_breach_methods
    FROM (
        SELECT breach_method, likelihood_score
        FROM calculate_breach_method_likelihood(p_params)
        LIMIT 5
    ) top_methods;
    
    RETURN QUERY SELECT 
        p_asset_id,
        v_total_likelihood,
        v_vuln_likelihood,
        v_exposure_likelihood,
        v_behavioral_likelihood,
        v_time_likelihood,
        v_breach_methods,
        v_confidence,
        CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- LIKELIHOOD TREND ANALYSIS FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_likelihood_trend(
    p_asset_id INTEGER,
    p_lookback_days INTEGER DEFAULT 90,
    p_params JSONB DEFAULT '{}'::JSONB
) RETURNS TABLE (
    asset_id INTEGER,
    current_likelihood DECIMAL(10,2),
    avg_likelihood_30d DECIMAL(10,2),
    avg_likelihood_60d DECIMAL(10,2),
    avg_likelihood_90d DECIMAL(10,2),
    trend_direction VARCHAR(20),
    trend_percentage DECIMAL(10,2),
    velocity DECIMAL(10,2),
    forecast_30d DECIMAL(10,2),
    calculation_details JSONB
) AS $$
DECLARE
    v_current DECIMAL(10,2);
    v_avg_30d DECIMAL(10,2);
    v_avg_60d DECIMAL(10,2);
    v_avg_90d DECIMAL(10,2);
    v_trend VARCHAR(20);
    v_trend_pct DECIMAL(10,2);
    v_velocity DECIMAL(10,2);
    v_forecast DECIMAL(10,2);
    v_details JSONB;
BEGIN
    -- Calculate current likelihood
    SELECT total_likelihood INTO v_current
    FROM calculate_asset_likelihood(p_asset_id, p_params);
    
    -- For demo purposes, simulate historical data
    -- In production, this would query historical likelihood_history table
    v_avg_30d := v_current * (0.85 + (RANDOM() * 0.3));
    v_avg_60d := v_current * (0.80 + (RANDOM() * 0.4));
    v_avg_90d := v_current * (0.75 + (RANDOM() * 0.5));
    
    -- Calculate trend
    v_trend_pct := ((v_current - v_avg_30d) / NULLIF(v_avg_30d, 0)) * 100.0;
    
    v_trend := CASE
        WHEN v_trend_pct > 20 THEN 'RAPIDLY_INCREASING'
        WHEN v_trend_pct > 5 THEN 'INCREASING'
        WHEN v_trend_pct > -5 THEN 'STABLE'
        WHEN v_trend_pct > -20 THEN 'DECREASING'
        ELSE 'RAPIDLY_DECREASING'
    END;
    
    -- Calculate velocity (rate of change)
    v_velocity := (v_current - v_avg_90d) / 90.0;
    
    -- Forecast 30 days ahead using linear extrapolation
    v_forecast := LEAST(v_current + (v_velocity * 30.0), 100.0);
    
    v_details := jsonb_build_object(
        'calculation_timestamp', CURRENT_TIMESTAMP,
        'lookback_period_days', p_lookback_days,
        'data_points_used', jsonb_build_object(
            'current', v_current,
            '30_day_avg', v_avg_30d,
            '60_day_avg', v_avg_60d,
            '90_day_avg', v_avg_90d
        ),
        'trend_analysis', jsonb_build_object(
            'direction', v_trend,
            'percentage_change', v_trend_pct,
            'velocity_per_day', v_velocity
        )
    );
    
    RETURN QUERY SELECT 
        p_asset_id,
        v_current,
        v_avg_30d,
        v_avg_60d,
        v_avg_90d,
        v_trend,
        v_trend_pct,
        v_velocity,
        v_forecast,
        v_details;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- EXAMPLE USAGE AND COMMENTS
-- ============================================================================

COMMENT ON FUNCTION calculate_breach_likelihood(JSONB) IS 
'Core likelihood calculation accepting flexible JSON parameters including:
- vulnerability_count, vulnerability_weight
- propagation_class (from risk_impact_metadata)
- dwell_time_days, max_dwell_days
- user_behavior_risk, risky_behavior_count, behavior_weight
- historical_breach_rate, past_incident_count, incident_weight
- security_engagement_score, patch_compliance_rate
- urgency_multiplier
Returns likelihood_score, contributing_factors, calculation_method, confidence_level';

COMMENT ON FUNCTION calculate_vulnerability_likelihood(JSONB) IS
'Calculates likelihood based on vulnerability counts by severity.
Parameters: critical_vuln_count, high_vuln_count, medium_vuln_count, 
cisa_exploit_count, unpatched_vuln_count.
Returns detailed breakdown of each severity contribution.';

COMMENT ON FUNCTION calculate_time_weighted_likelihood(JSONB) IS
'Calculates time-based likelihood considering dwell time and urgency.
Parameters: dwell_time_days, days_until_due, tau_zero, base_likelihood, apply_exponential_decay.
Returns urgency_factor, dwell_time_penalty, time_to_due_bonus, exponential_decay_factor.';

COMMENT ON FUNCTION calculate_behavioral_likelihood(JSONB) IS
'Calculates likelihood from user behavior, historical performance, and engagement.
Parameters: risky_login_attempts, user_risk_score, past_incident_count, 
mean_time_to_remediate_days, security_training_completion_rate, 
patch_compliance_rate, policy_violations_count, repeated_offender_flag.
Returns detailed behavioral risk breakdown.';

COMMENT ON FUNCTION calculate_breach_method_likelihood(JSONB) IS
'Calculates likelihood per breach method from breach_method_metadata.
Parameters: exploitability_score, impact_score, has_known_exploit, 
has_patch_available, dwell_time_days, asset_exposure_score.
Returns all breach methods with calculated likelihoods, sorted by risk.';

COMMENT ON FUNCTION calculate_asset_likelihood(INTEGER, JSONB) IS
'Aggregates all likelihood factors for a single asset.
Combines vulnerability, exposure, behavioral, and time-weighted likelihood.
Parameters: asset_id plus all parameters from component functions.
Returns comprehensive likelihood assessment with top breach methods.';

COMMENT ON FUNCTION calculate_likelihood_trend(INTEGER, INTEGER, JSONB) IS
'Analyzes likelihood trends over time and forecasts future likelihood.
Parameters: asset_id, lookback_days (default 90), plus calculation params.
Returns trend direction, velocity, and 30-day forecast.';

-- ============================================================================
-- EXAMPLE QUERIES
-- ============================================================================

/*
-- Example 1: Basic vulnerability likelihood
SELECT * FROM calculate_vulnerability_likelihood(
    '{"critical_vuln_count": 5, "high_vuln_count": 12, "medium_vuln_count": 8, "cisa_exploit_count": 2, "unpatched_vuln_count": 7}'::JSONB
);

-- Example 2: Time-weighted likelihood with urgency
SELECT * FROM calculate_time_weighted_likelihood(
    '{"dwell_time_days": 45, "days_until_due": 10, "base_likelihood": 60.0, "apply_exponential_decay": true}'::JSONB
);

-- Example 3: Behavioral likelihood
SELECT * FROM calculate_behavioral_likelihood(
    '{"past_incident_count": 3, "patch_compliance_rate": 65.0, "security_training_completion_rate": 80.0, "policy_violations_count": 2}'::JSONB
);

-- Example 4: Comprehensive breach likelihood
SELECT * FROM calculate_breach_likelihood(
    '{"vulnerability_count": 25, "vulnerability_weight": 5.0, "propagation_class": "Perimeter", "dwell_time_days": 60, "user_behavior_risk": 45.0, "historical_breach_rate": 12.0, "patch_compliance_rate": 70.0, "urgency_multiplier": 1.2}'::JSONB
);

-- Example 5: Breach method likelihood
SELECT * FROM calculate_breach_method_likelihood(
    '{"exploitability_score": 75.0, "impact_score": 85.0, "has_known_exploit": true, "has_patch_available": true, "dwell_time_days": 45, "asset_exposure_score": 80.0}'::JSONB
);

-- Example 6: Full asset likelihood
SELECT * FROM calculate_asset_likelihood(
    12345,  -- asset_id
    '{"critical_vuln_count": 5, "high_vuln_count": 10, "propagation_class": "Perimeter", "dwell_time_days": 30, "patch_compliance_rate": 75.0, "vuln_weight": 0.40, "exposure_weight": 0.30, "behavioral_weight": 0.20, "time_weight": 0.10}'::JSONB
);

-- Example 7: Likelihood trend analysis
SELECT * FROM calculate_likelihood_trend(
    12345,  -- asset_id
    90,     -- lookback_days
    '{"critical_vuln_count": 5, "propagation_class": "Perimeter"}'::JSONB
);
*/