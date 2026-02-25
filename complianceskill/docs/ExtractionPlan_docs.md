You can absolutely do this with **near-zero LLM calls** and still get a strong security-engineer KB—*if* you lean on (1) deterministic parsing, (2) controlled vocabularies + heuristics, and (3) weak supervision + rule engines.

Here’s a practical plan that fits your extractors (context/control/evidence/targeted fields/pattern recognition/requirement/domain) and your “local repo → process into knowledge bank” workflow.

---

## 1) Adopt a 2-phase pipeline: “Ingest raw” → “Deterministic normalize”

### Phase A: Raw collection (local repo mirror)

* Mirror each upstream source (git clone / periodic pull).
* Store **immutable snapshots**:

  * `source_id`, `commit_sha`, `path`, `retrieved_at`
* Keep the raw file as-is (Markdown, HTML, YAML, code, etc.).

**Why:** you can always re-run extraction with improved rules without losing provenance.

### Phase B: Deterministic normalization (no LLM)

Turn raw files into:

* `Document` (one file)
* `DocSection` (heading blocks + semantic blocks like tables/lists)
* `Entities` (control/requirement/evidence/terms/rules/CVE/etc.)
* `Edges` (mappings + references)

---

## 2) Replace LLM extraction with a “stack” of cheap deterministic techniques

### A) Structural parsing (high precision)

* Markdown AST parsing (headings, lists, tables, links, code blocks)
* HTML parsing (readability + heading tree)
* YAML/JSON parsing (Checkov rules metadata etc.)

This gives you:

* clean sections
* stable anchors
* “step lists” for playbooks
* tables parsed into key-value facts

### B) Entity dictionaries + controlled vocabularies (high precision, low effort)

Build small dictionaries that drive most extraction:

* Framework clause patterns (SOC2 CC*, ISO A.*, HIPAA CFR pattern)
* Control verbs: *implement, ensure, enforce, monitor, review, log, alert, restrict*
* Evidence artifact types: *ticket, screenshot, config export, log extract, attestation*
* Domains taxonomy: *IAM, vuln mgmt, logging/monitoring, IR, SDLC, encryption, backups…*
* Tool/vendor list (optional): Okta, Splunk, GitHub, AWS CloudTrail, etc.

### C) Pattern-based extraction (your “targeted fields”)

Use regex + structural cues:

* **Requirement**: clause id + normative language (“must/required/addressable/shall”)
* **Control**: “Control:” labels, “Objective”, “Policy Statement”, or bullet blocks with verbs
* **Evidence**: “Evidence:”, “Artifacts:”, “Collect:”, “Screenshots of…”
* **Steps**: numbered lists under “Procedure/Response/Runbook”
* **Mappings**: “maps to CC7.2 / A.12.4 / 164.312”

### D) Classical NLP (no LLM) for recall boost

Cheap additions that help a lot:

* lemmatization + POS tagging to identify “imperative steps”
* noun phrase extraction for “terms”
* sentence classification with linear models (TF-IDF + logistic regression)
* keyword + BM25 retrieval for Q&A

This is where you get decent recall without paying per token.

---

## 3) Use “weak supervision” for your Control/Requirement/ Evidence classifiers

Instead of LLM labeling, do this:

### Step 1: write labeling functions (LFs)

You already have extractors; treat each extractor as an LF that emits:

* `label` (CONTROL / REQUIREMENT / EVIDENCE / STEP / TERM / OTHER)
* `confidence`
* `span offsets`

Examples:

* LF_requirement_clause: matches `CC\d+(\.\d+)?` or `§164\.\d+`
* LF_control_verb_block: bullet list with “implement/enforce/monitor”
* LF_evidence_keyword: contains “evidence”, “artifact”, “attach”, “screenshot”
* LF_procedure_numbered_list: `1.` `2.` with imperative verbs

### Step 2: combine LFs

Use a weak-supervision approach:

* simplest: weighted voting
* better: Snorkel-style label model (still no LLM)

Output becomes your canonical entity extraction with traceable provenance:

* “CONTROL extracted by LF_control_verb_block + LF_policy_heading”

---

