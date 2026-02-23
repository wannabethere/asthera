# Security Intelligence Tools - Setup Guide

This guide provides a complete checklist for setting up all security intelligence tools, including required API keys and database ingestion requirements.

---

## **Quick Start Checklist**

- [ ] Set up environment variables for API keys
- [ ] Create Postgres database tables (Phase 1 - Critical)
- [ ] Set up data ingestion pipelines
- [ ] Test each tool category

---

## **1. Database Configuration**

### **Default Database (Required)**

The default database connection is used for all security intelligence tools unless source-specific configuration is provided.

```bash
# Default PostgreSQL connection (required)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=framework_kb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_SSL_MODE=require
```

### **Source-Specific Database Connections (Optional)**

You can configure separate database connections for different security intelligence sources. If not specified, tools will use the default database connection.

```bash
# ============================================================================
# CVE/ATT&CK Mappings Database (Optional)
# ============================================================================
# If not set, uses default database
SEC_INTEL_CVE_ATTACK_DB_HOST=localhost
SEC_INTEL_CVE_ATTACK_DB_PORT=5432
SEC_INTEL_CVE_ATTACK_DB_NAME=security_intel_cve_attack
SEC_INTEL_CVE_ATTACK_DB_USER=postgres
SEC_INTEL_CVE_ATTACK_DB_PASSWORD=your_password

# ============================================================================
# CPE Dictionary Database (Optional)
# ============================================================================
# If not set, uses default database
SEC_INTEL_CPE_DB_HOST=localhost
SEC_INTEL_CPE_DB_PORT=5432
SEC_INTEL_CPE_DB_NAME=security_intel_cpe
SEC_INTEL_CPE_DB_USER=postgres
SEC_INTEL_CPE_DB_PASSWORD=your_password

# ============================================================================
# Exploit Intelligence Database (Optional)
# ============================================================================
# If not set, uses default database
# Used for: Exploit-DB, Metasploit, Nuclei templates
SEC_INTEL_EXPLOIT_DB_HOST=localhost
SEC_INTEL_EXPLOIT_DB_PORT=5432
SEC_INTEL_EXPLOIT_DB_NAME=security_intel_exploit
SEC_INTEL_EXPLOIT_DB_USER=postgres
SEC_INTEL_EXPLOIT_DB_PASSWORD=your_password

# ============================================================================
# Compliance Database (Optional)
# ============================================================================
# If not set, uses default database
# Used for: CIS Benchmarks, Sigma Rules
SEC_INTEL_COMPLIANCE_DB_HOST=localhost
SEC_INTEL_COMPLIANCE_DB_PORT=5432
SEC_INTEL_COMPLIANCE_DB_NAME=security_intel_compliance
SEC_INTEL_COMPLIANCE_DB_USER=postgres
SEC_INTEL_COMPLIANCE_DB_PASSWORD=your_password
```

**Note:** If you don't specify source-specific database connections, all tools will use the default database. This is the recommended setup for most deployments.

---

## **2. API Keys Required**

### **Environment Variables (.env file)**

Add these to your `.env` file in the project root:

```bash
# ============================================================================
# NVD (National Vulnerability Database)
# ============================================================================
# Optional but recommended - increases rate limit from 5 to 50 req/30sec
# Get free API key at: https://nvd.nist.gov/developers/request-an-api-key
NVD_API_KEY=your_nvd_api_key_here

# ============================================================================
# Tavily Search
# ============================================================================
# Required for tavily_search tool
# Get API key at: https://tavily.com/
TAVILY_API_KEY=your_tavily_api_key_here

# ============================================================================
# GitHub Advisory Database
# ============================================================================
# Optional but recommended - increases rate limit from 60 to 5000 req/hr
# Create personal access token at: https://github.com/settings/tokens
# Required scopes: public_repo (read-only)
GITHUB_TOKEN=ghp_your_github_token_here

# ============================================================================
# AlienVault OTX (Open Threat Exchange)
# ============================================================================
# Required for otx_pulse_search tool
# Get free API key at: https://otx.alienvault.com/api
OTX_API_KEY=your_otx_api_key_here

# ============================================================================
# VirusTotal
# ============================================================================
# Required for virustotal_lookup tool
# Get free API key at: https://www.virustotal.com/gui/join-us
# Free tier: 500 requests/day, 15 requests/minute
VIRUSTOTAL_API_KEY=your_virustotal_api_key_here

# ============================================================================
# Optional: Additional Services (Not Yet Implemented)
# ============================================================================
# SHODAN_API_KEY=your_shodan_api_key_here  # For future shodan_search tool
# GREYNOISE_API_KEY=your_greynoise_api_key_here  # For future greynoise tool
```

