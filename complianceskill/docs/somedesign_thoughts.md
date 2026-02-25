Good, those choices are clean and consistent. Let me lock in the architectural decisions these answers drive, then surface the remaining open questions.

---

## Decisions Locked In

**Qdrant local on Docker** means no auth complexity for now. You'll run a single Qdrant container, connect via `localhost:6333`, and add an API key later by just dropping one env var into the container config. No structural changes needed when you make that switch. The collection schema should still be designed with a `source` payload field so you can shard by framework later if the volume grows.

**OpenAI `text-embedding-3-small`** is the right call here. It's 1536 dimensions, cost-effective, and handles domain-specific compliance language well enough. The one commitment this creates: all collections must use `1536` as their vector size from day one. If you ever switch models, you'll need to re-embed everything, so this is a permanent decision for now. Worth noting that `text-embedding-3-small` supports **Matryoshka dimensions** — you could store at 512 or 256 if you want faster search at the cost of some precision, but 1536 is the safe default for compliance/security content where nuance matters.

**Multi-format document ingestion** (PDF, Word, Markdown + external fetch) adds meaningful complexity to the Policy Ingestion Agent. The key library decision here is `unstructured` — it handles all three formats with a unified API and preserves structural metadata (headings, sections, page numbers) that matters for policy docs. External fetch means you also need an HTTP fetching layer with content-type detection so the pipeline routes the document to the right parser. Both paths should normalize to the same intermediate representation before embedding.

---

## Revised Architecture Based on Your Answers

### Qdrant Collection Design

You'll need these collections, each with 1536-dimension vectors:

`framework_controls` — one record per control across all frameworks, with `framework_id` as a filterable payload field. This is your most-queried collection.

`framework_requirements` — requirements per framework, linked to controls via `control_ids` in the payload.

`framework_risks` — risk records with `mitigated_by` control references in payload.

`framework_test_cases` — existing test cases, linked to their parent control.

`framework_scenarios` — scenario records for grounding queries in real-world context.

