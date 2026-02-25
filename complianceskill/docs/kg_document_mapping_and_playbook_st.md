# Document, mapping, and playbook storage location
_Exported on 2/2/2026 at 09:11:10 PST from Cursor (2.4.23)_

---

**User**

@preview @preview-vendor I want to create a curated set of overall kinds of documents, index mappings for qdrant db collections and playbooks where are they stored...Just tell me dont create a new md file..I will take care of it

---

**Cursor**


Searching the codebase for curated document kinds, Qdrant index/collection mappings, and playbook storage.



Checking Qdrant collection creation and kb-dump-utility config:



Checking Qdrant collection creation and kb-dump-utility index structure:



Here’s where things live:

---

**1. Curated set of document kinds (doc types)**

- **kb-dump-utility**
  - **`config/extractions.json`** – `taxonomies.doc_types`: playbook, procedure, policy, standard, framework, requirement, control, rule_reference, advisory, exception, guide, faq, documentation, product_docs.
  - **`config/knowledge_assistant_mapping.json`** – `doc_type_to_store`: maps each doc_type to Qdrant/store (`store_name`), `metadata_type`, and `extraction_type` (policy → domain_knowledge, playbook → domain_knowledge, control → compliance_controls, etc.).
- **flowharmonicai/knowledge**
  - **`indexing_cli/ingest_preview_files.py`** – `CONTENT_TYPE_TO_STORE` and related maps (e.g. `KNOWLEDGEBASE_ENTITY_TO_STORE`, `EXTRACTION_TYPE_TO_POLICY_STORE`, `EXTRACTION_TYPE_TO_RISK_STORE`) define content types and which store they go to; schema vs domain vs compliance vs product, etc.

---

**2. Index mappings for Qdrant (and collection names)**

- **flowharmonicai/knowledge**
  - **`app/storage/query/collection_factory.py`** – Canonical list of Qdrant/Chroma collection names and how they’re used: domain_knowledge, compliance_controls, entities, evidence, fields, controls, policy_documents, table_definitions, table_descriptions, column_definitions, schema_descriptions, features, contextual_edges. Schema collections are unprefixed; others use `collection_prefix` (e.g. `comprehensive_index_*`).
  - **`app/config/mdl_store_mapping_simplified.py`** – Maps MDL entity types to collections (e.g. table → table_descriptions, column → column_metadata, relationship → contextual_edges, entities, instructions, sql_pairs).
  - **`app/storage/documents.py`** – Where Qdrant collections are actually created: `create_collection(..., vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE))`. No separate payload/index schema file; metadata is whatever the ingest passes.
- **kb-dump-utility**
  - **`config/knowledge_assistant_mapping.json`** – Maps doc_type → store_name (collection) and metadata_type for retrieval; used so knowledge app can query the same logical “collections” (e.g. domain_knowledge with `type=playbook`).
  - **`config/elasticsearch_mapping.json`** and **`config/es-index.json`** – For Elasticsearch index mapping, not Qdrant. Qdrant collection creation is in flowharmonicai/knowledge (above).

So: **curated doc kinds** = kb-dump `extractions.json` + `knowledge_assistant_mapping.json`; **Qdrant collection/index mapping** = knowledge app `collection_factory.py` + `mdl_store_mapping_simplified.py` + `documents.py` (creation); **doc_type → collection** bridge = kb-dump `knowledge_assistant_mapping.json`.

---

**3. Playbooks – where they’re stored**

- **Files on disk**
  - **`flowharmonicai/data/cvedata/playbooks/`** – e.g. `cornerstone_playbook.md`, `snyk_silver_tables.md`.
- **Config**
  - **`config/extractions.json`** – playbook is a `doc_types` entry and has `playbook_markers` under `patterns.headings` and labeling rules under `labeling.section_labels` / `supports_traversals_rules`.
  - **`config/knowledge_assistant_mapping.json`** – playbook → `store_name: "domain_knowledge"`, `metadata_type: "playbook"`, `extraction_type: "context"`.
- **Code that uses playbooks**
  - **flowharmonicai/knowledge**: `app/agents/transform/playbook_driven_transform_agent.py`, `app/agents/transform/playbook_knowledge_helper.py`; **flowharmonicai/knowledge/config**: `config/extractions.json` (referenced from knowledge app); **flowharmonicai/data**: playbook markdown files and `AgenticSilverWorkflowInstructions.md`.