## 4) Solve the hard part deterministically: IDs + linking

### A) Stable IDs

* `doc_id = pub_id:path@commit`
* `section_id = doc_id#anchor` (anchor = normalized heading path + ordinal)
* `control_id` generated from (publication + normalized title + hash)
* `requirement_id = framework_id:clause`
* `rule_id` from Checkov (already exists)
* `cve_id` is canonical

### B) Linking without LLM

Use **string + rule-based entity linking**:

* Exact match first (CVE IDs, Checkov rule IDs, SOC2/ISO/HIPAA clauses)
* Alias tables for Terms (“MFA” = “multi-factor authentication”)
* Fuzzy matching (token sort ratio) for doc titles and control names
* Link edges when co-occurring within the same section + a cue phrase (“maps to”, “aligned with”, “satisfies”)

### C) Cross-source canonicalization rules

* If section mentions `CVE-\d{4}-\d+` → link to Vulnerability node
* If section mentions `CKV_` patterns → link to Rule node
* If text contains ISO clause patterns → link to Requirement

This alone gives you a surprisingly powerful graph.

---

## 5) Build the Knowledge Bank store (doc-only)

You can keep this simple:

### Option A: Postgres + “edges” table (fast, practical)

Tables:

* `publication`
* `document`
* `doc_section`
* `entity` (typed: CONTROL/REQUIREMENT/EVIDENCE/TERM/RULE/CVE)
* `edge` (src_id, rel_type, dst_id, props_json)
* `lexical_index` (for search)

### Option B: Neo4j (natural for traversals)

Great if you expect graph traversals as a primary feature.

For cost + simplicity, Postgres+edges is usually the fastest v1.

---

## 6) Q&A without LLM: “graph-first retrieval + extractive answers”

If you want *no LLM* at answer time, you can still do useful Q&A.

### A) Retrieval

* Use BM25 over `DocSection.excerpt + full text`
* Query expansion via your Term aliases
* Optional: hybrid BM25 + embeddings (embeddings can be done locally with small models)

### B) Answering (extractive)

* Return top sections + highlighted spans
* Build templated responses:

  * If question type = “evidence for control”: return EvidenceTemplate list from edges
  * If question type = “playbook steps”: return ProcedureStep list from parsed steps
  * If question type = “what maps to CC7.2”: return linked controls/docs

**This will feel like a very smart “documentation answer engine”** even without generative text.

### C) If you eventually want fluent answers, do it cheaply

* Keep everything deterministic
* Only use LLM as a **final summarizer** for a small number of retrieved sections
* Add a config flag: `LLM_SUMMARY=false` by default

---

## 7) Where you *should* allow a tiny amount of LLM (optional, huge ROI)

If you truly want to minimize calls, reserve LLM only for:

* **doc-to-ontology mapping** when rules are ambiguous
* building **alias expansions** for Terms once per corpus version
* generating **1–2 sentence summaries** for each document section offline (batch)

This is *offline*, cacheable, and can be done in small runs when budgets allow.

---

## 8) Concrete build order (minimal risk)

1. **Repo mirroring + provenance**
2. **Markdown/HTML/YAML parsing → doc/section**
3. **Run your extractors as labeling functions → entity spans**
4. **Deterministic linking** (CVE/rule/clause/term)
5. **Store in Postgres+edges**
6. **BM25 Q&A + traversal-based answers**
7. Optional: local embeddings later

---

## 9) Quick checklist: how you know you’re succeeding (no LLM)

You should be able to answer these *deterministically*:

* “Show the playbook steps for phishing response” → parsed step list + sections
* “What evidence is expected for access control?” → Control → EvidenceTemplate edges
* “Which SOC2 clauses relate to logging/monitoring?” → Requirement nodes by domain tags
* “What Checkov rules relate to S3 public access?” → Rule → sections + mapped controls

---

If you tell me what format your extracted outputs look like today (JSON schema for your extractors), I’ll give you:

* a **concrete Postgres schema** (tables + indexes)
* a **linking ruleset** (regex + fuzzy match thresholds)
* and a **non-LLM Q&A router** (question → traversal → response templates)
