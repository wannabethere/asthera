-- Transformation: raw_to_silver
-- Table: enrollments
-- Generated: 20251121_132228

-- Step: Clean enrollments
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_enrollments_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_enrollments
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate enrollments
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: user_id, course_id


CREATE TABLE silver_enrollments_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, course_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_enrollments_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

