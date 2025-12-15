-- ============================================================================
-- Metadata Transformation Examples
-- ============================================================================
-- These examples demonstrate how to use enum metadata tables to add
-- calculated columns and transformations to asset tables.
-- 
-- Key Rules:
-- 1. Never use the 'id' column from metadata tables as a join key
-- 2. Use 'code', 'enum_type', 'classification_type' for joins
-- 3. Retrieve numeric scores dynamically from metadata tables
-- ============================================================================

-- ============================================================================
-- Example 1: Calculate Impact Class Based on Roles
-- ============================================================================
-- Classify assets as Mission Critical, Critical, or Other based on their roles
-- and retrieve the corresponding numeric score from risk_impact_metadata

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.roles,
    CASE 
        WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
        WHEN rm.criticality_score >= 70 THEN 'Critical'
        ELSE 'Other'
    END AS impact_class,
    rim_impact.numeric_score AS impact_class_score
FROM asset a
LEFT JOIN roles_metadata rm ON a.roles = rm.code
LEFT JOIN risk_impact_metadata rim_impact 
    ON rim_impact.enum_type = 'impact_class' 
    AND rim_impact.code = CASE 
        WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
        WHEN rm.criticality_score >= 70 THEN 'Critical'
        ELSE 'Other'
    END;

-- ============================================================================
-- Example 2: Calculate Propagation Class Based on Network Interfaces
-- ============================================================================
-- Determine if an asset is Perimeter or Core based on network interface
-- access type (IP ranges, subnet classification, site location)

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    ai.ip,
    ai.subnet,
    ai.site,
    CASE 
        WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
        WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
        WHEN ai.subnet LIKE '%.0/24' AND ai.site IS NULL THEN 'Core'
        ELSE 'Perimeter'
    END AS propagation_class,
    rim_prop.numeric_score AS propagation_class_score
FROM asset a
INNER JOIN asset_interfaces ai ON a.nuid = ai.nuid AND a.dev_id = ai.dev_id
LEFT JOIN risk_impact_metadata rim_prop 
    ON rim_prop.enum_type = 'propagation_class' 
    AND rim_prop.code = CASE 
        WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
        WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
        WHEN ai.subnet LIKE '%.0/24' AND ai.site IS NULL THEN 'Core'
        ELSE 'Perimeter'
    END
WHERE ai.is_stale = false;

-- ============================================================================
-- Example 3: Calculate Device Type Criticality Score
-- ============================================================================
-- Get criticality score for assets based on their device type classification

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.device_type,
    a.device_subtype,
    a.platform,
    acm_canonical.criticality_score AS canonical_type_criticality,
    acm_platform.criticality_score AS platform_criticality,
    COALESCE(acm_canonical.criticality_score, acm_platform.criticality_score, 50.0) AS device_criticality_score
FROM asset a
LEFT JOIN asset_classification_metadata acm_canonical 
    ON acm_canonical.classification_type = 'canonical_type' 
    AND acm_canonical.code = a.device_type
LEFT JOIN asset_classification_metadata acm_platform 
    ON acm_platform.classification_type = 'platform' 
    AND acm_platform.code = a.platform;

-- ============================================================================
-- Example 4: Calculate Combined Impact Score Using Multiple Metadata Tables
-- ============================================================================
-- Combine impact class score, propagation class score, and device criticality
-- to create a comprehensive impact score

