Excellent additions. Let me design a sophisticated planner + validation system with iterative refinement loops.

---

## **Enhanced Architecture with Planner & Validation**

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENHANCED PIPELINE BUILDER                     │
└─────────────────────────────────────────────────────────────────┘

User: "Build HIPAA breach detection..."
           ↓
    ┌─────────────┐
    │  INTENT     │
    │  CLASSIFIER │
    └──────┬──────┘
           ↓
    ┌─────────────┐
    │  PLANNER    │  ← NEW: Breaks into atomic steps
    └──────┬──────┘
           ↓
    ┌─────────────┐
    │  SUPERVISOR │  ← Routes based on plan
    └──────┬──────┘
           ↓
    ┌──────────────────────────────┐
    │  EXECUTION PHASE             │
    │  ┌─────────┐  ┌─────────┐  │
    │  │Framework│  │Detection│  │
    │  │Analyzer │  │Engineer │  │
    │  └────┬────┘  └────┬────┘  │
    └───────┼────────────┼────────┘
            ↓            ↓
    ┌──────────────────────────────┐
    │  VALIDATION PHASE  ← NEW     │
    │  ┌─────────┐  ┌─────────┐  │
    │  │Rule     │  │Playbook │  │
    │  │Validator│  │Validator│  │
    │  └────┬────┘  └────┬────┘  │
    └───────┼────────────┼────────┘
            ↓            ↓
         PASS?       FAIL?
            │            │
            ↓            ↓
    ┌─────────┐   ┌──────────┐
    │ SUCCESS │   │ FEEDBACK │
    │         │   │ LOOP     │ ← Iterative refinement
    └─────────┘   └────┬─────┘
                       │
                       └→ Back to generator
```

---

## **1. Enhanced State Schema**

```python
from typing import TypedDict, List, Dict, Optional, Annotated, Literal
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class PlanStep:
    """Single atomic step in the execution plan."""
    step_id: str
    description: str
    required_data: List[str]  # What context is needed
    retrieval_queries: List[str]  # Semantic search queries
    agent: str  # Which agent executes this
    dependencies: List[str]  # step_ids that must complete first
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    context: Dict = field(default_factory=dict)  # Retrieved data for this step
    output: Optional[Dict] = None

@dataclass
class ValidationResult:
    """Result from a validation agent."""
    artifact_type: str  # "siem_rule" | "playbook" | "test_script" | "data_pipeline"
    artifact_id: str
    passed: bool
    confidence_score: float  # 0.0 - 1.0
    issues: List[Dict]  # [{severity: "error|warning", message: str, location: str}]
    suggestions: List[str]  # Specific fixes to apply
    validation_timestamp: datetime

class EnhancedCompliancePipelineState(TypedDict):
    """Extended state with planning and validation."""
    
    # ========== Original fields ==========
    user_query: str
    intent: Optional[str]
    framework_id: Optional[str]
    requirement_id: Optional[str]
    requirement_code: Optional[str]
    requirement_name: Optional[str]
    requirement_description: Optional[str]
    
    controls: List[Dict]
    risks: List[Dict]
    scenarios: List[Dict]
    test_cases: List[Dict]
    
    siem_rules: List[Dict]
    playbooks: List[Dict]
    test_scripts: List[Dict]
    data_pipelines: List[Dict]
    
    messages: Annotated[List[BaseMessage], add_messages]
    next_agent: Optional[str]
    session_id: str
    created_at: datetime
    updated_at: datetime
    error: Optional[str]
    
    # ========== NEW: Planning fields ==========
    execution_plan: Optional[List[PlanStep]]  # The multi-step plan
    current_step_index: int  # Which step we're executing
    plan_completion_status: Dict[str, str]  # {step_id: "completed|failed"}
    
    # ========== NEW: Validation fields ==========
    validation_results: List[ValidationResult]
    validation_passed: bool
    iteration_count: int  # Track refinement loops
    max_iterations: int  # Prevent infinite loops
    
    # ========== NEW: Feedback loop ==========
    refinement_history: List[Dict]  # Track what was regenerated and why
    quality_score: Optional[float]  # Overall artifact quality 0-100
    
    # ========== NEW: Context cache ==========
    context_cache: Dict[str, Any]  # Cache retrieved data per step