So: **playbook content** = under **`flowharmonicai/data/cvedata/playbooks/`** and referenced from **`flowharmonicai/data/`**; **playbook as a doc kind** = **kb-dump-utility `config/extractions.json`** and **`config/knowledge_assistant_mapping.json`**; **playbook-driven logic** = **flowharmonicai/knowledge `app/agents/transform/`** (playbook_driven_transform_agent, playbook_knowledge_helper).

---

**Short reference**

| What | Where |
|------|--------|
| Doc kinds (taxonomy) | kb-dump-utility `config/extractions.json` (`taxonomies.doc_types`) |
| Doc kind → store/type | kb-dump-utility `config/knowledge_assistant_mapping.json` (`doc_type_to_store`) |
| Qdrant collection list & usage | flowharmonicai/knowledge `app/storage/query/collection_factory.py` |
| MDL → collection mapping | flowharmonicai/knowledge `app/config/mdl_store_mapping_simplified.py` |
| Qdrant collection creation | flowharmonicai/knowledge `app/storage/documents.py` |
| Content type → store (ingest) | flowharmonicai/knowledge `indexing_cli/ingest_preview_files.py` (`CONTENT_TYPE_TO_STORE` etc.) |
| Playbook files | flowharmonicai/data/cvedata/playbooks/ (e.g. `cornerstone_playbook.md`, `snyk_silver_tables.md`) |
| Playbook as type + routing | kb-dump-utility `config/extractions.json` + `config/knowledge_assistant_mapping.json` |
| Playbook-driven agents | flowharmonicai/knowledge `app/agents/transform/playbook_driven_transform_agent.py`, `playbook_knowledge_helper.py` |
| Preview / preview-vendor index | kb-dump-utility `preview-vendor/index.json` (manifest of vendor docs); actual content under `preview-vendor/vendor-*/` and per-vendor JSONs (e.g. `Snyk Documentation.json`) |

---

**User**

Similarly can you create policies, frameworks and product docs

---

**Cursor**


Searching for where policies, frameworks, and product docs are defined and stored.



Checking kb-dump-utility `sources.json` for policy/framework sources and any product-doc paths:



Here’s the same style of summary for **policies**, **frameworks**, and **product docs** (where they’re stored and how they’re routed).

---

## Policies

- **Doc type**
  - **kb-dump-utility** `config/extractions.json`: `doc_types` includes `"policy"`; `patterns.headings.policy_markers`: `["policy", "purpose", "scope", "policy statement", "roles and responsibilities", "enforcement"]`; `extractors.doc_type_classifier.rules`: heading contains "policy" → `policy` (0.75).
- **Store / collection**
  - **kb-dump-utility** `config/knowledge_assistant_mapping.json`: `policy` → `store_name: "domain_knowledge"`, `metadata_type: "policy"`, `extraction_type: "full_content"`.
  - **flowharmonicai/knowledge** `indexing_cli/ingest_preview_files.py`: `policy_documents` content is routed to general stores with `type="policy"` via `EXTRACTION_TYPE_TO_POLICY_STORE` (context/entities/requirement/full_content/evidence/fields → domain_knowledge, entities, evidence, fields).
  - **flowharmonicai/knowledge** `app/storage/query/collection_factory.py`: policy lives in **domain_knowledge** and **policy_documents** (and entities/evidence/fields) with `metadata.type = "policy"`.
- **Source content**
  - **kb-dump-utility** `config/sources.json`: policy-style sources (e.g. SOC 2 Policy Templates, SOC 2 Type II Complete Policy System, SOC 2 Implementation Guide) under categories like `soc2`; cloned/dumped content ends up under the repo’s preview output (e.g. `preview/`), then enriched and indexed.

**Policies summary:** Doc kind in `extractions.json`; routing in `knowledge_assistant_mapping.json` and `ingest_preview_files.py`; stored in **domain_knowledge** (and entities/evidence/fields) with **type=policy**; policy source URLs in **sources.json**.

---

## Frameworks

