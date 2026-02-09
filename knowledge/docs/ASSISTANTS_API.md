# Knowledge Assistants API Documentation

This document describes how to call the Knowledge API assistants: streaming graph execution, simple Q&A, and MCP (Model Context Protocol). Use it for integration, testing, and sharing with consumers of the API.

---

## Base URL and authentication

- **Base URL:** `https://<your-host>/api/streams` (or `http://localhost:8000/api/streams` for local).
- **OpenAPI docs:** `GET /docs` (Swagger UI) and `GET /redoc` (ReDoc) on the same host as the API.

When **API security is enabled** (`API_SECURITY_ENABLED=true`), all `/api/*` requests except `/api/health` must include a provisioned token:

- **Header:** `Authorization: Bearer <token>` or `X-API-Token: <token>`

Example with curl:

```bash
curl -H "Authorization: Bearer YOUR_PROVISIONED_TOKEN" \
  https://<your-host>/api/streams/assistants
```

---

## 1. Health and status

### API health

```http
GET /api/health
```

No auth required. Returns API status, database, and vector store connectivity.

**Example:**

```bash
curl -s https://<your-host>/api/health | jq
```

### Streaming router health

```http
GET /api/streams/health
```

Returns streaming router status and assistant count.

**Example:**

```bash
curl -s https://<your-host>/api/streams/health | jq
```

### Assistants status (detailed)

```http
GET /api/assistants/status
```

Returns all assistants with operational status, graph count, default graph, and whether they can accept requests.

**Example:**

```bash
curl -s https://<your-host>/api/assistants/status | jq
```

**Sample response (trimmed):**

```json
{
  "total_assistants": 5,
  "operational_assistants": 5,
  "assistants": [
    {
      "assistant_id": "data_assistance_assistant",
      "name": "Data Assistance Assistant",
      "description": "Helps answer questions about metrics, schemas, and compliance controls",
      "status": "operational",
      "graph_count": 1,
      "default_graph_id": "data_assistance_graph",
      "graphs": [{"graph_id": "data_assistance_graph", "name": "Data Assistance Graph", "is_default": true, "is_operational": true}],
      "can_accept_requests": true
    }
  ]
}
```

---

## 2. List and manage assistants

All under prefix: **`/api/streams`**.

### List all assistants

```http
GET /api/streams/assistants
```

**Example:**

```bash
curl -s https://<your-host>/api/streams/assistants | jq
```

**Response:** `AssistantListResponse` — `assistants`: array of `AssistantInfo` (assistant_id, name, description, graph_count, default_graph_id, metadata).

### Get one assistant

```http
GET /api/streams/assistants/{assistant_id}
```

**Example:**

```bash
curl -s https://<your-host>/api/streams/assistants/data_assistance_assistant | jq
```

### List graphs for an assistant

```http
GET /api/streams/assistants/{assistant_id}/graphs
```

**Example:**

```bash
curl -s https://<your-host>/api/streams/assistants/data_assistance_assistant/graphs | jq
```

### Create assistant (programmatic)

```http
POST /api/streams/assistants
Content-Type: application/json
```

**Body:** `AssistantCreateRequest`

| Field         | Type            | Required | Description                |
|---------------|-----------------|----------|----------------------------|
| assistant_id  | string          | Yes      | Unique ID                  |
| name          | string          | Yes      | Display name               |
| description   | string          | No       | Description                 |
| metadata      | object          | No       | Extra key-value metadata   |

**Example:**

```bash
curl -X POST https://<your-host>/api/streams/assistants \
  -H "Content-Type: application/json" \
  -d '{"assistant_id":"my_assistant","name":"My Assistant","description":"Custom assistant"}'
```

### Delete assistant

```http
DELETE /api/streams/assistants/{assistant_id}
```

**Example:**

```bash
curl -X DELETE https://<your-host>/api/streams/assistants/my_assistant
```

---

## 3. Invoke a graph (streaming SSE)

Run an assistant’s graph and consume events over Server-Sent Events.

```http
POST /api/streams/invoke
Content-Type: application/json
```

**Body:** `GraphInvokeRequest`

| Field        | Type   | Required | Description |
|--------------|--------|----------|-------------|
| assistant_id | string | Yes      | Assistant ID (e.g. `data_assistance_assistant`) |
| query        | string | Yes      | User question or input |
| graph_id     | string | No       | Graph ID; if omitted, default graph is used |
| session_id   | string | No       | Thread/session ID; auto-generated if omitted |
| input_data   | object | No       | Extra inputs (e.g. product_name, project_id, actor) |
| config       | object | No       | LangGraph config overrides |

**Response:** `text/event-stream` (SSE). Event types include: `graph_started`, `node_started`, `node_completed`, `state_update`, `progress`, `result`, `graph_completed`, `graph_error`, `node_error`, `keep_alive`.

**Example (stream to stdout):**

```bash
curl -N -X POST https://<your-host>/api/streams/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "data_assistance_assistant",
    "query": "What tables do I need for a SOC2 vulnerability report for user access?"
  }'
```

**Example with optional fields:**

