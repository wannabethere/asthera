-- Transformation: raw_to_silver
-- Table: misconfigurations
-- Generated: 20251124_084146

-- Step: Clean misconfigurations
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_misconfigurations_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_misconfigurations
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate misconfigurations
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: asset_id, config_id


CREATE TABLE silver_misconfigurations_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY asset_id, config_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_misconfigurations_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