### **API Key Summary Table**

| Tool | API Key Required | Free Tier | Where to Get |
|------|-----------------|-----------|--------------|
| **NVD CVE API** | Optional | 5 req/30sec (no key)<br>50 req/30sec (with key) | https://nvd.nist.gov/developers/request-an-api-key |
| **Tavily Search** | ✅ Required | Free tier available | https://tavily.com/ |
| **GitHub Advisory** | Optional | 60 req/hr (no key)<br>5000 req/hr (with key) | https://github.com/settings/tokens |
| **AlienVault OTX** | ✅ Required | 10 req/min | https://otx.alienvault.com/api |
| **VirusTotal** | ✅ Required | 500 req/day, 15 req/min | https://www.virustotal.com/gui/join-us |
| **EPSS** | ❌ Not required | Unlimited | Public API |
| **CISA KEV** | ❌ Not required | Unlimited | Public JSON feed |

---

## **3. Database Tables Required**

### **Phase 1 - Critical for MVP** (Implement First)

These tables are required for core functionality:

#### **1. CVE → ATT&CK Technique Mapping**

```sql
CREATE TABLE cve_attack_mapping (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,           -- e.g. CVE-2024-1234
    attack_technique_id VARCHAR(20),        -- e.g. T1003.001
    attack_tactic VARCHAR(50),              -- e.g. Credential Access
    mapping_source VARCHAR(50),             -- mitre_official | ctid | manual | ai_inferred
    confidence_score FLOAT,                 -- 0.0 - 1.0
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX idx_cve_attack_cve ON cve_attack_mapping(cve_id);
CREATE INDEX idx_cve_attack_tech ON cve_attack_mapping(attack_technique_id);
```

**Data Sources:**
- MITRE ATT&CK Software/Malware entries
- CTID project: `center-for-threat-informed-defense/attack_to_cve`
- Manual curation
- LLM-assisted mapping

#### **2. ATT&CK Technique → Control Mapping**

```sql
CREATE TABLE attack_technique_control_mapping (
    id SERIAL PRIMARY KEY,
    attack_technique_id VARCHAR(20) NOT NULL,
    control_id VARCHAR(128) REFERENCES controls(id),  -- FK to your existing controls table
    mitigation_effectiveness VARCHAR(20),              -- full | partial | low
    mapping_source VARCHAR(50),                        -- manual | ai_generated | mitre_derived
    confidence_score FLOAT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_attack_control_tech ON attack_technique_control_mapping(attack_technique_id);
CREATE INDEX idx_attack_control_ctrl ON attack_technique_control_mapping(control_id);
```

**Data Sources:**
- MITRE ATT&CK mitigation mappings (from STIX data)
- Manual mapping to your framework controls
- LLM-assisted mapping

#### **3. CPE Dictionary**

```sql
CREATE TABLE cpe_dictionary (
    cpe_uri VARCHAR(255) PRIMARY KEY,       -- cpe:2.3:a:vendor:product:version:...
    vendor VARCHAR(255),
    product VARCHAR(255),
    version VARCHAR(100),
    cpe_title TEXT,                          -- Human-readable name
    deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cpe_vendor_product ON cpe_dictionary(vendor, product);
CREATE INDEX idx_cpe_product_version ON cpe_dictionary(product, version);

-- Junction table: CVE → affected CPEs
CREATE TABLE cve_cpe_affected (
    id SERIAL PRIMARY KEY,
    cve_id VARCHAR(20) NOT NULL,
    cpe_uri VARCHAR(255) REFERENCES cpe_dictionary(cpe_uri),
    version_start VARCHAR(100),             -- Vulnerable from version X
    version_end VARCHAR(100),               -- Vulnerable to version Y
    version_start_including BOOLEAN,
    version_end_including BOOLEAN
);

CREATE INDEX idx_cve_cpe_cve ON cve_cpe_affected(cve_id);
CREATE INDEX idx_cve_cpe_uri ON cve_cpe_affected(cpe_uri);
```

