#!/usr/bin/env python3
"""
Automated Agent Conversation Script

This script automates multi-turn conversations with agents via the API.
It:
1. Sends an initial query to an agent
2. Streams and collects responses
3. Detects when the agent needs more input (checkpoints, questions)
4. Automatically responds or continues the conversation
5. Repeats until final answer is received

Usage:
    # Basic usage - single question
    python tests/automated_agent_conversation.py \
        --agent-id csod-planner \
        --query "I want to create a metrics dashboard"

    # Multi-turn conversation with follow-ups
    python tests/automated_agent_conversation.py \
        --agent-id csod-planner \
        --query "I want to create a metrics dashboard" \
        --follow-ups "What metrics should I track?" "How do I visualize them?"

    # Interactive mode - prompts for follow-ups
    python tests/automated_agent_conversation.py \
        --agent-id csod-planner \
        --query "I want to create a metrics dashboard" \
        --interactive

    # With live server
    python tests/automated_agent_conversation.py \
        --agent-id csod-planner \
        --query "test query" \
        --server-url http://localhost:8002

    # Auto-respond to checkpoints (for testing)
    python tests/automated_agent_conversation.py \
        --agent-id csod-planner \
        --query "test query" \
        --auto-respond-checkpoints
"""

import os
import sys
import json
import uuid
import argparse
import logging
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Load .env file
base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / ".env"
if HAS_DOTENV and env_file.exists():
    load_dotenv(env_file, override=True)