WITH impact_scores AS (
    SELECT 
        a.nuid,
        a.dev_id,
        a.host_name,
        a.roles,
        -- Impact class from roles
        CASE 
            WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
            WHEN rm.criticality_score >= 70 THEN 'Critical'
            ELSE 'Other'
        END AS impact_class,
        rim_impact.numeric_score AS impact_class_score,
        -- Device criticality
        COALESCE(acm.criticality_score, 50.0) AS device_criticality_score
    FROM asset a
    LEFT JOIN roles_metadata rm ON a.roles = rm.code
    LEFT JOIN risk_impact_metadata rim_impact 
        ON rim_impact.enum_type = 'impact_class' 
        AND rim_impact.code = CASE 
            WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
            WHEN rm.criticality_score >= 70 THEN 'Critical'
            ELSE 'Other'
        END
    LEFT JOIN asset_classification_metadata acm 
        ON acm.classification_type = 'canonical_type' 
        AND acm.code = a.device_type
),
propagation_scores AS (
    SELECT 
        a.nuid,
        a.dev_id,
        CASE 
            WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
            WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
            ELSE 'Perimeter'
        END AS propagation_class,
        rim_prop.numeric_score AS propagation_class_score
    FROM asset a
    INNER JOIN asset_interfaces ai ON a.nuid = ai.nuid AND a.dev_id = ai.dev_id
    LEFT JOIN risk_impact_metadata rim_prop 
        ON rim_prop.enum_type = 'propagation_class' 
        AND rim_prop.code = CASE 
            WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
            WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
            ELSE 'Perimeter'
        END
    WHERE ai.is_stale = false
)
SELECT 
    isc.nuid,
    isc.dev_id,
    isc.host_name,
    isc.impact_class,
    isc.impact_class_score,
    ps.propagation_class,
    ps.propagation_class_score,
    isc.device_criticality_score,
    -- Combined impact: 50% impact class, 30% propagation, 20% device criticality
    (isc.impact_class_score * 0.5 + ps.propagation_class_score * 0.3 + isc.device_criticality_score * 0.2) AS combined_impact_score
FROM impact_scores isc
LEFT JOIN propagation_scores ps ON isc.nuid = ps.nuid AND isc.dev_id = ps.dev_id;

-- ============================================================================
-- Example 5: Calculate Breach Method Likelihood Scores
-- ============================================================================
-- Calculate likelihood scores for different breach methods based on asset
-- characteristics (vulnerabilities, credentials, encryption, etc.)

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    bmm.code AS breach_method,
    bmm.description AS breach_method_description,
    bmm.risk_score AS breach_method_base_score,
    -- Apply asset-specific multipliers
    CASE 
        WHEN bmm.code = 'unpatched_vulnerability' AND a.unpatched_vulnerability_likelihood > 0 
            THEN bmm.risk_score * (a.unpatched_vulnerability_likelihood / 100.0)
        WHEN bmm.code = 'weak_credentials' AND a.weak_credentials_likelihood > 0 
            THEN bmm.risk_score * (a.weak_credentials_likelihood / 100.0)
        WHEN bmm.code = 'compromised_credentials' AND a.compromised_credentials_likelihood > 0 
            THEN bmm.risk_score * (a.compromised_credentials_likelihood / 100.0)
        WHEN bmm.code = 'weak_encryption' AND a.weak_encryption_likelihood > 0 
            THEN bmm.risk_score * (a.weak_encryption_likelihood / 100.0)
        ELSE bmm.risk_score * 0.5  -- Default multiplier if no specific likelihood
    END AS adjusted_breach_likelihood_score
FROM asset a
CROSS JOIN breach_method_metadata bmm
WHERE bmm.code IN ('unpatched_vulnerability', 'weak_credentials', 'compromised_credentials', 'weak_encryption', 'zero_day');

-- ============================================================================
-- Example 6: Calculate Security Strength Score for Open Ports
-- ============================================================================
-- Assess security strength of services running on open ports

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    aop.port_num,
    aop.service,
    ssm.code AS security_strength_code,
    ssm.numeric_score AS security_strength_score,
    CASE 
        WHEN ssm.numeric_score >= 80 THEN 'STRONG'
        WHEN ssm.numeric_score >= 50 THEN 'MODERATE'
        ELSE 'WEAK'
    END AS security_strength_level
