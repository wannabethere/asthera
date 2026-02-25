# Tools and Retrieval Integration Guide

This document explains how security intelligence tools and retrieval services are integrated into the compliance automation workflow.

## Overview

The compliance automation workflow uses two main data sources:

1. **RetrievalService**: Framework knowledge base queries (controls, requirements, risks, scenarios, test cases)
2. **Security Intelligence Tools**: External APIs and databases (CVE, ATT&CK, exploits, threat intelligence)

## Retrieval Service Usage

### What It Does

`RetrievalService` provides semantic search and direct lookups for the framework knowledge base stored in PostgreSQL and Qdrant:

- **Controls**: Security controls from frameworks (HIPAA, SOC2, CIS, etc.)
- **Requirements**: Compliance requirements
- **Risks**: Risk assessments
- **Scenarios**: Attack scenarios
- **Test Cases**: Validation test cases

### Where It's Used

#### 1. Plan Executor Node (`plan_executor_node`)

The plan executor uses **intelligent retrieval** to fetch context based on plan step requirements:

```python
# Before: Only searched controls
search_result = retrieval_service.search_controls(query, limit=5)

# After: Intelligently routes based on required_data
retrieved_data = intelligent_retrieval(
    query=query,
    required_data=current_step.required_data,  # ["controls", "risks", "scenarios"]
    framework_id=state.get("framework_id"),
    retrieval_service=retrieval_service
)
```

**How it works:**
- Analyzes `required_data` hints from the plan step
- Routes to appropriate search methods (controls, requirements, risks, scenarios, test_cases)
- If no hints, searches all collections
- Automatically updates state with retrieved data

#### 2. Framework Analyzer Node (`framework_analyzer_node`)

Performs direct database lookups when exact IDs are known:

```python
# Search for requirement by code
req_context = retrieval_service.search_requirements(
    query=state["requirement_code"],
    limit=1,
    framework_filter=[state.get("framework_id")]
)

# Get controls for a requirement
req_context = retrieval_service.get_requirement_context(state["requirement_id"])
```

### Intelligent Retrieval Function

The `intelligent_retrieval()` function in `tool_integration.py` automatically routes queries:

```python
def intelligent_retrieval(
    query: str,
    required_data: List[str],  # ["controls", "risks"]
    framework_id: Optional[str] = None,
    retrieval_service: Optional[RetrievalService] = None
) -> Dict[str, Any]:
    # Analyzes required_data to determine what to search
    # Returns: {"controls": [...], "risks": [...], "scenarios": [...]}
```

**Routing Logic:**
- If `required_data` contains "control" → searches controls
- If `required_data` contains "requirement" → searches requirements
- If `required_data` contains "risk" → searches risks
- If `required_data` contains "scenario" → searches scenarios
- If `required_data` contains "test" → searches test cases
- If no hints → searches all collections using `search_all()`

## Security Intelligence Tools Usage

### What They Do

Security intelligence tools provide external threat and vulnerability data:

- **CVE Intelligence**: CVE details, EPSS scores, CISA KEV status
- **ATT&CK Framework**: Technique lookups, CVE→ATT&CK mappings, ATT&CK→Control mappings
- **Exploit Intelligence**: Exploit-DB, Metasploit modules, Nuclei templates
- **Threat Intelligence**: OTX pulses, VirusTotal lookups
- **Compliance Tools**: Framework control search, CIS benchmarks, gap analysis
- **Analysis Tools**: Attack path building, risk calculation, remediation prioritization

### Where They're Used

#### 1. Detection Engineer Node (`detection_engineer_node`)

The detection engineer **actively uses tools** via tool-calling agents to enrich SIEM rules:

**Available Tools (Conditionally Loaded):**
- `cve_intelligence`: Look up CVE details (only if CVEs mentioned)
- `epss_lookup`: Get exploit prediction scores (only if CVEs mentioned)
- `cisa_kev_check`: Check if CVE is in KEV (only if CVEs mentioned)
- `attack_technique_lookup`: Get ATT&CK technique details (always)
- `cve_to_attack_mapper`: Map CVEs to ATT&CK techniques (only if CVEs mentioned)
- `attack_to_control_mapper`: Map ATT&CK to controls (always)
- `exploit_db_search`: Check if exploits exist (only if exploits mentioned)
- `metasploit_module_search`: Find Metasploit modules (only if exploits mentioned)
- `nuclei_template_search`: Find Nuclei templates (only if exploits mentioned)
- `otx_pulse_search`: Get threat intelligence (only if IoCs/threats mentioned)
- `virustotal_lookup`: Check IoC reputation (only if IoCs mentioned)
- `attack_path_builder`: Build attack paths (always)
- `risk_calculator`: Calculate risk scores (always)

