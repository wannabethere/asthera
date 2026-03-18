# CVE → ATT&CK → Control Mapping Pipeline

## Why CVE Is the Right Starting Point

The batch job gaps listed above all share the same root cause: the pipeline was started from a technique ID, but in real security operations you rarely start there. You start from a vulnerability — a CVE — and need to answer:

1. **What can an attacker do with this CVE?** → ATT&CK techniques
2. **Which tactics does this enable?** → tactic contexts
3. **Which controls would prevent or detect it?** → framework items
4. **What are we missing?** → coverage gaps in `attack_control_mappings`

CVE is the natural entry point because it carries concrete exploit information — CVSS scores, affected products, CWE categories, known exploits — that makes the ATT&CK and control mappings far more precise than starting from an abstract technique ID.

---

## The Three-Stage Pipeline

```
[ CVE ]
   │
   ▼
[ Stage 1: CVE Enrichment ]
  Fetch NVD/CIRCL data → extract CVSS, CWE, affected products, exploit status
   │
   ▼
[ Stage 2: CVE → ATT&CK ]
  Map CVE to ATT&CK techniques + tactics using:
    - CWE → technique lookup table
    - LLM mapping with CVE description + exploit context
    - EPSS score as confidence signal
   │
   ▼
[ Stage 3: ATT&CK → Control (per tactic) ]
  For each (technique, tactic) pair:
    - Derive tactic_risk_lens (TacticContextualiserTool)
    - Retrieve framework items (FrameworkItemRetrievalTool)
    - LLM mapping → ControlMappingResult
    - Persist to attack_control_mappings
   │
   ▼
[ Output: CVE Risk Record ]
  cve_id + techniques + tactics + mapped controls + gap list
```

---

## Worked Example: CVE-2024-3400

### Stage 1 — CVE Enrichment

**Source:** NVD API (`https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-3400`)

| Field | Value |
|---|---|
| CVE ID | CVE-2024-3400 |
| Description | A command injection vulnerability in Palo Alto Networks PAN-OS software. An unauthenticated attacker may execute arbitrary OS commands on the firewall with root privileges. |
| CVSS v3.1 Base Score | 10.0 (Critical) |
| Attack Vector | Network |
| Attack Complexity | Low |
| Privileges Required | None |
| CWE | CWE-77 (Improper Neutralisation of Special Elements in OS Command) |
| Affected Products | Palo Alto Networks PAN-OS 10.2, 11.0, 11.1 |
| EPSS Score | 0.97 (97th percentile — actively exploited) |
| Known Exploit | Yes — CISA KEV listed |
| Exploit Maturity | Weaponised |

**What this tells the pipeline before the LLM is invoked:**
- Network-accessible, no auth required → Initial Access is certain
- OS command execution with root → Execution and Privilege Escalation are likely
- Firewall device → Persistence on network infrastructure is a high-risk tactic
- EPSS 0.97 → confidence in ATT&CK mapping should be treated as high

---

### Stage 2 — CVE → ATT&CK

#### 2a. CWE → Technique Lookup

CWE-77 (Command Injection) has a documented ATT&CK mapping via MITRE's CWE-ATT&CK crosswalk:

| CWE | Primary Technique | Tactics |
|---|---|---|
| CWE-77 | T1059 — Command and Scripting Interpreter | execution |
| CWE-77 | T1190 — Exploit Public-Facing Application | initial-access |
| CWE-77 | T1068 — Exploitation for Privilege Escalation | privilege-escalation |

This gives the pipeline a high-confidence starting set without any LLM call. The CWE lookup is deterministic and fast.

#### 2b. LLM Refinement

The LLM receives the CVE description, CVSS breakdown, affected product (PAN-OS firewall), exploit status, and the CWE-derived candidate techniques. It:

- Confirms or rejects each candidate technique based on the specific exploit mechanism
- Adds additional techniques the CWE crosswalk misses (e.g. T1133 External Remote Services, T1098 Account Manipulation for persistence on the device)
- Assigns a confidence score per technique derived partly from EPSS

**LLM output for CVE-2024-3400:**