**Data Sources:**
- NVD CPE Dictionary (500MB+ JSON feed)
- NVD CVE API (includes CPE data in CVE records)

### **Phase 2 - Enhanced Intelligence**

#### **4. Metasploit Module Index**

```sql
CREATE TABLE metasploit_modules (
    id SERIAL PRIMARY KEY,
    module_path VARCHAR(500) UNIQUE,        -- exploit/windows/smb/ms17_010_eternalblue
    module_type VARCHAR(50),                 -- exploit | auxiliary | post | payload
    name VARCHAR(255),
    description TEXT,
    author VARCHAR(255)[],
    platform VARCHAR(100)[],                 -- [windows, linux]
    arch VARCHAR(50)[],                      -- [x86, x64]
    cve_references VARCHAR(20)[],            -- Array of CVE IDs
    rank VARCHAR(20),                         -- excellent | great | good | normal | average | low | manual
    disclosure_date DATE,
    check_available BOOLEAN,                 -- Can test without exploiting
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_msf_cve ON metasploit_modules USING GIN(cve_references);
CREATE INDEX idx_msf_platform ON metasploit_modules USING GIN(platform);
```

**Data Source:**
- GitHub repo: `rapid7/metasploit-framework`
- Parse module Ruby files to extract metadata

#### **5. Nuclei Template Index**

```sql
CREATE TABLE nuclei_templates (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(255) UNIQUE,        -- CVE-2024-1234.yaml
    name VARCHAR(255),
    severity VARCHAR(20),                    -- info | low | medium | high | critical
    description TEXT,
    tags VARCHAR(100)[],                     -- [cve, rce, log4j]
    cve_references VARCHAR(20)[],
    cwe_references VARCHAR(20)[],
    template_path VARCHAR(500),
    metadata JSONB,                          -- Full YAML metadata block
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_nuclei_cve ON nuclei_templates USING GIN(cve_references);
CREATE INDEX idx_nuclei_tags ON nuclei_templates USING GIN(tags);
```

**Data Source:**
- GitHub repo: `projectdiscovery/nuclei-templates`
- Parse YAML template files

#### **6. Exploit-DB Index**

```sql
CREATE TABLE exploit_db_index (
    id SERIAL PRIMARY KEY,
    exploit_id INTEGER UNIQUE,               -- EDB-ID
    title VARCHAR(500),
    description TEXT,
    author VARCHAR(255),
    platform VARCHAR(100),                   -- windows, linux, hardware, etc.
    exploit_type VARCHAR(50),                -- remote, local, webapps, etc.
    cve_id VARCHAR(20),                      -- CVE reference if available
    date_published DATE,
    verified BOOLEAN,
    codes VARCHAR(100)[],                    -- Shellcode, exploits, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_edb_cve ON exploit_db_index(cve_id);
CREATE INDEX idx_edb_platform ON exploit_db_index(platform);
```

**Data Source:**
- GitLab repo: `exploit-database/exploitdb`
- Parse `files_exploits.csv` file

### **Phase 3 - Compliance & Enrichment**

#### **7. CIS Benchmark Rules**

```sql
CREATE TABLE cis_benchmark_rules (
    id SERIAL PRIMARY KEY,
    benchmark_id VARCHAR(100),              -- CIS_Ubuntu_Linux_22.04
    rule_number VARCHAR(20),                 -- 1.1.1.1
    title VARCHAR(500),
    description TEXT,
    rationale TEXT,
    remediation TEXT,
    audit_procedure TEXT,
    level INT,                               -- 1 | 2
    profile VARCHAR(50),                     -- Server | Workstation
    control_id VARCHAR(128) REFERENCES controls(id),  -- Your framework KB link
    attack_techniques VARCHAR(20)[],         -- ATT&CK techniques this mitigates
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cis_benchmark ON cis_benchmark_rules(benchmark_id);
CREATE INDEX idx_cis_control ON cis_benchmark_rules(control_id);
```

**Data Source:**
- CIS Benchmark PDFs (manual extraction)
- LLM-assisted mapping to controls and ATT&CK techniques

#### **8. Sigma Detection Rules** (Future)

