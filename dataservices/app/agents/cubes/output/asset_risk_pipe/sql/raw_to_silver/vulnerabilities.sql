-- Transformation: raw_to_silver
-- Table: vulnerabilities
-- Generated: 20251120_111506

-- Step: Clean vulnerabilities
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_vulnerabilities_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_vulnerabilities
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate vulnerabilities
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: asset_id, cve_id


CREATE TABLE silver_vulnerabilities_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY asset_id, cve_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_vulnerabilities_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

