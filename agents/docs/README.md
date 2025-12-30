# Feature Conversation Service

## Overview

The Feature Conversation Service provides a streaming conversation interface for feature recommendation. It allows users to:

1. **Continuously ask for feature recommendations** - Keep the conversation going with multiple queries
2. **Select features from recommendations** - Choose which features to add to the registry
3. **Save selected features to a file** - Persist selected features as JSON
4. **Maintain conversation context** - Context is preserved across multiple turns

## Architecture

The service wraps the `TransformationPipeline` and provides:

- **Streaming updates** - Real-time feedback as features are generated
- **Conversation management** - Maintains context across multiple queries
- **Feature registry** - Tracks all recommended and selected features
- **File persistence** - Saves selected features to JSON files

## Usage

### Basic Usage

```python
from app.services.transform import FeatureConversationService, FeatureConversationRequest

# Initialize service
service = FeatureConversationService()

# Request feature recommendations
request = FeatureConversationRequest(
    user_query="I need SOC2 vulnerability features",
    project_id="cve_data",
    domain="cybersecurity",
    action="recommend"
)

response = await service.process_request(request)

if response.status == "finished":
    for feature in response.recommended_features:
        print(f"{feature['feature_name']}: {feature['natural_language_question']}")
```

### Streaming Usage

```python
# Stream recommendations as they're generated
async for update in service.process_request_with_streaming(request):
    if update.get("status") == "recommending":
        print(f"Found {update.get('total_found')} features so far...")
        for feature in update.get("recommended_features", []):
            print(f"  - {feature['feature_name']}")
    elif update.get("status") == "finished":
        print(f"Complete! Generated {len(update.get('recommended_features', []))} features")
        break
```

### Feature Selection

```python
# Select features from recommendations
select_request = FeatureConversationRequest(
    query_id=response.query_id,
    project_id="cve_data",
    domain="cybersecurity",
    action="select",
    selected_feature_ids=[f["feature_id"] for f in response.recommended_features[:3]]
)

select_response = await service.process_request(select_request)
print(f"Selected {select_response.total_selected} features")
```

### Save Features

```python
# Save selected features to file
save_request = FeatureConversationRequest(
    query_id=response.query_id,
    project_id="cve_data",
    domain="cybersecurity",
    action="save",
    save_path="/path/to/save/features.json"  # Optional, will generate default if not provided
)

save_response = await service.process_request(save_request)
print(f"Saved to: {save_response.message}")
```

### Continuous Conversation

```python
# First query
request1 = FeatureConversationRequest(
    user_query="I need SOC2 vulnerability features",
    project_id="cve_data",
    domain="cybersecurity",
    action="recommend"
)
response1 = await service.process_request(request1)

# Select some features
select_request = FeatureConversationRequest(
    query_id=response1.query_id,
    project_id="cve_data",
    domain="cybersecurity",
    action="select",
    selected_feature_ids=[f["feature_id"] for f in response1.recommended_features[:2]]
)
await service.process_request(select_request)

# Ask for more features (context is maintained)
request2 = FeatureConversationRequest(
    user_query="Now I need risk scoring features",
    project_id="cve_data",  # Same project_id maintains context
    domain="cybersecurity",
    action="recommend"
)
response2 = await service.process_request(request2)

# Select more features
select_request2 = FeatureConversationRequest(
    query_id=response2.query_id,
    project_id="cve_data",
    domain="cybersecurity",
    action="select",
    selected_feature_ids=[f["feature_id"] for f in response2.recommended_features[:2]]
)
await service.process_request(select_request2)

# Save all selected features
save_request = FeatureConversationRequest(
    query_id=response2.query_id,
    project_id="cve_data",
    domain="cybersecurity",
    action="save"
)
save_response = await service.process_request(save_request)
```

## API Endpoints

### POST `/feature-conversation/recommend`

Generate feature recommendations.

**Request:**
```json
{
  "user_query": "I need SOC2 vulnerability features",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "recommend"
}
```

**Response:**
```json
{
  "query_id": "uuid",
  "status": "finished",
  "recommended_features": [...],
  "conversation_context": {...},
  "message": "Generated 10 feature recommendations"
}
```

### POST `/feature-conversation/recommend/stream`

Stream feature recommendations (SSE).

### POST `/feature-conversation/select`

Select features from recommendations.

**Request:**
```json
{
  "query_id": "uuid",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "select",
  "selected_feature_ids": ["feature_1", "feature_2"]
}
```

### POST `/feature-conversation/save`

Save selected features to file.

**Request:**
```json
{
  "query_id": "uuid",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "save",
  "save_path": "/optional/path/to/save.json"
}
```

### GET `/feature-conversation/state/{project_id}`

Get current conversation state.

### DELETE `/feature-conversation/state/{project_id}`

Clear conversation context.

### WebSocket `/feature-conversation/ws/{query_id}`

Real-time WebSocket endpoint for streaming updates.

## File Format

Saved feature files are JSON with the following structure:

```json
{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "saved_at": "2024-01-15T10:30:00",
  "total_features": 5,
  "features": [
    {
      "feature_id": "...",
      "feature_name": "...",
      "natural_language_question": "...",
      "transformation_layer": "gold",
      "silver_pipeline": {...},
      "gold_pipeline": {...},
      ...
    }
  ],
  "conversation_summary": {
    "total_queries": 3,
    "compliance_framework": "SOC2",
    "severity_levels": ["Critical", "High"],
    "sla_requirements": {"Critical": 7, "High": 30}
  }
}
```

## Conversation Context

The service maintains conversation context per `project_id` and `domain` combination:

- **Previous queries** - History of all queries in the conversation
- **Feature registry** - All recommended features (selected and unselected)
- **Selected features** - Set of feature IDs that have been selected
- **Compliance context** - Extracted compliance framework, severity levels, SLA requirements

Context persists until:
- Explicitly cleared via `clear_conversation()`
- TTL expires (default: 1 hour)
- Service is restarted

## Integration with Chat UX

This service is designed to work with the chat-based UX:

1. **User asks question** → `POST /recommend` or `POST /recommend/stream`
2. **User selects features** → `POST /select`
3. **User asks more questions** → `POST /recommend` (context maintained)
4. **User saves** → `POST /save`

The streaming endpoint provides real-time updates that can be displayed in the chat interface as features are generated.

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200 OK` - Success
- `400 Bad Request` - Invalid request (e.g., missing required fields)
- `404 Not Found` - Conversation not found
- `500 Internal Server Error` - Processing error

Error responses include an `error` field with details:

```json
{
  "status": "error",
  "error": "No active conversation found. Please recommend features first."
}
```