```bash
curl -N -X POST https://<your-host>/api/streams/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "data_assistance_assistant",
    "graph_id": "data_assistance_graph",
    "query": "List columns in DirectVulnerabilitiesCounts and Issue tables",
    "session_id": "my-session-123",
    "input_data": {
      "product_name": "Snyk",
      "project_id": "Snyk"
    }
  }'
```

**Preconfigured assistant IDs** (from `config/assistants_configuration.yaml`):

| assistant_id                 | Description |
|-----------------------------|-------------|
| data_assistance_assistant   | Metrics, schemas, compliance controls (SOC2, GDPR, etc.) |
| knowledge_assistance_assistant | SOC2 compliance knowledge, controls, risks |
| compliance_assistant        | Compliance, risk analysis, regulatory requirements |
| product_assistant           | Product docs, APIs, features, integrations |
| domain_knowledge_assistant  | Domain concepts, best practices, technical patterns |

---

## 4. Ask (simple Q&A, non-streaming)

Single request/response: ask a question for a given dataset; the API runs the assistant’s default graph and returns the final answer.

```http
POST /api/streams/ask
Content-Type: application/json
```

**Body:** `AskRequest`

| Field           | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| question        | string | Yes      | The question to ask |
| dataset         | string | Yes      | Dataset/product identifier (e.g. "Snyk") |
| agent           | string | No       | Assistant ID; if omitted, first available assistant is used |
| session_id      | string | No       | Session ID; auto-generated if omitted |
| dataset_metadata| object | No       | Extra metadata (e.g. actor) |

**Response:** `AskResponse`

| Field      | Type   | Description |
|------------|--------|-------------|
| answer     | string | Final answer text |
| agent_used | string | Assistant ID that was used |
| session_id | string | Session ID for the run |
| metadata   | object | Extra info (dataset, graph_id, sources, etc.) |

**Example:**

```bash
curl -s -X POST https://<your-host>/api/streams/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What SOC2 vulnerability metrics and KPIs should I show for an audit report?",
    "dataset": "Snyk"
  }' | jq
```

**Example with specific agent:**

```bash
curl -s -X POST https://<your-host>/api/streams/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Give me a playbook for top SOC2 controls and risks for Snyk",
    "dataset": "Snyk",
    "agent": "knowledge_assistance_assistant"
  }' | jq
```

---

## 5. MCP (Model Context Protocol) – JSON-RPC 2.0

MCP endpoint for tools that speak JSON-RPC 2.0 (e.g. MCP clients).

```http
POST /api/streams/mcp
Content-Type: application/json
```

**Request body:** JSON-RPC 2.0 envelope

```json
{
  "jsonrpc": "2.0",
  "method": "<method_name>",
  "params": { ... },
  "id": "<request_id>"
}
```

Supported methods:

- **`ask_question`** — Same semantics as the `/ask` endpoint.
- **`list_assistants`** — Returns available assistants (no params required).

### MCP: ask_question

**Params:**

| Key       | Type   | Required | Description |
|-----------|--------|----------|-------------|
| question  | string | Yes      | The question to ask |
| dataset   | string | Yes      | Dataset/product identifier |
| agent     | string | No       | Assistant ID |
| session_id| string | No       | Session ID |
| dataset_metadata | object | No | Extra metadata |

**Example:**

```bash
curl -s -X POST https://<your-host>/api/streams/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "ask_question",
    "params": {
      "question": "What columns are in DirectVulnerabilitiesCounts and Issue?",
      "dataset": "Snyk",
      "agent": "data_assistance_assistant"
    },
    "id": "req-1"
  }' | jq
```

**Success response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "answer": "...",
    "agent_used": "data_assistance_assistant",
    "session_id": "uuid",
    "metadata": {}
  },
  "id": "req-1"
}
```

### MCP: list_assistants

**Params:** None.

**Example:**

```bash
curl -s -X POST https://<your-host>/api/streams/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_assistants","params":{},"id":"req-2"}' | jq
```

**Success response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "assistants": [
      {
        "assistant_id": "data_assistance_assistant",
        "name": "Data Assistance Assistant",
        "description": "...",
        "graph_count": 1,
        "default_graph_id": "data_assistance_graph"
      }
    ]
  },
  "id": "req-2"
}
```

**Error response (method not found / invalid params):**

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "Method 'foo' is not supported. Available methods: ask_question, list_assistants"
  },
  "id": "req-2"
}
```

---

## 6. Quick reference: endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET    | /api/health | API health (no auth) |
| GET    | /api/streams/health | Streaming health |
| GET    | /api/assistants/status | All assistants status |
| GET    | /api/streams/assistants | List assistants |
| GET    | /api/streams/assistants/{id} | Get one assistant |
| GET    | /api/streams/assistants/{id}/graphs | List graphs for assistant |
| POST   | /api/streams/assistants | Create assistant |
| DELETE | /api/streams/assistants/{id} | Delete assistant |
| POST   | /api/streams/invoke | Run graph (SSE stream) |
| POST   | /api/streams/ask | Simple Q&A (single response) |
| POST   | /api/streams/mcp | MCP JSON-RPC (ask_question, list_assistants) |

Replace `<your-host>` with your API host (e.g. `localhost:8000` or your deployed base URL). When API security is enabled, add `Authorization: Bearer <token>` or `X-API-Token: <token>` to all requests except `GET /api/health`.
