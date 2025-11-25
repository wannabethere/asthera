-- Transformation: raw_to_silver
-- Table: external_exposure
-- Generated: 20251124_084146

-- Step: Clean external_exposure
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_external_exposure_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_external_exposure
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate external_exposure
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: exposure_id, timestamp


CREATE TABLE silver_external_exposure_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY exposure_id, timestamp
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_external_exposure_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