**Implementation:**
- Uses `create_tool_calling_agent()` to create an agent that can actively use tools
- LLM decides when to call tools based on context
- Falls back to simple LLM chain if tool-calling fails
- Max 10 iterations for tool usage

#### 2. Playbook Writer Node (`playbook_writer_node`)

**Actively uses tools** via tool-calling agents for threat context:

**Available Tools (Conditionally Loaded):**
- `otx_pulse_search`: Get threat intelligence (only if IoCs/threats mentioned)
- `virustotal_lookup`: Check IoC reputation (only if IoCs mentioned)
- `attack_technique_lookup`: Get ATT&CK technique details (always)
- `attack_path_builder`: Understand attack progression (always)
- `risk_calculator`: Assess risk levels (always)
- `cve_intelligence`: Get vulnerability context (only if CVEs mentioned)

**Implementation:**
- Uses tool-calling agent with max 8 iterations
- LLM can look up threat intelligence and ATT&CK details during playbook generation

#### 3. Test Generator Node (`test_generator_node`)

**Actively uses tools** via tool-calling agents for compliance context:

**Available Tools (Always Loaded):**
- `framework_control_search`: Search for controls
- `cis_benchmark_lookup`: Get CIS benchmark details
- `gap_analysis`: Identify gaps

**Implementation:**
- Uses tool-calling agent with max 5 iterations
- LLM can look up control details and benchmarks during test generation

#### 4. Framework Analyzer Node (`framework_analyzer_node`)

Uses compliance and mapping tools (tools available but primarily uses direct retrieval):

**Available Tools:**
- `framework_control_search`: Search controls
- `cis_benchmark_lookup`: CIS benchmarks
- `gap_analysis`: Gap analysis
- `attack_to_control_mapper`: Map ATT&CK to controls

**Implementation:**
- Primarily uses RetrievalService for direct lookups
- Tools are available for enrichment if needed

### Tool Loading

Tools are loaded per agent using `get_tools_for_agent()` with conditional loading:

```python
from app.agents.tool_integration import get_tools_for_agent

# Get tools for detection engineer (conditional loading)
tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)
# Returns: List of LangChain BaseTool instances, filtered based on state content
```

**Conditional Loading:**
- `conditional=True`: Only loads tools when their data is present/needed
- `conditional=False`: Loads all tools for the agent
- State is analyzed to determine which tools are relevant

**Tool Registry:**
- Tools are defined in `app/agents/tools/__init__.py`
- Each tool has a factory function (e.g., `create_cve_intelligence_tool()`)
- Tools are registered in `TOOL_REGISTRY` dictionary

## Integration Patterns

### Pattern 1: Retrieval in Plan Execution

```python
# In plan_executor_node
for query in current_step.retrieval_queries:
    retrieved_data = intelligent_retrieval(
        query=query,
        required_data=current_step.required_data,
        framework_id=state.get("framework_id")
    )
    # Retrieved data is stored in step_context and state
```

### Pattern 2: Tool-Calling Agents

```python
# In detection_engineer_node
tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)
use_tool_calling = should_use_tool_calling_agent("detection_engineer", state=state)

if use_tool_calling and tools:
    agent_executor = create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        use_react_agent=True,
        executor_kwargs={"max_iterations": 10}
    )
    response = agent_executor.invoke({...})
else:
    # Fallback to simple LLM chain
    chain = prompt | llm
    response = chain.invoke({...})
```

### Pattern 3: Direct Retrieval for Known IDs

```python
# In framework_analyzer_node
req_context = retrieval_service.get_requirement_context(requirement_id)
controls = req_context.requirements[0].satisfying_controls
```

## Tool-Calling Agents (IMPLEMENTED)

### Active Tool Usage

All agent nodes now use **tool-calling agents** when tools are available. The LLM can actively decide when to use tools during execution.

