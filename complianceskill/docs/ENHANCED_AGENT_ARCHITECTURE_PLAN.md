# Enhanced Agent Architecture Plan

## Overview

This plan expands the compliance automation pipeline with:
1. **XSOAR Playbooks Collection Integration** - Real-world playbook examples for agent learning
2. **Dashboard Generation Assistant Agent** - Creates compliance monitoring dashboards
3. **Data Architecture Assistant Agent** - Provides data model context and schema understanding

---

## Part 1: XSOAR Playbooks Collection Integration

### Collection Details

**Collection Name**: `xsoar_enriched` (or `xsoar_entities`)

**Entity Types** (filtered by `entity_type` metadata):
- **playbook** - Incident response workflows, tasks, automation
- **dashboard** - Dashboards, widgets, metrics/KPIs
- **script** - Helper scripts (enrichment, transformation)
- **integration** - Integrations and commands
- **report** - Reports and analytics
- **incidenttype** - Incident type definitions
- **layout** - UI layouts
- **classifier** - Classification rules

### Integration Strategy

#### 1.1 Create XSOAR Retrieval Service

**Purpose**: Access XSOAR collection similar to `RetrievalService` for framework KB

**Methods**:
- `search_xsoar_playbooks(query: str, limit: int = 5) -> List[Dict]`
  - Filters: `entity_type="playbook"`
  - Returns: Real-world playbook examples
  
- `search_xsoar_dashboards(query: str, limit: int = 5) -> List[Dict]`
  - Filters: `entity_type="dashboard"`
  - Returns: Dashboard examples with widgets/metrics
  
- `search_xsoar_scripts(query: str, limit: int = 5) -> List[Dict]`
  - Filters: `entity_type="script"`
  - Returns: Helper scripts for enrichment/transformation
  
- `search_xsoar_integrations(query: str, limit: int = 5) -> List[Dict]`
  - Filters: `entity_type="integration"`
  - Returns: Integration examples with commands

#### 1.2 Enhance Playbook Writer Agent

**Current State**: Generates playbooks from scratch based on scenarios/controls

**Enhancement**: Use XSOAR playbooks as examples/templates

**Integration Points**:
- **Planner**: When planning playbook generation, search for similar XSOAR playbooks
- **Playbook Writer Node**: 
  - Retrieve relevant XSOAR playbooks based on scenario type
  - Use as examples for structure, task patterns, automation commands
  - Adapt XSOAR patterns to compliance context
- **Prompt Enhancement**: Add section about learning from XSOAR examples

**Benefits**:
- Real-world tested patterns
- Industry-standard task structures
- Proven automation commands
- Better integration with existing XSOAR infrastructure

#### 1.3 Enhance Detection Engineer Agent

**Enhancement**: Use XSOAR scripts/integrations as examples

**Integration Points**:
- Search XSOAR scripts for similar detection logic
- Reference XSOAR integrations for data source patterns
- Learn command structures from XSOAR integrations

**Benefits**:
- Real-world detection patterns
- Proven integration patterns
- Better compatibility with XSOAR ecosystem

#### 1.4 Support Dashboard Generator Agent

**Enhancement**: Use XSOAR dashboards as templates

**Integration Points**:
- Search XSOAR dashboards for similar compliance monitoring needs
- Learn widget patterns, metric visualizations
- Adapt dashboard structures to compliance KPIs

---

## Part 2: Dashboard Generation Assistant Agent

### Agent Purpose

**Role**: `DASHBOARD_GENERATOR`

Generates compliance monitoring dashboards that:
- Visualize control compliance status
- Track metrics from `leen_metrics_registry`
- Monitor SIEM rule effectiveness
- Display test execution results
- Show risk trends over time

### Agent Capabilities

#### 2.1 Input Context

**Required Context**:
- **Controls**: Which controls to monitor
- **Metrics**: From `leen_metrics_registry` (KPIs, thresholds)
- **SIEM Rules**: What detection rules are active
- **Test Cases**: What validation tests exist
- **Tables**: From `leen_table_description` (data sources)
- **XSOAR Dashboards**: Examples from XSOAR collection

#### 2.2 Output Artifacts

**Dashboard Types**:
1. **Control Compliance Dashboard**
   - Control status (passed/failed/in-progress)
   - Compliance score over time
   - Control coverage by domain
   - Recent test results

2. **Risk Monitoring Dashboard**
   - Risk heatmap (likelihood × impact)
   - Risk trends over time
   - Top risks by severity
   - Risk mitigation progress

