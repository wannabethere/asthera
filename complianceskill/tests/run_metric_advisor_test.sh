#!/bin/bash
# Script to run metric advisor test against a live server

# Default server URL
SERVER_URL="${1:-http://localhost:8002}"

echo "=========================================="
echo "CSOD Metric Advisor Test"
echo "=========================================="
echo "Server URL: $SERVER_URL"
echo ""

# Navigate to the compliance skill directory
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR/.." || exit

# Run the test
python tests/automated_agent_conversation.py \
    --test-metric-advisor \
    --server-url "$SERVER_URL" \
    --auto-respond-checkpoints \
    --max-turns 20

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✓ All metric advisor tests passed."
else
    echo ""
    echo "✗ Some metric advisor tests failed."
fi

exit $EXIT_CODE
