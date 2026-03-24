# Lexy AI — Generic Causal Concept Mapping Design

**Version:** 1.2.0  
**Status:** Draft — All decisions §14.1–§14.5 resolved  
**Scope:** Multi-domain, multi-source causal graph architecture for Lexy AI pipeline  
**Related files:** `causal_engine_state.py`, `causal_context_extractor.py`, `vector_causal_graph_builder.py`, `causal_graph_nodes.py`, `metric_decision_tree.py`, `dt_metric_decision_nodes.py`, `dt_decision_tree_generation_node.py`, `control_domain_taxonomy.json`

---

## 1. Problem Statement

The current architecture is tightly coupled to two fixed assumptions:

**Domain coupling.** `CSODCausalPipelineState` hardcodes LMS/HR as the vertical. `metric_decision_tree.py` contains SOC2, HIPAA, and NIST AI RMF as explicit taxonomy entries. `causal_context_extractor.py` maps category names to focus areas using `if "compliance" in category_lower` chains. Adding a new domain (finance, supply chain, customer success) requires touching every one of these files.

**Source coupling.** `vector_causal_graph_builder.py` uses `vertical="lms"` as a filter constant. The `_ASSEMBLY_SYSTEM_PROMPT` explicitly describes "an enterprise LMS/HR analytics platform". Node and edge ingestion happens against a single unified collection with a `vertical` metadata field, but the coverage check assumes the MDL tables are Cornerstone or Workday tables by name.

This document specifies the changes needed to make both layers generic, pluggable, and vector-store-backed — while preserving all existing behavior for the LMS and security verticals.

---

## 2. Target Architecture Overview

The refactored system has five layers, each with a clean contract boundary:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Registry                                                   │
│  Static per-domain manifests (YAML/JSON). No code changes to add a domain.  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ domain_id, concept_ids, shared_concepts
┌──────────────────────────────▼──────────────────────────────────────────────┐
│  Layer 2: Domain Classifier                                                 │
│  Feature vector → multi-label domain scores. Activates domain partitions.  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ active_domains, domain_scores
┌──────────────────────────────▼──────────────────────────────────────────────┐
│  Layer 3: Concept Graph (vector-store-backed, partitioned by domain)        │
│  ConceptNode declared by capability, not by table name.                     │
│  CausalEdge stored in Qdrant/Chroma with domain + capability metadata.      │
│  On-the-fly graph built via semantic retrieval + LLM assembly.              │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ proposed_nodes, proposed_edges, causal_graph
┌──────────────────────────────▼──────────────────────────────────────────────┐
│  Layer 4: Capability Resolver + Source Adapter Registry                     │
│  Abstract capability → (source_id, column_path) at runtime.                │
│  Works identically for CSOD, Workday, Snowflake, CSV upload, REST API.     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ capability_coverage, resolved_sources
┌──────────────────────────────▼──────────────────────────────────────────────┐
│  Layer 5: Confidence Scorer → Final Concept Set                             │
│  α·DT_weight + β·capability_coverage + γ·causal_centrality                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1: Domain Registry

### 3.1 Domain Manifest Schema

Each domain is described in a single YAML file in `app/domains/{domain_id}/manifest.yaml`. No Python changes are required to register a new domain.

```yaml
# app/domains/lms/manifest.yaml
domain_id: lms
display_name: Learning & Development
version: "1.0"

# Concepts owned by this domain partition
concepts:
  - compliance_training
  - learner_operations
  - cert_renewal
  - engagement_signal
  - training_plan_management
  - yoy_activity_trends

# Shared concept IDs this domain can activate
shared_concepts:
  - deadline_sla
  - anomaly_detection
  - cohort_comparator
  - predictive_risk
  - current_state_lookup

# Feature signals the domain classifier looks for
classifier_signals:
  keywords:
    - completion rate
    - training
    - compliance
    - certification
    - cornerstone
    - csod
    - learner
    - enrollment
    - lms
  intent_prefixes:
    - compliance_gap
    - training_plan
    - learner_summary

# DT option overrides specific to this domain
dt_options:
  use_case: lms_learning_target
  goal_filter:
    - training_completion
    - compliance_posture
  required_groups:
    - training_completion
    - compliance_posture

# Causal graph vector store partition
vector_partition:
  domain_filter: lms
  node_collection: lexy_causal_nodes
  edge_collection: lexy_causal_edges
```

```yaml
# app/domains/security/manifest.yaml
domain_id: security
display_name: Security & GRC
version: "1.0"

concepts:
  - vulnerability_posture
  - control_coverage
  - audit_evidence
  - threat_detection
  - access_risk
  - patch_compliance

shared_concepts:
  - deadline_sla
  - anomaly_detection
  - cohort_comparator
  - predictive_risk

classifier_signals:
  keywords:
    - cve
    - vulnerability
    - soc2
    - patch
    - incident
    - mitre
    - att&ck
    - control
    - audit
    - hipaa
  intent_prefixes:
    - gap_analysis
    - vulnerability_management
    - incident_response

dt_options:
  use_case: soc2_audit
  goal_filter:
    - compliance_posture
    - control_effectiveness
    - risk_exposure
  required_groups:
    - compliance_posture
    - control_effectiveness
    - risk_exposure

vector_partition:
  domain_filter: security
  node_collection: lexy_causal_nodes
  edge_collection: lexy_causal_edges
```

```yaml
# app/domains/finance/manifest.yaml  (new domain — no code changes)
domain_id: finance
display_name: Financial Performance
version: "1.0"

concepts:
  - revenue_metrics
  - cost_efficiency
  - budget_variance
  - forecast_accuracy
  - margin_analysis

shared_concepts:
  - anomaly_detection
  - cohort_comparator
  - predictive_risk

classifier_signals:
  keywords:
    - revenue
    - margin
    - budget
    - forecast
    - spend
    - cac
    - ltv
    - arr

dt_options:
  use_case: executive_dashboard
  goal_filter:
    - risk_exposure
    - compliance_posture

vector_partition:
  domain_filter: finance
  node_collection: lexy_causal_nodes
  edge_collection: lexy_causal_edges
```

### 3.2 Shared Concept Registry

Shared concepts live in `app/domains/_shared/concepts.yaml`. They are available to any domain that lists them in `shared_concepts`.

```yaml
# app/domains/_shared/concepts.yaml
shared_concepts:

  - id: deadline_sla
    display_name: Deadline & SLA Tracking
    required_capabilities:
      - deadline.dimension
    optional_capabilities:
      - deadline.buffer_days
    causal_role: mediator
    cross_domain_edges:
      - source: any_terminal
        mechanism: "Deadline proximity amplifies urgency weight on all root→terminal paths"

  - id: anomaly_detection
    display_name: Anomaly Detection
    required_capabilities:
      - metric.time_series
      - metric.baseline
    optional_capabilities:
      - etl.run_log
    causal_role: diagnostic_overlay
    enforce_trend_only: true

  - id: cohort_comparator
    display_name: Cohort Comparator
    required_capabilities:
      - entity.segmentation_dimension
      - metric.aggregatable
    causal_role: exploratory_executor

  - id: predictive_risk
    display_name: Predictive Risk
    required_capabilities:
      - entity.deadline_dimension
      - entity.progress_signal
      - entity.engagement_signal
    causal_role: predictive_executor

  - id: current_state_lookup
    display_name: Current State Lookup
    required_capabilities:
      - metric.current_value
    causal_role: short_circuit
    skip_causal_graph: true
```

### 3.3 Domain Manifest Loader

```python
# app/domains/registry.py

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache

DOMAINS_DIR = Path(__file__).parent
SHARED_CONCEPTS_PATH = DOMAINS_DIR / "_shared" / "concepts.yaml"


@lru_cache(maxsize=1)
def load_all_domain_manifests() -> Dict[str, Dict[str, Any]]:
    """Load all domain manifests from disk. Cached after first call."""
    manifests = {}
    for path in DOMAINS_DIR.glob("*/manifest.yaml"):
        domain_id = path.parent.name
        if domain_id.startswith("_"):
            continue
        with open(path) as f:
            manifests[domain_id] = yaml.safe_load(f)
    return manifests


@lru_cache(maxsize=1)
def load_shared_concepts() -> Dict[str, Dict[str, Any]]:
    """Load shared concept registry."""
    with open(SHARED_CONCEPTS_PATH) as f:
        data = yaml.safe_load(f)
    return {c["id"]: c for c in data.get("shared_concepts", [])}


def get_domain_manifest(domain_id: str) -> Optional[Dict[str, Any]]:
    return load_all_domain_manifests().get(domain_id)


def get_all_domain_ids() -> List[str]:
    return list(load_all_domain_manifests().keys())


def get_classifier_signals_for_domain(domain_id: str) -> Dict[str, Any]:
    manifest = get_domain_manifest(domain_id)
    return manifest.get("classifier_signals", {}) if manifest else {}
```

---

## 4. Layer 2: Domain Classifier

The domain classifier replaces the hardcoded `vertical="lms"` constant throughout the pipeline. It runs once during Stage 1 (intent classification) and populates `active_domains` in state.

### 4.1 Classifier Logic

