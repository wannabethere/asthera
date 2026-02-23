Absolutely. Let me map out what's available via public APIs vs what needs custom Postgres storage, then design the tool architecture.

---

## **Available Public APIs (Free/Open)**

### **Tier 1 - Fully Free, No Auth Required**

| API | Endpoint | Rate Limit | What You Get |
|---|---|---|---|
| **NVD CVE API** | `https://services.nvd.nist.gov/rest/json/cves/2.0` | 5 req/30sec (no key)<br>50 req/30sec (with key) | CVE details, CVSS v2/v3, CWE, CPE, references, CVSS vector strings |
| **CISA KEV** | `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | Unlimited (static JSON) | Actively exploited CVEs, required action dates, vendor/product |
| **CVE.org API** | `https://cveawg.mitre.org/api/cve/{id}` | Generous | Raw CVE records, CNA assignments, timeline |
| **MITRE ATT&CK STIX** | `https://github.com/mitre-attack/attack-stix-data` | Unlimited (GitHub repo) | Full ATT&CK matrix as STIX 2.1 JSON (tactics, techniques, mitigations, relationships) |
| **FIRST EPSS** | `https://api.first.org/data/v1/epss` | Unlimited | Exploit prediction scores (0-1) for CVEs, percentile rankings |
| **Exploit-DB** | `https://gitlab.com/exploit-database/exploitdb` | Unlimited (Git repo) | CSV export of all exploits, shellcode, Google dorks (files.csv) |

### **Tier 2 - Free with API Key**

| API | Endpoint | Rate Limit | What You Get |
|---|---|---|---|
| **Shodan** | `https://api.shodan.io` | 1 query credit/month (free)<br>Paid: $49/mo unlimited | Internet-exposed services, banners, vulnerabilities, open ports |
| **VirusTotal** | `https://www.virustotal.com/api/v3` | 500 req/day (free)<br>15 req/min | File/URL/domain/IP reputation, malware analysis, detection ratios |
| **AlienVault OTX** | `https://otx.alienvault.com/api/v1` | 10 req/min (free) | Threat pulses, IoCs, malware samples, adversary intel |
| **GreyNoise** | `https://api.greynoise.io` | 1000 req/month (free) | Benign scanner vs malicious actor IP classification |
| **URLhaus (Abuse.ch)** | `https://urlhaus-api.abuse.ch/v1` | Unlimited | Malware distribution URLs, payloads, Mirai/emotet/etc campaigns |
| **GitHub Advisory DB** | `https://api.github.com/advisories` | 5000 req/hr | OSS package vulnerabilities (npm, PyPI, Maven, NuGet, RubyGems) |

### **Tier 3 - Commercial (But Have Free Tiers)**

| API | Free Tier | What You Get |
|---|---|---|
| **Censys** | 250 queries/mo | Internet scan data similar to Shodan |
| **Vulners** | 50 req/day | Vulnerability aggregation, exploit links, news |
| **SecurityTrails** | 50 req/mo | DNS history, WHOIS, subdomain discovery |
| **Recorded Future** | No free tier | Threat intelligence, CVE risk scores, dark web monitoring |

---

## **What Requires Custom Postgres Storage**

### **1. CVE → ATT&CK Technique Mapping**

**Problem:** MITRE ATT&CK doesn't officially publish CVE-to-technique mappings. Community projects exist but are incomplete.

**Solution:** Build your own mapping table via:
- **MITRE ATT&CK Software/Malware entries** - Some techniques reference CVEs in their descriptions
- **CTI Repos** - `center-for-threat-informed-defense/attack_to_cve` (CTID project)
- **Manual curation** - Security team adds mappings as new CVEs emerge

**Postgres Schema:**
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

### **2. ATT&CK Technique → Your Control Mappings**

**Problem:** You need to map ATT&CK techniques to your CIS/NIST/HIPAA controls for gap analysis.

**Solution:** Hybrid approach:
- MITRE publishes technique → mitigation mappings (in ATT&CK STIX data)
- You map MITRE mitigations → your framework controls manually or via LLM

**Postgres Schema:**
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

### **3. CPE (Common Platform Enumeration) Dictionary**

**Problem:** NVD references products via CPE URIs (`cpe:2.3:a:apache:log4j:2.14.1`). You need a searchable index to match "Apache Log4j 2.14.1" → applicable CVEs.

**Solution:** Ingest the official NVD CPE Dictionary (500MB+ JSON feed).

