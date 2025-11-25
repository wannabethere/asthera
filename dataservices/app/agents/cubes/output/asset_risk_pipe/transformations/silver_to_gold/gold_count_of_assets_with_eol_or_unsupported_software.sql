-- Transformation: silver_to_gold_gold_count_of_assets_with_eol_or_unsupported_software
-- Source: silver.gold_count_of_assets_with_eol_or_unsupported_software
-- Target: gold.gold_gold_count_of_assets_with_eol_or_unsupported_software
-- Description: Transform gold_count_of_assets_with_eol_or_unsupported_software from silver to gold

-- Metric: count_of_assets_with_eol_or_unsupported_software: The count of assets that have EOL or unsupported software.
INSERT INTO gold_count_of_assets_with_eol_or_unsupported_software (business_unit, asset_count)
SELECT 
    a.business_unit,
    COUNT(DISTINCT a.asset_id) AS asset_count
FROM 
    assets_table a
JOIN 
    software_table s ON a.software_id = s.software_id
WHERE 
    COALESCE(s.eol, FALSE) = TRUE OR COALESCE(s.unsupported, FALSE) = TRUE
GROUP BY 
    a.business_unit;