```python
# app/agents/domain_classifier.py

from typing import Dict, List, Tuple
from app.domains.registry import load_all_domain_manifests

DOMAIN_THRESHOLD = 0.35  # Min score to activate a domain partition


def classify_domains(
    user_query: str,
    intent: str = "",
    feature_vector: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Multi-label domain classifier.

    Returns:
        {
          "domain_scores": {"lms": 0.87, "security": 0.12, "hr": 0.41},
          "active_domains": ["lms", "hr"],
          "primary_domain": "lms",
        }
    """
    manifests = load_all_domain_manifests()
    query_lower = (user_query + " " + intent).lower()
    scores: Dict[str, float] = {}

    for domain_id, manifest in manifests.items():
        signals = manifest.get("classifier_signals", {})
        score = 0.0

        # Keyword matching
        keywords = signals.get("keywords", [])
        keyword_hits = sum(1 for kw in keywords if kw in query_lower)
        if keywords:
            score += 0.6 * (keyword_hits / len(keywords))

        # Intent prefix matching
        prefixes = signals.get("intent_prefixes", [])
        prefix_hits = sum(1 for p in prefixes if intent.startswith(p))
        if prefixes:
            score += 0.4 * (prefix_hits / max(len(prefixes), 1))

        # Feature vector boost (if available)
        if feature_vector:
            domain_hints = feature_vector.get("domain_hints", [])
            if domain_id in domain_hints:
                score = min(score + 0.25, 1.0)

        scores[domain_id] = round(score, 3)

    active = [d for d, s in scores.items() if s >= DOMAIN_THRESHOLD]
    primary = max(scores, key=scores.get) if scores else "lms"

    return {
        "domain_scores": scores,
        "active_domains": active if active else [primary],
        "primary_domain": primary,
    }
```

### 4.2 State Changes

`CSODCausalPipelineState.vertical: str` (single, hardcoded) is replaced by:

```python
domain_classification: Dict[str, Any]   # output of classify_domains()
active_domains: List[str]               # e.g. ["lms", "hr"]
primary_domain: str                     # highest-scoring domain
domain_scores: Dict[str, float]         # full score map for audit
```

The `vertical` field is retained as a computed alias for `primary_domain` to maintain backward compatibility with existing nodes that read `state.get("vertical", "lms")`.

---

## 5. Layer 3: Concept Graph — Domain-Generic Vector Store Design

### 5.1 Problem with the Current Schema

The current vector store uses a `vertical` metadata field as a partition key. This has two problems:

1. A node that is relevant across domains (e.g., `deadline_sla`) must be duplicated once per vertical, or the filter must be broadened to include it — creating inconsistency.
2. Cross-domain graph assembly (e.g., an LMS + HR question) requires two separate retrievals with different `vertical` filters and a manual merge.

### 5.1.1 Resolved: Multi-Domain Node Storage — One Record per Node

**Decision:** A node that belongs to multiple domains (e.g., `engagement_signal` used in both LMS and HR) is stored as **one record** with `domains: ["lms", "hr"]`. It is never duplicated.

**Rationale:**

The LLM assembly step (`assemble_causal_graph_with_llm`) already receives the full node payload, including the `domains` list, as part of the candidate set presented in the prompt. The LLM has the semantic context of the question and can select and correctly contextualise a multi-domain node — interpreting `engagement_signal` as login frequency in an LMS compliance question, or as absenteeism rate in an HR attrition question — without needing separate records.

Duplication would cause three concrete problems:

1. **Divergent payloads.** Two copies of `engagement_signal` would drift independently — different `temporal_grain`, different `required_capabilities`, different `framework_codes` — unless a synchronisation mechanism was added, which would be more expensive to maintain than the single-record approach.
2. **Double retrieval.** A cross-domain question retrieving `n_results=25` would burn slots on both `engagement_signal_lms` and `engagement_signal_hr`, halving the effective candidate pool.
3. **Broken cross-domain paths.** If `engagement_signal_lms → compliance_training` and `engagement_signal_hr → attrition_risk` were two separate node IDs, the LLM could not draw a causal path through a shared engagement signal to multiple terminals — which is exactly the correct graph for a cross-domain LMS+HR question.

**What the LLM does with a multi-domain node:**

The assembly prompt (see Section 8.2) passes the node's `domains` list in the candidate description line. The LLM uses this as a contextual signal to select the appropriate causal role and edge connections given the question:

```
- [engagement_signal] type=root, cat=engagement, domains=["lms","hr"],
  grain=weekly, caps=[engagement.login_trend, engagement.session_depth],
  score=0.84 | engagement_signal lms hr root node. User platform engagement
  measured as weekly login frequency and session depth. Mediates training
  completion in LMS context; mediates absenteeism and attrition in HR context.
```

The LLM selects this node and contextualises its causal role to the active question without needing two separate records.

**Node ID convention for multi-domain nodes:**

Single-domain nodes use `f"{metric_ref}_{primary_domain}"` as their deterministic ID. Multi-domain nodes use `metric_ref` alone — no domain suffix:

```python
# Single-domain (domain-specific concept)
node_id = "compliance_training_lms"
node_id = "vulnerability_posture_sec"

# Multi-domain (no suffix — owned by multiple partitions)
node_id = "engagement_signal"     # domains: ["lms", "hr"]
node_id = "deadline_sla"          # domains: ["_shared"]
node_id = "manager_hierarchy"     # domains: ["lms", "hr"]
```

This makes it immediately clear during ingestion and inspection which nodes are domain-specific vs. genuinely cross-partition.

### 5.2 Revised Node Schema

**Qdrant collection:** `lexy_causal_nodes`

Each node is stored exactly once. Domain affinity is expressed as a list. Pure shared concepts carry `domains: ["_shared"]`. Multi-domain nodes carry both domain IDs. Single-domain nodes carry one.

```python
# Qdrant point — single-domain node example
{
  "id": "compliance_training_lms",              # f"{metric_ref}_{domain}" for single-domain
  "vector": <embedding of doc_text>,
  "payload": {
    # Identity
    "node_id":          "compliance_training_lms",
    "metric_ref":       "compliance_training",
    "display_name":     "Compliance Training",

    # Domain & capability
    "domains":          ["lms"],               # single-domain: one entry
    "required_capabilities": ["completion.rate", "deadline.dimension"],
    "optional_capabilities": ["engagement.login_trend"],

    # Causal type
    "node_type":        "terminal",            # root|mediator|confounder|collider|terminal
    "causal_role":      "terminal",
    "temporal_grain":   "weekly",
    "observable":       True,
    "latent_proxy":     None,
    "collider_warning": False,
    "is_outcome":       True,

    # Framework linkage (new — replaces category-based mapping)
    "framework_codes":  ["CC1", "CC2", "164.308(a)(5)"],  # from control_domain_taxonomy.json
    "focus_areas":      ["training_compliance"],

    # Provenance
    "source":           "seed",               # seed|llm_generated|user_ingested
    "version":          "1.0",
    "created_at":       "2026-01-15T00:00:00Z",
  }
}
```

**Multi-domain node example** — `engagement_signal` stored once, used in both LMS and HR:

```python
{
  "id": "engagement_signal",                    # no domain suffix — multi-domain
  "vector": <embedding of doc_text>,
  "payload": {
    "node_id":          "engagement_signal",
    "metric_ref":       "engagement_signal",
    "display_name":     "Engagement Signal",

    "domains":          ["lms", "hr"],          # both domains — single record
    "required_capabilities": ["engagement.login_trend"],
    "optional_capabilities": ["engagement.session_depth"],

    "node_type":        "root",
    "causal_role":      "root",
    "temporal_grain":   "weekly",
    "observable":       True,
    "collider_warning": False,
    "is_outcome":       False,

    # Context-specific descriptions — LLM reads both and picks the right frame
    "domain_context": {
      "lms": "Login frequency and session depth. Mediates training completion — stable trend rules out disengagement as root cause.",
      "hr":  "Platform access regularity. Mediates absenteeism signal — declining trend precedes attrition by ~3 weeks."
    },

    "framework_codes":  [],
    "focus_areas":      ["learner_engagement", "workforce_engagement"],
    "source":           "seed",
    "version":          "1.0",
    "created_at":       "2026-01-15T00:00:00Z",
  }
}
```

**Embeddable doc text** (unchanged pattern from `_node_to_document`, extended with domain context):

```
engagement_signal lms hr root node. User platform engagement measured as 
weekly login frequency and session depth. Mediates training completion in 
LMS context; mediates absenteeism and attrition in HR context.
Capabilities: engagement.login_trend, engagement.session_depth. 
temporal grain: weekly. leading indicator.
```

Note the doc text deliberately mentions both domain contexts — this ensures the embedding captures both semantic meanings, so the node surfaces correctly for LMS questions ("training completion"), HR questions ("attrition"), and cross-domain questions mentioning both.

**Single-domain doc text** (unchanged for domain-specific nodes):

```
compliance_training lms terminal node. Measures whether employees complete 
required compliance training against an organizational target. 
Capabilities: completion.rate, deadline.dimension. 
temporal grain: weekly. lagging outcome. framework: CC1, CC2.
```