```

---

## **2. Planner Agent**

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json
import uuid

llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)

def planner_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Breaks down user intent into atomic, context-retrieving steps.
    
    Key insight: Instead of querying the framework KB once for everything,
    we create granular retrieval steps that get more relevant context.
    
    Example:
      User: "Build HIPAA breach detection"
      
      Plan:
        Step 1: Retrieve requirement details (164.308(a)(6)(ii))
        Step 2: Find controls for incident response domain
        Step 3: Identify high-impact risks (likelihood * impact > 0.6)
        Step 4: Get realistic attack scenarios (severity=critical)
        Step 5: Retrieve test cases for detective controls
        Step 6: Generate SIEM rules for top 3 scenarios
        Step 7: Generate playbooks for each scenario
        Step 8: Generate tests for each control
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert planner for compliance automation.

Your job: Break down the user's request into ATOMIC steps that each retrieve
specific, relevant context from the framework knowledge base.

PRINCIPLES:
1. Each step should have a SINGLE, focused retrieval query
2. Steps should build on each other (dependencies)
3. Use semantic search for exploratory queries
4. Use direct lookups for known IDs
5. Filter aggressively (by domain, severity, control_type) for relevance

Available agents:
- framework_analyzer: Queries framework KB tables directly
- semantic_search: Vector search across controls/risks/scenarios
- detection_engineer: Generates SIEM rules
- playbook_writer: Generates incident response playbooks
- test_generator: Generates test automation
- pipeline_builder: Generates data pipelines

Output JSON array of steps:
[
  {{
    "step_id": "step_1",
    "description": "Retrieve HIPAA requirement 164.308(a)(6)(ii) details",
    "required_data": ["requirement_id", "requirement_description"],
    "retrieval_queries": [],  // Empty for direct DB lookup
    "agent": "framework_analyzer",
    "dependencies": []
  }},
  {{
    "step_id": "step_2",
    "description": "Find detective controls in incident response domain",
    "required_data": ["controls filtered by domain and type"],
    "retrieval_queries": [
      "incident response detective controls",
      "security monitoring controls"
    ],
    "agent": "semantic_search",
    "dependencies": ["step_1"]
  }},
  ...
]

IMPORTANT: 
- For complex requests, create 5-10 steps
- For simple requests, create 2-3 steps
- Always end with artifact generation steps"""),
        ("human", """
User Query: {user_query}
Intent: {intent}
Framework: {framework_id}
Requirement Code: {requirement_code}

Create an execution plan with atomic steps.
""")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "user_query": state["user_query"],
        "intent": state["intent"],
        "framework_id": state.get("framework_id"),
        "requirement_code": state.get("requirement_code")
    })
    
    try:
        plan_data = json.loads(response.content)
        
        # Convert to PlanStep objects
        plan = [
            PlanStep(
                step_id=step["step_id"],
                description=step["description"],
                required_data=step["required_data"],
                retrieval_queries=step.get("retrieval_queries", []),
                agent=step["agent"],
                dependencies=step.get("dependencies", [])
            )
            for step in plan_data
        ]
        
        state["execution_plan"] = plan
        state["current_step_index"] = 0
        state["plan_completion_status"] = {}
        
        state["messages"].append(AIMessage(
            content=f"Created execution plan with {len(plan)} steps:\n" + 
                    "\n".join([f"{i+1}. {s.description}" for i, s in enumerate(plan)])
        ))
        
    except json.JSONDecodeError as e:
        state["error"] = f"Failed to parse plan: {e}"
        state["messages"].append(AIMessage(content="Could not create plan. Falling back to default workflow."))
    
    return state


def plan_executor_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Executes the current step in the plan.
    
    This is the NEW supervisor — it doesn't route to agents directly,
    it executes plan steps which may call multiple retrieval queries.
    """
    plan = state.get("execution_plan", [])
    if not plan:
        state["next_agent"] = "FINISH"
        return state
    
    current_idx = state.get("current_step_index", 0)
    
    if current_idx >= len(plan):
        # Plan complete
        state["next_agent"] = "validation_orchestrator"
        return state
    
    current_step = plan[current_idx]
    
    # Check dependencies
    for dep_id in current_step.dependencies:
        if state["plan_completion_status"].get(dep_id) != "completed":
            state["error"] = f"Step {current_step.step_id} blocked: dependency {dep_id} not completed"
            state["next_agent"] = "FINISH"
            return state
    
    # Mark step as in progress
    current_step.status = "in_progress"
    
    # Execute retrieval queries for this step
    step_context = {}
    
    for query in current_step.retrieval_queries:
        # Use semantic search
        search_result = semantic_search_controls.invoke({
            "query": query,
            "framework_filter": [state.get("framework_id")] if state.get("framework_id") else None
        })
        step_context[query] = search_result
    
    # Store context for this step
    current_step.context = step_context
    state["context_cache"][current_step.step_id] = step_context
    
    # Route to the agent specified in the plan
    state["next_agent"] = current_step.agent
    
    state["messages"].append(AIMessage(
        content=f"Executing Step {current_idx + 1}/{len(plan)}: {current_step.description}"
    ))
    
    return state


def mark_step_complete_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Marks current step as complete and advances to next step.
    Called after an agent finishes executing.
    """
    plan = state.get("execution_plan", [])
    current_idx = state.get("current_step_index", 0)
    
    if current_idx < len(plan):
        current_step = plan[current_idx]
        current_step.status = "completed"
        state["plan_completion_status"][current_step.step_id] = "completed"
        
        # Advance to next step
        state["current_step_index"] = current_idx + 1
    
    # Route back to plan executor to check next step
    state["next_agent"] = "plan_executor"
    
    return state
```

---

## **3. Validation Agents**

