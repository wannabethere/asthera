# MDL Knowledge Graph Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER QUERY INTERFACE                                │
│  "Show me tables with vulnerability data in Snyk"                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MDL CONTEXT BREAKDOWN AGENT                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Detect query type (table, column, feature, metric, etc.)         │   │
│  │  • Identify entity types needed                                     │   │
│  │  • Select appropriate ChromaDB collections                          │   │
│  │  • Build metadata filters (product, category, etc.)                 │   │
│  │  • Generate search questions                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STORE MAPPING CONFIGURATION                             │
│                   (app/config/mdl_store_mapping.py)                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EntityType.TABLE → Collection: "mdl_tables"                        │   │
│  │                  → PostgreSQL: "mdl_tables"                          │   │
│  │  Metadata Filters: {product_name, category_name, is_fact_table}    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HYBRID SEARCH SERVICE                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Dense Vector Search (ChromaDB)                                  │   │
│  │     • Semantic similarity via embeddings                            │   │
│  │     • Query: "tables with vulnerability data"                       │   │
│  │     • Top K candidates: 10                                          │   │
│  │                                                                      │   │
│  │  2. Sparse BM25 Ranking                                            │   │
│  │     • Keyword matching                                              │   │
│  │     • Term frequency analysis                                       │   │
│  │                                                                      │   │
│  │  3. Metadata Filtering                                             │   │
│  │     • Filter: product_name = "Snyk"                                 │   │
│  │     • Filter: category_name = "vulnerabilities"                     │   │
│  │                                                                      │   │
│  │  4. Combined Scoring                                               │   │
│  │     • Weight: 70% semantic + 30% keyword                            │   │
│  │     • Normalize and rank                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────────┐       ┌──────────────────────┐
        │   CHROMADB (VECTOR)   │       │   POSTGRESQL (RDBMS) │
        │                       │       │                      │
        │  mdl_products         │       │  mdl_products        │
        │  mdl_categories       │       │  mdl_categories      │
        │  mdl_tables ◄─────────┼───────┼─►mdl_tables          │
        │  mdl_columns          │       │  mdl_columns         │
        │  mdl_relationships    │       │  mdl_relationships   │
        │  mdl_features         │       │  mdl_features        │
        │  mdl_metrics          │       │  mdl_metrics         │
        │  mdl_examples         │       │  mdl_examples        │
        │  mdl_instructions     │       │  mdl_instructions    │
        │  mdl_insights         │       │  mdl_insights        │
        │  mdl_time_concepts    │       │  mdl_time_concepts   │
        │  mdl_calculated_cols  │       │  mdl_calculated_cols │
        │  mdl_business_funcs   │       │  mdl_business_funcs  │
        │  mdl_frameworks       │       │  mdl_frameworks      │
        │  mdl_ownership        │       │  mdl_ownership       │
        │  mdl_contextual_edges │       │  mdl_contextual_edges│
        │                       │       │                      │
        │  (Semantic Search)    │       │  (Structured Queries)│
        └───────────────────────┘       └──────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEARCH RESULTS                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Table: "Vulnerability"                                             │   │
