# Feature Engineering Conversation API Examples

Complete examples for all conversation API endpoints.

## Base URL
```
http://localhost:8020/feature-engineering
```

---

## 1. Recommend Features (Non-Streaming)

**Endpoint:** `POST /feature-engineering/recommend/stream` (or use conversation service)

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_query": "I want to generate SOC2 compliance report based on the assets, asset types and vulnerabilities for assets",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "recommend"
}'
```

**Response:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "recommended_features": [
    {
      "feature_id": "feat_123",
      "feature_name": "critical_vulnerability_count",
      "feature_type": "count",
      "natural_language_question": "Count the number of vulnerabilities where severity is Critical",
      "business_context": "Tracks critical vulnerabilities for SOC2 compliance",
      "transformation_layer": "gold",
      "recommendation_score": 0.95,
      "status": "recommended"
    }
  ],
  "message": "Generated 10 feature recommendations (8 new, 2 from cache) - Built upon 0 previously selected features",
  "metadata": {
    "new_features_count": 8,
    "existing_features_count": 2,
    "total_in_registry": 10,
    "selected_features_used": 0
  }
}
```

---

## 2. Recommend Features (Streaming - SSE)

**Endpoint:** `POST /feature-engineering/recommend/stream`

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_query": "I need risk assessment features for vulnerabilities",
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "recommend"
}'
```

**Response (SSE stream):**
```
data: {"query_id": "...", "status": "processing", "message": "Processing recommend request..."}

data: {"query_id": "...", "status": "recommending", "message": "Analyzing your query and generating feature recommendations..."}

data: {"query_id": "...", "status": "analyzing", "message": "Analyzing requirements and identifying relevant features..."}

data: {"query_id": "...", "status": "recommending", "recommended_features": [...], "total_found": 10, "current_batch": 1, "total_batches": 2}

data: {"query_id": "...", "status": "finished", "recommended_features": [...], "message": "Generated 10 feature recommendations"}
```

**JavaScript Example:**
```javascript
const eventSource = new EventSource('http://localhost:8020/feature-engineering/recommend/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    user_query: "I need risk assessment features",
    project_id: "cve_data",
    domain: "cybersecurity",
    action: "recommend"
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Status:', data.status);
  if (data.recommended_features) {
    console.log('Features:', data.recommended_features);
  }
};
```

---

## 3. Select Features

**Endpoint:** `POST /feature-engineering/select`

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/select' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "select",
  "selected_feature_ids": ["feat_123", "feat_456", "feat_789"],
  "auto_save": false
}'
```

**Response:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "selected_features": [
    {
      "feature_id": "feat_123",
      "feature_name": "critical_vulnerability_count",
      "status": "selected"
    }
  ],
  "total_selected": 3,
  "message": "Selected 3 features and stored in cache"
}
```

**With Auto-Save:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/select' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "select",
  "selected_feature_ids": ["feat_123", "feat_456"],
  "auto_save": true
}'
```

---

## 4. Save Selected Features

**Endpoint:** `POST /feature-engineering/save`

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "save"
}'
```

**With Custom Path:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/save' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "save",
  "save_path": "/path/to/my_features.json"
}'
```

**Response:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "message": "Saved 3 features to /path/to/selected_features_cve_data_cybersecurity_20240101_120000.json",
  "save_path": "/path/to/selected_features_cve_data_cybersecurity_20240101_120000.json"
}
```

---

## 5. Finalize Workflow

**Endpoint:** `POST /feature-engineering/finalize`

**Request:**
```bash
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/finalize' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "action": "finalize",
  "workflow_name": "SOC2_Vulnerability_Report",
  "workflow_description": "SOC2 compliance report for vulnerability tracking",
  "workflow_type": "feature_registry",
  "version": "1.0.0"
}'
```

**Response:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "finished",
  "workflow_name": "SOC2_Vulnerability_Report",
  "workflow_description": "SOC2 compliance report for vulnerability tracking",
  "workflow_type": "feature_registry",
  "version": "1.0.0",
  "total_features": 5,
  "save_path": "/path/to/finalized/SOC2_Vulnerability_Report_v1.0.0_20240101_120000.json",
  "message": "Finalized workflow 'SOC2_Vulnerability_Report' v1.0.0 with 5 features"
}
```