| Technique ID | Technique Name | Tactic(s) | Confidence | Source |
|---|---|---|---|---|
| T1190 | Exploit Public-Facing Application | initial-access | high | CWE lookup + LLM confirmed |
| T1059.004 | Unix Shell | execution | high | LLM — OS command injection executes via shell |
| T1068 | Exploitation for Privilege Escalation | privilege-escalation | high | CWE lookup + LLM confirmed |
| T1133 | External Remote Services | persistence | medium | LLM — firewall device enables persistent access |
| T1098 | Account Manipulation | persistence | medium | LLM — root access enables credential modification |
| T1562.004 | Disable or Modify System Firewall | defense-evasion | medium | LLM — root on firewall enables rule modification |

This is the output of Stage 2. Each row is a `(cve_id, technique_id, tactic)` triple ready to enter Stage 3.

---

### Stage 3 — ATT&CK → Control (per tactic)

Each `(technique_id, tactic)` triple is processed by the tool chain: `TacticContextualiserTool` → `FrameworkItemRetrievalTool` → `AttackControlMappingTool`. The results are written to `attack_control_mappings` and `tactic_contexts`.

Below are two complete examples.

---

#### Example A: T1190 under `initial-access` → CIS Controls v8.1

**TacticContextualiserTool output:**

```
technique_id:     T1190
tactic:           initial-access
tactic_risk_lens: Attacker exploits a vulnerability in a public-facing
                  application to gain initial access to the network. The
                  primary risk is an unauthenticated external actor achieving
                  a foothold via an unpatched or misconfigured internet-exposed
                  service. For CVE-2024-3400 specifically, this is a network
                  device (PAN-OS firewall) with a critical-severity command
                  injection flaw and no auth requirement.
blast_radius:     network
primary_asset_types: [network, endpoint]
source:           derived
```

**FrameworkItemRetrievalTool query:**

```
query:        <tactic_risk_lens above>
framework_id: cis_v8_1
tactic:       initial-access
top_k:        8
```

**Top candidates retrieved from `framework_items` (CIS v8.1):**

| Rank | item_id | Title | Similarity |
|---|---|---|---|
| 1 | CIS-RISK-012 | Unpatched Public-Facing Service Exploitation | 0.91 |
| 2 | CIS-RISK-007 | External Attack via Internet-Exposed Asset | 0.87 |
| 3 | CIS-RISK-031 | Vulnerability in Network Perimeter Device | 0.84 |
| 4 | CIS-RISK-019 | Failure to Apply Critical Security Patches | 0.79 |
| 5 | CIS-RISK-044 | Missing Network Segmentation Controls | 0.61 |

**AttackControlMappingTool LLM output:**

```
Mappings written to attack_control_mappings:

(T1190, initial-access, CIS-RISK-012, cis_v8_1)
  relevance_score: 0.94
  confidence:      high
  rationale:       CVE-2024-3400 is a textbook instance of CIS-RISK-012.
                   The vulnerability is in a public-facing firewall service,
                   requires no authentication, and is actively weaponised.
                   CIS IG2 controls 7.1 (vulnerability scanning) and 7.4
                   (patch management) are the primary mitigations.
  loss_outcomes:   [breach, operational impact]

(T1190, initial-access, CIS-RISK-007, cis_v8_1)
  relevance_score: 0.88
  confidence:      high
  rationale:       The affected asset (PAN-OS firewall) is an internet-exposed
                   asset. CIS-RISK-007 covers the failure to inventory and
                   monitor external attack surface — the vulnerability being
                   exploited in the wild indicates this control gap is real.
  loss_outcomes:   [breach]

(T1190, initial-access, CIS-RISK-031, cis_v8_1)
  relevance_score: 0.83
  confidence:      high
  rationale:       Perimeter network devices are specifically called out in
                   CIS-RISK-031. A firewall with an unauthenticated RCE
                   vulnerability directly satisfies this risk scenario's
                   trigger condition.
  loss_outcomes:   [breach, operational impact]

(T1190, initial-access, CIS-RISK-019, cis_v8_1)
  relevance_score: 0.76
  confidence:      medium
  rationale:       The CVE was disclosed in April 2024 with a patch available
                   on the same day. Any environment still running affected
                   PAN-OS versions post-patch demonstrates the failure mode
                   described in CIS-RISK-019.
  loss_outcomes:   [compliance violation, breach]

(T1190, initial-access, CIS-RISK-044, cis_v8_1)
  relevance_score: 0.48
  confidence:      low
  rationale:       Network segmentation reduces blast radius post-exploitation
                   but does not directly address the initial access vector.
                   Tangentially relevant.
  loss_outcomes:   [operational impact]
```