- **Doc type**
  - **kb-dump-utility** `config/extractions.json`: `doc_types` includes `"framework"`. Framework *hints* live in `patterns.identifiers` (e.g. `soc2_clause`, `iso27001_2022_clause`, `iso27001_2013_clause`, `hipaa_cfr`) with `framework_hint`: soc2, iso27001_2022, iso27001_2013, hipaa.
- **Store / collection**
  - **kb-dump-utility** `config/knowledge_assistant_mapping.json`: `framework` → `store_name: "domain_knowledge"`, `metadata_type: "framework"`, `extraction_type: "context"`. Filter key for framework/category: `supports_traversals_to_filters.category` → `"framework"`.
  - **flowharmonicai/knowledge** `indexing_cli/ingest_preview_files.py`: framework is not a separate content type; framework-specific controls (e.g. SOC2) go to **compliance_controls** with `framework="SOC2"` in metadata.
  - **flowharmonicai/knowledge** `app/storage/query/collection_factory.py`: framework-style content in **domain_knowledge** (filter `type="framework"`) and framework-tagged controls in **compliance_controls** (e.g. `framework` in metadata).
- **Index fields**
  - **kb-dump-utility** `config/elasticsearch_mapping.json` and `config/es-index.json`: `framework` and `framework_clauses` as keyword fields for ES.

**Frameworks summary:** Doc kind in `extractions.json`; routing in `knowledge_assistant_mapping.json` → **domain_knowledge** with **type=framework**; framework hints in `extractions.json` identifiers; ES mapping in **elasticsearch_mapping.json** / **es-index.json**; compliance_controls use **framework** metadata (e.g. SOC2).

---

## Product docs

- **Doc type**
  - **kb-dump-utility** `config/extractions.json`: `doc_types` includes `"product_docs"`.
- **Store / collection**
  - **kb-dump-utility** `config/knowledge_assistant_mapping.json`: `product_docs` → `store_name: "domain_knowledge"`, `metadata_type: "product"`, `extraction_type: "context"`.
  - **flowharmonicai/knowledge** `indexing_cli/ingest_preview_files.py`: product/connector content types and their stores:
    - `product_purpose` → domain_knowledge (type=product)
    - `product_docs_link` / `product_docs` → domain_knowledge (type=product)
    - `product_key_concepts` / `product_key_concept` → **entities** (type=product)
    - `extendable_entity` → entities (type=product); `extendable_doc` → domain_knowledge (type=product)
  - **flowharmonicai/knowledge** `app/storage/query/collection_factory.py`: product content in **entities** and **domain_knowledge** with **type=product**; `search_connectors()` queries those with `filters={"type": "product"}`.
- **Source content**
  - **kb-dump-utility** `preview-vendor/`: vendor/product doc dumps (e.g. Snyk, Trivy, Checkmarx, Prowler, Checkov, TruffleHog, Anchore, OSSF); `preview-vendor/index.json` lists categories/sources; per-source JSONs (e.g. `Snyk Documentation.json`, `OSSF Security Scorecard.json`) are the product-doc content that gets enriched and then ingested to ES/Qdrant with store/type from the mapping above.

**Product docs summary:** Doc kind in `extractions.json` as **product_docs**; routing in `knowledge_assistant_mapping.json` and **ingest_preview_files** → **domain_knowledge** and **entities** with **type=product**; raw product doc content in **kb-dump-utility** `preview-vendor/` (and index in **preview-vendor/index.json**).

---

**Quick reference**

| Kind          | Doc type source     | Store / collection (Qdrant/Chroma)        | Metadata filter   | Extra locations |
|---------------|---------------------|-------------------------------------------|-------------------|-----------------|
| **Policies**  | extractions.json    | domain_knowledge, policy_documents, entities, evidence, fields | type=policy        | sources.json (policy repo URLs) |
| **Frameworks**| extractions.json    | domain_knowledge, compliance_controls     | type=framework; framework (e.g. SOC2) | elasticsearch_mapping.json (framework, framework_clauses) |
| **Product docs** | extractions.json (product_docs) | domain_knowledge, entities | type=product      | preview-vendor/ (vendor JSONs + index.json); ingest_preview_files CONTENT_TYPE_TO_STORE |

---

**User**

From the github sources, what are the extractions, to all kinds or types of docs and finally relevant entitirs found

---

**Cursor**


Gathering extraction config, doc types, and entity definitions from kb-dump-utility (GitHub sources).