---

## 6. Get Conversation State

**Endpoint:** `GET /feature-engineering/conversation/state/{project_id}`

**Request:**
```bash
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/state/cve_data?domain=cybersecurity' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "total_queries": 3,
  "total_features": 15,
  "selected_features": 5,
  "compliance_framework": "SOC2",
  "last_query": "I need more risk assessment features",
  "all_cached_features": [...],
  "previous_queries": [
    "I want SOC2 compliance features",
    "I need risk assessment features",
    "I need more risk assessment features"
  ]
}
```

---

## 7. Get All Cached Features

**Endpoint:** `GET /feature-engineering/conversation/cache/{project_id}`

**Request:**
```bash
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/cache/cve_data?domain=cybersecurity' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "total_cached": 15,
  "features": [
    {
      "feature_id": "feat_123",
      "feature_name": "critical_vulnerability_count",
      "status": "selected"
    }
  ]
}
```

---

## 8. Get Selected Features Only

**Endpoint:** `GET /feature-engineering/conversation/selected/{project_id}`

**Request:**
```bash
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/selected/cve_data?domain=cybersecurity' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "project_id": "cve_data",
  "domain": "cybersecurity",
  "total_selected": 5,
  "features": [
    {
      "feature_id": "feat_123",
      "feature_name": "critical_vulnerability_count",
      "status": "selected"
    }
  ]
}
```

---

## 9. List Finalized Workflows

**Endpoint:** `GET /feature-engineering/finalized`

**Request:**
```bash
# List all
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized' \
  -H 'accept: application/json'

# Filter by project_id
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized?project_id=cve_data' \
  -H 'accept: application/json'

# Filter by domain
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized?domain=cybersecurity' \
  -H 'accept: application/json'

# Filter by workflow_name
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized?workflow_name=SOC2_Vulnerability_Report' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "total": 2,
  "workflows": [
    {
      "file_path": "/path/to/finalized/SOC2_Vulnerability_Report_v1.0.0_20240101_120000.json",
      "workflow_name": "SOC2_Vulnerability_Report",
      "workflow_description": "SOC2 compliance report for vulnerability tracking",
      "workflow_type": "feature_registry",
      "version": "1.0.0",
      "project_id": "cve_data",
      "domain": "cybersecurity",
      "finalized_at": "2024-01-01T12:00:00",
      "total_features": 5,
      "total_queries": 3
    }
  ]
}
```

---

## 10. Get Specific Finalized Workflow

**Endpoint:** `GET /feature-engineering/finalized/{workflow_name}`

**Request:**
```bash
# Get latest version
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized/SOC2_Vulnerability_Report' \
  -H 'accept: application/json'

# Get specific version
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized/SOC2_Vulnerability_Report?version=1.0.0' \
  -H 'accept: application/json'

# With filters
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/finalized/SOC2_Vulnerability_Report?version=1.0.0&project_id=cve_data&domain=cybersecurity' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "workflow": {
    "workflow_metadata": {
      "name": "SOC2_Vulnerability_Report",
      "version": "1.0.0",
      "description": "...",
      "finalized_at": "2024-01-01T12:00:00"
    },
    "conversations": {
      "total_queries": 3,
      "queries": [...]
    },
    "selected_features": {
      "total_count": 5,
      "features": [...]
    },
    "pipeline_structure": {...}
  },
  "file_path": "/path/to/finalized/SOC2_Vulnerability_Report_v1.0.0_20240101_120000.json",
  "version": "1.0.0"
}
```

---

## 11. Clear Conversation

**Endpoint:** `DELETE /feature-engineering/conversation/state/{project_id}`

**Request:**
```bash
curl -X 'DELETE' \
  'http://localhost:8020/feature-engineering/conversation/state/cve_data?domain=cybersecurity' \
  -H 'accept: application/json'
```

