-- ============================================================================
-- Security Intelligence Database Tables - DROP SCRIPT
-- ============================================================================
-- This script drops all security intelligence tables in the correct order
-- to handle foreign key dependencies.
-- 
-- Usage:
--   psql -U postgres -d your_database -f drop_tables.sql
--   Or connect to your database and run: \i drop_tables.sql
--
-- WARNING: This will permanently delete all data in these tables!
-- ============================================================================

BEGIN;

-- ============================================================================
-- DROP TRIGGERS FIRST
-- ============================================================================

DROP TRIGGER IF EXISTS update_cve_attack_mapping_updated_at ON cve_attack_mapping;
DROP TRIGGER IF EXISTS update_attack_technique_control_mapping_updated_at ON attack_technique_control_mapping;
DROP TRIGGER IF EXISTS update_cpe_dictionary_updated_at ON cpe_dictionary;
DROP TRIGGER IF EXISTS update_metasploit_modules_updated_at ON metasploit_modules;
DROP TRIGGER IF EXISTS update_nuclei_templates_updated_at ON nuclei_templates;
DROP TRIGGER IF EXISTS update_exploit_db_index_updated_at ON exploit_db_index;
DROP TRIGGER IF EXISTS update_cis_benchmark_rules_updated_at ON cis_benchmark_rules;
DROP TRIGGER IF EXISTS update_sigma_rules_updated_at ON sigma_rules;

-- Drop the trigger function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- ============================================================================
-- DROP TABLES IN REVERSE DEPENDENCY ORDER
-- ============================================================================

-- Phase 3 tables (no dependencies on other security intel tables)
DROP TABLE IF EXISTS sigma_rules CASCADE;
DROP TABLE IF EXISTS cis_benchmark_rules CASCADE;

-- Phase 2 tables (no dependencies on other security intel tables)
DROP TABLE IF EXISTS exploit_db_index CASCADE;
DROP TABLE IF EXISTS nuclei_templates CASCADE;
DROP TABLE IF EXISTS metasploit_modules CASCADE;

-- Phase 1 tables - drop dependent tables first
DROP TABLE IF EXISTS cve_cpe_affected CASCADE;  -- Depends on cpe_dictionary
DROP TABLE IF EXISTS cpe_dictionary CASCADE;

DROP TABLE IF EXISTS attack_technique_control_mapping CASCADE;  -- May reference controls table

DROP TABLE IF EXISTS cve_attack_mapping CASCADE;

-- Utility tables
DROP TABLE IF EXISTS cve_cache CASCADE;

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Check if any tables still exist
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'All security intelligence tables dropped successfully!'
        ELSE 'Warning: Some tables still exist: ' || string_agg(table_name, ', ')
    END as status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'cve_attack_mapping',
      'attack_technique_control_mapping',
      'cpe_dictionary',
      'cve_cpe_affected',
      'metasploit_modules',
      'nuclei_templates',
      'exploit_db_index',
      'cis_benchmark_rules',
      'sigma_rules',
      'cve_cache'
  );
