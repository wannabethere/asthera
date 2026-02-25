-- ============================================================================
-- Security Intelligence Database Tables - DROP PHASE 1 ONLY
-- ============================================================================
-- This script drops only the Phase 1 (critical) tables.
-- 
-- WARNING: This will permanently delete all data in these tables!
-- ============================================================================

BEGIN;

-- Drop triggers
DROP TRIGGER IF EXISTS update_cve_attack_mapping_updated_at ON cve_attack_mapping;
DROP TRIGGER IF EXISTS update_attack_technique_control_mapping_updated_at ON attack_technique_control_mapping;
DROP TRIGGER IF EXISTS update_cpe_dictionary_updated_at ON cpe_dictionary;

-- Drop tables in dependency order
DROP TABLE IF EXISTS cve_cpe_affected CASCADE;
DROP TABLE IF EXISTS cpe_dictionary CASCADE;
DROP TABLE IF EXISTS attack_technique_control_mapping CASCADE;
DROP TABLE IF EXISTS cve_attack_mapping CASCADE;
DROP TABLE IF EXISTS cve_cache CASCADE;

-- Note: We don't drop the trigger function as it may be used by other tables

COMMIT;

SELECT 'Phase 1 tables dropped successfully!' as status;