│  │  Category: "vulnerabilities"                                        │   │
│  │  Description: "Stores vulnerability scan results..."               │   │
│  │  Score: 0.92                                                        │   │
│  │  ────────────────────────────────────────────────────────────────  │   │
│  │  Table: "AssetVulnerability"                                       │   │
│  │  Category: "assets"                                                 │   │
│  │  Description: "Maps assets to vulnerabilities..."                  │   │
│  │  Score: 0.87                                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EDGE DISCOVERY (Optional)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Query mdl_contextual_edges collection:                            │   │
│  │  • Find relationships FROM discovered tables                        │   │
│  │  • Filter by edge_type: TABLE_RELATES_TO_TABLE                     │   │
│  │  • Get 20+ candidate edges                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MDL EDGE PRUNING AGENT                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • Apply edge type priorities (critical > high > medium > low)      │   │
│  │  • LLM-based relevance scoring                                      │   │
│  │  • Context-aware filtering                                          │   │
│  │  • Return top 10 most relevant edges                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FINAL RESULTS WITH EDGES                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Tables: ["Vulnerability", "AssetVulnerability"]                   │   │
│  │  Edges:                                                             │   │
│  │    • Vulnerability ─[HAS_COLUMN]─> severity                        │   │
│  │    • Vulnerability ─[TABLE_RELATES_TO]─> AssetVulnerability       │   │
│  │    • AssetVulnerability ─[BELONGS_TO_CATEGORY]─> assets           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Hierarchy Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             PRODUCT LEVEL                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Product: Snyk                                                    │   │
│  │  • product_id, product_name, description                          │   │
│  │  • vendor, api_endpoints, data_sources                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   CATEGORY LEVEL     │ │  FEATURE LEVEL   │ │ FRAMEWORK LEVEL  │
│  ┌────────────────┐  │ │ ┌──────────────┐ │ │ ┌──────────────┐ │
│  │ 15 Categories: │  │ │ │ Features:    │ │ │ │ Frameworks:  │ │
│  │ • assets       │  │ │ │ • Vuln Scan  │ │ │ │ • SOC2       │ │
│  │ • vulnerabil.. │  │ │ │ • Access Ctl │ │ │ │ • HIPAA      │ │
│  │ • projects     │  │ │ │ • Risk Mgmt  │ │ │ │ • GDPR       │ │
│  │ • ...          │  │ │ └──────────────┘ │ │ └──────────────┘ │
│  └────────────────┘  │ └──────────────────┘ └──────────────────┘
└──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          TABLE LEVEL                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Table: AssetAttributes                                         │ │
│  │  • table_id, table_name, schema_name                           │ │
│  │  • semantic_description, table_purpose, business_context       │ │
│  │  • category_id → "assets"                                       │ │
│  │  • primary_key, is_fact_table, data_volume_estimate           │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ COLUMN LEVEL │  │RELATIONSHIP  │  │TIME CONCEPTS │  │  INSIGHTS    │
│              │  │    LEVEL     │  │    LEVEL     │  │    LEVEL     │
│┌────────────┐│  │┌────────────┐│  │┌────────────┐│  │┌────────────┐│
││ Columns:   ││  ││Relationships││  ││Time Dims:  ││  ││Insights:   ││
││ • id       ││  ││• One-to-Many││  ││• created_at││  ││• Metrics   ││
││ • status   ││  ││• Many-to-..│││  ││• updated_at││  ││• Features  ││
││ • attrs    ││  ││• Belongs-to││  ││• event_time││  ││• Concepts  ││
│└────────────┘│  │└────────────┘│  │└────────────┘│  │└────────────┘│
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ METRIC LEVEL │  │ EXAMPLE LEV. │  │ INSTRUCTION  │  │ BUSINESS     │
│              │  │              │  │    LEVEL     │  │  FUNCTION    │
│┌────────────┐│  │┌────────────┐│  │┌────────────┐│  │┌────────────┐│
││ Metrics:   ││  ││Examples:   ││  ││Instructions││  ││Functions:  ││
││ • Count    ││  ││• Query 1   ││  ││• Best Prac.││  ││• Sec Monit.││
││ • Avg Time ││  ││• Query 2   ││  ││• Constraints││  ││• Compl Rep.││
││ • Risk Scr ││  ││• Natural Q ││  ││• Optimizat.││  ││• Risk Mgmt ││
│└────────────┘│  │└────────────┘│  │└────────────┘│  │└────────────┘│
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

## Edge Type Priority Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EDGE TYPE PRIORITIES                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  CRITICAL PRIORITY (Score: 1.0)                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • COLUMN_BELONGS_TO_TABLE                                        │  │
│  │  • TABLE_BELONGS_TO_CATEGORY                                      │  │
│  │  • TABLE_RELATES_TO_TABLE                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  HIGH PRIORITY (Score: 0.8)                                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • TABLE_HAS_FEATURE                                              │  │
│  │  • FEATURE_SUPPORTS_CONTROL                                       │  │
│  │  • METRIC_FROM_TABLE                                              │  │
│  │  • EXAMPLE_USES_TABLE                                             │  │
│  │  • CATEGORY_BELONGS_TO_PRODUCT                                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  MEDIUM PRIORITY (Score: 0.6)                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • TABLE_FOLLOWS_INSTRUCTION                                      │  │
│  │  • INSIGHT_USES_TABLE                                             │  │
│  │  • BUSINESS_FUNCTION_USES_TABLE                                   │  │
│  │  • TABLE_HAS_COLUMN                                               │  │
│  │  • COLUMN_REFERENCES_COLUMN                                       │  │
│  │  • COLUMN_IS_TIME_DIMENSION                                       │  │
│  │  • COLUMN_SUPPORTS_KPI                                            │  │
│  │  • METRIC_USES_COLUMN                                             │  │
│  │  • FEATURE_USES_TABLE                                             │  │
│  │  • FEATURE_USES_COLUMN                                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  LOW PRIORITY (Score: 0.4)                                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • OWNERSHIP_FOR_TABLE                                            │  │
│  │  • FRAMEWORK_MAPS_TO_TABLE                                        │  │
│  │  • PRODUCT_HAS_CATEGORY                                           │  │
│  │  • COLUMN_DERIVED_FROM                                            │  │
│  │  • CALCULATED_COLUMN_DERIVED_FROM                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Store Mapping Flow Diagram