---

#### Example B: T1059.004 under `execution` → NIST SP 800-53 Rev 5

**TacticContextualiserTool output:**

```
technique_id:     T1059.004
tactic:           execution
tactic_risk_lens: Attacker executes arbitrary OS commands via a Unix shell
                  obtained through a vulnerability exploit. For CVE-2024-3400,
                  commands run as root on the PAN-OS operating system, giving
                  unrestricted access to device configuration, routing tables,
                  VPN keys, and inter-network traffic. The execution surface
                  is the firewall OS itself, not an application runtime.
blast_radius:     network
primary_asset_types: [network, data]
source:           derived
```

**Top candidates retrieved from `framework_items` (NIST 800-53r5):**

| Rank | item_id | Title | Similarity |
|---|---|---|---|
| 1 | SI-3 | Malicious Code Protection | 0.82 |
| 2 | SI-7 | Software, Firmware, and Information Integrity | 0.79 |
| 3 | CM-7 | Least Functionality | 0.76 |
| 4 | AU-12 | Audit Record Generation | 0.74 |
| 5 | SC-7 | Boundary Protection | 0.71 |

**AttackControlMappingTool LLM output:**

```
Mappings written to attack_control_mappings:

(T1059.004, execution, SI-7, nist_800_53r5)
  relevance_score: 0.89
  confidence:      high
  rationale:       SI-7 requires integrity verification of software and
                   firmware. Root-level command execution via CVE-2024-3400
                   can modify PAN-OS firmware or configuration without leaving
                   detectable traces, directly exploiting the absence of the
                   integrity monitoring SI-7 requires.
  loss_outcomes:   [breach, operational impact]

(T1059.004, execution, CM-7, nist_800_53r5)
  relevance_score: 0.84
  confidence:      high
  rationale:       CM-7 requires disabling unnecessary functions, ports, and
                   services. The GlobalProtect feature that exposes the
                   vulnerable endpoint should be disabled if not operationally
                   required — a direct application of CM-7 least functionality.
  loss_outcomes:   [breach]

(T1059.004, execution, AU-12, nist_800_53r5)
  relevance_score: 0.77
  confidence:      medium
  rationale:       AU-12 requires audit record generation for command
                   execution events. Shell commands executed via the exploit
                   may not be logged by default PAN-OS audit configuration,
                   creating a detection gap this control is designed to close.
  loss_outcomes:   [breach, compliance violation]

(T1059.004, execution, SC-7, nist_800_53r5)
  relevance_score: 0.58
  confidence:      low
  rationale:       SC-7 boundary protection is relevant to limiting lateral
                   movement post-execution but is not a direct mitigant of the
                   shell execution itself.
  loss_outcomes:   [operational impact]
```

---

## What Gets Written to the Database

After processing all six `(technique, tactic)` pairs for CVE-2024-3400 against CIS v8.1 and NIST 800-53r5:

### `tactic_contexts` — 6 new rows

```
(T1190,     initial-access,        tactic_risk_lens, blast_radius=network)
(T1059.004, execution,             tactic_risk_lens, blast_radius=network)
(T1068,     privilege-escalation,  tactic_risk_lens, blast_radius=identity)
(T1133,     persistence,           tactic_risk_lens, blast_radius=network)
(T1098,     persistence,           tactic_risk_lens, blast_radius=identity)
(T1562.004, defense-evasion,       tactic_risk_lens, blast_radius=network)
```

### `attack_tactic_contexts` Qdrant collection — 6 new points

Same content as above, embedded as vector documents for semantic similarity reuse in future CVE/technique mappings.