3. **Detection Effectiveness Dashboard**
   - SIEM rule alert volume
   - False positive rates
   - Detection coverage by scenario
   - Alert response times

4. **Test Execution Dashboard**
   - Test pass/fail rates
   - Test execution history
   - Coverage gaps
   - Test performance metrics

#### 2.3 Integration with Existing Agents

**Planner Integration**:
- Planner can create dashboard generation steps
- Steps specify: dashboard type, controls/metrics to include, data sources

**Plan Executor Integration**:
- Executes dashboard generation after controls/metrics are retrieved
- Uses MDL collections for data source context
- Uses XSOAR dashboards for structure examples

**Validation Integration**:
- Dashboard validator checks:
  - All referenced metrics exist
  - Data sources are accessible
  - Widget configurations are valid
  - Dashboard structure follows best practices

### Agent Workflow

1. **Context Gathering**
   - Retrieve controls, metrics, SIEM rules, test cases
   - Search XSOAR dashboards for similar examples
   - Identify data sources from MDL collections

2. **Dashboard Design**
   - Determine dashboard type based on user query
   - Select relevant widgets/metrics
   - Design layout and visualization types

3. **Dashboard Generation**
   - Create dashboard JSON/YAML configuration
   - Define queries for each widget
   - Configure alerts/thresholds
   - Map to compliance requirements

4. **Validation**
   - Verify all data sources exist
   - Check metric definitions are valid
   - Ensure queries are syntactically correct

### Dashboard Output Format

**Options**:
- **XSOAR Dashboard Format**: JSON compatible with XSOAR
- **Grafana Dashboard Format**: JSON for Grafana
- **Custom JSON**: Internal dashboard format
- **Markdown Documentation**: Human-readable dashboard spec

---

## Part 3: Data Architecture Assistant Agent

### Agent Purpose

**Role**: `DATA_ARCHITECTURE_ASSISTANT`

Provides data model context and schema understanding to other agents:
- Explains table structures and relationships
- Identifies relevant data sources for monitoring
- Maps compliance controls to data sources
- Suggests data pipeline designs

### Agent Capabilities

#### 3.1 Input Context

**Required Context**:
- **User Query**: What data architecture question needs answering
- **Controls/Requirements**: What compliance needs must be met
- **MDL Collections**: Schema, table descriptions, project metadata

#### 3.2 Core Functions

1. **Schema Understanding**
   - Explain table structures from `leen_db_schema`
   - Describe relationships from `leen_table_description`
   - Identify relevant columns for compliance monitoring

2. **Data Source Mapping**
   - Map controls to data sources (which tables contain evidence)
   - Identify gaps (controls without data sources)
   - Suggest new data collection needs

3. **Query Generation**
   - Generate SQL queries for compliance validation
   - Create data pipeline queries (DBT models)
   - Design monitoring queries for dashboards

4. **Data Pipeline Design**
   - Suggest data transformation pipelines
   - Design data marts for compliance reporting
   - Recommend data quality checks

#### 3.3 Integration with Existing Agents

**Planner Integration**:
- Planner can call data architecture agent to understand data context
- Helps planner create data-aware execution steps

**Detection Engineer Integration**:
- Data architecture agent provides table/column names for SIEM rules
- Suggests data sources for detection logic

**Test Generator Integration**:
- Data architecture agent provides schema for test queries
- Identifies tables to query for validation

**Dashboard Generator Integration**:
- Data architecture agent identifies data sources for dashboard widgets
- Suggests query structures for metrics

**Pipeline Builder Integration** (if exists):
- Data architecture agent designs data pipelines
- Maps controls to data transformations

### Agent Workflow

1. **Question Analysis**
   - Understand what data architecture question is being asked
   - Identify relevant MDL collections to search

2. **Context Retrieval**
   - Search `leen_db_schema` for table structures
   - Search `leen_table_description` for relationships
   - Search `leen_project_meta` for project context

3. **Analysis & Synthesis**
   - Map compliance needs to data sources
   - Identify gaps and suggest solutions
   - Generate queries or pipeline designs

4. **Response Generation**
   - Provide clear explanations
   - Include relevant schema snippets
   - Suggest actionable next steps

### Output Format

**Response Types**:
- **Schema Explanations**: Markdown with table/column descriptions
- **Query Suggestions**: SQL/SPL/KQL queries
- **Pipeline Designs**: DBT models or data pipeline specs
- **Gap Analysis**: Report of missing data sources