```
┌──────────────────────┐
│   Entity Type        │
│   (from query)       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│          mdl_store_mapping.py Configuration                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  EntityType.TABLE                                          │  │
│  │    ↓                                                       │  │
│  │  StoreMapping(                                             │  │
│  │    chroma_collection = "mdl_tables"                       │  │
│  │    postgres_table = "mdl_tables"                          │  │
│  │    primary_key = "table_id"                               │  │
│  │    supports_hybrid_search = True                          │  │
│  │  )                                                         │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
           │
           ├─────────────────────────┬──────────────────────────┐
           ▼                         ▼                          ▼
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│  get_chroma_       │   │  get_postgres_     │   │  supports_hybrid_  │
│  collection()      │   │  table()           │   │  search()          │
│                    │   │                    │   │                    │
│  Returns:          │   │  Returns:          │   │  Returns:          │
│  "mdl_tables"      │   │  "mdl_tables"      │   │  True              │
└────────────────────┘   └────────────────────┘   └────────────────────┘
           │                         │                          │
           └─────────────────────────┴──────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   HybridSearchService                                   │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Initialize with:                                                 │ │
│  │  • collection_name = "mdl_tables"                                │ │
│  │  • vector_store_client (ChromaDB)                                │ │
│  │                                                                   │ │
│  │  Query both:                                                      │ │
│  │  • ChromaDB collection: "mdl_tables" (semantic search)           │ │
│  │  • PostgreSQL table: "mdl_tables" (metadata filters)             │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

## Query Pattern Flow Diagram

```
User Question: "Show me asset tables with vulnerability information"
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Step 1: Context Breakdown                               │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  MDLContextBreakdownAgent detects:                            │  │
│  │  • Query Type: "table_discovery"                              │  │
│  │  • Entity Types: [TABLE, CATEGORY]                            │  │
│  │  • Collections: ["mdl_tables", "mdl_categories"]              │  │
│  │  • Metadata Filters: {                                        │  │
│  │      product_name: "Snyk",                                    │  │
│  │      category_name: ["assets", "vulnerabilities"]            │  │
│  │    }                                                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Step 2: Hybrid Search (Tables)                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Collection: "mdl_tables"                                      │  │
│  │  Query: "asset tables with vulnerability information"         │  │
│  │  Filters: {product_name: "Snyk", category_name: "assets"}    │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  Results:                                                      │  │
│  │  1. AssetAttributes (score: 0.89)                            │  │
│  │  2. AssetVulnerability (score: 0.87)                         │  │
│  │  3. Asset (score: 0.82)                                       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Step 3: Edge Discovery                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Collection: "mdl_contextual_edges"                           │  │
│  │  Query: "relationships to vulnerability tables"               │  │
│  │  Filters: {                                                    │  │
│  │    source_entity_id: ["AssetAttributes", ...],                │  │
│  │    edge_type: "TABLE_RELATES_TO_TABLE"                        │  │
│  │  }                                                             │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  Results: 15 edges discovered                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Step 4: Edge Pruning                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  MDLEdgePruningAgent:                                          │  │
│  │  • Apply priority scoring                                      │  │
│  │  • LLM-based relevance filtering                              │  │
│  │  • Context-aware selection                                     │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  Pruned to 5 most relevant edges                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Step 5: Final Results                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tables:                                                       │  │
│  │  • AssetAttributes → category: "assets"                       │  │
│  │  • AssetVulnerability → category: "assets"                    │  │
│  │  • Asset → category: "assets"                                 │  │
│  │                                                                │  │
│  │  Relationships:                                                │  │
│  │  • Asset ─[TABLE_RELATES_TO]─> AssetVulnerability            │  │
│  │  • AssetVulnerability ─[TABLE_RELATES_TO]─> Vulnerability    │  │
│  │  • Asset ─[HAS_COLUMN]─> vulnerability_count                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                      INDEXING PHASE                                 │
└────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Snyk MDL File (snyk_mdl1.json)                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ {                                                               │ │
│  │   "catalog": "api",                                            │ │
│  │   "schema": "public",                                          │ │
│  │   "models": [                                                  │ │
│  │     {                                                           │ │
│  │       "name": "AccessRequest",                                 │ │
│  │       "columns": [...],                                        │ │
│  │       "properties": {...}                                      │ │
│  │     }                                                           │ │
│  │   ]                                                             │ │
│  │ }                                                               │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MDL Extractors (7 extractors)                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  1. MDLTableExtractor → Extract table entities                 │ │
│  │  2. MDLCategoryExtractor → Map to 15 categories                │ │
│  │  3. MDLRelationshipExtractor → Extract relationships           │ │
│  │  4. MDLFeatureExtractor → Extract features                     │ │
│  │  5. MDLMetricExtractor → Extract metrics                       │ │
│  │  6. MDLExampleExtractor → Extract examples                     │ │
│  │  7. MDLInstructionExtractor → Extract instructions             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
┌────────────────────────┐    ┌────────────────────────┐
│  ChromaDB Collections  │    │  PostgreSQL Tables     │
│  ┌──────────────────┐  │    │  ┌──────────────────┐  │
│  │ mdl_products     │  │    │  │ mdl_products     │  │
│  │ mdl_categories   │  │    │  │ mdl_categories   │  │
│  │ mdl_tables       │  │    │  │ mdl_tables       │  │
│  │ mdl_columns      │  │    │  │ mdl_columns      │  │
│  │ mdl_features     │  │    │  │ mdl_features     │  │
│  │ mdl_metrics      │  │    │  │ mdl_metrics      │  │
│  │ mdl_examples     │  │    │  │ mdl_examples     │  │
│  │ mdl_instructions │  │    │  │ mdl_instructions │  │
│  │ ...              │  │    │  │ ...              │  │
│  └──────────────────┘  │    │  └──────────────────┘  │
└────────────────────────┘    └────────────────────────┘
                            │