**Postgres Schema:**
```sql
CREATE TABLE cpe_dictionary (
    cpe_uri VARCHAR(255) PRIMARY KEY,       -- cpe:2.3:a:vendor:product:version:...
    vendor VARCHAR(255),
    product VARCHAR(255),
    version VARCHAR(100),
    cpe_title TEXT,                          -- Human-readable name
    deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
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

### **4. Metasploit Module Index**

**Problem:** Metasploit doesn't have a public API. Exploit availability is in their GitHub repo.

**Solution:** Parse Metasploit Framework repo (`rapid7/metasploit-framework`) and index modules.

**Postgres Schema:**
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

### **5. Nuclei Template Index**

**Problem:** Nuclei templates (CVE scanners) are in a GitHub repo, not queryable via API.

**Solution:** Index `projectdiscovery/nuclei-templates` YAML files.

**Postgres Schema:**
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

### **6. Sigma Detection Rules**

**Problem:** Sigma rules are in GitHub repos (SigmaHQ), not API-accessible.

**Solution:** Parse and index Sigma YAML rules.

**Postgres Schema:**
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

### **7. CIS Benchmark Mappings**

**Problem:** CIS Benchmarks (PDF documents) need to be mapped to your controls table for automated assessment.

**Solution:** Manual extraction + LLM-assisted mapping.

**Postgres Schema:**
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

---

## **Tool Implementation Architecture**

### **Tool Wrapper Pattern**

Each tool is a Python class implementing a standard interface:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    data: Any
    source: str                    # "nvd_api" | "postgres_cache" | "exploit_db"
    timestamp: str
    cache_hit: bool = False
    error_message: Optional[str] = None

class SecurityTool(ABC):
    """Base class for all security intelligence tools."""
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Run the tool with given parameters."""
        pass
    
    @abstractmethod
    def cache_key(self, **kwargs) -> str:
        """Generate cache key for result deduplication."""
        pass
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass
```

### **Hybrid API + Postgres Tools**

```python
class CVEIntelligenceTool(SecurityTool):
    """
    Fetch comprehensive CVE intelligence from multiple sources.
    
    Flow:
      1. Check Postgres cache (cve_cache table) - if fresh, return
      2. Query NVD API for CVE details
      3. Query EPSS API for exploit prediction
      4. Check CISA KEV for active exploitation
      5. Lookup Postgres for ATT&CK mappings
      6. Lookup Postgres for Metasploit modules
      7. Lookup Postgres for Nuclei templates
      8. Cache result in Postgres
    """
    
    def execute(self, cve_id: str, force_refresh: bool = False) -> ToolResult:
        # Check cache
        if not force_refresh:
            cached = self._check_cache(cve_id)
            if cached and self._is_fresh(cached, max_age_hours=24):
                return ToolResult(
                    success=True,
                    data=cached,
                    source="postgres_cache",
                    cache_hit=True,
                    timestamp=cached['cached_at']
                )
        
        # Gather from APIs
        nvd_data = self._fetch_nvd(cve_id)
        epss_data = self._fetch_epss(cve_id)
        kev_data = self._check_cisa_kev(cve_id)
        
        # Gather from Postgres
        attack_mappings = self._get_attack_mappings(cve_id)
        msf_modules = self._get_metasploit_modules(cve_id)
        nuclei_templates = self._get_nuclei_templates(cve_id)
        
        # Synthesize
        result = {
            'cve_id': cve_id,
            'nvd': nvd_data,
            'epss_score': epss_data.get('epss'),
            'actively_exploited': kev_data is not None,
            'attack_techniques': attack_mappings,
            'exploit_available': {
                'metasploit': len(msf_modules) > 0,
                'nuclei': len(nuclei_templates) > 0,
                'modules': msf_modules,
                'templates': nuclei_templates
            }
        }
        
        # Cache
        self._update_cache(cve_id, result)
        
        return ToolResult(
            success=True,
            data=result,
            source="aggregated",
            timestamp=datetime.utcnow().isoformat(),
            cache_hit=False
        )
```

### **Pure API Tools**

```python
class EPSSLookupTool(SecurityTool):
    """Query FIRST EPSS for exploit prediction scoring."""
    
    def execute(self, cve_id: str) -> ToolResult:
        response = requests.get(
            f"https://api.first.org/data/v1/epss",
            params={'cve': cve_id}
        )
        data = response.json()
        
        if not data['data']:
            return ToolResult(
                success=False,
                data=None,
                source="epss_api",
                timestamp=datetime.utcnow().isoformat(),
                error_message=f"No EPSS score for {cve_id}"
            )
        
        return ToolResult(
            success=True,
            data=data['data'][0],  # {cve, epss, percentile, date}
            source="epss_api",
            timestamp=data['data'][0]['date']
        )
```

### **Pure Postgres Tools**