---

## Part 4: Workflow Integration

### 4.1 Updated Workflow Graph

**New Nodes**:
- `data_architecture_assistant` - Provides data context
- `dashboard_generator` - Generates dashboards
- `dashboard_validator` - Validates dashboard configurations

**Enhanced Nodes**:
- `planner` - Can call data architecture assistant for context
- `playbook_writer` - Uses XSOAR playbooks as examples
- `detection_engineer` - Uses XSOAR scripts/integrations as examples

### 4.2 Workflow Flow

```
User Query
    ↓
Intent Classifier
    ↓
Planner
    ├─→ [Optional] Data Architecture Assistant (for data context)
    └─→ Creates execution plan
    ↓
Plan Executor
    ├─→ Framework Analyzer
    ├─→ Detection Engineer (with XSOAR examples)
    ├─→ Playbook Writer (with XSOAR examples)
    ├─→ Test Generator
    ├─→ Dashboard Generator (NEW)
    └─→ Data Architecture Assistant (if needed)
    ↓
Validation Phase
    ├─→ SIEM Rule Validator
    ├─→ Playbook Validator
    ├─→ Test Script Validator
    ├─→ Dashboard Validator (NEW)
    └─→ Cross-Artifact Validator
    ↓
Feedback Analyzer
    ↓
[Refinement Loop if needed]
    ↓
Artifact Assembler
```

### 4.3 State Schema Updates

**New Fields in `EnhancedCompliancePipelineState`**:
- `dashboards: List[Dict]` - Generated dashboard configurations
- `data_architecture_context: Optional[Dict]` - Data model context from data architecture agent
- `xsoar_examples: Dict[str, List[Dict]]` - XSOAR playbooks/scripts/dashboards used as examples

**Updated `PlanStep`**:
- `mdl_context: Optional[Dict]` - MDL collection context
- `xsoar_examples: Optional[List[Dict]]` - Relevant XSOAR examples for this step
- `data_architecture_consulted: bool` - Whether data architecture agent was called

---

## Part 5: Implementation Phases

### Phase 1: XSOAR Collection Integration (Foundation)

**Goal**: Enable access to XSOAR playbooks/scripts/dashboards

**Tasks**:
1. Create `XSOARRetrievalService` class
2. Add XSOAR collection to `get_doc_store_provider()`
3. Test XSOAR collection access
4. Update `tool_integration.py` to include XSOAR retrieval

**Deliverables**:
- XSOAR collection accessible via retrieval service
- Can search playbooks, scripts, dashboards, integrations

### Phase 2: Enhance Playbook Writer with XSOAR Examples

**Goal**: Playbook writer learns from real XSOAR playbooks

**Tasks**:
1. Update `playbook_writer_node()` to retrieve XSOAR examples
2. Enhance `04_playbook_writer.md` prompt with XSOAR section
3. Format XSOAR examples for prompt inclusion
4. Test playbook generation with XSOAR examples

**Deliverables**:
- Playbooks reference XSOAR patterns
- Better structure and automation commands

### Phase 3: Enhance Detection Engineer with XSOAR Examples

**Goal**: Detection engineer learns from XSOAR scripts/integrations

**Tasks**:
1. Update `detection_engineer_node()` to retrieve XSOAR scripts/integrations
2. Enhance `03_detection_engineer.md` prompt with XSOAR section
3. Test SIEM rule generation with XSOAR examples

**Deliverables**:
- SIEM rules use XSOAR patterns
- Better integration compatibility

### Phase 4: Create Data Architecture Assistant Agent

**Goal**: Agent provides data model context

**Tasks**:
1. Create `data_architecture_assistant_node()` in `nodes.py`
2. Create `10_data_architecture_assistant.md` prompt
3. Integrate with MDL collections (db_schema, table_description, project_meta)
4. Add to workflow graph
5. Test data architecture queries

**Deliverables**:
- Data architecture agent functional
- Can answer schema questions
- Can map controls to data sources

### Phase 5: Create Dashboard Generator Agent

**Goal**: Agent generates compliance monitoring dashboards

**Tasks**:
1. Create `dashboard_generator_node()` in `nodes.py`
2. Create `11_dashboard_generator.md` prompt
3. Integrate with:
   - MDL collections (metrics_registry, table_description)
   - XSOAR dashboards (examples)
   - Controls, SIEM rules, test cases