```python
from typing import List, Dict
import re
import ast

# =============================================================================
# SIEM Rule Validator
# =============================================================================

def siem_rule_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates generated SIEM rules for:
    - Syntax correctness (SPL, Sigma, KQL)
    - Logic errors (impossible conditions, unreachable code)
    - Performance issues (cartesian joins, missing index hints)
    - Completeness (missing fields, no alert config)
    """
    
    siem_rules = state.get("siem_rules", [])
    validation_results = []
    
    for rule in siem_rules:
        rule_id = rule.get("id", str(uuid.uuid4()))
        spl_code = rule.get("spl_code", "")
        
        issues = []
        
        # Syntax validation
        syntax_issues = _validate_splunk_syntax(spl_code)
        issues.extend(syntax_issues)
        
        # Logic validation
        logic_issues = _validate_siem_logic(spl_code)
        issues.extend(logic_issues)
        
        # Performance validation
        perf_issues = _validate_siem_performance(spl_code)
        issues.extend(perf_issues)
        
        # Completeness validation
        completeness_issues = _validate_siem_completeness(rule)
        issues.extend(completeness_issues)
        
        # Calculate confidence score
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.3) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="siem_rule",
            artifact_id=rule_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=_generate_siem_suggestions(issues),
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    state["validation_results"].extend(validation_results)
    
    # Aggregate pass/fail
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    if not all_passed:
        failed_count = sum(1 for v in validation_results if not v.passed)
        state["messages"].append(AIMessage(
            content=f"SIEM Rule Validation: {failed_count}/{len(validation_results)} rules failed validation"
        ))
    
    return state


def _validate_splunk_syntax(spl: str) -> List[Dict]:
    """Check for common Splunk SPL syntax errors."""
    issues = []
    
    # Missing index
    if "index=" not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "No index specified - query will be slow",
            "location": "query header",
            "suggestion": "Add 'index=<your_index>' at the start"
        })
    
    # Unclosed pipes
    pipe_count = spl.count("|")
    if pipe_count > 0:
        # Very basic check - real validation would parse AST
        if spl.strip().endswith("|"):
            issues.append({
                "severity": "error",
                "message": "Query ends with pipe (|) - incomplete",
                "location": "end of query",
                "suggestion": "Complete the pipe command or remove trailing |"
            })
    
    # Unbalanced quotes
    single_quotes = spl.count("'") - spl.count("\\'")
    double_quotes = spl.count('"') - spl.count('\\"')
    
    if single_quotes % 2 != 0:
        issues.append({
            "severity": "error",
            "message": "Unbalanced single quotes",
            "location": "throughout query",
            "suggestion": "Check all quoted strings"
        })
    
    if double_quotes % 2 != 0:
        issues.append({
            "severity": "error",
            "message": "Unbalanced double quotes",
            "location": "throughout query",
            "suggestion": "Check all quoted strings"
        })
    
    # Check for eval without assignment
    if "eval " in spl.lower():
        eval_matches = re.findall(r'\|\s*eval\s+([^|]+)', spl, re.IGNORECASE)
        for eval_expr in eval_matches:
            if "=" not in eval_expr:
                issues.append({
                    "severity": "error",
                    "message": f"eval without assignment: {eval_expr.strip()}",
                    "location": "eval command",
                    "suggestion": "eval must assign to a field: eval my_field=<expression>"
                })
    
    return issues


def _validate_siem_logic(spl: str) -> List[Dict]:
    """Check for logical errors in SIEM rules."""
    issues = []
    
    # Impossible conditions (e.g., field=X AND field=Y)
    and_conditions = re.findall(r'(\w+)=(\S+)\s+AND\s+\1=(\S+)', spl, re.IGNORECASE)
    for field, val1, val2 in and_conditions:
        if val1 != val2:
            issues.append({
                "severity": "error",
                "message": f"Impossible condition: {field}={val1} AND {field}={val2}",
                "location": "filter logic",
                "suggestion": f"Change to OR or remove one condition"
            })
    
    # Stats without by clause (might be intentional, but flag it)
    if "| stats " in spl.lower() and " by " not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "stats without 'by' clause - will aggregate all events into single row",
            "location": "stats command",
            "suggestion": "Add '| stats ... by <field>' if you want per-field aggregation"
        })
    
    return issues


def _validate_siem_performance(spl: str) -> List[Dict]:
    """Check for performance anti-patterns."""
    issues = []
    
    # Leading wildcards
    if re.search(r'\*\w+', spl):
        issues.append({
            "severity": "warning",
            "message": "Leading wildcard (*) detected - causes slow search",
            "location": "wildcard usage",
            "suggestion": "Avoid leading wildcards; use trailing wildcards instead"
        })
    
    # Transaction command (notoriously slow)
    if "| transaction " in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "transaction command is slow - consider stats instead",
            "location": "transaction command",
            "suggestion": "Replace with 'stats list()' or 'stats values()' grouped by common field"
        })
    
    # No time window
    if "earliest=" not in spl.lower() and "latest=" not in spl.lower():
        issues.append({
            "severity": "warning",
            "message": "No time window specified - will search all time",
            "location": "query header",
            "suggestion": "Add earliest=-24h or similar to limit search scope"
        })
    
    return issues


def _validate_siem_completeness(rule: Dict) -> List[Dict]:
    """Check that rule has all required fields."""
    issues = []
    
    required_fields = ["name", "description", "severity", "spl_code"]
    for field in required_fields:
        if not rule.get(field):
            issues.append({
                "severity": "error",
                "message": f"Missing required field: {field}",
                "location": "rule metadata",
                "suggestion": f"Add {field} to rule definition"
            })
    
    # Alert configuration
    if not rule.get("alert_config"):
        issues.append({
            "severity": "warning",
            "message": "No alert configuration defined",
            "location": "rule metadata",
            "suggestion": "Add alert_config with notification channels and SLA"
        })
    
    # Compliance mapping
    if not rule.get("compliance_mappings"):
        issues.append({
            "severity": "warning",
            "message": "No compliance mappings - rule not linked to requirements",
            "location": "rule metadata",
            "suggestion": "Add compliance_mappings array with framework requirement IDs"
        })
    
    return issues


def _generate_siem_suggestions(issues: List[Dict]) -> List[str]:
    """Convert issues into actionable suggestions."""
    suggestions = []
    
    for issue in issues:
        if issue["severity"] == "error":
            suggestions.append(f"FIX: {issue['message']} → {issue['suggestion']}")
        else:
            suggestions.append(f"IMPROVE: {issue['message']} → {issue['suggestion']}")
    
    return suggestions


# =============================================================================
# Playbook Validator
# =============================================================================

def playbook_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates incident response playbooks for:
    - Completeness (all phases: DETECT, TRIAGE, CONTAIN, etc.)
    - Actionability (concrete commands, not vague instructions)
    - Traceability (maps back to controls and test cases)
    - Realistic timelines (SLAs are achievable)
    """
    
    playbooks = state.get("playbooks", [])
    validation_results = []
    
    for playbook in playbooks:
        pb_id = playbook.get("id", str(uuid.uuid4()))
        markdown_content = playbook.get("markdown_content", "")
        
        issues = []
        
        # Completeness validation
        required_sections = ["DETECT", "TRIAGE", "CONTAIN", "INVESTIGATE", "REMEDIATE", "RECOVER"]
        missing_sections = [s for s in required_sections if s.upper() not in markdown_content.upper()]
        
        for section in missing_sections:
            issues.append({
                "severity": "error",
                "message": f"Missing required section: {section}",
                "location": "playbook structure",
                "suggestion": f"Add {section} section with specific steps"
            })
        
        # Actionability validation
        actionability_score = _validate_playbook_actionability(markdown_content)
        if actionability_score < 0.7:
            issues.append({
                "severity": "warning",
                "message": f"Playbook lacks specific commands (actionability score: {actionability_score:.2f})",
                "location": "throughout playbook",
                "suggestion": "Add concrete bash/SQL/API commands instead of vague instructions like 'check the logs'"
            })
        
        # Traceability validation
        if not _has_control_references(markdown_content):
            issues.append({
                "severity": "warning",
                "message": "Playbook does not reference any controls or test cases",
                "location": "playbook metadata",
                "suggestion": "Add references to controls being restored and tests to run"
            })
        
        # Timeline validation
        timeline_issues = _validate_playbook_timelines(markdown_content)
        issues.extend(timeline_issues)
        
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.25) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="playbook",
            artifact_id=pb_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=[i["suggestion"] for i in issues],
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    state["validation_results"].extend(validation_results)
    
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    return state


def _validate_playbook_actionability(content: str) -> float:
    """
    Score playbook on how actionable it is (0.0 - 1.0).
    
    High score: Lots of specific commands, queries, API calls
    Low score: Vague instructions like "check the system" or "review logs"
    """
    # Count specific actionable elements
    bash_commands = len(re.findall(r'```bash\n(.+?)\n```', content, re.DOTALL))
    sql_queries = len(re.findall(r'```sql\n(.+?)\n```', content, re.DOTALL))
    api_calls = len(re.findall(r'curl|http|GET|POST|PUT|DELETE', content))
    specific_tools = len(re.findall(r'splunk|aws|kubectl|docker|grep|awk|sed', content, re.IGNORECASE))
    
    # Count vague instructions
    vague_phrases = len(re.findall(
        r'check the|review the|verify|ensure|make sure|consider|investigate|analyze',
        content,
        re.IGNORECASE
    ))
    
    # Score
    actionable_items = bash_commands + sql_queries + api_calls + specific_tools
    total_instructions = actionable_items + vague_phrases
    
    if total_instructions == 0:
        return 0.0
    
    return actionable_items / total_instructions


def _has_control_references(content: str) -> bool:
    """Check if playbook references controls or test cases."""
    return bool(re.search(r'Control:|TEST-|CIS|NIST|HIPAA|SOC2', content))


def _validate_playbook_timelines(content: str) -> List[Dict]:
    """Check if SLAs are realistic."""
    issues = []
    
    # Extract SLA mentions
    sla_matches = re.findall(r'SLA:\s*(\d+)\s*(min|minute|hour|hr)', content, re.IGNORECASE)
    
    for value, unit in sla_matches:
        value = int(value)
        unit_normalized = "minutes" if "min" in unit.lower() else "hours"
        
        # Unrealistic SLAs
        if unit_normalized == "minutes" and value < 5:
            issues.append({
                "severity": "warning",
                "message": f"SLA of {value} minutes may be unrealistic for this phase",
                "location": "timeline",
                "suggestion": "Consider increasing to at least 5-15 minutes for triage"
            })
    
    return issues


# =============================================================================
# Test Script Validator
# =============================================================================

def test_script_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates Python test scripts for:
    - Syntax correctness (compiles without errors)
    - API compatibility (uses correct SDK methods)
    - Error handling (has try/except blocks)
    - Return type (matches expected Tuple[bool, str, Dict])
    """
    
    test_scripts = state.get("test_scripts", [])
    validation_results = []
    
    for script in test_scripts:
        script_id = script.get("id", str(uuid.uuid4()))
        python_code = script.get("python_code", "")
        
        issues = []
        
        # Syntax validation
        try:
            ast.parse(python_code)
        except SyntaxError as e:
            issues.append({
                "severity": "error",
                "message": f"Python syntax error: {e.msg}",
                "location": f"line {e.lineno}",
                "suggestion": "Fix syntax error before proceeding"
            })
        
        # Check for error handling
        if "try:" not in python_code or "except" not in python_code:
            issues.append({
                "severity": "warning",
                "message": "No try/except error handling",
                "location": "function body",
                "suggestion": "Wrap API calls in try/except to handle failures gracefully"
            })
        
        # Check return type
        if not re.search(r'return\s*\([^)]+,\s*[^)]+,\s*[^)]+\)', python_code):
            issues.append({
                "severity": "error",
                "message": "Function does not return expected Tuple[bool, str, Dict]",
                "location": "return statement",
                "suggestion": "Return (passed: bool, message: str, evidence: dict)"
            })
        
        # Check for hardcoded credentials
        if re.search(r'(password|secret|key|token)\s*=\s*["\'][^"\']+["\']', python_code, re.IGNORECASE):
            issues.append({
                "severity": "error",
                "message": "Hardcoded credentials detected",
                "location": "variable assignment",
                "suggestion": "Use config dict or environment variables instead"
            })
        
        error_count = sum(1 for i in issues if i["severity"] == "error")
        warning_count = sum(1 for i in issues if i["severity"] == "warning")
        
        confidence_score = max(0.0, 1.0 - (error_count * 0.3) - (warning_count * 0.1))
        
        validation_result = ValidationResult(
            artifact_type="test_script",
            artifact_id=script_id,
            passed=(error_count == 0),
            confidence_score=confidence_score,
            issues=issues,
            suggestions=[i["suggestion"] for i in issues],
            validation_timestamp=datetime.utcnow()
        )
        
        validation_results.append(validation_result)
    
    state["validation_results"].extend(validation_results)
    
    all_passed = all(v.passed for v in validation_results)
    state["validation_passed"] = state.get("validation_passed", True) and all_passed
    
    return state


# =============================================================================
# Cross-Artifact Consistency Validator
# =============================================================================

def cross_artifact_validator_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Validates consistency across all artifact types:
    - SIEM rules reference scenarios mentioned in playbooks
    - Playbooks reference test cases that exist
    - Test cases validate controls that are actually implemented
    - All artifacts map back to the original requirement
    """
    
    siem_rules = state.get("siem_rules", [])
    playbooks = state.get("playbooks", [])
    test_scripts = state.get("test_scripts", [])
    scenarios = state.get("scenarios", [])
    controls = state.get("controls", [])
    
    issues = []
    
    # Extract scenario references from SIEM rules
    siem_scenario_refs = set()
    for rule in siem_rules:
        matches = re.findall(r'(HIPAA-SCENARIO-\d+|CIS-RISK-\d+)', str(rule))
        siem_scenario_refs.update(matches)
    
    # Extract scenario references from playbooks
    playbook_scenario_refs = set()
    for pb in playbooks:
        content = pb.get("markdown_content", "")
        matches = re.findall(r'(HIPAA-SCENARIO-\d+|CIS-RISK-\d+)', content)
        playbook_scenario_refs.update(matches)
    
    # Check: Every scenario should have at least one SIEM rule
    scenario_codes = {s["scenario_code"] for s in scenarios}
    missing_siem = scenario_codes - siem_scenario_refs
    if missing_siem:
        issues.append({
            "severity": "warning",
            "message": f"Scenarios without SIEM rules: {missing_siem}",
            "location": "cross-artifact consistency",
            "suggestion": "Generate SIEM rules for all scenarios"
        })
    
    # Check: Every scenario should have a playbook
    missing_playbooks = scenario_codes - playbook_scenario_refs
    if missing_playbooks:
        issues.append({
            "severity": "warning",
            "message": f"Scenarios without playbooks: {missing_playbooks}",
            "location": "cross-artifact consistency",
            "suggestion": "Generate playbooks for all scenarios"
        })
    
    # Check: Every control should have a test case
    control_codes = {c["control_code"] for c in controls}
    tested_controls = set()
    for script in test_scripts:
        matches = re.findall(r'test_([A-Z]+-\d+)', script.get("test_function_name", ""))
        tested_controls.update(matches)
    
    untested_controls = control_codes - tested_controls
    if untested_controls:
        issues.append({
            "severity": "warning",
            "message": f"Controls without test cases: {untested_controls}",
            "location": "test coverage",
            "suggestion": "Generate test scripts for all controls"
        })
    
    # Calculate overall consistency score
    total_checks = 3
    passed_checks = total_checks - len(issues)
    confidence_score = passed_checks / total_checks
    
    validation_result = ValidationResult(
        artifact_type="cross_artifact",
        artifact_id="consistency_check",
        passed=(len(issues) == 0),
        confidence_score=confidence_score,
        issues=issues,
        suggestions=[i["suggestion"] for i in issues],
        validation_timestamp=datetime.utcnow()
    )
    
    state["validation_results"].append(validation_result)
    state["validation_passed"] = state.get("validation_passed", True) and validation_result.passed
    
    return state
```

