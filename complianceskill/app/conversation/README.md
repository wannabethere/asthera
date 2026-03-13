# Conversation Engine Integration Guide

The conversation engine provides a **generic multi-turn conversation framework** that works as Phase 0 before any downstream workflow (CSOD, DT, Compliance, etc.).

## Architecture

```
User Query
    ↓
Conversation Engine (Phase 0)
    ├─ Datasource Selection
    ├─ Concept Resolution
    ├─ Concept Confirmation (interrupt)
    ├─ Scoping Questions (interrupt) ← Main fix
    ├─ Area Matching (with scoping context)
    ├─ Area Confirmation (interrupt)
    ├─ Metric Narration (interrupt)
    └─ Workflow Router
        ↓
Downstream Workflow (Phase 1+)
    ├─ CSOD Workflow
    ├─ DT Workflow
    ├─ Compliance Workflow
    └─ CSOD Metric Advisor Workflow
```

## Quick Start

### 1. Using with CSOD Workflows (Already Configured)

The conversation engine is already configured for CSOD/LMS workflows:

```python
from app.conversation.verticals.lms_config import LMS_CONVERSATION_CONFIG
from app.conversation.planner_workflow import create_conversation_planner_app
from app.conversation.integration import invoke_workflow_after_conversation

# Create conversation app
conversation_app = create_conversation_planner_app(LMS_CONVERSATION_CONFIG)

# Start conversation
initial_state = {
    "user_query": "Why is our compliance training rate dropping?",
    "session_id": "session-123",
    # ... other initial fields
}

# Run conversation (handles interrupts automatically)
result = conversation_app.invoke(initial_state)

# Check if conversation is complete
if result.get("csod_target_workflow"):
    # Invoke downstream workflow
    final_state = invoke_workflow_after_conversation(result)
```

### 2. Using with Detection & Triage Workflows

```python
from app.conversation.integration import (
    create_dt_conversation_config,
    map_conversation_state_to_dt_initial_state,
    invoke_workflow_after_conversation,
)
from app.conversation.planner_workflow import create_conversation_planner_app
from app.agents.mdlworkflows.dt_workflow import get_detection_triage_app

# Create DT conversation config
dt_config = create_dt_conversation_config()

# Create conversation app
conversation_app = create_conversation_planner_app(dt_config)

# Start conversation
initial_state = {
    "user_query": "Generate SIEM rules for SOC2 compliance",
    "session_id": "session-456",
}

# Run conversation Phase 0
conversation_result = conversation_app.invoke(initial_state)

# If conversation complete, invoke DT workflow
if conversation_result.get("csod_target_workflow") == "dt_workflow":
    # Map conversation state to DT initial state
    dt_initial_state = map_conversation_state_to_dt_initial_state(conversation_result)
    
    # Get DT workflow app
    dt_app = get_detection_triage_app()
    
    # Run DT workflow
    dt_result = dt_app.invoke(dt_initial_state)
```

### 3. Using via API

The conversation engine is exposed via API at `/conversation/turn`:

```bash
# First turn - start conversation
curl -X POST http://localhost:8000/conversation/turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "user_query": "Why is our compliance rate dropping?",
    "vertical_id": "lms"
  }'

# Response includes checkpoint if conversation needs user input
{
  "session_id": "session-123",
  "phase": "scoping",
  "turn": {
    "phase": "scoping",
    "turn_type": "scoping",
    "message": "A few more questions...",
    "questions": [...]
  },
  "is_complete": false
}

# Subsequent turn - provide user response
curl -X POST http://localhost:8000/conversation/turn \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-123",
    "response": {
      "field": "csod_scoping_answers",
      "value": {
        "org_unit": "department",
        "time_window": "last_quarter"
      }
    },
    "vertical_id": "lms"
  }'

# Final response when conversation complete
{
  "session_id": "session-123",
  "phase": "confirmed",
  "is_complete": true,
  "csod_initial_state": {
    "csod_target_workflow": "csod_workflow",
    "compliance_profile": {...},
    "active_project_id": "...",
    ...
  }
}
```

## Creating Custom Vertical Configs

