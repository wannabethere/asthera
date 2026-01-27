# Graph Reasoning and Assistance Architecture

This document explains how the contextual graph reasoning system works and how the data/knowledge assistance nodes operate.

## Table of Contents

1. [Overview](#overview)
2. [Contextual Graph Reasoning System](#contextual-graph-reasoning-system)
   - [Retrieval Agent](#retrieval-agent)
   - [Reasoning Agent](#reasoning-agent)
   - [Context Breakdown Service](#context-breakdown-service)
3. [Data Assistance Nodes](#data-assistance-nodes)
4. [Knowledge Assistance Nodes](#knowledge-assistance-nodes)
5. [Complete Flow Example](#complete-flow-example)

---

## Overview

The system uses a **two-phase approach** for answering questions:

1. **Contextual Graph Reasoning**: Retrieves relevant contexts and performs multi-hop reasoning through a knowledge graph
2. **Assistance Nodes**: Specialized nodes that use the reasoning results to provide domain-specific answers

The architecture follows this pattern:
```
User Query
    ↓
Context Breakdown (enhances query understanding)
    ↓
Context Retrieval (finds relevant contexts)
    ↓
Reasoning Plan Creation (determines reasoning steps)
    ↓
Multi-Hop Reasoning (traverses graph)
    ↓
Enrichment (adds data from all stores)
    ↓
Assistance Nodes (domain-specific processing)
    ↓
Final Answer
```

---

## Contextual Graph Reasoning System

### Retrieval Agent

**File**: `contextual_graph_retrieval_agent.py`

The retrieval agent is responsible for:
- Finding relevant contexts for a query
- Creating reasoning plans
- Discovering and pruning edges
- Getting entities from edges

#### Step-by-Step: Context Retrieval

```python
async def retrieve_contexts(query, context_ids, top_k=5)
```

**Steps:**

1. **Context Breakdown** (if enabled):
   - Uses `ContextBreakdownService` to analyze the query
   - Extracts:
     - Compliance context (SOC2, HIPAA, etc.)
     - Action context (what user wants to do)
     - Identified entities (controls, requirements, evidence)
     - Query keywords
   - Enhances the query with extracted information
   - Adds metadata filters (e.g., framework filters)

2. **Context Search**:
   - If specific `context_ids` provided: Retrieves those contexts directly
   - Otherwise: Searches all contexts using enhanced query
   - Uses `contextual_graph_service.search_contexts()`

3. **Context Enrichment**:
   - Adds metadata (edges count, controls count, entity types)
   - Enriches with multi-store data if `collection_factory` available
   - Calculates completeness scores

4. **Returns**: List of enriched contexts with relevance scores

#### Step-by-Step: Reasoning Plan Creation

```python
async def create_reasoning_plan(user_action, retrieved_contexts, target_domain, schema_info)
```

**Steps:**

1. **Context Breakdown** (if enabled):
   - Analyzes user action to understand intent
   - Extracts compliance context, action context, entities, edge types

2. **Context Summarization**:
   - Prepares context summaries with:
     - Context IDs, types, industries
     - Regulatory frameworks
     - Maturity levels
     - Relevance scores

3. **LLM-Based Plan Generation**:
   - Uses LLM to create reasoning steps
   - Considers:
     - Context breakdown information
     - Available database schemas (if provided)
     - Multi-store knowledge hierarchy
   - **Critical for data queries**: Always includes schema/table retrieval steps

4. **Plan Structure**:
   ```json
   {
     "reasoning_steps": [
       {
         "step_number": 1,
         "step_type": "context_search",
         "description": "...",
         "stores_to_query": ["schemas", "compliance", "risks"],
         "consider_schemas": true,
         "table_retrieval_needed": true
       }
     ],
     "context_priorities": [...],
     "strategy": "...",
     "expected_outputs": [...]
   }
   ```

5. **Returns**: Complete reasoning plan with steps and strategy

#### Step-by-Step: Edge Discovery and Pruning

```python
async def discover_and_prune_edges(user_question, context_id, top_k=10)
```

**Steps:**

1. **Context Breakdown**:
   - Breaks down user question into context components
   - Identifies entities and their queries

2. **Edge Discovery**:
   - For each identified entity:
     - Generates entity-specific queries from `vector_store_prompts.json`
     - Searches for edges using `discover_edges_by_context()`
     - Applies metadata filters (framework, context_id, etc.)
   - Collects all discovered edges

3. **Edge Deduplication**:
   - Removes duplicate edges by `edge_id`

4. **Edge Pruning**:
   - Uses `EdgePruningService` with LLM to select best edges
   - Considers:
     - User question relevance
     - Context breakdown information
     - Edge types and relevance scores
   - Returns top `top_k` edges

5. **Returns**: Pruned edges with context breakdown metadata

---

### Reasoning Agent

**File**: `contextual_graph_reasoning_agent.py`

The reasoning agent performs:
- Multi-hop contextual reasoning
- Context-aware control prioritization
- Context-dependent property inference
- Multi-context synthesis

#### Step-by-Step: Multi-Hop Reasoning

```python
async def reason_with_context(query, context_id, max_hops=3)
```

**Steps:**

1. **Query Enhancement**:
   - Uses context breakdown to enhance query
   - Extracts keywords, entities, frameworks
   - Creates enhanced search query

2. **Multi-Hop Query**:
   - Calls `contextual_graph_service.multi_hop_query()`
   - This performs:
     - **Hop 1**: Find relevant controls in context
     - **Hop 2**: Find requirements for those controls
     - **Hop 3**: Find evidence types for those requirements
   - Each hop uses vector similarity search within the context

3. **Reasoning Path Enrichment**:
   - For each hop in reasoning path:
     - Gets requirements for controls
     - Gets contextual edges
     - Gets risk analytics
     - Gets evidence types

4. **Multi-Store Enrichment** (if available):
   - Searches all stores (connectors, domains, compliance, risks, schemas, features)
   - Adds store results to each hop

5. **Context Insights Generation**:
   - Uses LLM to generate context-specific insights
   - Explains why answer is specific to this context
   - Highlights context-dependent factors

6. **Returns**: 
   - Reasoning path (enriched hops)
   - Final answer
   - Context insights
   - Context breakdown (if available)

#### Step-by-Step: Table Suggestions

```python
async def suggest_relevant_tables(query, context_id, project_id, top_k=10)
```

**Steps:**

1. **Query Enhancement**:
   - Uses context breakdown to enhance query
   - Checks reasoning plan for schema retrieval needs
   - Combines enhanced query with reasoning plan context

2. **Context Information**:
   - Gets context definition
   - Extracts regulatory frameworks

3. **Entity Search**:
   - Searches `entities` collection for table-like entities
   - Searches `table_definitions` collection
   - Uses enhanced query with context information

4. **LLM-Based Suggestions**:
   - Uses LLM to analyze query and context
   - Suggests tables based on:
     - Query intent
     - Context domain and frameworks
     - Common table patterns
     - Table relationships

5. **Merge and Deduplicate**:
   - Combines search results with LLM suggestions
   - Deduplicates by table name
   - Sorts by relevance score

6. **Returns**: List of suggested tables with reasoning

#### Step-by-Step: Priority Controls

```python
async def get_priority_controls(context_id, query, filters, top_k=10)
```

**Steps:**

1. **Query Enhancement**:
   - Uses context breakdown to enhance query
   - Adds framework filters from breakdown

2. **Control Retrieval**:
   - Calls `contextual_graph_service.get_priority_controls()`
   - Gets controls prioritized by context relevance

3. **Control Enrichment**:
   - For each control:
     - Gets requirements from `requirement_service`
     - Gets contextual edges from `vector_storage`
     - Gets evidence types from edges
     - Gets measurements from `measurement_service`
     - Gets risk analytics
   - Adds context-specific reasoning

4. **Multi-Store Enrichment** (if available):
   - Searches all stores for related entities
   - Adds store connections to controls

5. **Returns**: Enriched controls with all available data

---

### Context Breakdown Service

**Purpose**: Enhances query understanding by breaking down user questions into structured components.

**Key Components Extracted**:

1. **Compliance Context**: Which frameworks (SOC2, HIPAA, etc.)
2. **Action Context**: What action user wants (find, check, assess)
3. **Product Context**: Which products mentioned (Snyk, Okta, etc.)
4. **User Intent**: High-level goal
5. **Identified Entities**: Relevant entity types (controls, requirements, evidence)
6. **Entity Sub-Types**: Specific sub-types (soc2_controls, hipaa_controls)
7. **Edge Types**: Relevant edge types (HAS_REQUIREMENT_IN_CONTEXT, PROVED_BY)
8. **Query Keywords**: Key terms for vector search

**How It Works**:

1. Uses LLM to analyze user question
2. Extracts structured information using prompts
3. Generates enhanced search queries
4. Creates metadata filters
5. Generates entity-specific queries from `vector_store_prompts.json`

**Benefits**:
- Better query understanding
- More precise vector searches
- Framework-aware filtering
- Entity-specific query generation

---

## Data Assistance Nodes

**File**: `data_assistance_nodes.py`

These nodes handle data-related queries: schemas, metrics, controls, and features.

### DataKnowledgeRetrievalNode

**Purpose**: Retrieves schemas, metrics, controls, and features for data assistance.

#### Step-by-Step Process

```python
async def __call__(state: ContextualAssistantState)
```

**Steps:**

1. **Extract Inputs**:
   - Gets query, project_id, context_ids from state
   - Uses context_ids from framework's context retrieval (already retrieved)

2. **Framework Extraction**:
   - Extracts compliance framework from query or user_context
   - Examples: SOC2, GDPR, HIPAA

3. **Table Suggestions** (if available):
   - Uses `suggested_tables` from contextual reasoning (if in state)
   - Extracts table names from suggestions
   - Logs table suggestion strategy

4. **Database Schema Retrieval**:
   - Calls `retrieval_helper.get_database_schemas()`
   - Passes suggested table names if available
   - Retrieves:
     - Table DDLs
     - Column definitions
     - Table relationships
   - Logs which tables were matched

5. **Metrics Retrieval**:
   - Calls `retrieval_helper.get_metrics()`
   - Gets existing metrics for the project

6. **Features Extraction**:
   - Extracts features from `reasoning_path` (if available)
   - Searches `features` collection directly if `collection_factory` available
   - Builds filters (framework, context_id)
   - Combines and deduplicates features

7. **Controls Retrieval**:
   - Uses context_ids from framework
   - Searches controls using `contextual_graph_service.search_controls()`
   - Filters by framework and context_id
   - Falls back to finding contexts if framework didn't retrieve any

8. **Store in State**:
   ```python
   state["data_knowledge"] = {
       "schemas": [...],
       "metrics": [...],
       "controls": [...],
       "features": [...],
       "framework": "SOC2",
       "project_id": "..."
   }
   ```

9. **Set Next Node**: `data_assistance_qa`

### MetricGenerationNode

**Purpose**: Generates new metrics based on schema definitions and control requirements.

#### Step-by-Step Process

```python
async def __call__(state: ContextualAssistantState)
```

**Steps:**

1. **Check if Generation Needed**:
   - Analyzes query for generation keywords ("generate", "create", "new metric")
   - Checks if controls present but no relevant metrics exist

2. **Format Context**:
   - Formats schemas for prompt (table DDLs)
   - Formats existing metrics
   - Formats controls with descriptions

3. **LLM-Based Generation**:
   - Uses LLM to generate metrics based on:
     - Available database schemas
     - Existing metrics (to avoid duplicates)
     - Compliance control requirements
   - Generates:
     - Metric name (snake_case)
     - Display name
     - Description
     - SQL query (`metric_sql`)
     - Metric type (count, sum, avg, percentage, ratio)
     - Aggregation type (daily, monthly, total)
     - Relevance to controls
     - Confidence level

4. **Store in State**:
   ```python
   state["generated_metrics"] = [
       {
           "name": "access_failure_rate",
           "display_name": "Access Failure Rate",
           "description": "...",
           "metric_sql": "SELECT ...",
           ...
       }
   ]
   ```

5. **Set Next Node**: `data_assistance_qa`

### DataAssistanceQANode

**Purpose**: Answers data assistance questions using retrieved knowledge.

#### Step-by-Step Process

```python
async def __call__(state: ContextualAssistantState)
```

**Steps:**

1. **Extract Knowledge**:
   - Gets schemas, metrics, controls, features from `data_knowledge`
   - Extracts features from `reasoning_path` if not in data_knowledge

2. **Format Context Summaries**:
   - `schema_summary`: Formatted table DDLs
   - `metrics_summary`: Existing + generated metrics
   - `controls_summary`: Controls with descriptions
   - `features_summary`: Features grouped by type
   - `risk_explanation`: Risk features and contexts

3. **LLM-Based Q&A**:
   - Uses LLM with comprehensive prompt
   - Prompt includes:
     - Actor context (consultant, analyst, etc.)
     - Communication style
     - Detail level preferences
     - All formatted summaries
   - LLM answers questions about:
     - What tables are necessary
     - What metrics are available
     - How metrics relate to controls
     - How to generate new metrics
     - Risk features and explanations

4. **Store Answer**:
   ```python
   state["qa_answer"] = "..."  # Markdown formatted answer
   state["qa_sources"] = {
       "schemas_count": 10,
       "metrics_count": 5,
       "controls_count": 8,
       "features_count": 12
   }
   state["qa_confidence"] = 0.9
   ```

5. **Add to Messages**:
   - Adds HumanMessage and AIMessage to conversation history

6. **Set Next Node**: `writer_agent`

---

## Knowledge Assistance Nodes

**File**: `knowledge_assistance_nodes.py`

These nodes handle compliance knowledge queries: controls, risks, and measures.

### KnowledgeRetrievalNode

**Purpose**: Retrieves SOC2 compliance knowledge: controls, risks, and measures.

#### Step-by-Step Process

```python
async def __call__(state: ContextualAssistantState)
```

**Steps:**

1. **Extract Inputs**:
   - Gets query, context_ids from state
   - Extracts framework (defaults to SOC2)

2. **Controls Retrieval**:
   - Uses context_ids from framework
   - Searches controls using `contextual_graph_service.search_controls()`
   - Gets top 20 controls for knowledge

3. **Control Enrichment**:
   - For each control (up to 15):
     - Gets requirements from `requirement_service`
     - Gets measurements from `measurement_service` (last 90 days)
     - Gets risk analytics
     - Extracts risks from control profile
     - Extracts risks from reasoning_path
   - Stores all data without aggregation

4. **Store in State**:
   ```python
   state["knowledge_data"] = {
       "controls": [
           {
               "control_id": "CC6.1",
               "control_name": "...",
               "control_description": "...",
               "risks": [...],
               "requirements": [...],
               "measures": [...],
               "risk_analytics": {...}
           }
       ],
       "framework": "SOC2",
       "total_controls": 15
   }
   ```

5. **Set Next Node**: `knowledge_qa`

### KnowledgeQANode

**Purpose**: Presents knowledge as markdown without aggregation.

#### Step-by-Step Process

```python
async def __call__(state: ContextualAssistantState)
```

**Steps:**

1. **Format Knowledge as Markdown**:
   - Formats each control separately (no consolidation)
   - Includes:
     - Control ID, name, description
     - Risks (with levels and descriptions)
     - Requirements (with types and text)
     - Measures (with dates, values, passed status)
     - Risk Analytics (scores, trends, failure counts)

2. **LLM-Based Presentation**:
   - Uses LLM to format knowledge clearly
   - **Important**: Does NOT aggregate or consolidate
   - Presents each control separately with all information
   - Uses markdown formatting (headers, lists, tables)

3. **Store Answer**:
   ```python
   state["qa_answer"] = "# SOC2 Compliance Knowledge\n\n..."
   state["qa_sources"] = {
       "controls_count": 15,
       "total_measures": 45,
       "total_risks": 20
   }
   ```

4. **Set Next Node**: `writer_agent`

---

## Complete Flow Example

### Example: "What tables do I need for SOC2 access control compliance?"

**Step 1: Context Retrieval**
```
Query: "What tables do I need for SOC2 access control compliance?"
    ↓
Context Breakdown:
  - Compliance Context: SOC2
  - Action Context: find tables
  - Identified Entities: compliance_controls, table_definitions
  - Query Keywords: SOC2, access control, tables
    ↓
Enhanced Query: "SOC2 access control tables compliance"
    ↓
Retrieve Contexts: Finds SOC2-related contexts
```

**Step 2: Reasoning Plan Creation**
```
User Action: "What tables do I need for SOC2 access control compliance?"
Retrieved Contexts: [context_id_1, context_id_2]
    ↓
Reasoning Plan:
  - Step 1: Retrieve SOC2 access control controls
  - Step 2: Retrieve table definitions (schemas)
  - Step 3: Map controls to tables
    ↓
Plan includes: stores_to_query: ["schemas", "compliance"]
```

**Step 3: Multi-Hop Reasoning**
```
Query: "SOC2 access control tables"
Context ID: context_id_1
    ↓
Hop 1: Find access control controls
  - Finds: CC6.1, CC6.2, CC6.3
    ↓
Hop 2: Find requirements for controls
  - Finds: Requirements for CC6.1, CC6.2, CC6.3
    ↓
Hop 3: Find evidence types
  - Finds: Access logs, user tables, permission tables
    ↓
Enrichment:
  - Adds requirements, edges, analytics
  - Adds store results (schemas, features)
```

**Step 4: Table Suggestions**
```
Query: "SOC2 access control tables"
Context ID: context_id_1
    ↓
Entity Search:
  - Searches entities collection
  - Searches table_definitions collection
    ↓
LLM Suggestions:
  - user_access_logs (relevance: 0.95)
  - user_permissions (relevance: 0.92)
  - authentication_events (relevance: 0.88)
    ↓
Returns: Suggested tables with reasoning
```

**Step 5: Data Knowledge Retrieval**
```
Suggested Tables: [user_access_logs, user_permissions, ...]
    ↓
Retrieve Schemas:
  - Gets DDLs for suggested tables
  - Gets column definitions
    ↓
Retrieve Metrics:
  - Gets existing metrics for project
    ↓
Retrieve Controls:
  - Gets CC6.1, CC6.2, CC6.3 from contextual graph
    ↓
Retrieve Features:
  - Gets access control features from reasoning_path
  - Searches features collection
    ↓
Store in State:
  - data_knowledge: {schemas, metrics, controls, features}
```

**Step 6: Q&A**
```
Query: "What tables do I need for SOC2 access control compliance?"
Knowledge: {schemas, metrics, controls, features}
    ↓
LLM Answer:
  - Lists required tables (user_access_logs, user_permissions, ...)
  - Explains how tables relate to controls
  - Shows which features use which tables
  - Provides risk explanations
    ↓
Returns: Comprehensive markdown answer
```

---

## Key Design Patterns

### 1. Context Breakdown Pattern
- **Purpose**: Enhance query understanding
- **When**: Before vector searches
- **Benefits**: More precise searches, framework-aware filtering

### 2. Multi-Hop Reasoning Pattern
- **Purpose**: Traverse knowledge graph
- **When**: Need to find related entities
- **Benefits**: Discovers connections (controls → requirements → evidence)

### 3. Enrichment Pattern
- **Purpose**: Add data from all stores
- **When**: After initial retrieval
- **Benefits**: Comprehensive information (requirements, measurements, analytics)

### 4. Multi-Store Search Pattern
- **Purpose**: Search across knowledge hierarchy
- **When**: Need comprehensive results
- **Benefits**: Finds entities in connectors, domains, compliance, risks, schemas

### 5. State Management Pattern
- **Purpose**: Pass data between nodes
- **When**: LangGraph node execution
- **Benefits**: Clean separation, avoids conflicts

---

## Integration Points

### Collection Factory
- Provides access to all knowledge stores
- Used for multi-store searches
- Collections: connectors, domains, compliance, risks, schemas, features

### Contextual Graph Service
- Main service for graph operations
- Provides: multi-hop queries, control search, context search
- Uses vector storage for similarity search

### Retrieval Helper
- Provides: schema retrieval, metrics retrieval
- Project-specific data access

### Services
- **Requirement Service**: Gets requirements for controls
- **Evidence Service**: Gets evidence types
- **Measurement Service**: Gets measurements and analytics

---

## Configuration

### Collection Prefix
- **Important**: Data assistance uses empty `collection_prefix` ("")
- Matches ingestion scripts (ingest_mdl_contextual_graph.py)
- Ensures contexts/edges/controls are accessible

### Model Configuration
- **Retrieval Agent**: `gpt-4o-mini` (temperature=0.2)
- **Reasoning Agent**: `gpt-4o` (temperature=0.2)
- **Q&A Nodes**: `gpt-4o` (temperature=0.3)

### Context Breakdown
- Enabled by default (`use_context_breakdown=True`)
- Can be disabled for faster processing
- Uses prompts from `vector_store_prompts.json`

---

## Error Handling

All methods include try-catch blocks that:
- Log errors with context
- Return error responses with success=False
- Continue processing when possible (graceful degradation)
- Fall back to original queries if breakdown fails

---

## Performance Considerations

1. **Limiting Results**:
   - Top-k limits on searches (top_k=10, top_k=20)
   - Limits on enrichment ([:5], [:10])

2. **Parallel Processing**:
   - Async/await throughout
   - Can process multiple contexts in parallel

3. **Caching Opportunities**:
   - Context definitions
   - Control profiles
   - Schema definitions

4. **Query Optimization**:
   - Context breakdown reduces search space
   - Edge pruning reduces processing
   - Suggested tables focus schema retrieval

---

## Future Enhancements

1. **Caching Layer**: Cache context definitions, control profiles
2. **Batch Processing**: Process multiple queries together
3. **Incremental Updates**: Update reasoning paths incrementally
4. **Confidence Scoring**: Better confidence metrics
5. **Explainability**: More detailed reasoning explanations

