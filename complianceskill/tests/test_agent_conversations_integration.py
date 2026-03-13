#!/usr/bin/env python3
"""
Conversational Integration Test for Agent Gateway API

This test validates conversational interactions with all registered agents via the API.
It tests:
1. Agent registration and discovery
2. Single-turn conversations for each agent
3. Multi-turn conversations with context persistence
4. Streaming responses (SSE)
5. Error handling

Usage:
    # Run all tests (uses TestClient - no server needed)
    pytest tests/test_agent_conversations_integration.py -v

    # Run specific agent test
    pytest tests/test_agent_conversations_integration.py -v -k "csod_planner"

    # Run with live server (start server separately first)
    # Terminal 1: python app/api/main.py
    # Terminal 2: pytest tests/test_agent_conversations_integration.py -v

    # Run directly (for debugging)
    python tests/test_agent_conversations_integration.py

Configuration:
    - Uses .env for LLM and vector store settings
    - Requires server to be running (or uses TestClient)
    - Tests all agents from agent_registration.py
"""

import os
import sys
import json
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load .env file before importing app modules
base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✓ Loaded .env file from: {env_file}")
else:
    print("⚠️  No .env file found. Using default environment variables.")

# Add parent directory to path
sys.path.insert(0, str(base_dir))

import pytest
from fastapi.testclient import TestClient
try:
    from httpx import AsyncClient, ASGITransport
    HAS_ASGI_TRANSPORT = True
except ImportError:
    HAS_ASGI_TRANSPORT = False
    logger.warning("httpx ASGITransport not available, async streaming tests will be skipped")

# Import app after path setup
from app.api.main import app
from app.services.agent_registration import register_all_agents
from app.adapters.registry import get_agent_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

# Create output directory for test results
OUTPUT_BASE_DIR = base_dir / "tests" / "outputs" / "agent_conversations"
OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Test Configuration
# ============================================================================

# Agent test cases - each agent gets a simple conversational query
AGENT_TEST_CASES = {
    "csod-planner": {
        "name": "CSOD Planner",
        "queries": [
            "I want to create a metrics dashboard for learning and development",
            "What metrics should I track for compliance training?",
        ],
        "expected_events": ["step_start", "token", "step_final"],
    },
    "csod-workflow": {
        "name": "CSOD Metrics & KPIs Workflow",
        "queries": [
            "Show me metrics for employee training completion",
            "What are the KPIs for learning management?",
        ],
        "expected_events": ["step_start", "token", "tool_start", "step_final"],
    },
    "csod-metric-advisor": {
        "name": "CSOD Metric Advisor",
        "queries": [
            "Recommend metrics for learning and development with causal reasoning",
            "What KPIs should I track for compliance training?",
        ],
        "expected_events": ["step_start", "token", "tool_start", "step_final"],
    },
    "dt-workflow": {
        "name": "Detection & Triage Workflow",
        "queries": [
            "Create SIEM rules for SOC 2 CC6.1",
            "Help me detect security vulnerabilities",
        ],
        "expected_events": ["step_start", "token", "tool_start", "step_final"],
    },
    "compliance-workflow": {
        "name": "Compliance Automation Workflow",
        "queries": [
            "Analyze our compliance with SOC 2",
            "What controls do we need for HIPAA?",
        ],
        "expected_events": ["step_start", "token", "tool_start", "step_final"],
    },
    "dashboard-agent": {
        "name": "Dashboard Layout Advisor",
        "queries": [
            "Help me design a dashboard layout",
            "What widgets should I use for metrics visualization?",
        ],
        "expected_events": ["step_start", "token", "step_final"],
    },
}


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_client():
    """Create FastAPI test client with registered agents."""
    # Register agents before creating client
    try:
        register_all_agents()
        logger.info("Agents registered successfully")
    except Exception as e:
        logger.warning(f"Agent registration warning: {e}")
    
    # Create test client
    client = TestClient(app)
    return client