### 5.3 Revised Edge Schema

**Qdrant collection:** `lexy_causal_edges`

```python
{
  "id": "E_overdue_count__compliance_training",
  "vector": <embedding of doc_text>,
  "payload": {
    # Identity
    "edge_id":           "E_overdue_count__compliance_training",
    "source_node_id":    "overdue_count_lms",
    "target_node_id":    "compliance_training_lms",
    "source_capability": "deadline.dimension",     # NEW — capability-level link
    "target_capability": "completion.rate",         # NEW

    # Causal properties
    "direction":         "negative",
    "mechanism":         "Increasing overdue assignment count directly suppresses compliance rate by adding items to the denominator that cannot close before the audit date.",
    "lag_window_days":   14,
    "lag_confidence":    0.82,
    "confidence_score":  0.91,

    # Validation
    "corpus_match_type": "confirmed",
    "evidence_type":     "operational_study",
    "corpus_validated":  True,

    # Domain & framework
    "domains":           ["lms", "_shared"],   # edge can be shared across domains
    "framework_codes":   ["CC1", "CC2"],
    "focus_areas":       ["training_compliance"],

    # Provenance
    "source":            "seed",
    "version":           "1.0",
    "created_at":        "2026-01-15T00:00:00Z",
  }
}
```

### 5.4 PostgreSQL Adjacency Table

The Postgres adjacency table provides fast structural lookups without re-embedding. It complements the vector store — semantic search finds relevant edges, structural lookup finds connected edges for any node set.

```sql
-- lexy_causal_graph_edges (replaces cce_causal_edges adjacency table)
CREATE TABLE lexy_causal_graph_edges (
    edge_id             TEXT PRIMARY KEY,
    source_node_id      TEXT NOT NULL,
    target_node_id      TEXT NOT NULL,
    source_capability   TEXT,                   -- NEW
    target_capability   TEXT,                   -- NEW
    domains             TEXT[] NOT NULL,         -- CHANGED: array not single value
    framework_codes     TEXT[],
    focus_areas         TEXT[],
    direction           TEXT NOT NULL DEFAULT 'positive',
    lag_window_days     INTEGER NOT NULL DEFAULT 14,
    confidence_score    NUMERIC(4,3) NOT NULL,
    corpus_match_type   TEXT DEFAULT 'novel',
    mechanism           TEXT,
    source              TEXT DEFAULT 'seed',
    version             TEXT DEFAULT '1.0',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lcge_source  ON lexy_causal_graph_edges(source_node_id);
CREATE INDEX idx_lcge_target  ON lexy_causal_graph_edges(target_node_id);
CREATE INDEX idx_lcge_domains ON lexy_causal_graph_edges USING GIN(domains);

-- lexy_causal_graph_nodes (structural metadata, vector payloads live in Qdrant)
CREATE TABLE lexy_causal_graph_nodes (
    node_id             TEXT PRIMARY KEY,
    metric_ref          TEXT NOT NULL,
    display_name        TEXT,
    domains             TEXT[] NOT NULL,
    required_capabilities TEXT[],
    optional_capabilities TEXT[],
    node_type           TEXT NOT NULL,
    temporal_grain      TEXT DEFAULT 'monthly',
    observable          BOOLEAN DEFAULT TRUE,
    collider_warning    BOOLEAN DEFAULT FALSE,
    is_outcome          BOOLEAN DEFAULT FALSE,
    framework_codes     TEXT[],
    focus_areas         TEXT[],
    source              TEXT DEFAULT 'seed',
    version             TEXT DEFAULT '1.0',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lcgn_domains   ON lexy_causal_graph_nodes USING GIN(domains);
CREATE INDEX idx_lcgn_metric    ON lexy_causal_graph_nodes(metric_ref);
CREATE INDEX idx_lcgn_node_type ON lexy_causal_graph_nodes(node_type);
```

### 5.4.1 Ingest Contract for Multi-Domain Nodes

The `ingest_nodes()` function in `vector_causal_graph_builder.py` is updated to handle the `domain_context` field and enforce the no-suffix ID convention:

```python
def _node_to_document(node: Dict[str, Any]) -> Tuple[str, str, Dict]:
    """
    Updated to handle multi-domain nodes.

    ID convention:
        - Single domain:  f"{metric_ref}_{domains[0]}"
        - Multi-domain:   metric_ref  (no suffix)
        - _shared:        metric_ref  (no suffix, same as multi-domain)
    """
    domains = node.get("domains", ["lms"])
    is_multi = len(domains) > 1 or domains == ["_shared"]

    node_id = (
        node.get("node_id")
        or (node["metric_ref"] if is_multi else f"{node['metric_ref']}_{domains[0]}")
    )

    # Build doc_text — include all domain contexts for multi-domain nodes
    domain_context = node.get("domain_context", {})
    context_str = " ".join(
        f"In {d} context: {ctx}" for d, ctx in domain_context.items()
    )

    doc_text = (
        f"{node.get('display_name', node_id)} "
        f"{' '.join(domains)} "
        f"{node.get('node_type', '')} node. "
        f"{node.get('description', '')} "
        f"{context_str} "
        f"Capabilities: {', '.join(node.get('required_capabilities', []))}. "
        f"temporal grain: {node.get('temporal_grain', 'monthly')}. "
        f"{'leading indicator.' if node.get('is_leading_indicator') else ''}"
        f"{'lagging outcome.' if node.get('is_outcome') else ''}"
    ).strip()

    metadata = {
        "node_id":                node_id,
        "metric_ref":             node.get("metric_ref", node_id),
        "domains":                domains,          # stored as list in Qdrant payload
        "domain_context":         domain_context,  # NEW — per-domain semantic description
        "required_capabilities":  node.get("required_capabilities", []),
        "optional_capabilities":  node.get("optional_capabilities", []),
        "node_type":              node.get("node_type", "mediator"),
        "temporal_grain":         node.get("temporal_grain", "monthly"),
        "observable":             str(node.get("observable", True)),
        "is_outcome":             str(node.get("node_type") == "terminal"),
        "collider_warning":       str(node.get("node_type") == "collider"),
        "framework_codes":        node.get("framework_codes", []),
        "focus_areas":            node.get("focus_areas", []),
        "source":                 node.get("source", "seed"),
    }
    return node_id, doc_text, metadata
```

Note: Qdrant stores `domains` as a list in the payload. The `$in` filter operator works against list-typed payload fields natively — no special handling needed at query time.

### 5.5 On-the-Fly Graph Build Flow

```
User question
     │
     ▼
Domain Classifier → active_domains = ["lms", "hr"]
     │
     ▼
retrieve_causal_nodes(
    query=enriched_query,
    domain_filter={"domains": {"$in": ["lms", "hr", "_shared"]}},   ← multi-domain
    n_results=25
)
     │
     ▼
retrieve_causal_edges(
    query=enriched_query,
    node_ids=[...],
    domain_filter={"domains": {"$in": ["lms", "hr", "_shared"]}},   ← multi-domain
    n_results=35
)
     │
     ▼
assemble_causal_graph_with_llm(
    question, nodes, edges
    # Multi-domain nodes surface once in the candidate set.
    # LLM reads each node's domains + domain_context fields and
    # selects the contextually correct causal role for this question.
)
     │
     ▼
Capability Resolver: node.required_capabilities → (source_id, column_path)
     │
     ▼
Confidence Scorer → final concept set + coverage report
```

---

## 6. Layer 4: Capability Resolver + Source Adapter Registry

### 6.1 Capability Vocabulary

Capabilities are the abstract interface between concepts and data sources. Every node declares what it needs; adapters declare what they provide.

```yaml
# app/capabilities/registry.yaml
capabilities:

  completion.rate:
    description: "Binary or percentage completion status for assigned work items"
    value_type: float          # 0.0–1.0 or 0–100
    temporal_types: [current_state, trend]

  deadline.dimension:
    description: "A timestamp or date field representing when work must be complete"
    value_type: datetime
    temporal_types: [current_state]
    required_for_intents:
      - predictive_risk_analysis
      - compliance_gap_close

  engagement.login_trend:
    description: "Time-series of user login or session activity"
    value_type: time_series
    temporal_types: [trend]

  entity.segmentation_dimension:
    description: "A categorical field usable for cohort grouping (department, role, region)"
    value_type: categorical

  entity.manager_hierarchy:
    description: "Manager-to-subordinate relationship chain for escalation routing"
    value_type: hierarchical

  metric.time_series:
    description: "Any time-indexed metric usable for anomaly detection"
    value_type: time_series
    temporal_types: [trend]

  metric.baseline:
    description: "A rolling baseline or mean against which anomalies are measured"
    value_type: float

  etl.run_log:
    description: "ETL pipeline execution log for upstream health checks"
    value_type: log

  revenue.actuals:
    description: "Actual realized revenue figures by period"
    value_type: float

  revenue.target:
    description: "Planned or budgeted revenue target by period"
    value_type: float
```

### 6.2 Source Adapter Schema

