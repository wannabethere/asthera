-- Transformation: raw_to_silver
-- Table: assets
-- Generated: 20251120_111506

-- Step: Clean assets
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_assets_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_assets
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate assets
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: asset_id


CREATE TABLE silver_assets_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY asset_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_assets_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