Checking how extraction is applied in the ingest pipeline:



Here’s a concise summary of what comes from the GitHub sources: extractions, doc kinds/types, and entities.

---

## 1. Extractions (what is extracted per section)

Defined in **`config/extractions.json`** and implemented in **`extraction/rules_extractors.py`** and **`output/elasticsearch_generator.py`**:

| Extractor | Config key | What it extracts | Output field / use |
|-----------|------------|------------------|--------------------|
| **Doc type classifier** | `extractors.doc_type_classifier` | Doc type from headings/content | `doc_type` |
| **Domain classifier** | `extractors.domain_classifier` | Domain from keyword sets (min 2 hits) | `domains` |
| **Requirement extractor** | `extractors.requirement_extractor` | Normative clauses (must/shall/required + sentence window) | `requirements[]` (requirement_id, text, type, confidence) |
| **Control extractor** | `extractors.control_extractor` | Control text by framework (SOC2, ISO27001, HIPAA, NIST, PCI-DSS) | `controls[]` (control_id, framework, text, confidence) |
| **Mapping extractor** | `extractors.mapping_extractor` | “Maps to” / aligned-with links (max char distance 120) | `mappings[]` (mapping_type, src, dst, evidence) |
| **Versioning extractor** | `extractors.versioning_extractor` | Version/changelog refs, supersedes | `version_info[]` |
| **Section label** | `labeling.section_labels` | Single section label from content + entities | `section_label` |
| **Supports traversals** | `labeling.supports_traversals_rules` | Which traversals this section supports | `supports_traversals[]` |
| **Entities** | `patterns.identifiers` (regexes) | CVE, Checkov, ExploitDB, framework clauses | `entities` (see below) |
| **Definitions** | `keywords.definition_cues` | Term/definition pairs | `definitions[]` |
| **Procedure steps** | (in generator) | Steps from procedure/playbook content | `procedure_steps[]` |
| **Evidence templates** | (in generator) | Evidence/artifact templates | `evidence_templates[]` |
| **Mitigations** | (in generator, for vuln/exploit sources) | Mitigation actions | `mitigations[]` |
| **Remediations** | (in generator) | Remediation actions, fixed versions | `remediations[]` |
| **Validations** | (in generator) | Validation method/steps | `validations[]` |

Enriched sections are written **by `doc_type`** under the write path (e.g. `policy.json`, `playbook.json`, …).

---

## 2. All doc kinds / types

**Taxonomy** in **`config/extractions.json` → taxonomies**:

- **Doc types (14):**  
  `playbook`, `procedure`, `policy`, `standard`, `framework`, `requirement`, `control`, `rule_reference`, `advisory`, `exception`, `guide`, `faq`, `documentation`, `product_docs`
- **Domains (13):**  
  `iam`, `vulnerability_management`, `logging_monitoring`, `incident_response`, `secure_sdlc`, `data_protection`, `network_security`, `cloud_security`, `endpoint_security`, `third_party_risk`, `backup_recovery`, `change_management`, `governance`

**Doc-type classification** uses **`extractors.doc_type_classifier.rules`** (heading/content → doc_type):

- playbook / runbook → **playbook** (0.85)  
- policy → **policy** (0.75)  
- standard / baseline → **standard** (0.70)  
- procedure / steps / process → **procedure** (0.70)  
- content matches Checkov rule ID → **rule_reference** (0.70)  
- content matches CVE or ExploitDB ID → **advisory** (0.60)  
- exception / risk acceptance / waiver → **exception** (0.75)  

**Section labels** (one per section from **`labeling.section_labels`**):  
`requirement`, `control`, `evidence`, `procedure`, `playbook`, `mapping`, `definition`, `advisory`, and fallback **`other`**.

**Traversals** (from **`labeling.supports_traversals_rules`**):  
`T1_req_to_control_to_impl_to_evidence`, `T6_scenario_to_playbook_steps`, `T8_playbook_to_evidence_checklist`, `T10_cve_to_internal_mitigation`, `T11_cve_to_exploit_signals`, `T12_rule_to_guidance_and_controls`.

---

## 3. Relevant entities (indexed under `entities`)