```python
# app/adapters/base.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


@dataclass
class CapabilityMapping:
    """Maps one abstract capability to a concrete source expression."""
    capability_id: str
    source_expression: str          # SQL column path, API field, or regex for CSV
    value_transform: Optional[str]  # e.g. "status == 'Completed' → 1 else 0"
    notes: str = ""


@dataclass
class SourceAdapterDeclaration:
    """
    Static declaration of what a data source can provide.
    Registered in AdapterRegistry at startup.
    """
    source_id: str                          # "csod", "workday", "snowflake", "csv"
    display_name: str
    source_type: str                        # "lms", "hcm", "warehouse", "file"
    capability_mappings: List[CapabilityMapping] = field(default_factory=list)
    freshness_query: Optional[str] = None  # SQL to check last ETL run

    def get_mapping(self, capability_id: str) -> Optional[CapabilityMapping]:
        return next(
            (m for m in self.capability_mappings if m.capability_id == capability_id),
            None
        )

    @property
    def provided_capabilities(self) -> List[str]:
        return [m.capability_id for m in self.capability_mappings]


class SourceAdapter(ABC):
    """Runtime adapter — executes queries against the source."""

    @abstractmethod
    def resolve_capability(self, capability_id: str, params: Dict[str, Any]) -> Any:
        """Return data for the given capability."""
        ...

    @abstractmethod
    def check_freshness(self) -> Dict[str, Any]:
        """Return freshness metadata for this source."""
        ...
```

```python
# app/adapters/declarations.py — static adapter declarations (no DB calls)

from .base import SourceAdapterDeclaration, CapabilityMapping

CSOD_ADAPTER = SourceAdapterDeclaration(
    source_id="csod",
    display_name="Cornerstone OnDemand LMS",
    source_type="lms",
    freshness_query="SELECT MAX(updated_at) FROM csod_etl_run_log",
    capability_mappings=[
        CapabilityMapping(
            capability_id="completion.rate",
            source_expression="csod_completion_log.status",
            value_transform="status IN ('Completed', 'Passed') → 1.0 else 0.0",
        ),
        CapabilityMapping(
            capability_id="deadline.dimension",
            source_expression="csod_training_assignments.due_date",
            value_transform=None,
        ),
        CapabilityMapping(
            capability_id="engagement.login_trend",
            source_expression="csod_user_sessions.login_ts",
            value_transform="COUNT(*) GROUP BY DATE_TRUNC('week', login_ts)",
        ),
        CapabilityMapping(
            capability_id="entity.segmentation_dimension",
            source_expression="workday_employees.department",
            value_transform=None,
        ),
        CapabilityMapping(
            capability_id="entity.manager_hierarchy",
            source_expression="workday_employees.manager_id",
            value_transform=None,
        ),
    ],
)

WORKDAY_ADAPTER = SourceAdapterDeclaration(
    source_id="workday",
    display_name="Workday HCM",
    source_type="hcm",
    freshness_query="SELECT MAX(last_sync_at) FROM wday_sync_log",
    capability_mappings=[
        CapabilityMapping(
            capability_id="completion.rate",
            source_expression="wday_learning_enrollment.completion_status",
            value_transform="completion_status = 'Completed' → 1.0 else 0.0",
        ),
        CapabilityMapping(
            capability_id="deadline.dimension",
            source_expression="wday_assignments.due_date_c",
            value_transform=None,
        ),
        CapabilityMapping(
            capability_id="entity.manager_hierarchy",
            source_expression="wday_workers.manager_wid",
            value_transform=None,
        ),
    ],
)

CSV_ADAPTER = SourceAdapterDeclaration(
    source_id="csv",
    display_name="CSV / File Upload",
    source_type="file",
    freshness_query=None,
    capability_mappings=[],  # Populated dynamically via schema fingerprinting
)
```

### 6.3 Adapter Registry + Capability Resolver

