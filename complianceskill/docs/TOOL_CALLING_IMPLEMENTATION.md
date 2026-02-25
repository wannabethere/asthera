# Tool-Calling Agents Implementation Summary

## Overview

All compliance automation workflow nodes now use **tool-calling agents** with **conditional tool loading**. This enables LLMs to actively use security intelligence tools during execution, while only loading tools when they're actually needed.

## What Was Implemented

### 1. Enhanced Tool Integration (`tool_integration.py`)

#### New Functions:

**`get_tools_for_agent(agent_name, state=None, conditional=True)`**
- Gets tools for a specific agent
- **Conditional loading**: Only loads tools when their data is present/needed
- Analyzes state content to determine which tools are relevant

**`_filter_tools_conditionally(tool_names, agent_name, state)`**
- Filters tools based on state content
- CVE tools only if CVEs mentioned
- Exploit tools only if exploits mentioned
- Threat intel tools only if IoCs/threats mentioned
- ATT&CK and compliance tools always loaded

**`create_tool_calling_agent(llm, tools, prompt, use_react_agent, executor_kwargs)`**
- Creates a LangChain tool-calling agent with AgentExecutor
- Supports both `create_react_agent` and `create_tool_calling_agent`
- Handles multiple LangChain import paths
- Returns AgentExecutor ready for use

**`should_use_tool_calling_agent(agent_name, state)`**
- Determines if an agent should use tool-calling vs simple LLM chain
- Checks if tools are available for the agent

### 2. Updated All Agent Nodes

All nodes now follow this pattern:

```python
# 1. Get tools conditionally
tools = get_tools_for_agent(agent_name, state=state, conditional=True)
use_tool_calling = should_use_tool_calling_agent(agent_name, state=state)

# 2. Try tool-calling agent if tools available
if use_tool_calling and tools:
    agent_executor = create_tool_calling_agent(...)
    response = agent_executor.invoke({...})
else:
    # 3. Fallback to simple LLM chain
    chain = prompt | llm
    response = chain.invoke({...})
```

#### Nodes Updated:

1. **intent_classifier_node**
   - Tools: Web search (tavily_search)
   - Conditional: Yes
   - Max iterations: 3

2. **planner_node**
   - Tools: Web search, framework control search
   - Conditional: Yes
   - Max iterations: 5

3. **detection_engineer_node**
   - Tools: CVE, ATT&CK, exploits, threat intel, analysis (12+ tools)
   - Conditional: Yes (CVE tools only if CVEs mentioned, etc.)
   - Max iterations: 10

4. **playbook_writer_node**
   - Tools: Threat intel, ATT&CK, risk analysis, CVE
   - Conditional: Yes
   - Max iterations: 8

5. **test_generator_node**
   - Tools: Compliance tools, gap analysis
   - Conditional: Yes
   - Max iterations: 5

6. **framework_analyzer_node**
   - Tools: Compliance tools, mapping tools
   - Conditional: Yes
   - Note: Primarily uses RetrievalService, tools available for enrichment

7. **artifact_assembler_node**
   - Tools: Web search
   - Conditional: Yes
   - Max iterations: 5

## Conditional Tool Loading Logic

### CVE-Related Tools
**Load if:**
- User query contains "CVE"
- Any scenario description contains "CVE"
- Any risk description contains "CVE"

**Tools:**
- `cve_intelligence`
- `cve_to_attack_mapper`
- `epss_lookup`
- `cisa_kev_check`

### Exploit Tools
**Load if:**
- Scenarios mention "exploit" or "vulnerability"
- User query mentions "exploit" or "vulnerability"

**Tools:**
- `exploit_db_search`
- `metasploit_module_search`
- `nuclei_template_search`

### Threat Intelligence Tools
**Load if:**
- Scenarios mention "IoC", "threat", or "malware"
- User query mentions "threat" or "malware"

**Tools:**
- `otx_pulse_search`
- `virustotal_lookup`

### Always Loaded Tools
**ATT&CK Tools:**
- `attack_technique_lookup`
- `attack_to_control_mapper`
- `attack_path_builder`

**Compliance Tools:**
- `framework_control_search`
- `cis_benchmark_lookup`
- `gap_analysis`

**Analysis Tools:**
- `risk_calculator`

### Context-Specific Tools
**Web Search:**
- Only for: `planner`, `artifact_assembler`, `intent_classifier`

## Example: Detection Engineer with Tools

```python
# State contains scenarios mentioning CVE-2021-44228
state = {
    "scenarios": [
        {"description": "Log4j vulnerability CVE-2021-44228 exploit"}
    ]
}

# Conditional loading detects CVE mention
tools = get_tools_for_agent("detection_engineer", state=state, conditional=True)
# Returns: [cve_intelligence, epss_lookup, cisa_kev_check, attack_technique_lookup, ...]

# Agent can actively use tools
agent_executor = create_tool_calling_agent(llm, tools, prompt)
response = agent_executor.invoke({
    "scenarios": json.dumps(state["scenarios"]),
    ...
})

# LLM might call:
# 1. cve_intelligence({"cve_id": "CVE-2021-44228"})
# 2. cve_to_attack_mapper({"cve_id": "CVE-2021-44228"})
# 3. exploit_db_search({"cve_id": "CVE-2021-44228"})
# Then uses results to generate enriched SIEM rules
```

## Benefits

1. **Active Tool Usage**: LLMs can actively decide when to use tools
2. **Conditional Loading**: Only loads tools when needed (reduces overhead)
3. **Graceful Fallback**: Falls back to simple LLM chains if tool-calling fails
4. **Better Artifacts**: Tools provide real threat intelligence, CVE details, ATT&CK mappings
5. **Efficient**: Conditional loading prevents loading unnecessary tools

## Error Handling

- Tool loading failures are logged but don't stop execution
- Agent creation failures fall back to simple LLM chains
- Tool execution errors are handled by AgentExecutor
- All errors are logged for debugging

## Testing

To test tool-calling agents:

```python
from app.agents import get_compliance_app
from app.agents.state import EnhancedCompliancePipelineState

app = get_compliance_app()

state = {
    "user_query": "Generate SIEM rules for CVE-2021-44228 Log4j vulnerability",
    "scenarios": [{"description": "Log4j CVE-2021-44228 exploit"}],
    # ... other state fields
}

result = app.invoke(state, config)
# Detection engineer will use CVE tools to enrich rules
```

## Future Enhancements

1. **Tool Result Caching**: Cache tool results in state for reuse
2. **Tool Usage Metrics**: Track which tools are used most
3. **Parallel Tool Execution**: Execute independent tools in parallel
4. **Tool Result Formatting**: Better formatting of tool results for prompts
