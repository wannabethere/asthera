#!/bin/bash

# Example curl command to validate an alert condition
# Based on the alert data from the create_single_alert response
#
# Usage:
#   ./validate_condition_curl.sh
#   or
#   curl -X POST "http://localhost:8000/alerts/validate-condition" \
#     -H "Content-Type: application/json" \
#     -d @validate_condition_request.json

BASE_URL="${BASE_URL:-http://localhost:8000}"
ENDPOINT="${BASE_URL}/alerts/validate-condition"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUEST_FILE="${SCRIPT_DIR}/validate_condition_request.json"

if [ ! -f "$REQUEST_FILE" ]; then
    echo "Error: Request file not found: $REQUEST_FILE"
    exit 1
fi

echo "Calling: $ENDPOINT"
echo "Using request file: $REQUEST_FILE"
echo ""

curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d @"$REQUEST_FILE" \
  -w "\n\nHTTP Status: %{http_code}\n"