```python
# app/adapters/registry.py

from typing import Dict, List, Optional, Any
from .base import SourceAdapterDeclaration, CapabilityMapping
from .declarations import CSOD_ADAPTER, WORKDAY_ADAPTER, CSV_ADAPTER


class AdapterRegistry:
    """
    Runtime registry of available source adapters.
    Built at startup from static declarations + any dynamically registered adapters.
    """

    def __init__(self):
        self._adapters: Dict[str, SourceAdapterDeclaration] = {}

    def register(self, adapter: SourceAdapterDeclaration) -> None:
        self._adapters[adapter.source_id] = adapter

    def get(self, source_id: str) -> Optional[SourceAdapterDeclaration]:
        return self._adapters.get(source_id)

    def all_adapters(self) -> List[SourceAdapterDeclaration]:
        return list(self._adapters.values())


class CapabilityResolver:
    """
    Resolves abstract capability requirements against connected adapters.

    When multiple adapters satisfy the same required capability the pipeline
    PAUSES and emits an adapter_conflict_clarification card. The user picks
    the source; the pipeline resumes with their selection applied.
    See capability_resolution_node() and apply_user_adapter_selections() below.
    """

    def __init__(self, registry: "AdapterRegistry", connected_sources: List[str]):
        self._registry = registry
        self._connected: List[SourceAdapterDeclaration] = [
            ad for sid in connected_sources
            if (ad := registry.get(sid)) is not None
        ]

    def resolve(
        self,
        required_capabilities: List[str],
        optional_capabilities: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns capability_map plus a non-empty adapter_conflicts list when
        more than one connected adapter satisfies the same required capability.

        Non-empty adapter_conflicts → pipeline pauses, user selects source.

        Return shape:
        {
          "required_fulfilled": 2,
          "required_total": 2,
          "coverage_score": 1.0,
          "capability_map": {
            "completion.rate": {
                "source_id":  "csod",
                "expression": "csod_completion_log.status",
                "fulfilled":  True,
                "optional":   False,
                "alternatives": [                      # populated when >1 adapter qualifies
                    {"source_id": "workday",
                     "expression": "wday_learning_enrollment.completion_status",
                     "display_name": "Workday HCM"}
                ],
                "conflict": True,                      # True until user resolves
            },
          },
          "adapter_conflicts": [                       # non-empty → pipeline pauses
              {
                "capability_id": "completion.rate",
                "candidates": [
                    {"source_id": "csod",    "display_name": "Cornerstone LMS",
                     "expression": "csod_completion_log.status"},
                    {"source_id": "workday", "display_name": "Workday HCM",
                     "expression": "wday_learning_enrollment.completion_status"},
                ],
                "recommended": "csod",
                "reason": "Domain manifest lms sets csod as primary source.",
              }
          ],
          "exclusion_reason": None,
        }
        """
        optional_capabilities = optional_capabilities or []
        capability_map: Dict[str, Dict[str, Any]] = {}
        adapter_conflicts: List[Dict[str, Any]] = []
        required_fulfilled = 0

        for cap_id in required_capabilities:
            matches = self._find_all_mappings(cap_id)
            if not matches:
                capability_map[cap_id] = {
                    "source_id": None, "expression": None,
                    "fulfilled": False, "optional": False,
                    "alternatives": [], "conflict": False,
                }
                continue

            required_fulfilled += 1
            primary    = matches[0]
            alternates = matches[1:]
            conflict   = len(matches) > 1

            if conflict:
                adapter_conflicts.append({
                    "capability_id": cap_id,
                    "candidates": [
                        {
                            "source_id":    m.source_id,
                            "display_name": self._registry.get(m.source_id).display_name,
                            "expression":   m.source_expression,
                        }
                        for m in matches
                    ],
                    "recommended": primary.source_id,
                    "reason": (
                        f"Domain manifest sets {primary.source_id!r} as primary source. "
                        f"Select an alternative only if {primary.source_id!r} data is "
                        "stale or incomplete."
                    ),
                })

            capability_map[cap_id] = {
                "source_id":  primary.source_id,
                "expression": primary.source_expression,
                "fulfilled":  True,
                "optional":   False,
                "alternatives": [
                    {
                        "source_id":    m.source_id,
                        "expression":   m.source_expression,
                        "display_name": self._registry.get(m.source_id).display_name,
                    }
                    for m in alternates
                ],
                "conflict": conflict,
            }

        for cap_id in optional_capabilities:
            matches = self._find_all_mappings(cap_id)
            primary = matches[0] if matches else None
            capability_map[cap_id] = {
                "source_id":  primary.source_id if primary else None,
                "expression": primary.source_expression if primary else None,
                "fulfilled":  primary is not None,
                "optional":   True, "alternatives": [], "conflict": False,
            }

        coverage_score = (
            required_fulfilled / len(required_capabilities)
            if required_capabilities else 1.0
        )

        exclusion_reason = None
        if coverage_score == 0.0:
            missing = [c for c in required_capabilities
                       if not capability_map[c]["fulfilled"]]
            exclusion_reason = (
                f"required: 0/{len(required_capabilities)} — "
                f"no connected source provides: {', '.join(missing)}"
            )

        return {
            "required_fulfilled": required_fulfilled,
            "required_total":     len(required_capabilities),
            "coverage_score":     round(coverage_score, 3),
            "capability_map":     capability_map,
            "adapter_conflicts":  adapter_conflicts,
            "exclusion_reason":   exclusion_reason,
        }

    def _find_all_mappings(self, capability_id: str) -> List[Any]:
        """Return all adapters satisfying capability_id, ordered by manifest priority."""
        matches = []
        for adapter in self._connected:
            m = adapter.get_mapping(capability_id)
            if m:
                m.source_id = adapter.source_id  # type: ignore[attr-defined]
                matches.append(m)
        return matches

    def _find_mapping(self, capability_id: str) -> Optional[Any]:
        """Backward-compat shim: returns primary match only."""
        m = self._find_all_mappings(capability_id)
        return m[0] if m else None


# ─── Conflict Disambiguation — LangGraph nodes ──────────────────────────────


def capability_resolution_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs CapabilityResolver over all proposed nodes.
    Emits an adapter_conflict_clarification card and halts if any capability
    has multiple connected adapters.

    LangGraph routing:
        adapter_conflict_resolved == False  →  capability_clarification_node
        adapter_conflict_resolved == True   →  causal_graph_creator_node
    """
    connected = state.get("connected_sources", [])
    registry  = _build_registry(connected)
    resolver  = CapabilityResolver(registry, connected)

    all_coverage: Dict[str, Any] = {}
    all_conflicts: List[Dict] = []
    seen: set = set()

    for node in state.get("causal_proposed_nodes", []):
        result = resolver.resolve(
            node.get("required_capabilities", []),
            node.get("optional_capabilities", []),
        )
        all_coverage[node["node_id"]] = result
        for c in result.get("adapter_conflicts", []):
            if c["capability_id"] not in seen:
                all_conflicts.append(c)
                seen.add(c["capability_id"])

    state["capability_coverage"]       = all_coverage
    state["pending_adapter_conflicts"] = all_conflicts
    state["adapter_conflict_resolved"] = len(all_conflicts) == 0

    if all_conflicts:
        n = len(all_conflicts)
        state.setdefault("messages", []).append(AIMessage(
            content="",
            additional_kwargs={
                "clarification_card": {
                    "type": "adapter_conflict_clarification",
                    "title": "Multiple data sources available",
                    "subtitle": (
                        f"{n} capability{'s' if n > 1 else ''} can be fulfilled by "
                        "more than one connected source. The recommended option is "
                        "pre-selected based on your domain configuration."
                    ),
                    "conflicts": [
                        {
                            "capability_id": c["capability_id"],
                            "display_label": _capability_display_label(c["capability_id"]),
                            "candidates":    c["candidates"],
                            "recommended":   c["recommended"],
                            "reason":        c["reason"],
                        }
                        for c in all_conflicts
                    ],
                    "action": "submit_adapter_selections",
                }
            },
        ))
    return state


def apply_user_adapter_selections(
    state: Dict[str, Any],
    selections: Dict[str, str],
) -> Dict[str, Any]:
    """
    Patches capability_coverage with the user's source choices, then clears conflicts.
    Called when the user submits their adapter_conflict_clarification response.

    Args:
        selections: {capability_id: chosen_source_id}
    """
    coverage = state.get("capability_coverage", {})
    for node_id, result in coverage.items():
        for cap_id, entry in result.get("capability_map", {}).items():
            if cap_id in selections and entry.get("conflict"):
                chosen_id = selections[cap_id]
                alt = next(
                    (a for a in entry.get("alternatives", [])
                     if a["source_id"] == chosen_id), None
                )
                if alt or entry["source_id"] == chosen_id:
                    if alt:
                        entry["source_id"]  = alt["source_id"]
                        entry["expression"] = alt["expression"]
                    entry["conflict"]      = False
                    entry["user_selected"] = True

    state["capability_coverage"]       = coverage
    state["user_adapter_selections"]   = selections
    state["pending_adapter_conflicts"] = []
    state["adapter_conflict_resolved"] = True
    return state


def _capability_display_label(capability_id: str) -> str:
    """Human-readable label for a capability ID, used in the clarification card."""
    return {
        "completion.rate":               "Training completion rate",
        "deadline.dimension":            "Assignment due date",
        "engagement.login_trend":        "Login / session activity",
        "entity.segmentation_dimension": "Department / team grouping",
        "entity.manager_hierarchy":      "Manager reporting chain",
        "revenue.actuals":               "Actual revenue figures",
        "revenue.target":                "Revenue targets / quota",
    }.get(capability_id, capability_id.replace(".", " ").title())


### 6.3.3 CSV Adapter Persistence — Backend Registry

# Schema fingerprinting for CSV / unstructured sources
import re
import pandas as pd

CAPABILITY_FINGERPRINTS: Dict[str, List[str]] = {
    "completion.rate":           [r"complet", r"done", r"finish", r"pass"],
    "deadline.dimension":        [r"due", r"deadline", r"expir", r"due_date"],
    "engagement.login_trend":    [r"login", r"session", r"access", r"visit"],
    "entity.segmentation_dimension": [r"dept", r"department", r"team", r"region", r"group"],
    "entity.manager_hierarchy":  [r"manager", r"supervisor", r"reports_to"],
    "revenue.actuals":           [r"revenue", r"sales", r"amount", r"actuals"],
    "revenue.target":            [r"target", r"quota", r"budget", r"plan"],
}


def fingerprint_csv_capabilities(df: "pd.DataFrame") -> List[CapabilityMapping]:
    """
    Infer capability mappings from column headers + value-distribution validation.
    Results are persisted to lexy_registered_adapters — NOT session-scoped.
    CSVs are ingested server-side (admin / integration pipeline, not chat UI).
    See load_registered_adapters_from_db() for the persistence contract.
    """
    mappings: List[CapabilityMapping] = []
    for capability_id, patterns in CAPABILITY_FINGERPRINTS.items():
        for col in df.columns:
            normalized = col.lower().replace(" ", "_").replace("-", "_")
            if any(re.search(p, normalized) for p in patterns):
                sample = df[col].dropna().head(200)
                if _validate_capability_sample(capability_id, sample):
                    mappings.append(CapabilityMapping(
                        capability_id=capability_id,
                        source_expression=col,
                        value_transform=None,
                        notes=f"auto-detected from header '{col}'",
                    ))
                break
    return mappings


def _validate_capability_sample(capability_id: str, sample: "pd.Series") -> bool:
    """
    Value-distribution guard: reduces false-positive header matches.
    Returns False if the column values don't match the capability's expected type.
    """
    if sample.empty:
        return False
    try:
        if capability_id == "completion.rate":
            unique_vals = {str(v).lower() for v in sample.unique()}
            return bool(
                unique_vals & {"completed", "passed", "true", "1", "done", "yes"}
                or (hasattr(sample, "dtype") and str(sample.dtype).startswith(("float", "int"))
                    and sample.between(0, 100).all())
            )
        if capability_id == "deadline.dimension":
            import pandas as _pd
            _pd.to_datetime(sample.iloc[0])
            return True
        if capability_id in ("engagement.login_trend", "revenue.actuals", "revenue.target"):
            return str(getattr(sample, "dtype", "")).startswith(("float", "int"))
    except Exception:
        return False
    return True


async def load_registered_adapters_from_db(
    conn_string: str,
    tenant_id: str,
) -> List[SourceAdapterDeclaration]:
    """
    Load all active registered adapters for a tenant from lexy_registered_adapters.
    Called at application startup and on a 5-minute TTL refresh.

    Postgres table:
        CREATE TABLE lexy_registered_adapters (
            adapter_id          TEXT PRIMARY KEY,
            tenant_id           TEXT NOT NULL,
            source_type         TEXT NOT NULL DEFAULT 'file',
            display_name        TEXT NOT NULL,
            capability_mappings JSONB NOT NULL,
            file_path           TEXT,
            fingerprint_hash    TEXT,
            ingested_at         TIMESTAMPTZ DEFAULT NOW(),
            last_seen_at        TIMESTAMPTZ DEFAULT NOW(),
            active              BOOLEAN DEFAULT TRUE
        );

    Registration flow:
        1. Admin uploads file to backend via /api/v1/data-sources  (not chat UI)
        2. Worker calls fingerprint_csv_capabilities() + _validate_capability_sample()
        3. Confirmed mappings written to lexy_registered_adapters
        4. AdapterRegistry picks them up at next TTL refresh
        5. CSV source appears in CapabilityResolver identically to any API adapter
        6. Conflict disambiguation card (§6.3.1) shows CSV as a candidate if it
           satisfies the same capability as an already-connected system adapter

    Deregistration:
        File deleted or replaced → active = FALSE.
        Inactive adapters are excluded from CapabilityResolver and conflict cards.
    """
    rows = await db.fetch("""
        SELECT adapter_id, display_name, source_type, capability_mappings
        FROM lexy_registered_adapters
        WHERE tenant_id = $1 AND active = TRUE
        ORDER BY ingested_at DESC
    """, tenant_id)

    return [
        SourceAdapterDeclaration(
            source_id=row["adapter_id"],
            display_name=row["display_name"],
            source_type=row["source_type"],
            capability_mappings=[CapabilityMapping(**m) for m in row["capability_mappings"]],
        )
        for row in rows
    ]
```

---

## 7. Layer 5: Confidence Scorer — System-Managed Adaptive Weights