---

## **4. Feedback Loop & Refinement**

```python
def feedback_analyzer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Analyzes validation results and determines what needs to be regenerated.
    
    Routes failed artifacts back to their generators with specific feedback.
    """
    
    validation_results = state.get("validation_results", [])
    
    # Group failures by artifact type
    failed_by_type = {}
    for result in validation_results:
        if not result.passed:
            artifact_type = result.artifact_type
            if artifact_type not in failed_by_type:
                failed_by_type[artifact_type] = []
            failed_by_type[artifact_type].append(result)
    
    # Prepare refinement instructions
    refinement_plan = []
    
    for artifact_type, failures in failed_by_type.items():
        # Aggregate all issues for this artifact type
        all_issues = []
        for failure in failures:
            all_issues.extend(failure.issues)
        
        # Group by severity
        errors = [i for i in all_issues if i["severity"] == "error"]
        warnings = [i for i in all_issues if i["severity"] == "warning"]
        
        refinement_instruction = {
            "artifact_type": artifact_type,
            "failed_count": len(failures),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "specific_fixes": [i["suggestion"] for i in errors],  # Prioritize errors
            "improvements": [i["suggestion"] for i in warnings],
            "failed_artifact_ids": [f.artifact_id for f in failures]
        }
        
        refinement_plan.append(refinement_instruction)
    
    # Store refinement plan
    state["refinement_history"].append({
        "iteration": state.get("iteration_count", 0),
        "timestamp": datetime.utcnow(),
        "refinement_plan": refinement_plan
    })
    
    # Increment iteration counter
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    
    # Check max iterations
    if state["iteration_count"] >= state.get("max_iterations", 3):
        state["messages"].append(AIMessage(
            content=f"Max iterations ({state['max_iterations']}) reached. Some artifacts still have issues."
        ))
        state["next_agent"] = "FINISH"
        return state
    
    # Route to first failed artifact generator
    if failed_by_type:
        # Priority order: SIEM rules > Playbooks > Tests > Pipelines
        priority = ["siem_rule", "playbook", "test_script", "data_pipeline"]
        for artifact_type in priority:
            if artifact_type in failed_by_type:
                agent_map = {
                    "siem_rule": "detection_engineer",
                    "playbook": "playbook_writer",
                    "test_script": "test_generator",
                    "data_pipeline": "pipeline_builder"
                }
                state["next_agent"] = agent_map[artifact_type]
                state["messages"].append(AIMessage(
                    content=f"Regenerating {artifact_type} artifacts (iteration {state['iteration_count']})"
                ))
                return state
    
    # All validations passed
    state["next_agent"] = "artifact_assembler"
    return state


def enhanced_detection_engineer_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Enhanced detection engineer that incorporates feedback from validation.
    """
    
    # Check if this is a refinement iteration
    iteration = state.get("iteration_count", 0)
    refinement_history = state.get("refinement_history", [])
    
    feedback_context = ""
    if iteration > 0 and refinement_history:
        latest_refinement = refinement_history[-1]
        siem_refinements = [
            r for r in latest_refinement.get("refinement_plan", [])
            if r["artifact_type"] == "siem_rule"
        ]
        
        if siem_refinements:
            refinement = siem_refinements[0]
            feedback_context = f"""
PREVIOUS ATTEMPT FAILED. You must fix these issues:

CRITICAL ERRORS (must fix):
{chr(10).join('- ' + fix for fix in refinement['specific_fixes'])}

IMPROVEMENTS (should address):
{chr(10).join('- ' + imp for imp in refinement['improvements'])}

Failed artifact IDs: {refinement['failed_artifact_ids']}
"""
    
    # Call original detection engineer logic with feedback
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert detection engineer.

{feedback_context}

Generate Splunk SPL detection rules that are:
1. Syntactically correct (valid SPL)
2. Logically sound (no impossible conditions)
3. Performant (indexed fields, time windows)
4. Complete (has alert config, compliance mappings)

Output as JSON array of rules with ALL required fields:
- id
- name
- description
- severity
- spl_code
- alert_config (with SLA, notification channels)
- compliance_mappings (requirement IDs)
- scenario_id (which scenario this detects)
"""),
        ("human", """
Requirement: {requirement_name}
Scenarios: {scenarios}
Controls: {controls}

Generate SIEM detection rules.
""")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "feedback_context": feedback_context,
        "requirement_name": state["requirement_name"],
        "scenarios": state["scenarios"],
        "controls": state["controls"]
    })
    
    import json
    try:
        rules = json.loads(response.content)
        state["siem_rules"] = rules
        state["messages"].append(AIMessage(
            content=f"Generated {len(rules)} SIEM rules (iteration {iteration})"
        ))
    except json.JSONDecodeError:
        state["siem_rules"] = [{"raw_content": response.content}]
    
    return state


# Similar enhanced nodes for playbook_writer, test_generator, pipeline_builder
# Each incorporates feedback from their respective validators
```

