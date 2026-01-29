. Via streams (HTTP)
List assistants
GET {base_url}/api/streams/assistants
Use the assistant_id from each item when calling invoke or ask.
Streaming invoke
POST {base_url}/api/streams/invoke
Body (JSON): assistant_id (required), query (required), optional: graph_id, session_id, input_data, config.
Response: SSE stream. Consume with an EventSource client or by reading the stream.
Non‑streaming ask
POST {base_url}/api/streams/ask
Body (JSON): question (required), dataset (required), optional: agent (= assistant_id), session_id, dataset_metadata.
Response: JSON with answer, agent_used, session_id, metadata.
2. Via AsyncQueryPipeline (in code)
Get the pipeline from the pipeline registry (e.g. after pipeline_startup has run):
from app.pipelines import get_pipeline_registry
registry = get_pipeline_registry()
pipeline = registry.get_pipeline("general_query_pipeline")
(Use the same pipeline_id you used when registering, e.g. in pipeline_startup.py.)
Call it:
result = await pipeline.run(inputs={"query": "<user question>", "context": {}, "options": {}})
Use the result:
result["success"], result["data"], result.get("error").
There is no HTTP endpoint that calls AsyncQueryPipeline by id; streams use assistant_id (LangGraph assistants). To call a specific pipeline over HTTP you’d need to add a route that gets the pipeline by id from the pipeline registry and calls run() as above.

import asyncio
from app.pipelines import get_pipeline_registry

async def main():
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline("general_query")
    result = await pipeline.run(inputs={
        "query": "What are key SOC2 controls?",
        "context": {},
        "options": {}
    })
    print(result["success"], result.get("data"), result.get("error"))

asyncio.run(main())


import requests
BASE = "http://localhost:8000"

# List
r = requests.get(f"{BASE}/api/streams/assistants")
assistants = r.json()["assistants"]

# Ask
r = requests.post(f"{BASE}/api/streams/ask", json={
    "question": "What is SOC2?",
    "dataset": "Snyk",
    "agent": "knowledge_assistance_assistant"
})
print(r.json()["answer"])

# Invoke stream
r = requests.post(f"{BASE}/api/streams/invoke",
    json={"assistant_id": "knowledge_assistance_assistant", "query": "Explain SOC2"},
    stream=True)
for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        print(line.decode())


# List assistants
curl -s http://localhost:8000/api/streams/assistants | jq .

# Ask (no agent = first assistant)
curl -s -X POST http://localhost:8000/api/streams/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is SOC2?", "dataset": "Snyk"}' | jq .

# Ask a specific assistant
curl -s -X POST http://localhost:8000/api/streams/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is SOC2?", "dataset": "Snyk", "agent": "knowledge_assistance_assistant"}' | jq .

# Invoke stream (SSE)
curl -s -N -X POST http://localhost:8000/api/streams/invoke \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": "knowledge_assistance_assistant", "query": "Explain SOC2 in one sentence"}'