### 7.1 Formula

```
final_confidence[concept] = α · DT_weight + β · capability_coverage + γ · causal_centrality
```

### 7.2 Weight Management — Resolved Decision

**Decision:** Weights are tunable per domain manifest but system-managed — not user-configurable at runtime. The system uses a best-of-both approach: domain manifests declare a static prior; the system refines weights nightly using observed concept selection quality.

**Why system-managed, not user-changed:** Weights are a calibration parameter, not a UX knob. Optimising them requires understanding the precision/recall trade-off between DT routing signal, data coverage, and graph topology — context users should not need. The system handles this automatically; a domain manifest sets the starting prior before enough signal has accumulated.

### 7.3 Domain Manifest Weight Declaration

```yaml
# app/domains/lms/manifest.yaml (excerpt)
scorer_weights:
  alpha: 0.45          # slightly lower — LMS domain signals are noisier than security
  beta:  0.40          # slightly higher — CSOD data coverage is highly reliable
  gamma: 0.15          # unchanged — graph topology signal is domain-agnostic
  exclusion_threshold: 0.28
```

Global defaults apply when not declared: `α=0.50, β=0.35, γ=0.15, threshold=0.30`.

### 7.4 System-Managed Weight Update Cycle

```python
# app/scoring/weight_manager.py

from dataclasses import dataclass
from typing import Dict, Optional

GLOBAL_DEFAULTS = {"alpha": 0.50, "beta": 0.35, "gamma": 0.15, "threshold": 0.30}


@dataclass
class ScorerWeights:
    alpha: float = 0.50
    beta:  float = 0.35
    gamma: float = 0.15
    exclusion_threshold: float = 0.30

    def normalise(self) -> "ScorerWeights":
        """Ensure α + β + γ = 1.0."""
        total = self.alpha + self.beta + self.gamma
        return ScorerWeights(
            alpha=round(self.alpha / total, 4),
            beta=round(self.beta  / total, 4),
            gamma=round(self.gamma / total, 4),
            exclusion_threshold=self.exclusion_threshold,
        )


def load_weights(domain_id: str, db_weights: Optional[Dict] = None) -> ScorerWeights:
    """
    Weight loading priority (highest → lowest):
      1. System-learned weights from lexy_scorer_weights (nightly Bayesian update)
      2. Domain manifest static prior (app/domains/{domain_id}/manifest.yaml)
      3. Global defaults

    Minimum 50 resolved conversations required before system-learned row is written.
    Below that threshold, manifest prior or global default is used.
    """
    from app.domains.registry import get_domain_manifest

    # Tier 3: global defaults
    w = ScorerWeights(**GLOBAL_DEFAULTS)

    # Tier 2: domain manifest prior
    manifest = get_domain_manifest(domain_id) or {}
    mw = manifest.get("scorer_weights", {})
    if mw:
        w = ScorerWeights(
            alpha=mw.get("alpha", w.alpha),
            beta=mw.get("beta",   w.beta),
            gamma=mw.get("gamma", w.gamma),
            exclusion_threshold=mw.get("exclusion_threshold", w.exclusion_threshold),
        )

    # Tier 1: system-learned weights (highest priority)
    if db_weights:
        w = ScorerWeights(
            alpha=db_weights.get("alpha", w.alpha),
            beta=db_weights.get("beta",   w.beta),
            gamma=db_weights.get("gamma", w.gamma),
            exclusion_threshold=db_weights.get("exclusion_threshold", w.exclusion_threshold),
        )

    return w.normalise()


def score_concept(
    dt_weight: float,
    capability_coverage: float,
    causal_centrality: float,
    weights: ScorerWeights,
) -> float:
    return round(
        weights.alpha * dt_weight
        + weights.beta  * capability_coverage
        + weights.gamma * causal_centrality,
        4,
    )
```

**Postgres table for system-learned weights:**

```sql
CREATE TABLE lexy_scorer_weights (
    domain_id           TEXT PRIMARY KEY,
    alpha               NUMERIC(5,4) NOT NULL,
    beta                NUMERIC(5,4) NOT NULL,
    gamma               NUMERIC(5,4) NOT NULL,
    exclusion_threshold NUMERIC(5,4) NOT NULL DEFAULT 0.30,
    sample_count        INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**Update cadence:** Nightly batch job. Requires ≥50 resolved conversations before the row is written.

### 7.5 Exclusion Record

A concept is excluded when `final_confidence < exclusion_threshold` OR `capability_coverage == 0.0` (hard gate).

```json
{
  "concept_id": "ilt_instructor_scheduling",
  "dt_weight": 0.12,
  "capability_coverage": 0.0,
  "causal_centrality": 0.05,
  "final_score": 0.06,
  "weights_used": {"alpha": 0.45, "beta": 0.40, "gamma": 0.15, "source": "manifest_prior"},
  "excluded": true,
  "exclusion_reason": "required: 0/1 — no connected source provides ilt.schedule_dimension",
  "gate_triggered": "capability_coverage_zero"
}
```

---

## 7.6 Cross-Domain Graph Assembly — LLM Clarification Protocol

### 7.6.1 Resolved Decision

**Decision:** When the LLM detects nodes spanning multiple active domains, it generates 1–3 clarifying questions with pre-populated recommended answers. The LLM handles the cross-domain graph reasoning autonomously — the questions confirm framing intent, not missing data.

**Why questions with recommended answers:** Cross-domain questions are ambiguous at the framing level, not the data level. "Which employees have both low training completion and high attrition risk?" is data-clear — the LLM knows which nodes to activate. What it cannot determine is whether to frame from an L&D perspective (fix training to reduce attrition) or HR perspective (identify flight-risk employees with compliance exposure). That framing determines which node is `terminal` and which direction Shapley flows — it changes output structure meaningfully. Pre-populated answers make this a single-click confirmation, not a free-text exchange.

### 7.6.2 Updated Assembly Prompt — PART D

The `_ASSEMBLY_SYSTEM_PROMPT` gains a PART D when `active_domains` has more than one entry:

```
PART D — CROSS-DOMAIN CLARIFICATION (only when nodes span >1 domain)

If you select nodes from more than one domain, generate 1–3 clarifying questions.
Requirements:
  - Each question resolves framing ambiguity (which terminal to optimise for)
  - Answerable by selecting one of 2–4 short options
  - Each option states its consequence in plain language
  - First option is the recommended default

Question format:
{
  "question_id": "q1",
  "question": "This spans LMS compliance and HR attrition. Which outcome is primary?",
  "options": [
    {
      "option_id": "a", "label": "Training completion — fix the compliance gap",
      "consequence": "Terminal = compliance_training_lms. Shapley flows from
        assignment overload toward compliance rate. HR data used as confounder.",
      "recommended": true
    },
    {
      "option_id": "b", "label": "Attrition risk — identify at-risk employees",
      "consequence": "Terminal = attrition_risk_hr. Shapley flows from manager
        engagement and training toward attrition. Compliance used as root signal.",
      "recommended": false
    }
  ]
}

Set clarification_questions = [] for single-domain questions.
```

### 7.6.3 Updated Assembly JSON Schema

```json
{
  "clarification_questions": [
    {
      "question_id": "q1",
      "question": "This spans LMS compliance and HR attrition. Which outcome matters most?",
      "options": [
        { "option_id": "a", "label": "Training completion", "consequence": "Terminal = compliance_training_lms.", "recommended": true },
        { "option_id": "b", "label": "Attrition risk",      "consequence": "Terminal = attrition_risk_hr.",     "recommended": false }
      ]
    }
  ],
  "selected_nodes": [ "..." ],
  "selected_edges": [ "..." ],
  "terminal_nodes": [ "..." ],
  "root_nodes":     [ "..." ],
  "hot_paths":      [ "..." ],
  "diagnosis":      "...",
  "coverage_note":  "..."
}
```

### 7.6.4 LangGraph Routing

```python
def vector_causal_graph_node(state):
    assembly = assemble_causal_graph_with_llm(question, nodes, edges, llm)
    questions = assembly.get("clarification_questions", [])
    if questions:
        state["pending_clarification_questions"] = questions
        state["causal_graph_clarification_required"] = True
        state.setdefault("messages", []).append(AIMessage(
            content="",
            additional_kwargs={"clarification_card": {
                "type": "cross_domain_framing",
                "title": "Help me frame this analysis",
                "subtitle": "Your question spans multiple data domains. Select the primary outcome.",
                "questions": questions,
                "action": "submit_clarification_answers",
            }},
        ))
        return state   # halt — routing sends to clarification handler
    state["causal_graph_clarification_required"] = False
    # ... rest of existing assembly logic
    return state


def apply_clarification_answers(state, answers):
    original = state.get("user_query", "")
    ctx = " | ".join(
        f"{q['question']} → {next(o['label'] for o in q['options'] if o['option_id'] == answers.get(q['question_id']))}"
        for q in state.get("pending_clarification_questions", [])
        if answers.get(q["question_id"])
    )
    state["user_query_with_framing"] = f"{original}\n\n[Framing: {ctx}]"
    state["causal_graph_clarification_required"] = False
    state["user_clarification_answers"] = answers
    return vector_causal_graph_node(state)  # re-run with augmented question


