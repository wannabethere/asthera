-- Transformation: raw_to_silver
-- Table: software_inventory
-- Generated: 20251124_084146

-- Step: Clean software_inventory
-- Type: TransformationType.CLEANING
-- Description: Remove invalid records and handle nulls


CREATE TABLE silver_software_inventory_cleaned AS
SELECT 
    *,
    CASE 
        WHEN id IS NULL THEN FALSE 
        ELSE TRUE 
    END AS is_valid_record
FROM raw_software_inventory
WHERE id IS NOT NULL;


--------------------------------------------------------------------------------

-- Step: Deduplicate software_inventory
-- Type: TransformationType.DEDUPLICATION
-- Description: Deduplicate using LOD dimensions: asset_id, software_name, version


CREATE TABLE silver_software_inventory_deduped AS
SELECT *
FROM (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY asset_id, software_name, version
            ORDER BY updated_at DESC
        ) as row_num
    FROM silver_software_inventory_cleaned
) ranked
WHERE row_num = 1;


--------------------------------------------------------------------------------

