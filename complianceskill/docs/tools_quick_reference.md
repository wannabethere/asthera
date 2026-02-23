# Security Intelligence Tools - Quick Reference

Quick reference for all implemented tools, their requirements, and status.

---

## **All Tools Summary**

| Tool Name | Category | API Key | Database Table | Status | Priority |
|-----------|----------|---------|----------------|--------|----------|
| **cve_intelligence** | CVE | NVD_API_KEY (opt) | None | ✅ Ready | High |
| **epss_lookup** | CVE | None | None | ✅ Ready | High |
| **cisa_kev_check** | CVE | None | None | ✅ Ready | High |
| **github_advisory_search** | CVE | GITHUB_TOKEN (opt) | None | ✅ Ready | Medium |
| **cpe_lookup** | Infrastructure | NVD_API_KEY (opt) | `cpe_dictionary` (opt) | ✅ Ready | High |
| **cpe_resolver** | Infrastructure | None | `cpe_dictionary`, `cve_cpe_affected` | ⚠️ Needs DB | High |
| **cve_to_attack_mapper** | ATT&CK | None | `cve_attack_mapping` | ⚠️ Needs DB | High |
| **attack_to_control_mapper** | ATT&CK | None | `attack_technique_control_mapping` | ⚠️ Needs DB | High |
| **attack_technique_lookup** | ATT&CK | None | None | ✅ Ready | Medium |
| **exploit_db_search** | Exploit | None | `exploit_db_index` | ⚠️ Needs DB | Medium |
| **metasploit_module_search** | Exploit | None | `metasploit_modules` | ⚠️ Needs DB | Medium |
| **nuclei_template_search** | Exploit | None | `nuclei_templates` | ⚠️ Needs DB | Medium |
| **framework_control_search** | Compliance | None | `controls`, `frameworks` | ✅ Ready | High |
| **cis_benchmark_lookup** | Compliance | None | `cis_benchmark_rules` | ⚠️ Needs DB | Medium |
| **gap_analysis** | Compliance | None | Multiple | 🚧 Stub | Low |
| **otx_pulse_search** | Threat Intel | OTX_API_KEY | None | ✅ Ready | Medium |
| **virustotal_lookup** | Threat Intel | VIRUSTOTAL_API_KEY | None | ✅ Ready | Medium |
| **tavily_search** | Search | TAVILY_API_KEY | None | ✅ Ready | Medium |
| **attack_path_builder** | Analysis | None | Multiple | 🚧 Stub | Low |
| **risk_calculator** | Analysis | None | Multiple | 🚧 Stub | Low |
| **remediation_prioritizer** | Analysis | None | Multiple | 🚧 Stub | Low |

**Legend:**
- ✅ Ready: Fully functional, no setup needed (or minimal setup)
- ⚠️ Needs DB: Requires database tables to be created and populated
- 🚧 Stub: Placeholder implementation, needs full development

---

## **Required API Keys**

### **Critical (Required for Core Tools)**
```bash
TAVILY_API_KEY=          # Required for tavily_search
OTX_API_KEY=             # Required for otx_pulse_search
VIRUSTOTAL_API_KEY=      # Required for virustotal_lookup
```

### **Recommended (Increases Rate Limits)**
```bash
NVD_API_KEY=             # Increases NVD rate limit (5→50 req/30sec)
GITHUB_TOKEN=            # Increases GitHub rate limit (60→5000 req/hr)
```

### **Not Required**
- EPSS API: Public, no key needed
- CISA KEV: Public JSON feed, no key needed

---

## **Required Database Tables**

### **Phase 1 - Critical (Implement First)**
1. `cve_attack_mapping` - CVE → ATT&CK technique mappings
2. `attack_technique_control_mapping` - ATT&CK → Control mappings
3. `cpe_dictionary` - CPE software/product catalog
4. `cve_cpe_affected` - CVE → CPE relationships

### **Phase 2 - Enhanced Intelligence**
5. `metasploit_modules` - Metasploit exploit modules
6. `nuclei_templates` - Nuclei detection templates
7. `exploit_db_index` - Exploit-DB catalog

### **Phase 3 - Compliance**
8. `cis_benchmark_rules` - CIS benchmark rules
9. `sigma_rules` - Sigma detection rules (future)

---

## **Data Ingestion Requirements**

### **Daily Jobs**
- NVD CVE updates (last 7 days)
- CISA KEV feed
- EPSS scores
- Exploit-DB CSV
- Nuclei templates

### **Weekly Jobs**
- MITRE ATT&CK STIX data
- Metasploit modules
- Sigma rules

### **One-Time Initial Load**
- NVD CPE Dictionary (500MB+ JSON)
- Historical CVEs (optional)

---

## **Quick Start Commands**

### **1. Set Environment Variables**
```bash
# Add to .env file
echo "TAVILY_API_KEY=your_key" >> .env
echo "OTX_API_KEY=your_key" >> .env
echo "VIRUSTOTAL_API_KEY=your_key" >> .env
echo "NVD_API_KEY=your_key" >> .env  # Optional but recommended
```

### **2. Create Database Tables**
```sql
-- Run Phase 1 table creation scripts
-- See tool_setup_guide.md Section 2 for SQL schemas
```

### **3. Test Tools**
```python
from app.agents.tools import TOOL_REGISTRY

# Test API tool (should work immediately)
tool = TOOL_REGISTRY["cve_intelligence"]()
result = tool.invoke({"cve_id": "CVE-2021-44228"})
print(result)
```

---

## **Tool Categories**

### **CVE & Vulnerability Intelligence**
- `cve_intelligence` - Comprehensive CVE data
- `epss_lookup` - Exploit prediction scores
- `cisa_kev_check` - Known exploited vulnerabilities
- `github_advisory_search` - OSS package vulnerabilities
- `cpe_lookup` - Software/product discovery

### **ATT&CK Framework**
- `attack_technique_lookup` - ATT&CK technique details
- `cve_to_attack_mapper` - CVE → ATT&CK mapping
- `attack_to_control_mapper` - ATT&CK → Control mapping

### **Exploit Intelligence**
- `exploit_db_search` - Public exploits
- `metasploit_module_search` - Metasploit modules
- `nuclei_template_search` - Nuclei templates

### **Compliance & Frameworks**
- `framework_control_search` - Framework controls
- `cis_benchmark_lookup` - CIS benchmarks
- `gap_analysis` - Gap analysis (stub)

### **Threat Intelligence**
- `otx_pulse_search` - AlienVault OTX
- `virustotal_lookup` - VirusTotal reputation

### **Infrastructure**
- `cpe_resolver` - CPE → CVE resolution

### **Search**
- `tavily_search` - Web search

### **Analysis** (Stubs)
- `attack_path_builder` - Attack path analysis
- `risk_calculator` - Risk scoring
- `remediation_prioritizer` - Remediation prioritization

---

## **Getting Help**

- **Full Setup Guide**: See `tool_setup_guide.md`
- **Tool Design**: See `tool_design.md`
- **Tool Implementation**: See `app/agents/tools/`

---

**Last Updated**: See git commit history