def route_after_causal_graph(state):
    if state.get("causal_graph_clarification_required"):
        return "cross_domain_clarification_node"
    if not state.get("adapter_conflict_resolved", True):
        return "capability_clarification_node"
    return "causal_context_extractor_node"
```

**State fields added:**

| Field | Type | Purpose |
|---|---|---|
| `pending_clarification_questions` | `List[Dict]` | LLM-generated cross-domain framing questions |
| `user_clarification_answers` | `Dict[str, str]` | `question_id → selected option_id` |
| `user_query_with_framing` | `str` | Original query augmented with user's framing choices |
| `causal_graph_clarification_required` | `bool` | Routing flag — pauses pipeline when True |

---

## 8. Changes Required to Existing Files

### 8.1 `causal_engine_state.py` → `lexy_pipeline_state.py`

**Rename** and replace the CSOD-specific TypedDict with a generic one. All existing CSOD fields move to a backward-compatible `csod_compat` namespace.

```python
class LexyPipelineState(TypedDict, total=False):

    # ── Domain (replaces vertical: str) ───────────────────────
    domain_classification: Dict[str, Any]   # output of classify_domains()
    active_domains: List[str]               # e.g. ["lms", "hr"]
    primary_domain: str
    domain_scores: Dict[str, float]
    vertical: str                           # COMPAT ALIAS → primary_domain

    # ── Capability resolution (NEW) ────────────────────────────
    connected_sources: List[str]            # e.g. ["csod", "workday"]
    capability_coverage: Dict[str, Dict]    # concept_id → CapabilityResolver result
    resolved_adapter_map: Dict[str, str]    # capability_id → source_id

    # ── Adapter conflict resolution (NEW §6.3.1) ──────────────
    pending_adapter_conflicts: List[Dict]   # conflicts waiting for user input
    user_adapter_selections: Dict[str, str] # capability_id → chosen source_id
    adapter_conflict_resolved: bool         # routing flag

    # ── Cross-domain clarification (NEW §7.6) ─────────────────
    pending_clarification_questions: List[Dict]  # LLM-generated framing questions
    user_clarification_answers: Dict[str, str]   # question_id → selected option_id
    user_query_with_framing: str                 # query augmented with framing context
    causal_graph_clarification_required: bool    # routing flag

    # ── Scorer weights (NEW §7.4) ──────────────────────────────
    scorer_weights: Dict[str, float]        # loaded by load_weights() — system-managed

    # ── Causal engine — unchanged field names ──────────────────
    proposed_nodes: List[Dict[str, Any]]
    proposed_edges: List[Dict[str, Any]]
    causal_graph: Dict[str, Any]
    graph_metadata: Dict[str, Any]

    # ── Bridge layer — unchanged ───────────────────────────────
    causal_signals: Dict[str, Any]
    causal_graph_boost_focus_areas: List[str]
    causal_graph_panel_data: Optional[Dict[str, Any]]
    causal_node_index: Dict[str, Dict[str, Any]]

    # ── Generic pipeline fields ────────────────────────────────
    user_query: str
    intent: Optional[str]
    intent_confidence: float
    feature_vector: Dict[str, Any]          # NEW — structured signal vector
    metric_recommendations: List[Dict[str, Any]]
    current_phase: str
    messages: List
    error: Optional[str]
```

### 8.2 `vector_causal_graph_builder.py`

**Three changes only:**

1. Replace `vertical: str = "lms"` with `domains: List[str]` in `retrieve_causal_nodes` and `retrieve_causal_edges`.

2. Replace `where_filter = {"vertical": vertical}` with a multi-value filter:
   ```python
   where_filter = {"domains": {"$in": domains + ["_shared"]}}
   ```

3. Replace `_ASSEMBLY_SYSTEM_PROMPT` header from `"enterprise LMS/HR analytics platform"` to `"enterprise analytics platform"`. Remove all LMS-specific examples from the prompt body. The prompt itself is already domain-agnostic — only the framing sentence needs updating.

4. In `vector_causal_graph_node`, replace:
   ```python
   vertical = state.get("causal_vertical", state.get("vertical", "lms"))
   ```
   with:
   ```python
   active_domains = state.get("active_domains") or [state.get("primary_domain", "lms")]
   ```

### 8.3 `causal_context_extractor.py`

The `_derive_focus_area` and `_category_to_focus_area` functions use hardcoded `if/elif` chains over category names. Replace with a lookup against node payload's `focus_areas` list, which is now stored directly in the vector store:

```python
# BEFORE — fragile string matching
def _derive_focus_area(terminal_nodes):
    category = terminal_nodes[0].get("category", "")
    if "compliance" in category.lower():
        return "compliance_posture"
    ...

# AFTER — direct payload lookup
def _derive_focus_area(terminal_nodes):
    if not terminal_nodes:
        return None
    primary = terminal_nodes[0]
    focus_areas = primary.get("focus_areas", [])
    return focus_areas[0] if focus_areas else "compliance_posture"
```

The `_derive_complexity` and `_derive_metric_profile` functions are unchanged — they operate on graph topology and temporal grains, which are already domain-agnostic.

### 8.4 `causal_graph_nodes.py`

Replace the `vertical` extraction:

```python
# BEFORE
vertical = state.get("causal_vertical", state.get("vertical", "lms"))

# AFTER
active_domains = state.get("active_domains") or [state.get("primary_domain", "lms")]
```

Add capability resolution step between graph assembly and context extraction:

```python
# After vector_causal_graph_node(state) returns:
from app.adapters.registry import AdapterRegistry, CapabilityResolver

connected_sources = state.get("connected_sources", ["csod"])
registry = AdapterRegistry()
registry.register(CSOD_ADAPTER)
registry.register(WORKDAY_ADAPTER)
# ... register any dynamically ingested CSV adapters

resolver = CapabilityResolver(registry, connected_sources)

# Resolve coverage for each proposed node
capability_coverage = {}
for node in state.get("causal_proposed_nodes", []):
    req = node.get("required_capabilities", [])
    opt = node.get("optional_capabilities", [])
    capability_coverage[node["node_id"]] = resolver.resolve(req, opt)

state["capability_coverage"] = capability_coverage
```

### 8.5 `metric_decision_tree.py`

Replace the hardcoded `VALID_OPTIONS` and `OPTION_TAGS` dictionaries with registry-driven lookups:

```python
# BEFORE — hardcoded per SOC2/HIPAA
VALID_OPTIONS = {
    "use_case": ["soc2_audit", "lms_learning_target", ...],
    "focus_area": ["access_control", "training_compliance", ...],
}

# AFTER — loaded from active domain manifests
def get_valid_options(active_domains: List[str]) -> Dict[str, List[str]]:
    from app.domains.registry import load_all_domain_manifests
    manifests = load_all_domain_manifests()
    
    use_cases, goals, focus_areas = set(), set(), set()
    for domain_id in active_domains:
        m = manifests.get(domain_id, {})
        dt_opts = m.get("dt_options", {})
        use_cases.add(dt_opts.get("use_case", ""))
        goals.update(dt_opts.get("goal_filter", []))
        focus_areas.update(dt_opts.get("focus_areas", []))
    
    # Always include cross-domain options
    use_cases.add("executive_dashboard")
    use_cases.add("operational_monitoring")
    
    return {
        "use_case":   sorted(use_cases - {""}),
        "goal":       sorted(goals),
        "focus_area": sorted(focus_areas),
        "audience":   [...],   # static, domain-agnostic
        "timeframe":  [...],   # static
        "metric_type": [...],  # static
    }
