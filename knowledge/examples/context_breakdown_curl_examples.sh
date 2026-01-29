#!/bin/bash
# Context Breakdown API - curl Examples

BASE_URL="http://localhost:8000"

echo "=== Context Breakdown API Examples ==="
echo

# 1. Health Check
echo "1. Health Check"
curl -X GET "$BASE_URL/api/context/health" | jq '.'
echo
echo

# 2. MDL Breakdown (Non-Streaming)
echo "2. MDL Breakdown - What features does Vulnerability table have?"
curl -X POST "$BASE_URL/api/context/breakdown" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What features does the Vulnerability table provide?",
    "domain": "mdl",
    "product_name": "Snyk"
  }' | jq '.'
echo
echo

# 3. Compliance Breakdown (Non-Streaming)
echo "3. Compliance Breakdown - SOC2 access control requirements"
curl -X POST "$BASE_URL/api/context/breakdown" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What evidence is needed for SOC2 access control?",
    "domain": "compliance",
    "frameworks": ["SOC2"]
  }' | jq '.query_type, .domains_involved, .frameworks, .search_questions[0:2]'
echo
echo

# 4. Auto-Routing (Cross-Domain Query)
echo "4. Auto-Routing - Cross-domain query"
curl -X POST "$BASE_URL/api/context/breakdown" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does Snyk vulnerability table support SOC2 controls?",
    "domain": "auto",
    "product_name": "Snyk",
    "frameworks": ["SOC2"]
  }' | jq '.query_type, .domains_involved, .search_questions | length'
echo
echo

# 5. Summary Endpoint (Lightweight)
echo "5. Summary Endpoint"
curl -X POST "$BASE_URL/api/context/breakdown/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What features does Vulnerability table have?",
    "domain": "mdl",
    "product_name": "Snyk"
  }' | jq '.'
echo
echo

# 6. Streaming Endpoint (SSE)
echo "6. Streaming Endpoint (Server-Sent Events)"
echo "Note: This will stream events in real-time"
curl -X POST "$BASE_URL/api/context/breakdown/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What vulnerability tables exist in Snyk?",
    "domain": "mdl",
    "product_name": "Snyk"
  }'
echo
echo

echo "=== Examples Complete ==="
