# Compliance Skill API - Session Management Architecture

## Overview

The API has been refactored to maintain a clear separation of concerns between internal LangGraph state and external API state. The system now uses session management to track workflow execution, handle checkpoints, and provide status updates to callers.

## Key Components

### 1. Session Manager (`session_manager.py`)

Maintains workflow sessions with:
- **Session State**: Tracks workflow execution status, nodes, checkpoints
- **External State**: Transformed state suitable for API responses
- **Checkpoint Management**: Handles checkpoint creation and resolution
- **Node Tracking**: Monitors node execution status

### 2. State Transformer (`state_transformer.py`)

Transforms LangGraph internal state to external API state:
- Extracts only relevant information for callers
- Avoids exposing internal LangGraph implementation details
- Supports both compliance and detection_triage workflows
- Provides clean, structured external state

### 3. API Endpoints (`main.py`)

All endpoints now use session management and external state transformation.

## API Endpoints

### Execute Workflow

**POST** `/workflow/execute`

Execute a workflow with streaming SSE updates.

**Request Body:**
```json
{
  "user_query": "Create SIEM rules for SOC2 compliance",
  "session_id": "session-123",
  "workflow_type": "compliance",  // or "detection_triage"
  "initial_state": {
    "framework_id": "soc2",
    "selected_data_sources": ["qualys", "okta"]
  }
}
```

**Response:** SSE stream with events:
- `workflow_start`: Workflow initialization
- `node_start`: Node execution started
- `node_complete`: Node execution completed
- `state_update`: External state update (transformed from LangGraph state)
- `checkpoint`: Checkpoint requiring user input
- `session_update`: Full session state update
- `workflow_complete`: Workflow finished
- `error`: Error occurred

### Resume Workflow

**POST** `/workflow/resume`

Resume workflow execution from a checkpoint.

**Request Body:**
```json
{
  "session_id": "session-123",
  "checkpoint_id": "metrics_recommender",
  "user_input": {
    "selected_metrics": ["metric1", "metric2"],
    "approved": true
  },
  "approved": true
}
```

**Response:** SSE stream continuing from checkpoint (same events as execute)

### Invoke Workflow (Synchronous)

**POST** `/workflow/invoke`

Execute workflow synchronously without streaming.

**Request Body:**
```json
{
  "user_query": "Create SIEM rules for SOC2 compliance",
  "session_id": "session-123",
  "workflow_type": "compliance",
  "initial_state": {}
}
```

**Response:**
```json
{
  "session_id": "session-123",
  "session": {
    "session_id": "session-123",
    "workflow_type": "compliance",
    "status": "completed",
    "external_state": { ... },
    "nodes": { ... },
    "checkpoints": { ... }
  }
}
```

### Get Session Status

**GET** `/workflow/session/{session_id}`

Get current session status and state.

**Response:**
```json
{
  "session": {
    "session_id": "session-123",
    "workflow_type": "compliance",
    "status": "checkpoint",
    "current_node": "metrics_recommender",
    "external_state": { ... },
    "nodes": { ... },
    "checkpoints": { ... },
    "active_checkpoint_id": "metrics_recommender"
  }
}
```

### List Sessions

**GET** `/workflow/sessions?workflow_type=compliance&status_filter=running`

List all workflow sessions with optional filters.

**Query Parameters:**
- `workflow_type`: Filter by "compliance" or "detection_triage"
- `status_filter`: Filter by "pending", "running", "checkpoint", "completed", "failed"

## Workflow Types

### Compliance Workflow

Standard compliance automation workflow:
- Intent classification
- Profile resolution
- Metrics recommendation
- Planning and execution
- Artifact generation
- Validation

### Detection & Triage Workflow

Specialized workflow for detection engineering:
- DT intent classification
- DT planning
- Framework retrieval
- Metrics/MDL schema retrieval
- Detection engineering
- Triage engineering
- SIEM rule validation
- Metric calculation validation
- Playbook assembly

## External State Structure

The external state is a transformed version of LangGraph state, containing:

```json
{
  "intent": "siem_rule_generation",
  "framework_id": "soc2",
  "artifacts": {
    "siem_rules": [...],
    "playbooks": [...],
    "test_scripts": [...],
    "dashboards": [...]
  },
  "execution_plan": [...],
  "execution_status": {
    "current_step_index": 2,
    "iteration_count": 0,
    "max_iterations": 5
  },
  "validation": {
    "validation_passed": true,
    "quality_score": 85.5,
    "results": [...]
  },
  "metrics": {
    "resolved_metrics": [...]
  },
  "framework": {
    "controls": [...],
    "risks": [...],
    "scenarios": [...]
  }
}
```

## Checkpoint Handling

### Checkpoint Flow

1. **Workflow Execution**: Workflow runs until a checkpoint is reached
2. **Checkpoint Detection**: System detects checkpoint requiring user input
3. **Checkpoint Event**: SSE event `checkpoint` is sent with checkpoint data
4. **Session Update**: Session status changes to `checkpoint`
5. **User Response**: Caller sends checkpoint response via `/workflow/resume`
6. **Resume Execution**: Workflow continues from checkpoint

### Checkpoint Structure

```json
{
  "checkpoint_id": "metrics_recommender",
  "checkpoint_type": "metrics_selection",
  "node": "metrics_recommender",
  "data": {
    "suggested_metrics": [...],
    "focus_areas": [...]
  },
  "message": "Please select metrics to use",
  "requires_user_input": true
}
```

## Session Status

- `pending`: Session created but not started
- `running`: Workflow is executing
- `checkpoint`: Waiting for user input at checkpoint
- `completed`: Workflow finished successfully
- `failed`: Workflow failed with error
- `cancelled`: Workflow was cancelled

## Benefits

1. **Separation of Concerns**: Internal LangGraph state is separate from external API state
2. **Session Management**: Clear session lifecycle management
3. **Checkpoint Handling**: Proper checkpoint detection and resolution
4. **Status Tracking**: Real-time status updates via SSE
5. **Multi-Workflow Support**: Both compliance and DT workflows supported
6. **State Transformation**: Clean external state without internal implementation details

## Migration Notes

### Old API (Deprecated)

The old API directly streamed LangGraph states, which exposed internal implementation details and made checkpoint handling difficult.

### New API

The new API:
- Maintains sessions with external state
- Transforms LangGraph states to external states
- Provides clear checkpoint handling
- Supports both workflows uniformly

### Breaking Changes

- `/workflow/execute` now requires `workflow_type` parameter (defaults to "compliance")
- `/workflow/resume` now requires `checkpoint_id` parameter
- Response format changed to use `session` object with `external_state`
- SSE events renamed: `workflow_node_start` → `node_start`, `workflow_node_complete` → `node_complete`