### `attack_control_mappings` — ~24 new rows

Approximately 4 control mappings per `(technique, tactic)` pair, across two frameworks. Each row has a 4-column primary key `(technique_id, tactic, item_id, framework_id)`. The exact rows for Examples A and B above are shown. The remaining four technique-tactic pairs follow the same pattern.

### `cve_attack_mappings` — 6 new rows *(new table, see below)*

One row per `(cve_id, technique_id, tactic)` triple, linking the CVE stage output to the control mapping stage input.

---

## New SQL Table: `cve_attack_mappings`

This table does not exist in the current schema. It is the join point between CVE intelligence and the ATT&CK → control pipeline.

```sql
cve_attack_mappings (
    cve_id              TEXT NOT NULL,
    technique_id        TEXT NOT NULL REFERENCES attack_techniques(technique_id),
    tactic              TEXT NOT NULL,

    -- CVE context (denormalised for fast retrieval)
    cvss_score          NUMERIC(4,2),
    epss_score          NUMERIC(5,4),
    attack_vector       TEXT,
    cwe_ids             TEXT[],
    affected_products   TEXT[],
    exploit_available   BOOLEAN,
    exploit_maturity    TEXT,     -- 'none' | 'poc' | 'weaponised'

    -- Mapping quality
    confidence          TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    mapping_source      TEXT NOT NULL,  -- 'cwe_lookup' | 'llm' | 'cwe_lookup+llm'
    rationale           TEXT,

    -- Lifecycle
    mapping_run_id      UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (cve_id, technique_id, tactic)
)
```

---

## New Qdrant Collection: `cve_intelligence`

Stores CVE summaries as vector documents for future semantic retrieval — e.g. "find all CVEs similar to this new vulnerability" or "which CVEs share the same attack pattern as this technique."

**Embedded text:**
```
{cve_id}. {description}. Affected: {affected_products}. CWE: {cwe_ids}.
Exploit: {exploit_maturity}. CVSS: {cvss_score}.
```

**Payload:**
```json
{
  "cve_id":           "CVE-2024-3400",
  "cvss_score":       10.0,
  "epss_score":       0.97,
  "attack_vector":    "network",
  "cwe_ids":          ["CWE-77"],
  "exploit_maturity": "weaponised",
  "technique_ids":    ["T1190", "T1059.004", "T1068", "T1133", "T1098", "T1562.004"],
  "tactics":          ["initial-access", "execution", "privilege-escalation",
                       "persistence", "defense-evasion"],
  "frameworks_mapped": ["cis_v8_1", "nist_800_53r5"]
}
```

---

## New Tool: `CVEEnrichmentTool`

**File:** `app/agents/tools/cve_enrichment.py`

**Input:** `cve_id: str`

**Output:**
```
cve_id              : str
description         : str
cvss_score          : float
cvss_vector         : str
attack_vector       : str      — "network" | "adjacent" | "local" | "physical"
attack_complexity   : str
privileges_required : str
cwe_ids             : List[str]
affected_products   : List[str]
epss_score          : float
exploit_available   : bool
exploit_maturity    : str
published_date      : str
last_modified       : str
```

**Data sources (in priority order):**
1. Postgres `cve_intelligence` table — cached rows from previous enrichments
2. NVD API 2.0 — `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}`
3. FIRST EPSS API — `https://api.first.org/data/1.0/epss?cve={cve_id}` — augments CVSS with exploitation probability
4. CIRCL CVE-Search — fallback if NVD rate-limits

**LangChain tool name:** `cve_enrich`

---

## New Tool: `CVEToATTACKMapperTool`

**File:** `app/agents/tools/cve_attack_mapper.py`

**Input:**
```
cve_id         : str
cve_detail     : CVEDetail     — output of CVEEnrichmentTool
frameworks     : List[str]     — e.g. ["cis_v8_1", "nist_800_53r5"]
```

**Output:** `List[CVEATTACKMapping]`, each:
```
cve_id          : str
technique_id    : str
tactic          : str
confidence      : str
mapping_source  : str   — "cwe_lookup" | "llm" | "cwe_lookup+llm"
rationale       : str
```