4. Create dashboard output format (JSON/YAML)
5. Add to workflow graph
6. Test dashboard generation

**Deliverables**:
- Dashboard generator functional
- Generates multiple dashboard types
- Uses real metrics and data sources

### Phase 6: Create Dashboard Validator

**Goal**: Validate generated dashboard configurations

**Tasks**:
1. Create `dashboard_validator_node()` in `nodes.py`
2. Create `12_dashboard_validator.md` prompt
3. Validate:
   - All referenced metrics exist
   - Data sources are accessible
   - Widget configurations are valid
   - Queries are syntactically correct
4. Add to validation chain in workflow

**Deliverables**:
- Dashboard validator functional
- Catches configuration errors
- Provides improvement suggestions

### Phase 7: Planner Integration

**Goal**: Planner can leverage all new capabilities

**Tasks**:
1. Update `planner_node()` to optionally call data architecture assistant
2. Update `02_planner.md` prompt with:
   - XSOAR collection awareness
   - Dashboard generation steps
   - Data architecture consultation
3. Test planner with complex queries requiring data context

**Deliverables**:
- Planner creates data-aware plans
- Planner includes dashboard generation steps
- Planner consults data architecture when needed

### Phase 8: End-to-End Testing

**Goal**: Verify complete workflow with all enhancements

**Tasks**:
1. Test complete workflow with:
   - XSOAR examples in playbooks/SIEM rules
   - Dashboard generation
   - Data architecture consultation
2. Verify artifacts reference real data sources
3. Validate all artifacts pass validation

**Deliverables**:
- End-to-end workflow functional
- All artifacts use real data sources
- All validations pass

---

## Part 6: Use Cases

### Use Case 1: Complete Compliance Dashboard Request

**User Query**: "Create a HIPAA compliance dashboard for requirement 164.308(a)(6)(ii)"

**Workflow**:
1. Intent Classifier: Identifies dashboard generation intent
2. Planner:
   - Retrieves requirement and controls
   - Calls data architecture assistant to identify data sources
   - Searches XSOAR dashboards for examples
   - Creates plan with dashboard generation step
3. Plan Executor:
   - Retrieves controls, metrics, SIEM rules
   - Retrieves relevant XSOAR dashboard examples
   - Retrieves data sources from MDL collections
4. Dashboard Generator:
   - Generates dashboard using:
     - Controls for compliance status widgets
     - Metrics from metrics_registry for KPIs
     - XSOAR dashboard structure as template
     - Data sources from table_description
5. Dashboard Validator:
   - Validates all metrics exist
   - Verifies data sources are accessible
   - Checks widget configurations

**Output**: Complete dashboard JSON with widgets for HIPAA compliance monitoring

### Use Case 2: Data-Aware SIEM Rule Generation

**User Query**: "Generate SIEM rules for detecting unauthorized access to patient data"

**Workflow**:
1. Planner:
   - Identifies need for data context
   - Calls data architecture assistant
2. Data Architecture Assistant:
   - Searches MDL collections for patient data tables
   - Identifies access log tables
   - Maps to compliance controls
3. Detection Engineer:
   - Uses data architecture context for table/column names
   - Uses XSOAR scripts for detection patterns
   - Generates SIEM rules with actual table references

**Output**: SIEM rules using real table names (e.g., `patient_access_logs`, `user_authentication_events`)

### Use Case 3: XSOAR-Compatible Playbook Generation

**User Query**: "Create a playbook for responding to a data breach"

**Workflow**:
1. Planner:
   - Searches XSOAR playbooks for similar breach response playbooks
2. Playbook Writer:
   - Retrieves XSOAR playbook examples
   - Adapts XSOAR task structure to compliance context
   - Uses XSOAR automation commands
   - Maps to compliance requirements

**Output**: Playbook compatible with XSOAR structure, using real automation commands

---

## Part 7: Benefits Summary

### XSOAR Integration Benefits

1. **Real-World Patterns**: Agents learn from production-tested playbooks/scripts
2. **Industry Standards**: Follow XSOAR best practices
3. **Compatibility**: Generated artifacts work with existing XSOAR infrastructure
4. **Automation**: Use proven automation commands and integrations

### Dashboard Generator Benefits

1. **Visualization**: Compliance status visible in dashboards
2. **Metrics Integration**: Uses real metrics from metrics_registry
3. **Monitoring**: Continuous compliance monitoring capabilities
4. **Reporting**: Executive-friendly compliance dashboards