```sql
CREATE TABLE sigma_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) UNIQUE,            -- UUID from rule
    title VARCHAR(500),
    description TEXT,
    status VARCHAR(20),                      -- stable | test | experimental
    level VARCHAR(20),                       -- low | medium | high | critical
    logsource JSONB,                         -- {product: windows, service: sysmon}
    detection JSONB,                         -- Full detection logic
    attack_technique_refs VARCHAR(20)[],     -- [T1003.001, T1078]
    tags VARCHAR(100)[],
    author VARCHAR(255),
    falsepositives TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sigma_attack ON sigma_rules USING GIN(attack_technique_refs);
CREATE INDEX idx_sigma_tags ON sigma_rules USING GIN(tags);
```

**Data Source:**
- GitHub repo: `SigmaHQ/sigma`
- Parse YAML rule files

---

## **4. Data Ingestion Pipelines**

### **Daily Batch Jobs**

Create scheduled tasks (cron jobs or Celery tasks) to run:

```python
# 1. Fetch recent CVEs from NVD (last 7 days)
# Frequency: Daily
# API: NVD CVE API v2.0
# Endpoint: https://services.nvd.nist.gov/rest/json/cves/2.0
# Params: pubStartDate, pubEndDate

# 2. Fetch CISA KEV updates
# Frequency: Daily
# Source: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
# Format: JSON feed (static file)

# 3. Fetch EPSS scores (bulk)
# Frequency: Daily
# API: FIRST EPSS API
# Endpoint: https://api.first.org/data/v1/epss
# Note: Can download full CSV dataset

# 4. Sync Exploit-DB
# Frequency: Daily
# Source: GitLab repo exploit-database/exploitdb
# File: files_exploits.csv
# Method: Git clone or download CSV

# 5. Sync Nuclei templates
# Frequency: Daily
# Source: GitHub repo projectdiscovery/nuclei-templates
# Method: Git clone, parse YAML files
```

### **Weekly Batch Jobs**

```python
# 1. Sync MITRE ATT&CK STIX data
# Frequency: Weekly
# Source: https://github.com/mitre-attack/attack-stix-data
# Format: STIX 2.1 JSON
# Use: Extract technique details, mitigations, relationships

# 2. Sync Metasploit modules
# Frequency: Weekly
# Source: GitHub repo rapid7/metasploit-framework
# Method: Git clone, parse Ruby module files
# Extract: Module metadata, CVE references, platform info

# 3. Sync Sigma rules
# Frequency: Weekly
# Source: GitHub repo SigmaHQ/sigma
# Method: Git clone, parse YAML rule files
```

### **On-Demand Jobs** (Triggered by User Query)

```python
# 1. Enrich CVE with ATT&CK mappings
# Trigger: When new CVE is queried or discovered
# Method: LLM-assisted analysis of CVE description
# Input: CVE description, CWE, references
# Output: ATT&CK technique suggestions with confidence scores

# 2. Map ATT&CK techniques to controls
# Trigger: When technique → control mapping is needed
# Method: LLM-assisted mapping using technique mitigations
# Input: ATT&CK technique ID, framework controls
# Output: Control mappings with effectiveness ratings
```

### **One-Time Initial Load**

```python
# 1. Load NVD CPE Dictionary
# Source: NVD CPE Dictionary JSON feed (500MB+)
# Method: Download and parse JSON, bulk insert to Postgres
# Frequency: One-time initial load, then incremental updates

# 2. Load historical CVE data (optional)
# Source: NVD CVE API (all CVEs)
# Method: Paginated API calls or download CVE JSON feeds
# Frequency: One-time for historical data, then daily updates
```

---

## **5. Tool Implementation Status**

### **✅ Fully Implemented Tools**

| Tool Name | Category | API Key | Database Table | Status |
|-----------|----------|---------|----------------|--------|
| `cve_intelligence` | API | NVD_API_KEY (optional) | None | ✅ Ready |
| `epss_lookup` | API | None | None | ✅ Ready |
| `cisa_kev_check` | API | None | None | ✅ Ready |
| `github_advisory_search` | API | GITHUB_TOKEN (optional) | None | ✅ Ready |
| `cpe_lookup` | API | NVD_API_KEY (optional) | `cpe_dictionary` (optional) | ✅ Ready |
| `tavily_search` | Search | TAVILY_API_KEY | None | ✅ Ready |
| `otx_pulse_search` | Threat Intel | OTX_API_KEY | None | ✅ Ready |
| `virustotal_lookup` | Threat Intel | VIRUSTOTAL_API_KEY | None | ✅ Ready |
| `framework_control_search` | Compliance | None | `controls`, `frameworks` | ✅ Ready |
| `attack_technique_lookup` | ATT&CK | None | None (uses cache) | ✅ Ready |