sys.path.insert(0, str(base_dir))

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from fastapi.testclient import TestClient
from app.api.main import app
from app.services.agent_registration import register_all_agents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class AgentConversationClient:
    """Client for automated agent conversations."""
    
    def __init__(
        self,
        agent_id: str,
        server_url: Optional[str] = None,
        use_test_client: bool = False,
        auto_respond_checkpoints: bool = False,
    ):
        """
        Initialize conversation client.
        
        Args:
            agent_id: Agent identifier
            server_url: Base URL for live server (e.g., "http://localhost:8002")
            use_test_client: If True, use TestClient (no server needed)
            auto_respond_checkpoints: If True, automatically approve checkpoints
        """
        self.agent_id = agent_id
        self.server_url = server_url
        self.use_test_client = use_test_client
        self.auto_respond_checkpoints = auto_respond_checkpoints
        self.thread_id = f"auto-conv-{uuid.uuid4().hex[:8]}"
        self.conversation_history: List[Dict[str, Any]] = []
        
        if use_test_client:
            # Register agents
            try:
                register_all_agents()
                logger.info("✓ Agents registered")
            except Exception as e:
                logger.warning(f"Agent registration warning: {e}")
            
            self.client = TestClient(app)
            self.base_url = ""
        else:
            self.client = None
            if not server_url:
                raise ValueError("Either use_test_client=True or provide server_url")
            if not HAS_REQUESTS:
                raise ImportError("requests module is required for live server mode. Install with: pip install requests")
            self.base_url = server_url.rstrip("/")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request (works with both TestClient and requests)."""
        if self.use_test_client:
            if method.upper() == "POST":
                return self.client.post(endpoint, **kwargs)
            elif method.upper() == "GET":
                return self.client.get(endpoint, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
        else:
            url = f"{self.base_url}{endpoint}"
            if method.upper() == "POST":
                return requests.post(url, **kwargs, stream=True, timeout=300)
            elif method.upper() == "GET":
                return requests.get(url, **kwargs, stream=True, timeout=300)
            else:
                raise ValueError(f"Unsupported method: {method}")
    
    def _parse_sse_stream(self, response) -> List[Dict[str, Any]]:
        """Parse SSE stream from response."""
        events = []
        
        if self.use_test_client:
            # TestClient returns text directly
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        events.append(event)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SSE line: {line}")
        else:
            # requests.Response with stream=True
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        try:
                            event = json.loads(line_str[6:])
                            events.append(event)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE line: {line_str}")
        
        return events
    
    def send_message(
        self,
        query: str,
        step_index: int = 0,
    ) -> Dict[str, Any]:
        """
        Send a message to the agent and collect response.
        
        Args:
            query: User query
            step_index: Step index in conversation
        
        Returns:
            Dict with events, final_answer, and metadata
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Turn {step_index + 1}: {query}")
        logger.info(f"{'='*60}")
        
        request_data = {
            "agent_id": self.agent_id,
            "input": query,
            "thread_id": self.thread_id,
            "step_id": f"step_{step_index + 1}",
            "step_index": step_index,
            "use_context_token": True,
            "claims": {
                "sub": "auto_test_user",
                "tenant_id": "test_tenant",
                "roles": ["compliance_analyst", "admin"],
                "agent_access": [],
                "context_tier": "full",
            },
        }
        
        # Make request
        response = self._make_request(
            "POST",
            "/v1/agents/invoke",
            json=request_data,
            headers={"Accept": "text/event-stream"},
        )
        
        if response.status_code != 200:
            raise Exception(f"Request failed with status {response.status_code}: {response.text}")
        
        # Parse events
        events = self._parse_sse_stream(response)
        
        # Extract information
        tokens = []
        final_answer = None
        error = None
        checkpoint = None
        is_final = False
        step_final_count = 0
        
        for event in events:
            event_type = event.get("type")
            event_data = event.get("data", {})
            
            if event_type == "token":
                # Collect streaming tokens
                token_text = event_data.get("text", "")
                if token_text:
                    tokens.append(token_text)
            
            elif event_type == "final":
                is_final = True
                final_answer = event_data.get("response", "")
                if not final_answer and tokens:
                    final_answer = "".join(tokens)
            
            elif event_type == "step_final":
                step_final_count += 1
                # Check if there's a checkpoint in the data
                if "checkpoint" in event_data:
                    checkpoint = event_data["checkpoint"]
                # Also check metadata
                if "checkpoint" in event.get("metadata", {}):
                    checkpoint = event["metadata"]["checkpoint"]
            
            elif event_type == "error":
                error = event_data.get("error", "Unknown error")
            
            elif event_type == "step_start":
                # Check if there's a checkpoint in the data
                if "checkpoint" in event_data:
                    checkpoint = event_data["checkpoint"]
        
        # If we have tokens but no final answer, combine them
        if not final_answer and tokens:
            final_answer = "".join(tokens)
        
        # If we got step_final but no final event, check if we should consider it complete
        # (Some agents may not emit FINAL event)
        if not is_final and step_final_count > 0 and final_answer:
            # If we have a complete answer and no checkpoint, consider it done
            if not checkpoint:
                is_final = True
        
        result = {
            "query": query,
            "events": events,
            "tokens": tokens,
            "final_answer": final_answer,
            "error": error,
            "checkpoint": checkpoint,
            "is_final": is_final,
            "event_count": len(events),
            "event_types": [e.get("type") for e in events],
        }
        
        # Store in history
        self.conversation_history.append(result)
        
        # Log summary
        logger.info(f"Received {len(events)} events")
        logger.info(f"Event types: {', '.join(set(result['event_types']))}")
        if final_answer:
            logger.info(f"Response: {final_answer[:200]}..." if len(final_answer) > 200 else f"Response: {final_answer}")
        if checkpoint:
            logger.info(f"Checkpoint detected: {checkpoint}")
        if error:
            logger.error(f"Error: {error}")
        
        return result
    
    def _detect_question(self, text: str) -> bool:
        """Detect if the response contains a question that needs answering."""
        if not text:
            return False
        
        # Check for question marks
        if "?" in text:
            # Look for common question patterns
            question_patterns = [
                r'\?[^?]*$',  # Question at end
                r'(what|which|how|when|where|why|who|would you|could you|can you|do you|are you)',
            ]
            for pattern in question_patterns:
                if re.search(pattern, text.lower()):
                    return True
        
        # Check for prompts that need input
        prompt_patterns = [
            r'please (provide|specify|select|choose|enter)',
            r'(select|choose|pick|enter|provide|specify) (one|a|an)',
            r'which (one|option|choice)',
        ]
        for pattern in prompt_patterns:
            if re.search(pattern, text.lower()):
                return True
        
        return False
    
    def run_conversation(
        self,
        initial_query: str,
        follow_up_queries: Optional[List[str]] = None,
        interactive: bool = False,
        max_turns: int = 10,
    ) -> Dict[str, Any]:
        """
        Run a complete conversation until final answer.
        
        Args:
            initial_query: First query to send
            follow_up_queries: Optional list of follow-up queries
            interactive: If True, prompt for follow-ups interactively
            max_turns: Maximum number of turns
        
        Returns:
            Complete conversation result
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Starting automated conversation with agent: {self.agent_id}")
        logger.info(f"Thread ID: {self.thread_id}")
        logger.info(f"{'='*80}\n")
        
        all_results = []
        current_query = initial_query
        turn = 0
        
        while turn < max_turns:
            # Send message
            result = self.send_message(current_query, step_index=turn)
            all_results.append(result)
            
            # Check for errors
            if result["error"]:
                logger.error(f"Error in turn {turn + 1}: {result['error']}")
                break
            
            # Check if final
            if result["is_final"]:
                logger.info(f"\n✓ Conversation completed after {turn + 1} turn(s)")
                break
            
            # Check for checkpoint
            if result["checkpoint"]:
                checkpoint_info = result["checkpoint"]
                logger.info(f"\n⚠️  Checkpoint detected:")
                logger.info(f"  Type: {checkpoint_info.get('checkpoint_type', 'unknown')}")
                logger.info(f"  Message: {checkpoint_info.get('message', 'No message')}")
                logger.info(f"  Node: {checkpoint_info.get('node', 'unknown')}")
                
                if self.auto_respond_checkpoints:
                    # Auto-approve checkpoint for automated testing
                    logger.info("Auto-approving checkpoint (using default response)...")
                    # Generate a default response based on checkpoint type
                    checkpoint_type = checkpoint_info.get("checkpoint_type", "")
                    if "approval" in checkpoint_type.lower() or "confirm" in checkpoint_type.lower():
                        current_query = "Yes, proceed"
                    elif "selection" in checkpoint_type.lower():
                        # Try to get first option if available
                        checkpoint_data = checkpoint_info.get("data", {})
                        if "options" in checkpoint_data and checkpoint_data["options"]:
                            current_query = checkpoint_data["options"][0]
                        else:
                            current_query = "Continue"
                    else:
                        current_query = "Continue"
                    turn += 1
                    continue
                elif interactive:
                    response = input("\nEnter response (or 'skip' to continue, 'auto' to auto-respond): ").strip()
                    if response.lower() == 'skip':
                        break
                    if response.lower() == 'auto':
                        current_query = "Continue"
                    else:
                        current_query = response
                    turn += 1
                    continue
                else:
                    # No auto-respond and not interactive - wait for follow-up query
                    logger.info("Waiting for follow-up query...")
            
            # Determine next query
            if follow_up_queries and turn < len(follow_up_queries):
                current_query = follow_up_queries[turn]
                turn += 1
            elif interactive:
                # Check if agent asked a question
                if result["final_answer"] and self._detect_question(result["final_answer"]):
                    logger.info("\n💬 Agent appears to be asking a question")
                    logger.info(f"Response: {result['final_answer'][:200]}...")
                    response = input("\nEnter your response (or 'done' to finish, 'auto' for auto-response): ").strip()
                    if response.lower() == 'done':
                        break
                    if response.lower() == 'auto':
                        # Generate a simple auto-response
                        current_query = "Please continue"
                    else:
                        current_query = response
                    turn += 1
                else:
                    response = input("\nEnter follow-up query (or 'done' to finish): ").strip()
                    if response.lower() == 'done':
                        break
                    current_query = response
                    turn += 1
            else:
                # No more queries, check if agent asked a question
                if result["final_answer"] and self._detect_question(result["final_answer"]) and not result["is_final"]:
                    # Agent asked a question but we have no follow-up - generate auto-response
                    logger.info("\n💬 Agent appears to be asking a question, generating auto-response...")
                    current_query = "Please continue with your recommendation"
                    turn += 1
                elif result["is_final"]:
                    break
                elif result["final_answer"]:
                    # Got a complete answer, end conversation
                    logger.info("Received complete answer, ending conversation")
                    break
                else:
                    turn += 1
        
        if turn >= max_turns:
            logger.warning(f"Reached maximum turns ({max_turns})")
        
        # Compile final result
        final_result = {
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "turns": turn + 1,
            "results": all_results,
            "final_answer": all_results[-1]["final_answer"] if all_results else None,
            "conversation_complete": all_results[-1]["is_final"] if all_results else False,
        }
        
        return final_result
    
    def _filter_result_for_saving(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter result to remove unnecessary data for testing.
        Removes individual token events and keeps only essential information.
        """
        filtered_result = {
            "agent_id": result.get("agent_id"),
            "thread_id": result.get("thread_id"),
            "turns": result.get("turns"),
            "conversation_complete": result.get("conversation_complete"),
            "final_answer": result.get("final_answer"),
            "results": [],
        }
        
        # Process each turn result
        for turn_result in result.get("results", []):
            filtered_turn = {
                "query": turn_result.get("query"),
                "final_answer": turn_result.get("final_answer"),
                "error": turn_result.get("error"),
                "checkpoint": turn_result.get("checkpoint"),
                "is_final": turn_result.get("is_final"),
                "event_count": turn_result.get("event_count"),
                "event_types": turn_result.get("event_types"),
            }
            
            # Count event types
            event_type_counts = {}
            for event_type in turn_result.get("event_types", []):
                event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            filtered_turn["event_type_counts"] = event_type_counts
            
            # Keep only non-token events (step_start, step_final, final, error, checkpoint)
            # These are useful for debugging workflow progression
            important_events = []
            for event in turn_result.get("events", []):
                event_type = event.get("type")
                if event_type in ["step_start", "step_final", "final", "error"]:
                    # Keep essential fields only
                    important_event = {
                        "type": event_type,
                        "data": event.get("data", {}),
                    }
                    # Include checkpoint if present
                    if "checkpoint" in event.get("data", {}):
                        important_event["checkpoint"] = event["data"]["checkpoint"]
                    if "checkpoint" in event.get("metadata", {}):
                        important_event["checkpoint"] = event["metadata"]["checkpoint"]
                    important_events.append(important_event)
            
            # Only include events if there are any (avoid empty arrays)
            if important_events:
                filtered_turn["important_events"] = important_events
            
            filtered_result["results"].append(filtered_turn)
        
        return filtered_result
    
    def save_conversation(self, result: Dict[str, Any], output_dir: Optional[Path] = None):
        """Save conversation to file (filtered to remove unnecessary data)."""
        if output_dir is None:
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{self.agent_id}_{timestamp}.json"
        
        # Filter result to remove token events and redundant data
        filtered_result = self._filter_result_for_saving(result)
        
        with open(output_file, "w") as f:
            json.dump(filtered_result, f, indent=2)
        
        # Log size reduction
        original_size = len(json.dumps(result, indent=2))
        filtered_size = len(json.dumps(filtered_result, indent=2))
        reduction = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
        
        logger.info(f"\n✓ Conversation saved to: {output_file}")
        logger.info(f"  Size reduction: {reduction:.1f}% ({original_size:,} → {filtered_size:,} bytes)")
        return output_file