```python
class ATTACKtoControlMapperTool(SecurityTool):
    """Map ATT&CK technique to framework controls."""
    
    def execute(self, technique_id: str, frameworks: List[str] = None) -> ToolResult:
        with get_session() as session:
            stmt = (
                select(
                    attack_technique_control_mapping.attack_technique_id,
                    Control.id,
                    Control.name,
                    Control.framework_id,
                    Framework.name.label('framework_name'),
                    attack_technique_control_mapping.mitigation_effectiveness,
                    attack_technique_control_mapping.confidence_score
                )
                .join(Control, attack_technique_control_mapping.control_id == Control.id)
                .join(Framework, Control.framework_id == Framework.id)
                .where(attack_technique_control_mapping.attack_technique_id == technique_id)
            )
            
            if frameworks:
                stmt = stmt.where(Control.framework_id.in_(frameworks))
            
            results = session.execute(stmt).all()
            
            return ToolResult(
                success=True,
                data=[dict(r._mapping) for r in results],
                source="postgres_attack_mapping",
                timestamp=datetime.utcnow().isoformat()
            )
```

---

## **Recommended Postgres Tables (Priority Order)**

### **Phase 1 - Critical for MVP**
1. `cve_cache` - Cache NVD API responses (rate limit management)
2. `cve_attack_mapping` - CVE → ATT&CK technique
3. `attack_technique_control_mapping` - ATT&CK → your controls
4. `cpe_dictionary` + `cve_cpe_affected` - Product version → CVE lookup

### **Phase 2 - Enhanced Intelligence**
5. `metasploit_modules` - Exploit availability
6. `nuclei_templates` - Detection templates
7. `sigma_rules` - SIEM detection rules
8. `exploit_db_index` - Public exploits catalog

### **Phase 3 - Enrichment**
9. `cis_benchmark_rules` - Automated compliance scoring
10. `threat_intel_feeds` - OTX pulses, MISP events, custom IoCs
11. `asset_inventory` - Your infrastructure (for asset → CVE correlation)
12. `vulnerability_scan_results` - Qualys/Nessus/Snyk findings

---

## **Ingestion Pipeline Design**

```python
#Daily batch jobs
1. fetch_nvd_recent_cves()        # Last 7 days from NVD
2. fetch_cisa_kev_updates()       # Updated KEV list
3. fetch_epss_bulk()              # Daily EPSS scores
4. sync_attack_stix_data()        # Weekly ATT&CK matrix update
5. sync_exploit_db_csv()          # Daily Exploit-DB commits
6. sync_metasploit_modules()      # Weekly MSF repo scan
7. sync_nuclei_templates()        # Daily Nuclei template updates
8. sync_sigma_rules()             # Weekly SigmaHQ updates

# On-demand jobs (triggered by user query or new CVE alert)
9. enrich_cve_with_attack()       # LLM-assisted CVE → technique mapping
10. map_attack_to_controls()      # LLM-assisted technique → control mapping
```

---

## **Complete Tool Registry**

```python
TOOL_REGISTRY = {
    # === CVE & Vulnerability Intelligence ===
    "cve_details": CVEIntelligenceTool(),
    "epss_lookup": EPSSLookupTool(),
    "cisa_kev_check": CISAKEVTool(),
    "github_advisory_search": GitHubAdvisoryTool(),
    
    # === Exploit Intelligence ===
    "exploit_db_search": ExploitDBTool(),
    "metasploit_module_search": MetasploitModuleTool(),
    "nuclei_template_search": NucleiTemplateTool(),
    
    # === ATT&CK Framework ===
    "attack_technique_lookup": ATTACKTechniqueTool(),
    "cve_to_attack_mapper": CVEtoATTACKMapperTool(),
    "attack_to_control_mapper": ATTACKtoControlMapperTool(),
    
    # === Asset & Infrastructure ===
    "shodan_search": ShodanTool(),
    "cpe_resolver": CPEResolverTool(),
    "asset_vulnerability_lookup": AssetVulnerabilityTool(),
    
    # === Detection Engineering ===
    "sigma_rule_search": SigmaRuleTool(),
    "generate_sigma_rule": SigmaRuleGeneratorTool(),
    
    # === Compliance & Frameworks ===
    "framework_control_search": FrameworkControlTool(),
    "cis_benchmark_lookup": CISBenchmarkTool(),
    "gap_analysis": GapAnalysisTool(),
    
    # === Threat Intelligence ===
    "otx_pulse_search": AlienVaultOTXTool(),
    "virustotal_lookup": VirusTotalTool(),
    
    # === Analysis & Synthesis ===
    "attack_path_builder": AttackPathBuilderTool(),
    "risk_calculator": RiskCalculatorTool(),
    "remediation_prioritizer": RemediationPrioritizerTool(),
}
```

Want me to implement the full Postgres schema migration, the tool wrapper classes, or design the LangGraph agent topology that orchestrates these tools?