FROM asset a
INNER JOIN asset_open_ports aop ON a.nuid = aop.nuid AND a.dev_id = aop.dev_id
LEFT JOIN security_strength_metadata ssm 
    ON ssm.enum_type = 'cipher' 
    AND ssm.code = CASE 
        WHEN aop.service LIKE '%SSL%' OR aop.service LIKE '%TLS%' THEN 'STRONG'
        WHEN aop.service LIKE '%HTTPS%' THEN 'STRONG'
        WHEN aop.service LIKE '%HTTP%' THEN 'WEAK'
        ELSE 'MODERATE'
    END
WHERE aop.is_stale = false;

-- ============================================================================
-- Example 7: Calculate Risk Level Based on Raw Risk Score
-- ============================================================================
-- Classify assets into risk levels (CRITICAL, HIGH, MEDIUM) based on raw_risk
-- and retrieve corresponding scores from metadata

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.raw_risk,
    CASE 
        WHEN a.raw_risk >= 75 THEN 'CRITICAL'
        WHEN a.raw_risk >= 50 THEN 'HIGH'
        ELSE 'MEDIUM'
    END AS risk_level,
    rim_risk.numeric_score AS risk_level_score,
    rim_risk.priority_order AS risk_priority_order
FROM asset a
LEFT JOIN risk_impact_metadata rim_risk 
    ON rim_risk.enum_type = 'risk_level' 
    AND rim_risk.code = CASE 
        WHEN a.raw_risk >= 75 THEN 'CRITICAL'
        WHEN a.raw_risk >= 50 THEN 'HIGH'
        ELSE 'MEDIUM'
    END;

-- ============================================================================
-- Example 8: Calculate OS Type Risk Weight
-- ============================================================================
-- Get risk weight and criticality for assets based on OS type

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.os_name,
    acm_os.risk_weight AS os_risk_weight,
    acm_os.criticality_score AS os_criticality_score,
    a.raw_risk,
    -- Adjust raw risk by OS risk weight
    a.raw_risk * COALESCE(acm_os.risk_weight, 1.0) AS os_adjusted_risk
FROM asset a
LEFT JOIN asset_classification_metadata acm_os 
    ON acm_os.classification_type = 'os_type' 
    AND acm_os.code = a.os_name;

-- ============================================================================
-- Example 9: Calculate Vulnerability Risk Score
-- ============================================================================
-- Assess vulnerability risk based on vulnerability type and state

-- Note: This assumes there's a vulnerability table that references vulnerability types
-- For demonstration, we'll show how to join with vulnerability_metadata

SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    vm.enum_type AS vuln_enum_type,
    vm.code AS vuln_code,
    vm.description AS vuln_description,
    vm.risk_score AS vuln_risk_score,
    vm.remediation_priority AS vuln_remediation_priority,
    -- Calculate weighted risk
    vm.risk_score * vm.weight AS weighted_vuln_risk_score
FROM asset a
-- This would typically join through a vulnerability instance table
-- For example: INNER JOIN vuln_instances vi ON a.nuid = vi.asset_nuid
CROSS JOIN vulnerability_metadata vm
WHERE vm.enum_type IN ('type', 'subtype')
ORDER BY vm.risk_score DESC
LIMIT 100;  -- Limit for demonstration

-- ============================================================================
-- Example 10: Multi-Table Transformation - Complete Asset Risk Profile
-- ============================================================================
-- Comprehensive transformation combining multiple metadata sources