### **⚠️ Partially Implemented (Requires Database Tables)**

| Tool Name | Category | Database Tables Required | Status |
|-----------|----------|-------------------------|--------|
| `cve_to_attack_mapper` | ATT&CK | `cve_attack_mapping` | ⚠️ Needs table |
| `attack_to_control_mapper` | ATT&CK | `attack_technique_control_mapping` | ⚠️ Needs table |
| `cpe_resolver` | Infrastructure | `cpe_dictionary`, `cve_cpe_affected` | ⚠️ Needs tables |
| `exploit_db_search` | Exploit | `exploit_db_index` | ⚠️ Needs table |
| `metasploit_module_search` | Exploit | `metasploit_modules` | ⚠️ Needs table |
| `nuclei_template_search` | Exploit | `nuclei_templates` | ⚠️ Needs table |
| `cis_benchmark_lookup` | Compliance | `cis_benchmark_rules` | ⚠️ Needs table |

### **🚧 Stub Implementation (Future Work)**

| Tool Name | Category | Notes |
|-----------|----------|-------|
| `gap_analysis` | Compliance | Requires comprehensive ATT&CK mappings |
| `attack_path_builder` | Analysis | Requires ATT&CK relationship graph |
| `risk_calculator` | Analysis | Requires integration with multiple data sources |
| `remediation_prioritizer` | Analysis | Requires risk calculation + control mappings |

---

## **6. Setup Instructions**

### **Step 1: Database Configuration**

1. Set up default database connection (required):
   ```bash
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=framework_kb
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   ```

2. (Optional) Configure source-specific databases if you want separate databases:
   - Add `SEC_INTEL_*_DB_*` environment variables for each source
   - If not set, tools will use the default database

### **Step 2: Environment Variables (API Keys)**

1. Copy `.env.example` to `.env` (if exists) or create new `.env` file
2. Add all required API keys (see Section 2)
3. Verify keys are loaded: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('NVD_API_KEY:', bool(os.getenv('NVD_API_KEY')))"`

### **Step 3: Database Setup**

1. **Create Phase 1 tables** (Critical):
   ```bash
   # Run SQL migrations or Alembic migrations
   # See SQL schemas in Section 3
   # 
   # Note: If using source-specific databases, create tables in the appropriate database:
   # - cve_attack_mapping, attack_technique_control_mapping → cve_attack database
   # - cpe_dictionary, cve_cpe_affected → cpe database
   # - metasploit_modules, nuclei_templates, exploit_db_index → exploit database
   # - cis_benchmark_rules, sigma_rules → compliance database
   ```

2. **Verify tables exist**:
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name IN (
       'cve_attack_mapping',
       'attack_technique_control_mapping',
       'cpe_dictionary',
       'cve_cpe_affected'
   );
   ```

### **Step 4: Data Ingestion**

1. **Set up ingestion scripts** (create in `app/ingestion/security_intel/`):
   - `nvd_cve_ingestion.py` - Daily CVE updates
   - `cpe_dictionary_ingestion.py` - Initial CPE load
   - `exploit_db_ingestion.py` - Daily Exploit-DB sync
   - `metasploit_ingestion.py` - Weekly Metasploit sync
   - `nuclei_ingestion.py` - Daily Nuclei sync
   - `attack_stix_ingestion.py` - Weekly ATT&CK sync

2. **Run initial data load**:
   ```bash
   # Load CPE dictionary (one-time)
   python -m app.ingestion.security_intel.cpe_dictionary_ingestion

   # Load historical CVEs (optional, can take hours)
   python -m app.ingestion.security_intel.nvd_cve_ingestion --full
   ```

### **Step 5: Test Tools**

```python
from app.agents.tools import get_all_tools, TOOL_REGISTRY

# Test API-based tools (should work immediately)
cve_tool = TOOL_REGISTRY["cve_intelligence"]()
result = cve_tool.invoke({"cve_id": "CVE-2021-44228"})  # Log4j
print(result)