`user_policies` — a separate collection for user-uploaded or externally fetched documents. Each chunk gets `source_doc_id`, `doc_title`, `section_heading`, `page_or_position`, and `framework_scope` (if the user specified which framework they're uploading against) in its payload.

The separation of `user_policies` from framework artifacts is intentional — it keeps your authoritative knowledge base clean while still allowing cross-collection queries during gap analysis.

### Document Ingestion Pipeline (Revised)

The pipeline now has three entry points feeding one normalized path:

**PDF upload** → `unstructured` PDF parser → section/paragraph chunks with heading metadata preserved

**Word/Markdown upload** → `unstructured` DOCX/MD parser → same normalized chunks

**External URL fetch** → HTTP GET with content-type detection → route to appropriate parser → same normalized chunks

All three paths produce a `DocumentChunk` object with: `text`, `section_heading`, `position`, `source_doc_id`, `doc_title`, `page_number` (if applicable). This is what gets embedded and stored. The normalization happens here, not downstream.

One important design note: policy documents are often long and poorly structured. You'll want a **sliding window chunking strategy** (e.g., 512 tokens with 64-token overlap) rather than strict section-by-section splitting, because policy language often spans section boundaries. The section heading gets attached to every chunk within that section as a payload field so you can still group results by section.

---

## Remaining Open Questions

Three questions from the original list still need answers before implementation starts:

**1. Hierarchy index: Qdrant-only or SQLite alongside?**

This is the most impactful remaining decision. Pure Qdrant gives you semantic search but not reliable `control → requirement → risk` traversal — you'd have to chain multiple vector searches and the determinism isn't guaranteed. A small SQLite file (just a few tables mirroring your hierarchy) gives you fast, exact traversal that the Retrieval Agent uses after the initial semantic search lands it on a node. The overhead is minimal. My recommendation is SQLite alongside Qdrant, but worth confirming if you have a reason to avoid adding another persistence layer.

**2. What frameworks are coming next?**

You already have CIS v8.1 and HIPAA. Your CIS YAML references SOC2 and NIST CSF 2.0 in the `related_frameworks` mappings — are full YAML files being prepared for those? And is there a longer roadmap (PCI-DSS, ISO 27001, FedRAMP)? This matters because the normalization layer needs to handle framework-specific quirks upfront rather than retrofitting them. If you know the full list now, we can build one normalization layer that handles all of them rather than adding adapters incrementally.

**3. What is the exact output format for test cases?**

This is the most consequential remaining question. You said tests are the final outcome, but there are two meaningfully different interpretations:

**Document-form test procedures** — structured YAML/markdown outputs that describe what to test, how to test it, what evidence to collect, and what pass/fail looks like. These mirror your existing `test_cases` YAML and would be stored back into `framework_test_cases`. A compliance auditor or security engineer would then execute these manually or feed them into their tooling.

**Executable test scripts** — Python/shell scripts that actually call your security APIs (XSOAR, Snyk, Qualys) to run the test and return a result. These are a significantly larger scope and require the agent to understand your API integrations.

Given your existing work with XSOAR/Snyk/Qualys agents, there's a natural bridge here — but the implementation phases are very different. The safest approach is to start with document-form test procedures (Phase 1) and add API-executable generation as Phase 2 once the knowledge base is solid.

---

Once you answer these three, we can finalize the full component list and start implementation in the right order. What's your call on the hierarchy index?


Perfect. Postgres alongside Qdrant is actually a better call than SQLite for your use case — it gives you proper relational integrity, indexing on foreign keys, and it'll handle concurrent agent queries cleanly when you scale to multiple users. It also means you're not managing a file-based store in production. Let me lock everything in and flag what this changes.

---

## All Decisions Now Locked

| Decision | Choice |
|---|---|
| Vector store | Qdrant local on Docker |
| Relational store | Postgres (Docker, same compose) |
| Embedding model | OpenAI `text-embedding-3-small` (1536d) |
| Document ingestion | PDF, Word, Markdown + external URL fetch |
| Frameworks (initial) | CIS v8.1, HIPAA, SOC2, NIST CSF 2.0 |
| Frameworks (later) | FedRAMP |
| Test output | Document-form first, executable second |

---

## What Postgres Changes in the Architecture

Postgres now plays a distinct and non-overlapping role from Qdrant. The division is clean:

**Qdrant** owns everything that needs semantic search — controls, requirements, risks, test cases, scenarios, user policy chunks. You query it with natural language and get back semantically similar artifacts.

**Postgres** owns the authoritative relational structure — the exact `framework → requirement → risk → control → test_case` linkages, framework metadata, user session state, uploaded document registry, and gap analysis results. You query it deterministically when you need to traverse the hierarchy or look up "give me all controls that mitigate this risk."

This means the Retrieval Agent has a two-step pattern for almost every query: semantic search in Qdrant to find the entry point, then Postgres traversal to get the full context chain around that entry point.

---

## Postgres Schema Design

### Core Hierarchy Tables

```
frameworks
  id, name, version, description, source_url, created_at

requirements
  id, framework_id (FK), requirement_code, name, description, domain, parent_requirement_id (self-ref for nested requirements)

risks
  id, framework_id (FK), risk_code, name, description, likelihood, impact

controls
  id, framework_id (FK), control_code, name, description, domain, control_type, cis_control_id

risk_controls  (many-to-many bridge)
  risk_id (FK), control_id (FK), mitigation_strength

requirement_controls  (many-to-many bridge)
  requirement_id (FK), control_id (FK)

test_cases
  id, control_id (FK), name, description, test_type, expected_evidence, pass_criteria, fail_criteria

scenarios
  id, framework_id (FK), name, description, severity
  
scenario_controls  (many-to-many bridge)
  scenario_id (FK), control_id (FK)
```

### Cross-Framework Mapping Table

This is critical given you have four frameworks and they share significant overlap (your CIS YAML already references SOC2 and NIST mappings inline):

```
cross_framework_mappings
  id, source_framework_id (FK), source_control_id (FK), 
  target_framework_id (FK), target_control_id (FK), 
  mapping_type (equivalent | related | partial), confidence_score
```

This table is what lets the agent answer "I have a SOC2 gap — what CIS controls address the same area?" without doing a fuzzy vector search. It also means when a user uploads a policy and you find a gap against HIPAA, you can immediately show them the equivalent NIST and CIS controls without additional retrieval.

### User Session & Document Tables

```
user_sessions
  id, created_at, framework_scope (array), intent_classification, clarification_state

uploaded_documents
  id, session_id (FK), filename, source_type (upload | url), 
  format (pdf | docx | markdown), framework_scope (FK to frameworks), 
  ingestion_status, created_at

document_chunks
  id, document_id (FK), chunk_index, section_heading, page_number, 
  text_preview (first 200 chars), qdrant_vector_id (links back to Qdrant record)

gap_analysis_results
  id, session_id (FK), document_id (FK), framework_id (FK),
  requirement_id (FK), gap_type, similarity_score, 
  matched_chunk_id (FK to document_chunks), created_at
```

The `qdrant_vector_id` field on `document_chunks` is the critical bridge — when Postgres finds a chunk via relational query, you can immediately fetch its vector neighborhood from Qdrant if needed. When Qdrant returns a semantically similar chunk, you can pull its full relational context from Postgres using the stored ID.

---

## What Changes for the Four Frameworks

With SOC2, NIST CSF 2.0, ISO 27001, and CIS v8.1 + HIPAA, the normalization layer needs to handle five distinct YAML structures before FedRAMP arrives. The key quirk per framework that affects normalization:

**CIS v8.1** — controls organized by Implementation Groups (IG1/IG2/IG3), safeguards nested under controls. Your YAML already handles this reasonably.

**HIPAA** — split between Administrative, Physical, and Technical safeguards. Required vs. Addressable distinction is important and needs its own field in the requirements table.

**SOC2** — organized by Trust Service Criteria (TSC). Controls are tied to criteria not domains. The CC/A/C/PI/P prefix system maps to your `control_code` field.

**NIST CSF 2.0** — two-level hierarchy of Functions → Categories → Subcategories. The v2.0 update added the Govern function, so if your YAMLs were built against v1.1 you'll need to verify coverage.

**ISO 27001** — Annex A controls organized by clauses (5 through 8) and Annex A sections. The 2022 revision reorganized the control numbering significantly from 2013, so the normalization layer needs to know which version it's ingesting.

The normalization layer should be a **per-framework adapter** (one Python class per framework) that reads that framework's raw YAML shape and outputs the canonical Postgres + Qdrant schema. Adding FedRAMP later then means writing one new adapter class, not touching the core pipeline.

---

## Updated Implementation Order

With Postgres in the picture, the order shifts slightly:

**Step 1 — Infrastructure** — Docker Compose with Qdrant + Postgres + a minimal Python service. Alembic migrations for the Postgres schema. No agent code yet.

**Step 2 — Framework Adapters + Ingestion** — one adapter per framework, ingestion scripts that populate Postgres first (relational links), then embed and push to Qdrant with the Postgres IDs in the payload. Validate that cross-framework mappings are populated correctly.

**Step 3 — Retrieval Layer** — a `RetrievalService` class that wraps both stores. Given a query, it: searches Qdrant → gets artifact IDs → fetches full context from Postgres → returns a unified `RetrievedContext` object. Test this in isolation before adding any agent complexity.

**Step 4 — Planner + Clarification Agent** — LangGraph supervisor with state carrying session context. Connects to the RetrievalService. Handles the clarification loop before dispatching retrieval tasks.

**Step 5 — Document Ingestion Agent** — `unstructured`-based pipeline for PDF/Word/Markdown + URL fetch. Stores chunks in Postgres `document_chunks`, embeds into `user_policies` Qdrant collection.

**Step 6 — Gap Analysis Agent** — cross-collection comparison between `user_policies` and framework collections. Writes results to `gap_analysis_results` in Postgres.

**Step 7 — Test Generation Agent** — takes a control + its full hierarchy context from Postgres and generates document-form test cases mirroring your existing YAML structure.

---

Are you ready to start on Step 1 — the Docker Compose setup and Postgres schema migrations? That's the foundation everything else depends on.