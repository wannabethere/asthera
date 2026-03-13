#!/bin/bash
# Run Agent Conversation Integration Tests
#
# This script helps you run the agent conversation integration tests.
# You can either:
# 1. Run tests with TestClient (no server needed) - default
# 2. Run tests against a live server (start server separately)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Agent Conversation Integration Tests"
echo "=========================================="
echo ""

# Check if server URL is provided
if [ -n "$SERVER_URL" ]; then
    echo "⚠️  SERVER_URL is set: $SERVER_URL"
    echo "   Make sure the server is running at that URL"
    echo ""
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing..."
    pip install pytest pytest-asyncio
fi

# Run tests
echo "Running tests..."
echo ""

# Default: run with TestClient (no server needed)
if [ -z "$SERVER_URL" ]; then
    echo "Mode: TestClient (no server needed)"
    pytest tests/test_agent_conversations_integration.py -v "$@"
else
    echo "Mode: Live server at $SERVER_URL"
    pytest tests/test_agent_conversations_integration.py -v "$@"
fi

echo ""
echo "=========================================="
echo "Tests completed"
echo "=========================================="