**Identifier patterns** in **`config/extractions.json` → patterns.identifiers`** drive **`_extract_entities()`** in **`output/elasticsearch_generator.py`**. Stored structure is **`entities`** with these keys (and same in **`config/elasticsearch_mapping.json`**):

| Entity key | Identifier in config | Entity type | Regex / source |
|------------|----------------------|------------|----------------|
| **cve_ids** | `cve` | vulnerability | `\bCVE-\d{4}-\d{4,7}\b` |
| **checkov_rule_ids** | `checkov_rule_id` | rule | `\bCKV_[A-Z]{2,10}_[0-9]{1,5}\b`, `\bBC_[A-Z]{2,10}_[0-9]{1,5}\b` |
| **framework_clauses** | `soc2_clause`, `iso27001_2022_clause`, `iso27001_2013_clause`, `hipaa_cfr` | requirement | SOC2: `CC\d+(\.\d+)?`, `A\d+(\.\d+)?`; ISO27001:2022 `A.(5|6|7|8).\d{1,2}`; ISO27001:2013 `A.(5..18).\d{1,2}(\.\d{1,2})?`; HIPAA CFR `164.3xx` |
| **exploitdb_ids** | `exploitdb_id` | exploit_entry | `EDB-ID`, `EXPLOIT-DB` + numeric |
| **terms** | (definitions / glossary terms) | — | From definition extractor / terms |

**`manage_elasticsearch.py`** exposes entity search for: **`cve_ids`, `checkov_rule_ids`, `framework_clauses`, `exploitdb_ids`**.

---

## 4. GitHub sources (what feeds these extractions)

**`config/sources.json`** — categories and example repos:

| Category | Example sources |
|----------|------------------|
| **playbooks** | SOCFortress Playbooks, Awesome Playbooks, Microsoft Engineering Playbook |
| **soc2** | SOC 2 Policy Templates, SOC 2 Type II Complete Policy System, SOC 2 Implementation Guide, Probo (SOC 2 platform) |
| **compliance** | Comply (policy generator) |
| **iso27001** | ISO 27001 Templates, ISO 27001:2022 Revision Templates, ISO 27001:2013 Controls List, Azure ISO 27001 Control Mapping, ISMS Public |
| **iac-security** | Checkov Policy Reference (bridgecrewio/checkov) |
| **policies** | General Security Policies (Jowin/policies) |
| **hipaa** | HIPAA Policies Repository |
| **llm-security** | Awesome LLM Security, OSS LLM Security, Awesome LLM4Cybersecurity, Awesome LLM Supply Chain Security, LLM Guard, LLM Security (attack vectors) |

Each source has **include_patterns** (e.g. `*.md`, `*.yaml`, `*.py`) and **extract_metadata** (frontmatter, headers, links, code_blocks). Content is cloned/dumped into **preview** (and **preview-vendor** for vendor docs), then run through the pipeline above so **extractions → doc types → section labels → entities** all align with the config.

---

**User**

What are the extracted keywords or entities from the rules.md lets bucket them so I can think about how to reformat the prompts, dont create any doc - just give it here

---

**Cursor**


rules.md doesn’t define the literal keyword/entity lists; it says *what* to extract and whether to use rules vs ML. The concrete lists are in **extractions.json**. Below are the **extracted keywords/entities** implied by rules.md and extractions.json, **bucketed** so you can reuse them in prompts.

---

## Bucket 1 — **Identifier entities (regex; high precision)**

*Use in prompts for: “extract or match these ID types.”*

| Name | Entity type | Notes |
|------|-------------|--------|
| `cve` | vulnerability | CVE-YYYY-NNNNN |
| `checkov_rule_id` | rule | CKV_*, BC_* |
| `soc2_clause` | requirement | CC*, A* (framework_hint: soc2) |
| `iso27001_2022_clause` | requirement | A.5–8.* |
| `iso27001_2013_clause` | requirement | A.5–18.* |
| `hipaa_cfr` | requirement | 164.3xx, 45 CFR |
| `exploitdb_id` | exploit_entry | EDB-ID, EXPLOIT-DB |
| `version_expr` | (rules.md only) | version expressions |

---

## Bucket 2 — **Heading / section cues**

*Use in prompts for: “detect section type from headings.”*

- **policy_markers:** policy, purpose, scope, policy statement, roles and responsibilities, enforcement  
- **standard_markers:** standard, baseline, requirements, minimum, configuration  
- **procedure_markers:** procedure, steps, process, how to, workflow  
- **playbook_markers:** playbook, runbook, incident response, triage, containment, eradication, recovery  
- **evidence_markers:** evidence, artifacts, records, logs, proof, audit evidence  
- **mapping_markers:** maps to, aligned with, satisfies, covers, related controls, references  
- **exception_markers:** exception, waiver, risk acceptance, compensating control, deviation  
- **version_markers:** version, revision, changelog, last updated, effective date, supersedes  

---

## Bucket 3 — **Keyword cues (verbs / phrases)**

*Use in prompts for: “classify or tag by language.”*

- **control_verbs:** implement, ensure, enforce, restrict, review, monitor, detect, alert, log, audit, approve, rotate, encrypt, backup, patch, scan, validate  
- **evidence_cues:** evidence, artifact, attach, screenshot, export, report, ticket, approval, attestation, retain, retention, audit trail  
- **mapping_cues:** maps to, aligned with, satisfies, covers, implements, supports  
- **definition_cues:** definition, means, is defined as, for purposes of, we define, terminology  
- **change_cues:** changelog, revision history, diff, updated, deprecated, superseded  
- **Normative (requirement) words:** must, shall, required, addressable, recommended  
- **Control heading cues:** control, control objective, control statement  

---

## Bucket 4 — **Doc types (taxonomy)**

*Use in prompts for: “assign one doc type per document/section.”*

playbook, procedure, policy, standard, framework, requirement, control, rule_reference, advisory, exception, guide, faq, documentation, product_docs  

---

## Bucket 5 — **Section labels (per-section tag)**

*Use in prompts for: “assign one section label.”*

requirement, control, evidence, procedure, playbook, mapping, definition, advisory, other  

---

## Bucket 6 — **Domains (multi-label topic)**

*Use in prompts for: “tag domains; min 2 keyword hits.”*

iam, vulnerability_management, logging_monitoring, incident_response, secure_sdlc, data_protection, network_security, cloud_security, endpoint_security, third_party_risk, backup_recovery, change_management, governance  

*(Domain keyword sets in extractions.json — e.g. iam: mfa, least privilege, rbac, sso, …; use those in prompts if you want “why” this domain.)*

---

## Bucket 7 — **Traversals (intent / graph edges)**

*Use in prompts for: “which intents or paths does this section support?”*

- T1_req_to_control_to_impl_to_evidence  
- T6_scenario_to_playbook_steps  
- T8_playbook_to_evidence_checklist  
- T10_cve_to_internal_mitigation  
- T11_cve_to_exploit_signals  
- T12_rule_to_guidance_and_controls  

---

## Bucket 8 — **Structured extract outputs (what to fill)**

*Use in prompts for: “extract and return these structures.”*

- **requirements:** requirement_id, text, type, confidence  
- **controls:** control_id, framework, text, confidence  
- **definitions:** term, definition, confidence  
- **version_info:** version, changelog_ref, confidence  
- **mappings:** mapping_type, src, dst, evidence, confidence  
- **procedure_steps:** step_id, step_number, action, outcome  
- **evidence_templates:** evidence_id, name, artifact_type, acceptance_criteria  
- **mitigations:** mitigation_id, type, title, action, scope, preconditions, risk_reduction, references  
- **remediations:** remediation_id, type, title, action, fixed_in_version, urgency, references  
- **validations:** validation_id, method, title, steps, evidence_hint, references  

---

## Bucket 9 — **Entity index fields (for search/retrieval)**

*Use in prompts for: “filter or search by these entity fields.”*

cve_ids, checkov_rule_ids, framework_clauses, exploitdb_ids, terms  

---

**Prompt-reformat idea:**  
- **Buckets 1 + 9:** “Extract/match these identifier types and return them under these keys.”  
- **Buckets 2 + 3:** “Use these headings and phrases to classify section type and intent.”  
- **Buckets 4 + 5:** “Choose exactly one doc_type and one section_label from these lists.”  
- **Bucket 6:** “Tag with one or more domains from this list (optionally using these keywords).”  
- **Bucket 7:** “Indicate which of these traversals this section supports.”  
- **Bucket 8:** “For each type (requirements, controls, definitions, …), output these fields.”

