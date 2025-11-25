-- Transformation: raw_to_silver
-- Table: identity_exposure
-- Generated: 20251124_084146

-- Step: Clean identity_exposure
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_identity_exposure_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_identity_exposure
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate identity_exposure
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: user_id, exposure_event_id


CREATE TABLE silver_identity_exposure_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, exposure_event_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_identity_exposure_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