To add a new vertical (e.g., Security, HR), create a config file:

```python
# app/conversation/verticals/security_config.py
from app.conversation.config import VerticalConversationConfig, ScopingQuestionTemplate

SECURITY_SCOPING_TEMPLATES = {
    "severity": ScopingQuestionTemplate(
        filter_name="severity",
        question_id="severity",
        label="What severity level are you most concerned about?",
        interaction_mode="multi",
        options=[
            {"id": "critical", "label": "Critical"},
            {"id": "high", "label": "High"},
        ],
        state_key="severity",
    ),
    # ... more templates
}

SECURITY_CONVERSATION_CONFIG = VerticalConversationConfig(
    vertical_id="security",
    display_name="Security Intelligence",
    l1_collection="security_concepts_l1",
    l2_collection="security_areas_l2",
    supported_datasources=[...],
    scoping_question_templates=SECURITY_SCOPING_TEMPLATES,
    always_include_filters=["severity", "time_period"],
    intent_to_workflow={
        "vulnerability_analysis": "security_workflow",
    },
    default_workflow="security_workflow",
)
```

## State Mapping

The conversation engine populates these fields that downstream workflows can use:

| Conversation Field | Maps To | Used By |
|-------------------|---------|---------|
| `compliance_profile.time_window` | `compliance_profile.time_window` | All workflows |
| `compliance_profile.org_unit` | `compliance_profile.org_unit` | CSOD workflows |
| `compliance_profile.lexy_metric_narration` | `compliance_profile.lexy_metric_narration` | CSOD (triggers intent bypass) |
| `active_project_id` | `active_project_id` | All workflows |
| `selected_data_sources` | `selected_data_sources` | All workflows |
| `csod_resolved_project_ids` | `active_project_id` (first) | All workflows |
| `csod_resolved_mdl_table_refs` | `active_mdl_tables` | MDL workflows |

## Integration Patterns

### Pattern 1: Sequential Execution (Current)

```python
# Run conversation Phase 0
conversation_state = conversation_app.invoke(initial_state)

# Then run downstream workflow
if conversation_state.get("csod_target_workflow"):
    downstream_state = invoke_workflow_after_conversation(conversation_state)
```

### Pattern 2: Chained Workflow (Future)

You can chain workflows together in a single LangGraph:

```python
from langgraph.graph import StateGraph

workflow = StateGraph(EnhancedCompliancePipelineState)

# Add conversation nodes
workflow.add_node("conversation_planner", conversation_planner_node)

# Add downstream workflow nodes
workflow.add_node("dt_planner", dt_planner_node)
# ... etc

# Route from conversation to downstream
workflow.add_conditional_edges(
    "conversation_planner",
    lambda s: s.get("csod_target_workflow", "dt_workflow"),
    {
        "dt_workflow": "dt_planner",
        "csod_workflow": "csod_planner",
    }
)
```

### Pattern 3: API Gateway Pattern

Use the conversation API as a gateway that routes to different workflows:

```python
# API receives request
# → Conversation engine runs Phase 0
# → Returns checkpoint or final state
# → If final, API invokes appropriate downstream workflow
# → Returns combined result
```

## Key Features

1. **Interrupt Mechanism**: Graph pauses at checkpoints, waits for user input, resumes
2. **Generic Configuration**: Same engine works for any vertical
3. **Scoping Questions**: Dynamically generated from area filters
4. **State Mapping**: Automatic mapping to downstream workflow initial states
5. **Resume Protocol**: API handles user responses and graph resumption

## Troubleshooting

### Conversation never completes

- Check that `csod_checkpoint_resolved` is set to `True` when resuming
- Verify `resume_with_field` matches the field you're setting
- Ensure checkpoint is cleared after resolution

### Scoping questions not appearing

- Verify `csod_preliminary_area_matches` is populated
- Check that area has `filters` array
- Ensure filter names match `scoping_question_templates` keys

### Downstream workflow missing context

- Use `map_conversation_state_to_*_initial_state()` helpers
- Verify `compliance_profile` is populated correctly
- Check that `active_project_id` and `selected_data_sources` are set