### Data Architecture Assistant Benefits

1. **Context Awareness**: Agents understand actual data sources
2. **Schema-Aware Generation**: Artifacts reference real tables/columns
3. **Gap Identification**: Identifies missing data sources
4. **Query Generation**: Creates valid queries for actual schemas

---

## Part 8: Risk Mitigation

### Risk 1: XSOAR Collection Not Available
- **Mitigation**: Make XSOAR retrieval optional, graceful degradation
- **Fallback**: Agents work without XSOAR examples (current behavior)

### Risk 2: Dashboard Format Compatibility
- **Mitigation**: Support multiple dashboard formats (XSOAR, Grafana, custom)
- **Fallback**: Generate Markdown documentation if JSON format fails

### Risk 3: Data Architecture Agent Complexity
- **Mitigation**: Start with simple schema queries, expand gradually
- **Fallback**: Return basic schema info if complex analysis fails

### Risk 4: Performance Impact
- **Mitigation**: 
  - Cache XSOAR examples in context_cache
  - Limit XSOAR search results (5 per entity type)
  - Make data architecture consultation optional

---

## Part 9: Configuration

### Environment Variables

```bash
# XSOAR Collection
XSOAR_COLLECTION_NAME=xsoar_enriched
ENABLE_XSOAR_INTEGRATION=true

# Dashboard Configuration
DASHBOARD_OUTPUT_FORMAT=xsoar  # xsoar | grafana | custom | markdown
ENABLE_DASHBOARD_GENERATION=true

# Data Architecture
ENABLE_DATA_ARCHITECTURE_ASSISTANT=true
```

### Settings

```python
class Settings:
    # XSOAR
    XSOAR_COLLECTION_NAME: str = "xsoar_enriched"
    ENABLE_XSOAR_INTEGRATION: bool = True
    
    # Dashboard
    DASHBOARD_OUTPUT_FORMAT: str = "xsoar"
    ENABLE_DASHBOARD_GENERATION: bool = True
    
    # Data Architecture
    ENABLE_DATA_ARCHITECTURE_ASSISTANT: bool = True
```

---

## Part 10: Success Criteria

1. ✅ XSOAR playbooks/scripts/dashboards accessible via retrieval service
2. ✅ Playbook writer uses XSOAR examples in generation
3. ✅ Detection engineer uses XSOAR scripts/integrations as examples
4. ✅ Dashboard generator creates functional dashboards
5. ✅ Dashboard validator catches configuration errors
6. ✅ Data architecture assistant provides useful schema context
7. ✅ Planner can create data-aware execution plans
8. ✅ All artifacts reference real data sources when MDL available
9. ✅ End-to-end workflow produces complete compliance solution

---

## Part 11: Questions to Resolve

1. **XSOAR Collection Name**: Exact collection name? (`xsoar_enriched` vs `xsoar_entities`)
2. **XSOAR Collection Structure**: What metadata fields are available? (entity_type, project_id, etc.)
3. **Dashboard Format**: Which format should be primary? (XSOAR, Grafana, custom)
4. **Data Architecture Agent**: Should it be a separate node or a helper function?
5. **Workflow Routing**: When should planner call data architecture assistant? (always, conditional, on-demand)
6. **XSOAR Integration Depth**: How closely should generated artifacts match XSOAR format? (exact match vs inspired by)

---

## Part 12: Dependencies

### Required Collections

1. **XSOAR Collection**: `xsoar_enriched` (or `xsoar_entities`)
   - Must have `entity_type` metadata for filtering
   - Should contain playbooks, dashboards, scripts, integrations

2. **MDL Collections** (from previous plan):
   - `leen_db_schema`
   - `leen_table_description`
   - `leen_project_meta`
   - `leen_metrics_registry`

3. **Framework KB Collections** (existing):
   - `controls`
   - `requirements`
   - `risks`
   - `scenarios`
   - `test_cases`

### Required Services

1. **XSOARRetrievalService**: New service for XSOAR collection access
2. **MDLRetrievalService**: From previous plan
3. **RetrievalService**: Existing framework KB service

---

## Next Steps

1. **Review this plan** - Confirm approach and priorities
2. **Verify collections exist** - Check XSOAR and MDL collections are indexed
3. **Start with Phase 1** - Create XSOAR retrieval service
4. **Iterate** - Implement phases incrementally, testing after each phase