def test_metric_advisor(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
) -> Dict[str, Any]:
    """
    Test CSOD Metric Advisor agent with conversation Phase 0.
    
    Uses test queries from test_metric_advisor.py to validate the metric advisor
    workflow with conversation capabilities.
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD METRIC ADVISOR WITH CONVERSATION")
    logger.info("="*80)
    
    # Test queries from test_metric_advisor.py
    test_queries = [
        "What metrics should I track for compliance training effectiveness?",
        "What metrics should I track for learning effectiveness and pass rates?",
        "Show me how completion rate relates to pass rate and compliance metrics.",
    ]
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Query {i}/{len(test_queries)}")
        logger.info(f"{'='*80}")
        
        client = AgentConversationClient(
            agent_id="csod-metric-advisor",
            server_url=server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=auto_respond_checkpoints,
        )
        
        try:
            result = client.run_conversation(
                initial_query=query,
                max_turns=max_turns,  # Allow more turns for conversation Phase 0
            )
            
            results.append({
                "query": query,
                "success": result.get("conversation_complete", False),
                "turns": result.get("turns", 0),
                "final_answer": result.get("final_answer", ""),
                "thread_id": result.get("thread_id"),
                "has_checkpoints": any(
                    r.get("checkpoint") for r in result.get("results", [])
                ),
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "metric_advisor"
            client.save_conversation(result, output_dir)
            
        except Exception as e:
            logger.error(f"Test query {i} failed: {e}", exc_info=True)
            results.append({
                "query": query,
                "success": False,
                "error": str(e),
            })
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("METRIC ADVISOR TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for r in results if r.get("success", False))
    total = len(results)
    
    logger.info(f"Total tests: {total}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {total - passed}")
    logger.info(f"Pass rate: {(passed/total*100) if total > 0 else 0:.1f}%")
    logger.info("")
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
        logger.info(f"{status} Test {i}: {result['query'][:60]}...")
        if result.get("turns"):
            logger.info(f"    Turns: {result['turns']}")
        if result.get("error"):
            logger.info(f"    Error: {result['error']}")
        if result.get("has_checkpoints"):
            logger.info(f"    Had checkpoints: Yes")
    
    logger.info("="*80)
    
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Automated agent conversation script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--agent-id",
        help="Agent identifier (e.g., csod-planner, csod-workflow, dt-workflow). If not provided and --test-metric-advisor is used, defaults to csod-metric-advisor.",
    )
    
    parser.add_argument(
        "--query",
        help="Initial query to send to the agent",
    )
    
    parser.add_argument(
        "--test-metric-advisor",
        action="store_true",
        help="Run metric advisor test suite (uses predefined test queries). Requires --server-url or --use-test-client.",
    )
    
    parser.add_argument(
        "--follow-ups",
        nargs="+",
        help="Follow-up queries to send after initial response",
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode - prompt for follow-up queries",
    )
    
    parser.add_argument(
        "--server-url",
        help="Base URL for live server (e.g., http://localhost:8002). If not provided, uses TestClient.",
    )
    
    parser.add_argument(
        "--use-test-client",
        action="store_true",
        help="Use TestClient instead of live server (default if server-url not provided)",
    )
    
    parser.add_argument(
        "--auto-respond-checkpoints",
        action="store_true",
        help="Automatically approve/respond to checkpoints (for automated testing)",
    )
    
    parser.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="Maximum number of conversation turns (default: 10)",
    )
    
    parser.add_argument(
        "--output-dir",
        help="Directory to save conversation output (default: tests/outputs/automated_conversations)",
    )
    
    args = parser.parse_args()
    
    # If test-metric-advisor flag is set, run the test suite
    if args.test_metric_advisor:
        use_test_client = args.use_test_client or not args.server_url
        if not use_test_client and not args.server_url:
            parser.error("--test-metric-advisor requires either --server-url or --use-test-client")
        
        result = test_metric_advisor(
            server_url=args.server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=args.auto_respond_checkpoints or True,  # Default to True for tests
            max_turns=args.max_turns,
        )
        return 0 if result["passed"] == result["total"] else 1
    
    # Otherwise, run normal conversation
    if not args.agent_id:
        parser.error("--agent-id is required unless --test-metric-advisor is used")
    if not args.query:
        parser.error("--query is required unless --test-metric-advisor is used")
    
    # Determine client mode
    use_test_client = args.use_test_client or not args.server_url
    
    # Create client
    client = AgentConversationClient(
        agent_id=args.agent_id,
        server_url=args.server_url,
        use_test_client=use_test_client,
        auto_respond_checkpoints=args.auto_respond_checkpoints,
    )
    
    # Run conversation
    result = client.run_conversation(
        initial_query=args.query,
        follow_up_queries=args.follow_ups,
        interactive=args.interactive,
        max_turns=args.max_turns,
    )
    
    # Save result
    output_dir = Path(args.output_dir) if args.output_dir else None
    client.save_conversation(result, output_dir)
    
    # Print summary
    print("\n" + "="*80)
    print("CONVERSATION SUMMARY")
    print("="*80)
    print(f"Agent: {result['agent_id']}")
    print(f"Thread ID: {result['thread_id']}")
    print(f"Turns: {result['turns']}")
    print(f"Complete: {result['conversation_complete']}")
    if result['final_answer']:
        print(f"\nFinal Answer:\n{result['final_answer']}")
    print("="*80)
    
    return 0 if result['conversation_complete'] else 1


if __name__ == "__main__":
    sys.exit(main())