WITH role_impact AS (
    SELECT 
        a.nuid,
        a.dev_id,
        CASE 
            WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
            WHEN rm.criticality_score >= 70 THEN 'Critical'
            ELSE 'Other'
        END AS impact_class,
        rim_impact.numeric_score AS impact_class_score
    FROM asset a
    LEFT JOIN roles_metadata rm ON a.roles = rm.code
    LEFT JOIN risk_impact_metadata rim_impact 
        ON rim_impact.enum_type = 'impact_class' 
        AND rim_impact.code = CASE 
            WHEN rm.criticality_score >= 90 THEN 'Mission Critical'
            WHEN rm.criticality_score >= 70 THEN 'Critical'
            ELSE 'Other'
        END
),
propagation_class AS (
    SELECT DISTINCT
        a.nuid,
        a.dev_id,
        CASE 
            WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
            WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
            ELSE 'Perimeter'
        END AS propagation_class,
        rim_prop.numeric_score AS propagation_class_score
    FROM asset a
    INNER JOIN asset_interfaces ai ON a.nuid = ai.nuid AND a.dev_id = ai.dev_id
    LEFT JOIN risk_impact_metadata rim_prop 
        ON rim_prop.enum_type = 'propagation_class' 
        AND rim_prop.code = CASE 
            WHEN ai.site IN ('DMZ', 'Perimeter', 'External') THEN 'Perimeter'
            WHEN ai.ip LIKE '10.%' OR ai.ip LIKE '172.%' OR ai.ip LIKE '192.168.%' THEN 'Core'
            ELSE 'Perimeter'
        END
    WHERE ai.is_stale = false
),
risk_level AS (
    SELECT 
        a.nuid,
        a.dev_id,
        CASE 
            WHEN a.raw_risk >= 75 THEN 'CRITICAL'
            WHEN a.raw_risk >= 50 THEN 'HIGH'
            ELSE 'MEDIUM'
        END AS risk_level,
        rim_risk.numeric_score AS risk_level_score
    FROM asset a
    LEFT JOIN risk_impact_metadata rim_risk 
        ON rim_risk.enum_type = 'risk_level' 
        AND rim_risk.code = CASE 
            WHEN a.raw_risk >= 75 THEN 'CRITICAL'
            WHEN a.raw_risk >= 50 THEN 'HIGH'
            ELSE 'MEDIUM'
        END
)
SELECT 
    a.nuid,
    a.dev_id,
    a.host_name,
    a.roles,
    a.device_type,
    a.os_name,
    a.raw_risk,
    a.raw_impact,
    a.raw_likelihood,
    -- Impact classifications
    ri.impact_class,
    ri.impact_class_score,
    pc.propagation_class,
    pc.propagation_class_score,
    rl.risk_level,
    rl.risk_level_score,
    -- Device criticality
    COALESCE(acm.criticality_score, 50.0) AS device_criticality_score,
    COALESCE(acm_os.risk_weight, 1.0) AS os_risk_weight,
    -- Calculated scores
    (ri.impact_class_score * 0.4 + pc.propagation_class_score * 0.3 + COALESCE(acm.criticality_score, 50.0) * 0.3) AS calculated_impact_score,
    (a.raw_likelihood * COALESCE(acm_os.risk_weight, 1.0)) AS os_adjusted_likelihood,
    (a.raw_risk * COALESCE(acm_os.risk_weight, 1.0)) AS os_adjusted_risk
FROM asset a
LEFT JOIN role_impact ri ON a.nuid = ri.nuid AND a.dev_id = ri.dev_id
LEFT JOIN propagation_class pc ON a.nuid = pc.nuid AND a.dev_id = pc.dev_id
LEFT JOIN risk_level rl ON a.nuid = rl.nuid AND a.dev_id = rl.dev_id
LEFT JOIN asset_classification_metadata acm 
    ON acm.classification_type = 'canonical_type' 
    AND acm.code = a.device_type
LEFT JOIN asset_classification_metadata acm_os 
    ON acm_os.classification_type = 'os_type' 
    AND acm_os.code = a.os_name;

-- ============================================================================
-- Notes on Join Patterns:
-- ============================================================================
-- 1. Always join on 'code' columns, not 'id'
-- 2. For enum_type-based tables, use both enum_type AND code in join conditions
-- 3. Use LEFT JOIN when metadata might not exist for all assets
-- 4. Use CASE statements to map asset attributes to metadata codes
-- 5. Retrieve numeric scores dynamically from metadata tables
-- 6. Combine multiple metadata sources using CTEs or subqueries
-- 7. Apply weights and multipliers from metadata tables
-- ============================================================================