**Logic:**

1. **CWE → technique lookup** — query a static crosswalk table (MITRE's published CWE-ATT&CK mappings, loaded into `cwe_technique_mappings` Postgres table). This is deterministic and produces high-confidence mappings instantly for any CWE with a known ATT&CK association.

2. **LLM refinement** — send the CVE description, CVSS breakdown, affected products, exploit maturity, and CWE-derived candidates to the LLM. The LLM confirms, rejects, and augments the candidate list. EPSS score is included as a signal for confidence calibration — a 0.97 EPSS score means the LLM should lean toward high confidence on confirmed mappings.

3. **Write to `cve_attack_mappings`** — persist each `(cve_id, technique_id, tactic)` triple.

4. **Return** `List[CVEATTACKMapping]` — passed directly into `AttackControlMappingTool` per triple.

**LangChain tool name:** `cve_to_attack_map`

---

## New SQL Table: `cwe_technique_mappings`

The static crosswalk table. Loaded once from MITRE's published CWE-ATT&CK mapping document.

```sql
cwe_technique_mappings (
    cwe_id          TEXT NOT NULL,    -- "CWE-77"
    technique_id    TEXT NOT NULL,    -- "T1059"
    tactic          TEXT NOT NULL,    -- "execution"
    confidence      TEXT NOT NULL,    -- "high" | "medium"
    mapping_source  TEXT NOT NULL,    -- "mitre_crosswalk" | "community"
    notes           TEXT,
    PRIMARY KEY (cwe_id, technique_id, tactic)
)
```

---

## Full Tool Chain for CVE-2024-3400

```
CVEEnrichmentTool("CVE-2024-3400")
        │
        │  cve_detail (CVSS=10.0, CWE-77, EPSS=0.97, exploit=weaponised)
        ▼
CVEToATTACKMapperTool(cve_detail, frameworks=["cis_v8_1", "nist_800_53r5"])
        │
        │  6 x (technique_id, tactic) triples
        │  written to: cve_attack_mappings
        ▼
for each (technique_id, tactic):
    │
    ├── TacticContextualiserTool(technique_id, tactic)
    │       │  written to: tactic_contexts + attack_tactic_contexts
    │       ▼
    ├── FrameworkItemRetrievalTool(tactic_risk_lens, framework_id, tactic)
    │       │  reads from: framework_items (Qdrant)
    │       ▼
    └── AttackControlMappingTool(technique_id, tactic, framework_id)
            │  written to: attack_control_mappings (~4 rows per triple per framework)
            ▼
        MappingRepository.save_mappings()
```

**Total writes for CVE-2024-3400 across two frameworks:**
- `cve_attack_mappings`: 6 rows
- `tactic_contexts`: 6 rows
- `attack_tactic_contexts` (Qdrant): 6 points
- `attack_control_mappings`: ~48 rows (6 triples × 2 frameworks × ~4 controls each)
- `cve_intelligence` (Qdrant): 1 point

---

## Addressing the Original Batch Job Gaps

| Gap | Root cause | Fix in this pipeline |
|---|---|---|
| No `attack_control_mappings` rows | Batch job had no LLM mapping step | `AttackControlMappingTool` writes one row per `(technique, tactic, item, framework)` |
| No LLM-based mapping step | Batch enricher only ran retrieval, not mapping | `CVEToATTACKMapperTool` + `AttackControlMappingTool` are both LLM-driven |
| No `tactic_contexts` population | No `TacticContextualiserTool` invocation | Called once per `(technique, tactic)` pair before retrieval |
| No `attack_tactic_contexts` Qdrant population | Same — tool never ran | Written by `TacticContextualiserTool` on first derivation |
| `framework_items` not populated | `FrameworkItemIngestTool` was never run | Run `FrameworkItemIngestTool` once per framework before the CVE pipeline starts |

The last gap — `framework_items` not populated — is a prerequisite. `FrameworkItemIngestTool` must run first. The CVE pipeline will fall back to querying `framework_risks` + `framework_scenarios` separately if `framework_items` is empty, but the quality of retrieval is lower without the holistic embeddings.