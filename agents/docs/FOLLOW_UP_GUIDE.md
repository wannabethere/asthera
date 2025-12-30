# Follow-Up Feature Recommendation Guide

This guide explains how to make follow-up requests for feature recommendations that build upon previously selected features.

## How Follow-Up Requests Work

The system maintains **conversation context** per `project_id` and `domain` combination. When you make follow-up requests:

1. **Context is automatically retrieved** - The system finds your existing conversation
2. **Selected features are included** - Previously selected features are passed to the agent
3. **Query is enhanced** - Your new query is automatically enhanced with context about selected features
4. **New features are generated** - The agent generates complementary features that build upon your selections

## Making Follow-Up Requests

### Option 1: Using the Conversation Service (Recommended)

The conversation service automatically handles context management:

```python
# First request - initial feature recommendations
request1 = FeatureConversationRequest(
    user_query="I want to generate SOC2 compliance report based on assets, asset types and vulnerabilities",
    project_id="cve_data",
    domain="cybersecurity",
    action="recommend"
)

response1 = await service.process_request(request1)
# User selects some features...

# Follow-up request - automatically uses context
request2 = FeatureConversationRequest(
    user_query="I need more features for risk assessment",  # New query
    project_id="cve_data",  # Same project_id
    domain="cybersecurity",  # Same domain
    action="recommend"
)

response2 = await service.process_request(request2)
# This will automatically:
# - Include previously selected features in context
# - Generate complementary features
```

### Option 2: Using the REST API

#### Step 1: Initial Recommendation

```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_query": "I want to generate SOC2 compliance report based on assets, asset types and vulnerabilities",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "recommend"
}'
```

#### Step 2: Select Features

```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/select' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "select",
  "selected_feature_ids": ["feature_id_1", "feature_id_2", "feature_id_3"],
  "auto_save": false
}'
```

#### Step 3: Follow-Up Request

```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_query": "I need more features for risk assessment and exploitability metrics",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "recommend"
}'
```

**Key Points:**
- Use the **same `project_id` and `domain`** to maintain context
- The system automatically includes selected features
- New features are added to the registry (not replacing existing ones)

## What Happens Behind the Scenes

1. **Context Retrieval**: System finds conversation context for `project_id` + `domain`
2. **Selected Features Extraction**: Gets all features with `SELECTED` status from registry
3. **Query Enhancement**: Your new query is enhanced with:
   ```
   [Your new query]
   
   Previously selected features (N):
   1. feature_name_1: natural_language_question_1
   2. feature_name_2: natural_language_question_2
   ...
   
   Please generate additional features that complement or build upon these selected features.
   ```
4. **Agent Context**: Selected features are passed via `available_features` in initial state
5. **Feature Generation**: Agent generates new features that complement existing selections
6. **Registry Update**: New features are added to registry (deduplicated by name)

## Example Conversation Flow

```python
# 1. Initial request
request1 = FeatureConversationRequest(
    user_query="I need SOC2 vulnerability features",
    project_id="cve_data",
    domain="cybersecurity",
    action="recommend"
)
response1 = await service.process_request(request1)
# Returns: 10 recommended features

# 2. Select some features
select_request = FeatureConversationRequest(
    project_id="cve_data",
    domain="cybersecurity",
    action="select",
    selected_feature_ids=["feat_1", "feat_2", "feat_3"]
)
await service.process_request(select_request)
# 3 features now marked as SELECTED

# 3. Follow-up request - asks for more specific features
request2 = FeatureConversationRequest(
    user_query="I need features for exploitability and reachability analysis",
    project_id="cve_data",  # Same project_id
    domain="cybersecurity",  # Same domain
    action="recommend"
)
response2 = await service.process_request(request2)
# Returns: New features that complement the 3 selected ones
# The agent knows about the selected features and generates complementary ones

# 4. Another follow-up - even more specific
request3 = FeatureConversationRequest(
    user_query="Add features for SLA tracking and remediation time",
    project_id="cve_data",
    domain="cybersecurity",
    action="recommend"
)
response3 = await service.process_request(request3)
# Returns: More complementary features
```

## Checking Conversation State

You can check the current state of your conversation:

```bash
# Get full conversation state
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/state/cve_data?domain=cybersecurity'

# Get all cached features
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/cache/cve_data?domain=cybersecurity'

# Get only selected features
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/selected/cve_data?domain=cybersecurity'
```

## Response Metadata

Follow-up responses include metadata about how features were generated:

```json
{
  "status": "finished",
  "recommended_features": [...],
  "metadata": {
    "new_features_count": 8,
    "existing_features_count": 2,
    "total_in_registry": 15,
    "selected_features_used": 3,
    "selected_feature_names": ["feature_1", "feature_2", "feature_3"]
  }
}
```

- `new_features_count`: Features newly generated in this request
- `existing_features_count`: Features that were already in registry (deduplicated)
- `total_in_registry`: Total features in the conversation registry
- `selected_features_used`: Number of selected features used as context
- `selected_feature_names`: Names of selected features used

## Best Practices

1. **Use consistent project_id and domain** - This maintains conversation context
2. **Select features before follow-ups** - Selected features provide better context
3. **Be specific in follow-up queries** - More specific queries generate better complementary features
4. **Check conversation state** - Use the state endpoints to see what's cached
5. **Clear context when needed** - Use `DELETE /conversation/state/{project_id}` to start fresh

## Clearing Conversation Context

To start a fresh conversation:

```bash
curl -X 'DELETE' \
  'http://localhost:8020/feature-engineering/conversation/state/cve_data?domain=cybersecurity'
```

This clears:
- All conversation history
- All feature registry entries
- All selected features

## WebSocket Streaming

For real-time follow-up requests via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8020/feature-engineering/ws/query_123');

// Initial request
ws.send(JSON.stringify({
  action: "recommend",
  user_query: "I need SOC2 vulnerability features",
  project_id: "cve_data",
  domain: "cybersecurity"
}));

// After selecting features, follow-up request
ws.send(JSON.stringify({
  action: "recommend",
  user_query: "I need more risk assessment features",
  project_id: "cve_data",  // Same project_id
  domain: "cybersecurity"  // Same domain
}));
```

## Summary

Follow-up requests are **automatic** - just use the same `project_id` and `domain`:
- ✅ Context is maintained automatically
- ✅ Selected features are included automatically
- ✅ Query is enhanced automatically
- ✅ New features complement existing selections
- ✅ Registry accumulates features (no duplicates)

You don't need to manually pass context - the system handles it for you!