```

### 8.6 `control_domain_taxonomy.json`

This file is already well-structured for multi-framework support. The change is purely structural: move it under `app/domains/security/taxonomy.json` and extend it with framework codes that map to the node payload's `framework_codes` field.

Add a top-level `_framework_to_focus_area_map` key so the taxonomy is self-describing:

```json
{
  "_framework_to_focus_area_map": {
    "CC1": "training_compliance",
    "CC2": "training_compliance",
    "CC3": "vulnerability_management",
    "CC4": "audit_logging",
    "CC5": "access_control",
    "CC6": "access_control",
    "CC7": "incident_response",
    "CC8": "change_management",
    "CC9": "data_protection",
    "164.308(a)(5)": "training_compliance",
    "164.312(a)": "access_control",
    "164.312(b)": "audit_logging",
    "GOVERN": "training_compliance",
    "MAP": "vulnerability_management",
    "MEASURE": "audit_logging",
    "MANAGE": "incident_response"
  },
  "soc2": { ... },
  "hipaa": { ... },
  "nist_ai_rmf": { ... }
}
```

This map is used by `causal_context_extractor._category_to_focus_area` and by the node ingestion pipeline to auto-populate `focus_areas` from `framework_codes`.

---

## 9. New Components Required

### 9.1 `app/domains/registry.py`
Domain manifest loader with `@lru_cache`. See Section 3.3.

### 9.2 `app/agents/domain_classifier.py`
Multi-label domain scorer. See Section 4.1.

### 9.3 `app/capabilities/registry.yaml`
Static capability vocabulary. See Section 6.1.

### 9.4 `app/adapters/base.py`
`CapabilityMapping`, `SourceAdapterDeclaration`, `SourceAdapter` ABC. See Section 6.2.

### 9.5 `app/adapters/declarations.py`
Static adapter declarations for CSOD, Workday, CSV. See Section 6.2.

### 9.6 `app/adapters/registry.py`
`AdapterRegistry`, `CapabilityResolver`, `fingerprint_csv_capabilities`. See Section 6.3.

### 9.7 Node/Edge Ingestion Migration Script

```python
# scripts/migrate_nodes_edges_to_capability_schema.py
"""
One-time migration: adds required_capabilities and optional_capabilities
to existing node payloads, and adds source_capability / target_capability
to existing edge payloads.

Maps from existing 'category' strings using control_domain_taxonomy.json
and the new _framework_to_focus_area_map.

Run once after deploying the new schema.
"""
```

---

## 10. Vector Store Query Patterns

### 10.1 Single-domain query (unchanged behavior)

```python
# LMS-only question — identical to current behavior
results = await vector_store_client.query(
    collection_name="lexy_causal_nodes",
    query_texts=["compliance training completion rate gap"],
    n_results=20,
    where={"domains": {"$in": ["lms", "_shared"]}},
)
```

### 10.2 Multi-domain query (new capability)

```python
# LMS + HR cross-domain question
results = await vector_store_client.query(
    collection_name="lexy_causal_nodes",
    query_texts=["employees who failed SOC2 training and have high attrition risk"],
    n_results=25,
    where={"domains": {"$in": ["lms", "hr", "_shared"]}},
)
```

### 10.3 Capability-filtered query (concept coverage pre-check)

```python
# Find nodes that require a specific capability — for coverage pre-check
results = await vector_store_client.query(
    collection_name="lexy_causal_nodes",
    query_texts=["compliance deadline training"],
    n_results=20,
    where={
        "$and": [
            {"domains": {"$in": ["lms", "_shared"]}},
            {"required_capabilities": {"$contains": "deadline.dimension"}},
        ]
    },
)
```

### 10.4 Postgres structural adjacency (unchanged interface, updated schema)

```python
async def fetch_adjacent_edges_pg(
    conn_string: str,
    node_ids: List[str],
    active_domains: List[str],          # CHANGED: was vertical: str
    min_confidence: float = 0.45,
) -> List[Dict[str, Any]]:
    query = """
        SELECT * FROM lexy_causal_graph_edges
        WHERE (source_node_id = ANY($1) OR target_node_id = ANY($1))
          AND domains && $2                     -- array overlap
          AND confidence_score >= $3
        ORDER BY confidence_score DESC
        LIMIT 50
    """
    domains_with_shared = active_domains + ["_shared"]
    # ... execute query
```

---

## 11. State Flow — End-to-End with Generic Architecture

```
Stage 1: Intent Classification
  Input:  user_query
  Output: intent, confidence, feature_vector, routing

Stage 1.5: Domain Classification  [NEW]
  Input:  user_query, intent, feature_vector
  Output: domain_scores, active_domains, primary_domain
          (state["vertical"] = primary_domain for compat)

Stage 2: Concept Mapping
  2a. DT Router
      Input:  feature_vector + active_domain manifests
      Output: candidate_concepts with DT weights

  2b. Vector Retrieval (nodes + edges)
      Input:  enriched_query, active_domains
      Output: retrieved_nodes, retrieved_edges (multi-domain)

  2c. LLM Assembly
      Input:  question, retrieved_nodes, retrieved_edges
      Output: proposed_nodes, proposed_edges, causal_graph

  2d. Capability Resolution  [NEW]
      Input:  proposed_nodes.required_capabilities, connected_sources
      Output: capability_coverage per node

  2e. Confidence Scoring
      Input:  DT_weight, capability_coverage, causal_centrality
      Output: final_concept_set (ranked, coverage-gated, causal-ordered)
              excluded_concepts (machine-readable reasons)

Stage 3: Schema Retrieval
  Input:  final_concept_set, capability_coverage.capability_map
  Output: resolved source expressions per concept
          (replaces raw table name lookup with capability → column path)

Stage 4: Metric Resolution
  Input:  resolved source expressions, DT decisions
  Output: dt_scored_metrics, dt_metric_groups

Stage 5: Response Assembly
  Input:  dt_scored_metrics, causal_graph_panel_data, capability_coverage
  Output: output (inline_analysis | dashboard | alert)
```

---

## 12. Adding a New Domain — Step-by-Step

No Python changes are required. The complete registration is:

1. Create `app/domains/{domain_id}/manifest.yaml` with classifier signals, concept list, shared concepts, and DT option hints.

2. Create concept manifests in `app/domains/{domain_id}/concepts/` — one YAML file per concept with `required_capabilities` and `causal_edges_out`.

3. Create adapter declaration in `app/adapters/declarations.py` (if a new source system is being connected), or map to existing capabilities if the domain's data comes from an already-connected source.

4. Ingest seed nodes and edges into the vector store:
   ```bash
   python scripts/ingest_domain_nodes.py --domain finance \
       --nodes app/domains/finance/seed_nodes.json \
       --edges app/domains/finance/seed_edges.json
   ```
   This script calls `ingest_nodes()` and `ingest_edges()` from `vector_causal_graph_builder.py`, which is already domain-agnostic.

5. Add framework codes to `app/domains/security/taxonomy.json` if the domain uses a compliance framework. Otherwise skip.

6. Restart the application. The domain classifier picks up the new manifest on next cold start via `@lru_cache`.

---

## 13. Backward Compatibility

| Existing field | Change | Compatibility guarantee |
|---|---|---|
| `state["vertical"]` | Now an alias for `state["primary_domain"]` | All existing reads continue to work |
| `state["csod_intent"]` | Retained as a CSOD-specific field in compat namespace | No breakage |
| `retrieve_causal_nodes(vertical="lms")` | Signature gains `domains: List[str]` kwarg, `vertical` deprecated but still accepted | Both call signatures work during transition |
| `control_domain_taxonomy.json` | Moved to `app/domains/security/taxonomy.json`, same structure | Existing imports updated via path alias |
| `NODE_COLLECTION = "cce_causal_edges"` | Renamed to `"lexy_causal_edges"` | Migration script handles re-indexing |
| `EDGE_COLLECTION = "cce_causal_nodes"` | Renamed to `"lexy_causal_nodes"` | Migration script handles re-indexing |

---

## 14. Open Questions

| # | Question | Recommended approach |
|---|---|---|
| 1 | How should a node that belongs to multiple domains (e.g., `engagement_signal` appears in both LMS and HR) be stored — one record or two? | **RESOLVED (v1.1.0):** One record with `domains: ["lms", "hr"]` and a `domain_context` map per domain. No domain suffix in `node_id`. LLM assembly reads the `domain_context` field and selects the contextually correct causal role. Embedding covers both domain meanings in a single doc text. See §5.1.1. |
| 2 | What happens when the capability resolver finds multiple adapters that satisfy the same capability (e.g., both CSOD and Workday provide `completion.rate`)? | **RESOLVED (v1.2.0):** Pipeline pauses. `CapabilityResolver.resolve()` returns a non-empty `adapter_conflicts` list. `capability_resolution_node` emits a structured choice card to the user with all alternatives listed and the domain-manifest-priority adapter pre-selected as the recommended default. The user makes one selection per conflicting capability, then the pipeline resumes. See §6.3.1. |
| 3 | For CSV uploads, should fingerprinted capabilities persist beyond the conversation? | **RESOLVED (v1.2.0):** CSVs are ingested server-side by admin or integration pipeline — not uploaded per session. Fingerprinted mappings are written to `lexy_registered_adapters` in Postgres and loaded into `AdapterRegistry` at startup (TTL: 5min refresh). They are durable across all conversations for the tenant, identical to any API-backed adapter. Value-distribution validation (`_validate_capability_sample`) runs before persistence to reduce false-positive fingerprinting. See §6.3.2. |
| 4 | Should the confidence scorer's `α/β/γ` weights be tunable per domain manifest? | **RESOLVED (v1.2.0):** Yes, per manifest — but system-managed, not user-changed. Weights are loaded in priority order: (1) system-learned weights from nightly Bayesian update stored in `lexy_scorer_weights` Postgres table; (2) domain manifest static prior; (3) global defaults `α=0.50, β=0.35, γ=0.15`. The nightly batch requires ≥50 resolved conversations before writing a system-learned row. Below that threshold the manifest prior or global default is used. See §7.2–§7.4. |
| 5 | How does the LLM assembly prompt handle cross-domain graphs where nodes from different domains interact? | **RESOLVED (v1.2.0):** LLM decides the graph autonomously but surfaces 1–3 clarifying questions with recommended pre-selected answers when nodes span >1 active domain. Questions resolve framing ambiguity (which node is `terminal`, which direction Shapley flows) via a single-click choice card. The user's selection is injected into the augmented query for a re-run of assembly. Single-domain questions receive `clarification_questions = []` and proceed without interruption. See §7.6. |