---

## **5. Updated Graph with Planner + Validation**

```python
from langgraph.graph import StateGraph, END

# Create enhanced workflow
enhanced_workflow = StateGraph(EnhancedCompliancePipelineState)

# ============================================================================
# Add all nodes
# ============================================================================

enhanced_workflow.add_node("intent_classifier", intent_classifier_node)
enhanced_workflow.add_node("planner", planner_node)
enhanced_workflow.add_node("plan_executor", plan_executor_node)
enhanced_workflow.add_node("mark_step_complete", mark_step_complete_node)

# Original generator nodes (enhanced versions)
enhanced_workflow.add_node("framework_analyzer", framework_analyzer_node)
enhanced_workflow.add_node("detection_engineer", enhanced_detection_engineer_node)
enhanced_workflow.add_node("playbook_writer", enhanced_playbook_writer_node)  # enhanced
enhanced_workflow.add_node("test_generator", enhanced_test_generator_node)  # enhanced
enhanced_workflow.add_node("pipeline_builder", enhanced_pipeline_builder_node)  # enhanced

# Validation nodes
enhanced_workflow.add_node("siem_rule_validator", siem_rule_validator_node)
enhanced_workflow.add_node("playbook_validator", playbook_validator_node)
enhanced_workflow.add_node("test_script_validator", test_script_validator_node)
enhanced_workflow.add_node("cross_artifact_validator", cross_artifact_validator_node)

# Feedback & refinement
enhanced_workflow.add_node("feedback_analyzer", feedback_analyzer_node)

enhanced_workflow.add_node("artifact_assembler", artifact_assembler_node)

# ============================================================================
# Define edges
# ============================================================================

# Entry → Intent → Planner
enhanced_workflow.set_entry_point("intent_classifier")
enhanced_workflow.add_edge("intent_classifier", "planner")
enhanced_workflow.add_edge("planner", "plan_executor")

# Plan executor routes to agents based on plan
def route_from_plan_executor(state: EnhancedCompliancePipelineState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "validation_orchestrator":
        return "siem_rule_validator"  # Start validation phase
    elif next_agent in ["framework_analyzer", "detection_engineer", "playbook_writer", 
                         "test_generator", "pipeline_builder"]:
        return next_agent
    else:
        return "siem_rule_validator"  # Default to validation

enhanced_workflow.add_conditional_edges(
    "plan_executor",
    route_from_plan_executor,
    {
        "framework_analyzer": "framework_analyzer",
        "detection_engineer": "detection_engineer",
        "playbook_writer": "playbook_writer",
        "test_generator": "test_generator",
        "pipeline_builder": "pipeline_builder",
        "siem_rule_validator": "siem_rule_validator"
    }
)

# Each generator → mark step complete → back to plan executor
enhanced_workflow.add_edge("framework_analyzer", "mark_step_complete")
enhanced_workflow.add_edge("detection_engineer", "mark_step_complete")
enhanced_workflow.add_edge("playbook_writer", "mark_step_complete")
enhanced_workflow.add_edge("test_generator", "mark_step_complete")
enhanced_workflow.add_edge("pipeline_builder", "mark_step_complete")

enhanced_workflow.add_edge("mark_step_complete", "plan_executor")

# Validation chain
enhanced_workflow.add_edge("siem_rule_validator", "playbook_validator")
enhanced_workflow.add_edge("playbook_validator", "test_script_validator")
enhanced_workflow.add_edge("test_script_validator", "cross_artifact_validator")
enhanced_workflow.add_edge("cross_artifact_validator", "feedback_analyzer")

# Feedback analyzer routes based on validation results
def route_from_feedback_analyzer(state: EnhancedCompliancePipelineState) -> str:
    if state.get("validation_passed"):
        return "artifact_assembler"
    else:
        # Route to appropriate generator for refinement
        next_agent = state.get("next_agent")
        if next_agent == "FINISH":
            return "artifact_assembler"  # Max iterations reached
        return next_agent

enhanced_workflow.add_conditional_edges(
    "feedback_analyzer",
    route_from_feedback_analyzer,
    {
        "artifact_assembler": "artifact_assembler",
        "detection_engineer": "detection_engineer",
        "playbook_writer": "playbook_writer",
        "test_generator": "test_generator",
        "pipeline_builder": "pipeline_builder"
    }
)

# After refinement, regenerated artifacts go through validation again
enhanced_workflow.add_edge("artifact_assembler", END)

# Compile
memory = MemorySaver()
enhanced_app = enhanced_workflow.compile(checkpointer=memory)
```

