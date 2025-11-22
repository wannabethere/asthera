-- Transformation: raw_to_silver
-- Table: users
-- Generated: 20251121_132228

-- Step: Clean users
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_users_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_users
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate users
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: user_id


CREATE TABLE silver_users_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_users_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