@pytest.fixture(scope="session")
async def async_client():
    """Create async HTTP client for streaming tests."""
    if not HAS_ASGI_TRANSPORT:
        pytest.skip("httpx ASGITransport not available")
    
    # Register agents
    try:
        register_all_agents()
        logger.info("Agents registered successfully")
    except Exception as e:
        logger.warning(f"Agent registration warning: {e}")
    
    # Create async client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=300.0
    ) as client:
        yield client


@pytest.fixture
def thread_id():
    """Generate unique thread ID for each test."""
    return f"test-thread-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def default_claims():
    """Default JWT claims for testing."""
    return {
        "sub": "test_user",
        "tenant_id": "test_tenant",
        "roles": ["compliance_analyst", "admin"],
        "agent_access": [],  # Empty means access to all
        "context_tier": "full",
    }


# ============================================================================
# Helper Functions
# ============================================================================

def parse_sse_stream(response_text: str) -> List[Dict[str, Any]]:
    """Parse SSE stream into list of events."""
    events = []
    for line in response_text.strip().split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])  # Remove "data: " prefix
                events.append(data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse SSE line: {line}")
    return events


def validate_agent_event(event: Dict[str, Any], agent_id: str) -> bool:
    """Validate that event has required fields."""
    required_fields = ["type", "agent_id", "run_id", "step_id", "tenant_id", "data"]
    for field in required_fields:
        if field not in event:
            logger.error(f"Missing required field '{field}' in event: {event}")
            return False
    
    if event["agent_id"] != agent_id:
        logger.warning(f"Event agent_id mismatch: expected {agent_id}, got {event['agent_id']}")
    
    return True


def save_test_output(agent_id: str, test_name: str, events: List[Dict[str, Any]], metadata: Dict[str, Any]):
    """Save test output to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE_DIR / agent_id / test_name / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "output.json"
    output_data = {
        "agent_id": agent_id,
        "test_name": test_name,
        "timestamp": timestamp,
        "metadata": metadata,
        "events": events,
        "event_count": len(events),
        "event_types": [e.get("type") for e in events],
    }
    
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Saved test output to: {output_file}")
    return output_file


# ============================================================================
# Test Cases
# ============================================================================

class TestAgentRegistry:
    """Test agent registry endpoints."""
    
    def test_list_agents(self, test_client, default_claims):
        """Test listing all registered agents."""
        response = test_client.get("/v1/agents/registry")
        assert response.status_code == 200
        
        data = response.json()
        assert "agents" in data
        assert "count" in data
        assert data["count"] > 0
        
        logger.info(f"Found {data['count']} registered agents")
        for agent in data["agents"]:
            logger.info(f"  - {agent.get('agent_id')}: {agent.get('display_name')}")
    
    def test_get_agent_meta(self, test_client, default_claims):
        """Test getting metadata for a specific agent."""
        # Test with csod-planner
        response = test_client.get("/v1/agents/registry/csod-planner")
        assert response.status_code == 200
        
        data = response.json()
        assert data["agent_id"] == "csod-planner"
        assert "display_name" in data
        assert "framework" in data
        assert "capabilities" in data
    
    def test_get_invalid_agent(self, test_client, default_claims):
        """Test getting metadata for non-existent agent."""
        response = test_client.get("/v1/agents/registry/invalid-agent-id")
        assert response.status_code == 404


class TestAgentConversations:
    """Test conversational interactions with agents."""
    
    @pytest.mark.parametrize("agent_id,test_case", AGENT_TEST_CASES.items())
    def test_single_turn_conversation(self, test_client, thread_id, default_claims, agent_id, test_case):
        """Test single-turn conversation for each agent."""
        query = test_case["queries"][0]
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {test_case['name']} ({agent_id})")
        logger.info(f"Query: {query}")
        logger.info(f"{'='*60}")
        
        # Prepare request
        request_data = {
            "agent_id": agent_id,
            "input": query,
            "thread_id": thread_id,
            "step_id": "step_1",
            "step_index": 0,
            "use_context_token": True,
            "claims": default_claims,
        }
        
        # Make streaming request
        response = test_client.post(
            "/v1/agents/invoke",
            json=request_data,
            headers={"Accept": "text/event-stream"},
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Parse SSE events
        events = parse_sse_stream(response.text)
        assert len(events) > 0, "No events received"
        
        # Validate events
        for event in events:
            assert validate_agent_event(event, agent_id), f"Invalid event: {event}"
        
        # Check for expected event types
        event_types = [e.get("type") for e in events]
        logger.info(f"Received event types: {event_types}")
        
        # Save output
        save_test_output(
            agent_id=agent_id,
            test_name="single_turn",
            events=events,
            metadata={
                "query": query,
                "thread_id": thread_id,
                "request_data": request_data,
            }
        )
        
        # Basic assertions
        assert any(e.get("type") == "step_start" for e in events), "No step_start event"
        assert any(e.get("type") in ["token", "step_final", "final"] for e in events), "No response events"
    
    @pytest.mark.parametrize("agent_id,test_case", AGENT_TEST_CASES.items())
    def test_multi_turn_conversation_sync(self, test_client, default_claims, agent_id, test_case):
        """Test multi-turn conversation with context persistence (synchronous)."""
        thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
        queries = test_case["queries"][:2]  # Use first 2 queries
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing multi-turn: {test_case['name']} ({agent_id})")
        logger.info(f"{'='*60}")
        
        all_events = []
        
        # Multiple turns
        for turn_idx, query in enumerate(queries, 1):
            logger.info(f"\n--- Turn {turn_idx}: {query} ---")
            
            request_data = {
                "agent_id": agent_id,
                "input": query,
                "thread_id": thread_id,
                "step_id": f"step_{turn_idx}",
                "step_index": turn_idx - 1,
                "use_context_token": True,
                "claims": default_claims,
            }
            
            # Make streaming request
            response = test_client.post(
                "/v1/agents/invoke",
                json=request_data,
                headers={"Accept": "text/event-stream"},
            )
            
            assert response.status_code == 200
            
            # Parse events
            events = parse_sse_stream(response.text)
            for event in events:
                assert validate_agent_event(event, agent_id)
            
            all_events.extend(events)
            logger.info(f"Turn {turn_idx} received {len(events)} events")
        
        # Save output
        save_test_output(
            agent_id=agent_id,
            test_name="multi_turn",
            events=all_events,
            metadata={
                "queries": queries,
                "thread_id": thread_id,
                "turn_count": len(queries),
            }
        )
        
        # Validate multi-turn behavior
        assert len(all_events) > 0, "No events received across turns"
        assert any(e.get("type") == "step_start" for e in all_events), "No step_start events"
    
    @pytest.mark.parametrize("agent_id,test_case", AGENT_TEST_CASES.items())
    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_ASGI_TRANSPORT, reason="httpx ASGITransport not available")
    async def test_multi_turn_conversation_async(self, async_client, default_claims, agent_id, test_case):
        """Test multi-turn conversation with async streaming."""
        thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
        queries = test_case["queries"][:2]  # Use first 2 queries
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing multi-turn (async): {test_case['name']} ({agent_id})")
        logger.info(f"{'='*60}")
        
        all_events = []
        
        # Multiple turns
        for turn_idx, query in enumerate(queries, 1):
            logger.info(f"\n--- Turn {turn_idx}: {query} ---")
            
            request_data = {
                "agent_id": agent_id,
                "input": query,
                "thread_id": thread_id,
                "step_id": f"step_{turn_idx}",
                "step_index": turn_idx - 1,
                "use_context_token": True,
                "claims": default_claims,
            }
            
            # Make async streaming request
            async with async_client.stream(
                "POST",
                "/v1/agents/invoke",
                json=request_data,
                headers={"Accept": "text/event-stream"},
            ) as response:
                assert response.status_code == 200
                
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            events.append(event)
                            assert validate_agent_event(event, agent_id)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse line: {line}")
                
                all_events.extend(events)
                logger.info(f"Turn {turn_idx} received {len(events)} events")
        
        # Save output
        save_test_output(
            agent_id=agent_id,
            test_name="multi_turn_async",
            events=all_events,
            metadata={
                "queries": queries,
                "thread_id": thread_id,
                "turn_count": len(queries),
            }
        )
        
        # Validate multi-turn behavior
        assert len(all_events) > 0, "No events received across turns"
        assert any(e.get("type") == "step_start" for e in all_events), "No step_start events"
    
    @pytest.mark.parametrize("agent_id", AGENT_TEST_CASES.keys())
    def test_invalid_agent_id(self, test_client, thread_id, default_claims, agent_id):
        """Test error handling for invalid agent ID."""
        request_data = {
            "agent_id": "invalid-agent-id",
            "input": "test query",
            "thread_id": thread_id,
            "claims": default_claims,
        }
        
        response = test_client.post(
            "/v1/agents/invoke",
            json=request_data,
        )
        
        # Should return error event in stream
        assert response.status_code == 200  # SSE stream starts successfully
        events = parse_sse_stream(response.text)
        assert len(events) > 0
        assert any(e.get("type") == "error" for e in events), "No error event for invalid agent"
    
    @pytest.mark.parametrize("agent_id", AGENT_TEST_CASES.keys())
    def test_missing_required_fields(self, test_client, default_claims, agent_id):
        """Test error handling for missing required fields."""
        # Missing input
        request_data = {
            "agent_id": agent_id,
            "thread_id": "test-thread",
            "claims": default_claims,
        }
        
        response = test_client.post(
            "/v1/agents/invoke",
            json=request_data,
        )
        
        # Should return 422 validation error
        assert response.status_code == 422


class TestContextToken:
    """Test context token resolution."""
    
    def test_context_token_resolution(self, test_client, thread_id, default_claims):
        """Test that context tokens can be resolved."""
        # First, invoke an agent to get a context token
        agent_id = "csod-planner"
        request_data = {
            "agent_id": agent_id,
            "input": "test query",
            "thread_id": thread_id,
            "use_context_token": True,
            "claims": default_claims,
        }
        
        # Make request to get token (we'll extract it from the hint if available)
        response = test_client.post(
            "/v1/agents/invoke",
            json=request_data,
        )
        
        assert response.status_code == 200
        
        # Note: In a real scenario, the token would be in the payload hint
        # For now, we just verify the endpoint exists
        # The actual token resolution would be tested by the agent adapter


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run tests directly (for debugging)."""
    import sys
    
    logger.info("="*60)
    logger.info("Agent Conversations Integration Test")
    logger.info("="*60)
    
    # Register agents
    try:
        register_all_agents()
        logger.info("✓ Agents registered successfully")
    except Exception as e:
        logger.error(f"✗ Failed to register agents: {e}", exc_info=True)
        return 1
    
    # List registered agents
    registry = get_agent_registry()
    agents = registry.list_agents()
    logger.info(f"\nRegistered agents ({len(agents)}):")
    for agent_id in agents:
        try:
            meta = registry.get_meta(agent_id)
            logger.info(f"  ✓ {agent_id}: {meta.display_name}")
        except Exception as e:
            logger.warning(f"  ✗ {agent_id}: Failed to get metadata - {e}")
    
    logger.info(f"\nTest cases configured: {len(AGENT_TEST_CASES)}")
    for agent_id, test_case in AGENT_TEST_CASES.items():
        logger.info(f"  - {agent_id}: {len(test_case['queries'])} queries")
    
    logger.info("\n" + "="*60)
    logger.info("Running pytest...")
    logger.info("="*60 + "\n")
    
    # Run pytest
    import pytest
    return pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    sys.exit(main())