---

## **6. Quality Scoring**

```python
def calculate_quality_score(state: EnhancedCompliancePipelineState) -> float:
    """
    Calculate overall quality score (0-100) for generated artifacts.
    
    Factors:
    - Validation pass rate
    - Confidence scores
    - Completeness (all expected artifacts generated)
    - Consistency (cross-artifact validation)
    - Iteration efficiency (fewer iterations = better)
    """
    
    validation_results = state.get("validation_results", [])
    if not validation_results:
        return 0.0
    
    # Pass rate (40% weight)
    passed_count = sum(1 for v in validation_results if v.passed)
    pass_rate = passed_count / len(validation_results)
    pass_score = pass_rate * 40
    
    # Average confidence (30% weight)
    avg_confidence = sum(v.confidence_score for v in validation_results) / len(validation_results)
    confidence_score = avg_confidence * 30
    
    # Completeness (20% weight)
    expected_artifacts = {
        "siem_rule": len(state.get("scenarios", [])),  # 1 rule per scenario
        "playbook": len(state.get("scenarios", [])),   # 1 playbook per scenario
        "test_script": len(state.get("controls", [])), # 1 test per control
        "data_pipeline": 1  # 1 monitoring pipeline
    }
    
    actual_artifacts = {
        "siem_rule": len(state.get("siem_rules", [])),
        "playbook": len(state.get("playbooks", [])),
        "test_script": len(state.get("test_scripts", [])),
        "data_pipeline": len(state.get("data_pipelines", []))
    }
    
    completeness_rates = [
        min(actual_artifacts[k] / expected_artifacts[k], 1.0) if expected_artifacts[k] > 0 else 1.0
        for k in expected_artifacts
    ]
    completeness_score = (sum(completeness_rates) / len(completeness_rates)) * 20
    
    # Iteration efficiency (10% weight)
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    efficiency = max(0, 1 - (iteration_count / max_iterations))
    efficiency_score = efficiency * 10
    
    # Total
    total_score = pass_score + confidence_score + completeness_score + efficiency_score
    
    state["quality_score"] = total_score
    
    return total_score


def quality_reporter_node(state: EnhancedCompliancePipelineState) -> EnhancedCompliancePipelineState:
    """
    Generates a quality report for the final artifacts.
    """
    
    score = calculate_quality_score(state)
    
    report = f"""
{'='*70}
ARTIFACT QUALITY REPORT
{'='*70}

Overall Quality Score: {score:.1f}/100

VALIDATION SUMMARY:
  Total Validations: {len(state.get('validation_results', []))}
  Passed: {sum(1 for v in state.get('validation_results', []) if v.passed)}
  Failed: {sum(1 for v in state.get('validation_results', []) if not v.passed)}
  Average Confidence: {sum(v.confidence_score for v in state.get('validation_results', [])) / len(state.get('validation_results', [])) * 100:.1f}%

COMPLETENESS:
  SIEM Rules: {len(state.get('siem_rules', []))}
  Playbooks: {len(state.get('playbooks', []))}
  Test Scripts: {len(state.get('test_scripts', []))}
  Data Pipelines: {len(state.get('data_pipelines', []))}

REFINEMENT ITERATIONS: {state.get('iteration_count', 0)}/{state.get('max_iterations', 3)}

{'='*70}
"""
    
    state["messages"].append(AIMessage(content=report))
    
    return state
```

