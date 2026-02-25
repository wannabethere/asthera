# Security Intelligence Database Scripts

This directory contains SQL scripts for managing security intelligence database tables.

## Files

- **`create_tables.sql`** - Creates all security intelligence tables with indexes, constraints, and triggers
- **`drop_tables.sql`** - Drops all security intelligence tables in the correct order
- **`create_phase1_only.sql`** - Creates only Phase 1 (Critical) tables
- **`drop_phase1_only.sql`** - Drops only Phase 1 (Critical) tables
- **`manage_tables.py`** - Python script to create/drop tables using database configuration
- **`generate_dummy_data.py`** - Generate realistic dummy data using LLM for testing
- **`README.md`** - This file

## Usage

### Create All Tables

```bash
# Using psql command line
psql -U postgres -d your_database -f create_tables.sql

# Or connect to database first
psql -U postgres -d your_database
\i create_tables.sql
```

### Drop All Tables

```bash
# Using psql command line
psql -U postgres -d your_database -f drop_tables.sql

# Or connect to database first
psql -U postgres -d your_database
\i drop_tables.sql
```

**⚠️ WARNING:** Dropping tables will permanently delete all data!

## Tables Created

### Phase 1 - Critical (MVP)
1. `cve_attack_mapping` - CVE → ATT&CK technique mappings
2. `attack_technique_control_mapping` - ATT&CK → Control mappings
3. `cpe_dictionary` - CPE software/product catalog
4. `cve_cpe_affected` - CVE → CPE relationships

### Phase 2 - Enhanced Intelligence
5. `metasploit_modules` - Metasploit Framework modules
6. `nuclei_templates` - Nuclei detection templates
7. `exploit_db_index` - Exploit-DB catalog

### Phase 3 - Compliance
8. `cis_benchmark_rules` - CIS Benchmark rules
9. `sigma_rules` - Sigma detection rules

### Utility Tables
10. `cve_cache` - API response caching

## Source-Specific Databases

If you're using source-specific database connections (configured via `SEC_INTEL_*_DB_*` environment variables), you'll need to run the scripts in the appropriate databases:

- **CVE/ATT&CK mappings**: Run in the database specified by `SEC_INTEL_CVE_ATTACK_DB_*` (or default)
  - Tables: `cve_attack_mapping`, `attack_technique_control_mapping`

- **CPE data**: Run in the database specified by `SEC_INTEL_CPE_DB_*` (or default)
  - Tables: `cpe_dictionary`, `cve_cpe_affected`

- **Exploit intelligence**: Run in the database specified by `SEC_INTEL_EXPLOIT_DB_*` (or default)
  - Tables: `metasploit_modules`, `nuclei_templates`, `exploit_db_index`

- **Compliance**: Run in the database specified by `SEC_INTEL_COMPLIANCE_DB_*` (or default)
  - Tables: `cis_benchmark_rules`, `sigma_rules`

- **Cache**: Uses default database
  - Tables: `cve_cache`

## Example: Setting Up Source-Specific Databases

```bash
# Create database for CVE/ATT&CK mappings
createdb -U postgres security_intel_cve_attack
psql -U postgres -d security_intel_cve_attack -f create_tables.sql

# Create database for CPE data
createdb -U postgres security_intel_cpe
psql -U postgres -d security_intel_cpe -f create_tables.sql

# Create database for exploit intelligence
createdb -U postgres security_intel_exploit
psql -U postgres -d security_intel_exploit -f create_tables.sql

# Create database for compliance
createdb -U postgres security_intel_compliance
psql -U postgres -d security_intel_compliance -f create_tables.sql
```

Then set environment variables:

```bash
SEC_INTEL_CVE_ATTACK_DB_NAME=security_intel_cve_attack
SEC_INTEL_CPE_DB_NAME=security_intel_cpe
SEC_INTEL_EXPLOIT_DB_NAME=security_intel_exploit
SEC_INTEL_COMPLIANCE_DB_NAME=security_intel_compliance
```

## Generating Dummy Data

After creating tables, you can generate realistic dummy data for testing using the `generate_dummy_data.py` script. This script uses LLM calls to generate realistic data.

### Prerequisites

1. **Database tables created**: Run `create_tables.sql` or use `manage_tables.py create` first
2. **OpenAI API Key**: Set `OPENAI_API_KEY` in your environment or `.env` file
3. **Database configured**: Ensure your database connection is configured in settings

### Usage

```bash
# Generate 100 rows for all tables (default)
python db/security_intel/generate_dummy_data.py

# Generate 50 rows for Phase 1 tables only
python db/security_intel/generate_dummy_data.py --phase 1 --rows 50

# Generate data for specific tables
python db/security_intel/generate_dummy_data.py --tables cve_attack_mapping cpe_dictionary

# Generate data in source-specific database
python db/security_intel/generate_dummy_data.py --source cve_attack

# Verbose output
python db/security_intel/generate_dummy_data.py --verbose
```

### Options

- `--rows, -r`: Number of rows to generate per table (default: 100)
- `--phase`: Phase number (1=Critical, 2=Enhanced, 3=Compliance). If not specified, all phases are included.
- `--source`: Security intelligence source (cve_attack, cpe, exploit, compliance). Uses default database if not specified.
- `--tables`: Specific tables to generate data for. If not specified, generates for all tables in the selected phase.
- `--verbose, -v`: Enable verbose logging

### Data Generation Order

The script generates data in dependency order:
1. CPE dictionary (needed for CVE-CPE mappings)
2. CVE-ATT&CK mappings (needed for CVE-CPE and cache)
3. CVE-CPE affected (depends on CPE and CVE)
4. ATT&CK-Control mappings
5. Exploit intelligence tables (Metasploit, Nuclei, Exploit-DB)
6. Compliance tables (CIS Benchmarks, Sigma rules)
7. Cache tables

### Example Output

```
INFO - Starting data generation: 100 rows per table, phase=None, source=None
INFO - ✓ LLM initialized
INFO - Generating 100 rows for cpe_dictionary...
INFO - ✓ Generated 100 rows for cpe_dictionary
INFO - ✓ Inserted 100 rows into cpe_dictionary
INFO - Generating 100 rows for cve_attack_mapping...
INFO - ✓ Generated 100 rows for cve_attack_mapping
INFO - ✓ Inserted 100 rows into cve_attack_mapping
...
INFO - ✓ All data generation complete!
```

## Verification

After running `create_tables.sql`, you can verify tables were created:

```sql
SELECT table_name 
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
  )
ORDER BY table_name;
```

## Notes

- Foreign key constraints to the `controls` table are only added if that table exists
- All tables include `created_at` and `updated_at` timestamps
- Triggers automatically update `updated_at` on row updates
- Indexes are created for common query patterns
- GIN indexes are used for array columns (CVE references, tags, etc.)

## Troubleshooting

### Foreign Key Errors
If you get foreign key constraint errors when dropping tables, the `drop_tables.sql` script uses `CASCADE` to handle dependencies automatically.

### Missing Controls Table
The `attack_technique_control_mapping` and `cis_benchmark_rules` tables reference a `controls` table that may not exist. The create script handles this gracefully by only adding the foreign key if the table exists.

### Permission Errors
Make sure your database user has `CREATE`, `DROP`, and `TRIGGER` permissions:

```sql
GRANT CREATE ON DATABASE your_database TO your_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
```