**Response:**
```json
{
  "status": "success",
  "message": "Conversation cleared for cve_data/cybersecurity"
}
```

---

## 12. WebSocket Connection

**Endpoint:** `WS /feature-engineering/ws/{query_id}`

**JavaScript Example:**
```javascript
const ws = new WebSocket('ws://localhost:8020/feature-engineering/ws/my_query_123');

ws.onopen = () => {
  // Send recommend request
  ws.send(JSON.stringify({
    action: "recommend",
    user_query: "I need SOC2 vulnerability features",
    project_id: "cve_data",
    domain: "cybersecurity"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Status:', data.status);
  
  if (data.status === "finished" && data.recommended_features) {
    console.log('Features:', data.recommended_features);
    
    // Select features
    ws.send(JSON.stringify({
      action: "select",
      project_id: "cve_data",
      domain: "cybersecurity",
      selected_feature_ids: data.recommended_features.slice(0, 3).map(f => f.feature_id)
    }));
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

---

## Complete Conversation Flow Example

```bash
# Step 1: Initial recommendation
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_query": "I want SOC2 compliance features for vulnerabilities",
    "project_id": "cve_data",
    "domain": "cybersecurity",
    "action": "recommend"
  }'

# Step 2: Select features (use feature_ids from Step 1 response)
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/select' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "cve_data",
    "domain": "cybersecurity",
    "action": "select",
    "selected_feature_ids": ["feat_123", "feat_456", "feat_789"]
  }'

# Step 3: Follow-up recommendation (same project_id/domain = context maintained)
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/recommend/stream' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_query": "I need more risk assessment features",
    "project_id": "cve_data",
    "domain": "cybersecurity",
    "action": "recommend"
  }'

# Step 4: Check conversation state
curl -X 'GET' \
  'http://localhost:8020/feature-engineering/conversation/state/cve_data?domain=cybersecurity'

# Step 5: Finalize workflow
curl -X 'POST' \
  'http://localhost:8020/feature-engineering/finalize' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "cve_data",
    "domain": "cybersecurity",
    "action": "finalize",
    "workflow_name": "SOC2_Vulnerability_Report",
    "workflow_description": "Complete SOC2 compliance workflow"
  }'
```

---

## Python Example

```python
import requests
import json

BASE_URL = "http://localhost:8020/feature-engineering"

# 1. Recommend features
response = requests.post(
    f"{BASE_URL}/recommend/stream",
    json={
        "user_query": "I want SOC2 compliance features",
        "project_id": "cve_data",
        "domain": "cybersecurity",
        "action": "recommend"
    }
)
data = response.json()
feature_ids = [f["feature_id"] for f in data["recommended_features"][:3]]

# 2. Select features
response = requests.post(
    f"{BASE_URL}/select",
    json={
        "project_id": "cve_data",
        "domain": "cybersecurity",
        "action": "select",
        "selected_feature_ids": feature_ids
    }
)

# 3. Follow-up request
response = requests.post(
    f"{BASE_URL}/recommend/stream",
    json={
        "user_query": "I need more risk features",
        "project_id": "cve_data",  # Same project_id
        "domain": "cybersecurity",  # Same domain
        "action": "recommend"
    }
)

# 4. Get conversation state
response = requests.get(
    f"{BASE_URL}/conversation/state/cve_data",
    params={"domain": "cybersecurity"}
)
state = response.json()
print(f"Total features: {state['total_features']}")
print(f"Selected: {state['selected_features']}")

# 5. Finalize
response = requests.post(
    f"{BASE_URL}/finalize",
    json={
        "project_id": "cve_data",
        "domain": "cybersecurity",
        "action": "finalize",
        "workflow_name": "SOC2_Report",
        "workflow_description": "SOC2 compliance workflow"
    }
)
```

---

## Notes

- **Context is maintained automatically** by `project_id` + `domain` combination
- **Selected features** are automatically included in follow-up requests
- **Features accumulate** in the registry (no duplicates)
- **Streaming endpoints** use Server-Sent Events (SSE)
- **WebSocket** provides bidirectional real-time communication
- All endpoints return JSON except streaming which returns SSE format