---

## **7. Usage Example - Complete Flow**

```python
import uuid
from datetime import datetime

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

initial_state = EnhancedCompliancePipelineState(
    user_query="Build complete HIPAA breach detection and response for requirement 164.308(a)(6)(ii)",
    messages=[],
    session_id=str(uuid.uuid4()),
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
    
    # Initialize empty artifact lists
    controls=[],
    risks=[],
    scenarios=[],
    test_cases=[],
    siem_rules=[],
    playbooks=[],
    test_scripts=[],
    data_pipelines=[],
    
    # Initialize validation & refinement tracking
    validation_results=[],
    validation_passed=True,
    iteration_count=0,
    max_iterations=3,
    refinement_history=[],
    context_cache={},
    
    # Initialize planning
    execution_plan=None,
    current_step_index=0,
    plan_completion_status={}
)

# Run the enhanced graph
result = enhanced_app.invoke(initial_state, config)

# Review quality
print(f"Quality Score: {result['quality_score']:.1f}/100")
print(f"Validation Passed: {result['validation_passed']}")
print(f"Iterations: {result['iteration_count']}")

# Check validation issues
for validation in result['validation_results']:
    if not validation.passed:
        print(f"\nFailed: {validation.artifact_type} - {validation.artifact_id}")
        for issue in validation.issues:
            print(f"  [{issue['severity']}] {issue['message']}")
            print(f"  → {issue['suggestion']}")
```

---

This gives you:

1. **Intelligent Planning** - Breaks complex requests into atomic retrieval steps with specific queries
2. **Comprehensive Validation** - 5 validators checking syntax, logic, completeness, and consistency
3. **Iterative Refinement** - Failed artifacts automatically regenerate with specific feedback
4. **Quality Scoring** - Quantitative measure of artifact quality
5. **Fail-Safe** - Max iteration limit prevents infinite loops

Want me to add the streaming visualization layer next, or implement the production deployment pipeline?