# Test database tools (will return empty if tables not populated)
attack_tool = TOOL_REGISTRY["cve_to_attack_mapper"]()
result = attack_tool.invoke({"cve_id": "CVE-2021-44228"})
print(result)
```

---

## **7. Priority Order for Implementation**

### **Week 1: Core Functionality**
1. ✅ Set up API keys (NVD, Tavily, OTX, VirusTotal)
2. ✅ Create Phase 1 database tables
3. ✅ Test API-based tools
4. ✅ Set up daily CVE ingestion from NVD

### **Week 2: CPE & Mapping**
1. ✅ Load CPE dictionary (initial bulk load)
2. ✅ Set up CVE → CPE ingestion
3. ✅ Start building CVE → ATT&CK mappings (manual + LLM-assisted)
4. ✅ Map ATT&CK techniques to existing controls

### **Week 3: Exploit Intelligence**
1. ✅ Set up Exploit-DB ingestion
2. ✅ Set up Metasploit module parsing
3. ✅ Set up Nuclei template indexing
4. ✅ Test exploit search tools

### **Week 4: Compliance & Enrichment**
1. ✅ Set up CIS benchmark ingestion
2. ✅ Enhance ATT&CK mappings
3. ✅ Set up weekly ATT&CK STIX sync
4. ✅ Test compliance tools

---

## **8. Data Sources & Links**

### **Free Public APIs**
- **NVD CVE API**: https://services.nvd.nist.gov/rest/json/cves/2.0
- **NVD CPE API**: https://services.nvd.nist.gov/rest/json/cpes/2.0
- **EPSS API**: https://api.first.org/data/v1/epss
- **CISA KEV**: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

### **GitHub Repositories**
- **MITRE ATT&CK STIX**: https://github.com/mitre-attack/attack-stix-data
- **Exploit-DB**: https://gitlab.com/exploit-database/exploitdb
- **Metasploit Framework**: https://github.com/rapid7/metasploit-framework
- **Nuclei Templates**: https://github.com/projectdiscovery/nuclei-templates
- **Sigma Rules**: https://github.com/SigmaHQ/sigma
- **CTID Attack-to-CVE**: https://github.com/center-for-threat-informed-defense/attack_to_cve

### **API Key Registration**
- **NVD API Key**: https://nvd.nist.gov/developers/request-an-api-key
- **Tavily**: https://tavily.com/
- **AlienVault OTX**: https://otx.alienvault.com/api
- **VirusTotal**: https://www.virustotal.com/gui/join-us
- **GitHub Token**: https://github.com/settings/tokens

---

## **9. Troubleshooting**

### **Database Connection Issues**
- Verify database credentials in `.env`
- Check if source-specific database configs are correct
- Tools automatically fall back to default database if source-specific config is missing
- Use `get_security_intel_database_pool(source)` in `dependencies.py` to test connections

### **Tool Returns Empty Results**
- Check if database tables exist and are populated
- Verify API keys are set correctly
- Check tool logs for errors

### **Rate Limiting Issues**
- Add API keys to increase rate limits
- Implement caching for frequently accessed data
- Use Postgres cache tables for API responses

### **Database Connection Issues**
- Verify database credentials in `.env`
- Check SQLAlchemy session configuration
- Ensure tables are created in the correct schema

---

## **10. Using Source-Specific Databases**

### **In Code**

Tools automatically use the appropriate database connection based on their source:

```python
from app.storage.sqlalchemy_session import get_security_intel_session

# CVE/ATT&CK mappings use "cve_attack" source
with get_security_intel_session("cve_attack") as session:
    # Query cve_attack_mapping, attack_technique_control_mapping tables
    pass

# CPE tools use "cpe" source
with get_security_intel_session("cpe") as session:
    # Query cpe_dictionary, cve_cpe_affected tables
    pass

# Exploit tools use "exploit" source
with get_security_intel_session("exploit") as session:
    # Query metasploit_modules, nuclei_templates, exploit_db_index tables
    pass

# Compliance tools use "compliance" source
with get_security_intel_session("compliance") as session:
    # Query cis_benchmark_rules, sigma_rules tables
    pass
```

### **For Async Operations**

```python
from app.core.dependencies import get_security_intel_database_pool

# Get async pool for a specific source
pool = await get_security_intel_database_pool("cve_attack")
async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM cve_attack_mapping LIMIT 10")
```

---

## **Next Steps**

1. Start with Phase 1 database tables
2. Set up API keys for critical tools
3. Begin daily CVE ingestion
4. Gradually add Phase 2 and Phase 3 tables
5. Build out ingestion pipelines incrementally

For questions or issues, refer to the tool implementation code in `app/agents/tools/`.
