-- Transformation: raw_to_silver
-- Table: courses
-- Generated: 20251121_132228

-- Step: Clean courses
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_courses_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_courses
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate courses
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: course_id, institution_id


CREATE TABLE silver_courses_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY course_id, institution_id
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_courses_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