**Implementation:**
```python
# In detection_engineer_node
tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)
use_tool_calling = should_use_tool_calling_agent("detection_engineer", state=state)

if use_tool_calling and tools:
    agent_executor = create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
        use_react_agent=True,
        executor_kwargs={"max_iterations": 10}
    )
    response = agent_executor.invoke({...})
```

**How It Works:**
1. Agent receives prompt with tool descriptions
2. LLM decides when to call tools based on context
3. Tools are executed and results returned to LLM
4. LLM uses tool results to generate final output
5. Falls back to simple LLM chain if tool-calling fails

### Conditional Tool Loading (IMPLEMENTED)

Tools are only loaded when their data is actually present or needed:

```python
# Conditional loading based on state content
tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)

# Only loads CVE tools if scenarios mention CVEs
# Only loads exploit tools if scenarios mention exploits
# Only loads threat intel tools if scenarios mention IoCs
```

**Conditional Logic:**
- **CVE tools**: Only if scenarios/risks/user_query mention "CVE"
- **Exploit tools**: Only if scenarios mention "exploit" or "vulnerability"
- **Threat intel tools**: Only if scenarios mention "IoC", "threat", or "malware"
- **ATT&CK tools**: Always loaded (always useful)
- **Compliance tools**: Always loaded (always useful)
- **Web search**: Only for planner, artifact_assembler, intent_classifier

### Tool Results in State

Tool execution results are automatically included in agent responses and stored in state messages. Future enhancement could explicitly store tool results:

```python
# Future: Store tool results explicitly
state["tool_results"] = {
    "cve_lookup": {...},
    "attack_mapping": {...}
}
```

## Best Practices

1. **Use Intelligent Retrieval**: Always use `intelligent_retrieval()` instead of direct `search_controls()` calls
2. **Load Tools Per Agent**: Use `get_tools_for_agent()` to get appropriate tools
3. **Cache Retrieval Results**: Retrieved data is stored in `state["context_cache"]` to avoid duplicate queries
4. **Framework Filtering**: Always pass `framework_id` when available to filter results
5. **Error Handling**: Wrap tool and retrieval calls in try/except blocks

## Example: Complete Flow

```python
# 1. Plan step specifies: "Find controls and risks for credential theft"
step = PlanStep(
    retrieval_queries=["credential theft detection"],
    required_data=["controls", "risks"]
)

# 2. Plan executor uses intelligent retrieval
retrieved = intelligent_retrieval(
    query="credential theft detection",
    required_data=["controls", "risks"],
    framework_id="hipaa"
)
# Returns: {"controls": [...], "risks": [...]}

# 3. State is updated with retrieved data
state["controls"].extend(retrieved["controls"])
state["risks"].extend(retrieved["risks"])

# 4. Detection engineer uses tools for threat enrichment
tools = get_tools_for_agent("detection_engineer")
# Tools available: CVE lookup, ATT&CK mapping, exploit search, etc.

# 5. Agent generates SIEM rules with enriched context
```

## Summary

- **RetrievalService**: Used for framework knowledge base queries (controls, requirements, risks, scenarios, test cases)
- **Security Intelligence Tools**: Used for external threat data (CVE, ATT&CK, exploits, threat intel)
- **Intelligent Routing**: `intelligent_retrieval()` automatically routes queries based on hints
- **Tool Loading**: `get_tools_for_agent()` provides appropriate tools per agent with conditional loading
- **Tool-Calling Agents**: All nodes use tool-calling agents when tools are available (LLMs actively use tools)
- **Conditional Loading**: Tools are only loaded when their data is present/needed (e.g., CVE tools only if CVEs mentioned)
- **Graceful Fallback**: Falls back to simple LLM chains if tool-calling fails

## Nodes Using Tool-Calling Agents

| Node | Tools Available | Conditional Loading | Max Iterations |
|------|----------------|---------------------|----------------|
| **intent_classifier** | Web search | Yes | 3 |
| **planner** | Web search, framework control search | Yes | 5 |
| **detection_engineer** | CVE, ATT&CK, exploits, threat intel, analysis | Yes | 10 |
| **playbook_writer** | Threat intel, ATT&CK, risk analysis | Yes | 8 |
| **test_generator** | Compliance tools, gap analysis | Yes | 5 |
| **framework_analyzer** | Compliance tools, mapping | Yes | N/A (uses retrieval primarily) |
| **artifact_assembler** | Web search | Yes | 5 |
