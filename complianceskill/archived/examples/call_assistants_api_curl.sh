#!/usr/bin/env bash
# Curl examples for Knowledge Assistants API at http://52.6.13.191:8040
# Token is set below (change if your server uses a different provisioned token).
# Usage: ./call_assistants_api_curl.sh
#
# Difference from chat app (agentic_chat):
# - Chat uses POST /api/streams/invoke (SSE streaming): assistant_id, query, input_data.
#   Same as the "invoke" example below; use an assistant that has a default graph.
# - This script also shows POST /api/streams/ask (single JSON response): question, dataset, agent.
#   /ask requires the chosen agent to have a default graph configured.
#
# If you see "has no default graph" or "has no graphs": on this server no assistants have
# graphs registered. Check GET /api/assistants/status for "operational" assistants, or
# configure graphs (assistants_configuration.yaml + graph registration) on the server.
# Override the assistant used for invoke: INVOKE_ASSISTANT_ID=an_operational_id ./call_assistants_api_curl.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="http://52.6.13.191:8040"
# Fixed token (must be in server's API_PROVISIONED_TOKENS when API_SECURITY_ENABLED=true)
TOKEN="eyJvcmciOiJkZWZhdWx0IiwidGVhbSI6InBsYXRmb3JtIiwiaWF0IjoxNzM1Njg5NjAwLCJ2YWxpZF9zZWMiOjYzMDcyMDAwfQ"
# Assistant used for /invoke; must have graph_count > 0 and a default graph. Check /api/assistants/status.
INVOKE_ASSISTANT_ID="${INVOKE_ASSISTANT_ID:-data_assistance_assistant}"

echo "Base URL: $BASE_URL"
echo "Token (first 20 chars): ${TOKEN:0:20}..."
echo ""

# Health (no auth required)
echo "=== GET /api/health ==="
curl -s "$BASE_URL/api/health" | head -c 500
echo -e "\n"

# Authenticated endpoints
AUTH_HEADER="Authorization: Bearer $TOKEN"

echo "=== GET /api/streams/health ==="
curl -s -H "$AUTH_HEADER" "$BASE_URL/api/streams/health" | head -c 500
echo -e "\n"

echo "=== GET /api/streams/assistants ==="
curl -s -H "$AUTH_HEADER" "$BASE_URL/api/streams/assistants" | head -c 800
echo -e "\n"

# /invoke = streaming SSE (same as chat app). Use an assistant that has a default graph.
# Chat app sends: assistant_id, query, session_id, input_data: { query, project_id, user_context }.
INVOKE_MAX_TIME=600
echo "=== POST /api/streams/invoke (SSE stream, like chat app; assistant=$INVOKE_ASSISTANT_ID; up to ${INVOKE_MAX_TIME}s) ==="
echo "Request body: assistant_id, query, input_data.project_id (dataset). First 1200 chars of stream:"
curl -s -N --max-time "$INVOKE_MAX_TIME" -X POST "$BASE_URL/api/streams/invoke" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d "{\"assistant_id\":\"$INVOKE_ASSISTANT_ID\",\"query\":\"What tables are needed for SOC2 vulnerability reporting?\",\"session_id\":\"curl-session-1\",\"input_data\":{\"query\":\"What tables are needed for SOC2 vulnerability reporting?\",\"project_id\":\"Snyk\",\"user_context\":{\"project_id\":\"Snyk\"}}}" | head -c 1200
echo -e "\n"

# /ask = single JSON response (question, dataset, agent). Agent must have a default graph.
ASK_MAX_TIME=600
echo "=== POST /api/streams/ask (single response; waiting up to ${ASK_MAX_TIME}s)... ==="
curl -s --max-time "$ASK_MAX_TIME" -X POST "$BASE_URL/api/streams/ask" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"question":"What SOC2 vulnerability metrics should I show for an audit report?","dataset":"Snyk","agent":"compliance_assistant"}' | head -c 600
echo -e "\n"


#curl -s --max-time 600 -X POST "http://localhost:8040/api/streams/ask" \
#  -H "Content-Type: application/json" \
#  -d '{"question":"What SOC2 vulnerability metrics should I show for an audit report?","dataset":"Snyk","agent":"data_assistance_assistant"}' | head -c 600
#echo -e "\n"

echo "=== POST /api/streams/mcp (list_assistants) ==="
curl -s -X POST "$BASE_URL/api/streams/mcp" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_assistants","params":{},"id":"req-1"}' | head -c 600
echo -e "\n"

echo "Done."