┌────────────────────────────────────────────────────────────────────┐
│                      QUERY PHASE                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Component Integration Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                  COMPONENT INTEGRATION MAP                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────┐         ┌──────────────────────┐           │
│  │  User Interface    │────────►│  MDL Context         │           │
│  │  (API/CLI)         │         │  Breakdown Agent     │           │
│  └────────────────────┘         └──────────┬───────────┘           │
│                                            │                         │
│                                            ▼                         │
│  ┌────────────────────┐         ┌──────────────────────┐           │
│  │  Store Mapping     │◄────────│  Query Pattern       │           │
│  │  Configuration     │         │  Identification      │           │
│  └────────┬───────────┘         └──────────────────────┘           │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────┐              │
│  │         HybridSearchService                      │              │
│  │  ┌────────────────┐     ┌────────────────────┐  │              │
│  │  │  ChromaDB      │     │  PostgreSQL        │  │              │
│  │  │  Vector Search │     │  Structured Query  │  │              │
│  │  └────────────────┘     └────────────────────┘  │              │
│  └──────────────────────────────────────────────────┘              │
│           │                                                          │
│           ▼                                                          │
│  ┌────────────────────┐         ┌──────────────────────┐           │
│  │  Search Results    │────────►│  MDL Edge            │           │
│  │  (Tables, etc.)    │         │  Discovery           │           │
│  └────────────────────┘         └──────────┬───────────┘           │
│                                            │                         │
│                                            ▼                         │
│  ┌────────────────────┐         ┌──────────────────────┐           │
│  │  Final Results     │◄────────│  MDL Edge            │           │
│  │  with Edges        │         │  Pruning Agent       │           │
│  └────────────────────┘         └──────────────────────┘           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

**Note:** All diagrams are represented in ASCII art for maximum compatibility. For visual rendering, consider converting to tools like Mermaid, PlantUML, or draw.io.
