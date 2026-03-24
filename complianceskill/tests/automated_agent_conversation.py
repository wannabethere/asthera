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

# Only import TestClient if needed (for use_test_client mode)
HAS_TEST_CLIENT = False
try:
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.services.agent_registration import register_all_agents
    HAS_TEST_CLIENT = True
except ImportError:
    # TestClient not available - will only work with --server-url
    TestClient = None
    app = None

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
        self._pending_checkpoint_response: Optional[Dict[str, Any]] = None
        
        if use_test_client:
            if not HAS_TEST_CLIENT:
                raise ImportError(
                    "TestClient not available. Install fastapi and dependencies, "
                    "or use --server-url to connect to a live server."
                )
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
    
    def _make_request(self, method: str, endpoint: str, **kwargs):
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
        
        # First downstream call only: same body as service chain (later turns use checkpoint/thread only)
        if (
            step_index == 0
            and hasattr(self, "planner_output")
            and self.planner_output
        ):
            from app.services.agent_registration import (
                build_csod_chain_invoke_payload_after_planner,
            )

            chain = build_csod_chain_invoke_payload_after_planner(
                self.planner_output,
                thread_id=self.thread_id,
                original_run_id=getattr(self, "_planner_chain_run_id", None),
            )
            request_data.update(chain)
            request_data["agent_id"] = self.agent_id
            request_data["claims"] = {
                "sub": "auto_test_user",
                "tenant_id": "test_tenant",
                "roles": ["compliance_analyst", "admin"],
                "agent_access": [],
                "context_tier": "full",
            }
        
        # Add initial state if available (for testing workflow modes)
        if hasattr(self, '_initial_state') and self._initial_state and step_index == 0:
            # Merge initial state into request (only on first turn)
            for key, value in self._initial_state.items():
                request_data[key] = value
        
        # Add pending checkpoint response if available (for resuming from checkpoints)
        if hasattr(self, '_pending_checkpoint_response') and self._pending_checkpoint_response:
            # Merge checkpoint response data into request
            for key, value in self._pending_checkpoint_response.items():
                request_data[key] = value
            # Clear pending response after using it
            self._pending_checkpoint_response = None
        
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
        
        # Log all event types for debugging
        event_types_received = [e.get("type") for e in events]
        logger.debug(f"Received event types: {event_types_received}")
        
        # Extract information
        tokens = []
        final_answer = None
        error = None
        checkpoint = None
        checkpoints_this_turn: List[Dict[str, Any]] = []  # Collect all checkpoints; use first (workflow pauses on first)
        reasoning_tokens: List[Dict[str, Any]] = []  # Planner narrator stream (thinking panel)
        reasoning_done_events: List[Dict[str, Any]] = []  # Completed narrator step text
        is_final = False
        step_final_count = 0
        
        for event in events:
            event_type = event.get("type")
            event_data = event.get("data", {})
            
            # Log checkpoint-related events in detail
            if event_type in ["checkpoint", "step_final", "step_start"]:
                logger.debug(f"Processing {event_type} event:")
                logger.debug(f"  Event data keys: {list(event_data.keys())}")
                if "checkpoint" in event_data:
                    logger.debug(f"  Checkpoint in data: {event_data['checkpoint']}")
                if "metadata" in event:
                    logger.debug(f"  Metadata keys: {list(event.get('metadata', {}).keys())}")
                    if "checkpoint" in event.get("metadata", {}):
                        logger.debug(f"  Checkpoint in metadata: {event['metadata']['checkpoint']}")
            
            if event_type == "token":
                # Collect streaming tokens
                token_text = event_data.get("text", "")
                if token_text:
                    tokens.append(token_text)

            elif event_type == "reasoning_token":
                # Planner narrator stream (thinking panel)
                reasoning_tokens.append({"node": event_data.get("node"), "text": event_data.get("text", "")})
                if reasoning_tokens and len(reasoning_tokens) <= 3:
                    logger.debug(f"  reasoning_token: node={event_data.get('node')} text={event_data.get('text', '')[:50]}...")

            elif event_type == "reasoning_done":
                reasoning_done_events.append({
                    "node": event_data.get("node"),
                    "text": event_data.get("text", ""),
                    "node_output": event_data.get("node_output"),
                })
                logger.info(f"✓ Reasoning done: node={event_data.get('node')}, text length={len(event_data.get('text', ''))}")
            
            elif event_type == "final":
                is_final = True
                final_answer = event_data.get("response", "")
                if not final_answer and tokens:
                    final_answer = "".join(tokens)
            
            elif event_type == "checkpoint":
                # Checkpoint events are emitted separately; collect (don't overwrite) so we respond to first
                checkpoints_this_turn.append(event_data)
                checkpoint_phase = event_data.get("phase") or event_data.get("checkpoint_type", "unknown")
                logger.info(f"✓ Checkpoint event received: phase={checkpoint_phase}")
                if event_data.get("options"):
                    logger.info(f"  Options: {len(event_data['options'])} available")
            
            elif event_type == "step_final":
                step_final_count += 1
                logger.info(f"Processing step_final event #{step_final_count}")
                logger.info(f"  step_final.data keys: {list(event_data.keys())}")
                
                # Check if there's a checkpoint in the data (append so first-wins at end)
                if "checkpoint" in event_data:
                    checkpoints_this_turn.append(event_data["checkpoint"])
                    cp = event_data["checkpoint"]
                    logger.info(f"✓ Checkpoint found in step_final.data: type={cp.get('checkpoint_type', cp.get('phase', 'unknown'))}")
                    if cp.get("options"):
                        logger.info(f"  Checkpoint has {len(cp['options'])} options")
                
                # Also check metadata
                if "checkpoint" in event.get("metadata", {}):
                    checkpoints_this_turn.append(event["metadata"]["checkpoint"])
                    cp = event["metadata"]["checkpoint"]
                    logger.info(f"✓ Checkpoint found in step_final.metadata: type={cp.get('checkpoint_type', cp.get('phase', 'unknown'))}")
                    if cp.get("options"):
                        logger.info(f"  Checkpoint has {len(cp['options'])} options")
                
                # Check for planner output in step_final
                if event_data.get("is_planner_output"):
                    logger.info(f"Planner output detected in step_final: next_agent={event_data.get('next_agent_id')}")
                
                # Check final_state for checkpoint (checkpoint might be in state but not emitted as separate event)
                if "final_state" in event_data:
                    logger.info(f"  final_state present, type: {type(event_data['final_state'])}")
                    if isinstance(event_data["final_state"], dict):
                        final_state = event_data["final_state"]
                        logger.info(f"  final_state keys: {list(final_state.keys())[:20]}")  # Show first 20 keys
                        if "csod_planner_checkpoint" in final_state:
                            csod_checkpoint = final_state["csod_planner_checkpoint"]
                            logger.info(f"  Found csod_planner_checkpoint in final_state, type: {type(csod_checkpoint)}")
                            if csod_checkpoint and isinstance(csod_checkpoint, dict):
                                logger.info(f"  csod_planner_checkpoint keys: {list(csod_checkpoint.keys())}")
                                logger.info(f"  requires_user_input: {csod_checkpoint.get('requires_user_input', False)}")
                                if csod_checkpoint.get("requires_user_input", False):
                                    # Extract checkpoint from state
                                    extracted = {
                                        "checkpoint_type": csod_checkpoint.get("phase", "unknown"),
                                        "phase": csod_checkpoint.get("phase"),
                                        "node": "csod_concept_resolver_node",  # Common node for concept selection
                                        "message": csod_checkpoint.get("message", ""),
                                        "options": csod_checkpoint.get("options", []),
                                        "data": csod_checkpoint,
                                        "requires_user_input": True,
                                    }
                                    checkpoints_this_turn.append(extracted)
                                    logger.info(f"✓ Checkpoint found in step_final.final_state.csod_planner_checkpoint: phase={extracted.get('phase')}")
                                    if extracted.get("options"):
                                        logger.info(f"  Checkpoint has {len(extracted['options'])} options")
                                else:
                                    logger.info(f"  Checkpoint found but requires_user_input=False, skipping")
                            else:
                                logger.info(f"  csod_planner_checkpoint is not a dict or is None")
                        else:
                            logger.info(f"  csod_planner_checkpoint not found in final_state")
                    else:
                        logger.info(f"  final_state is not a dict, it's {type(event_data['final_state'])}")
                else:
                    logger.info(f"  No final_state in step_final.data")
                
                # Also check if checkpoint might be nested deeper (e.g., in state or other fields)
                for key in ["state", "checkpoint_data"]:
                    if key in event_data and isinstance(event_data[key], dict):
                        if "checkpoint" in event_data[key]:
                            checkpoints_this_turn.append(event_data[key]["checkpoint"])
                            cp = event_data[key]["checkpoint"]
                            logger.info(f"✓ Checkpoint found in step_final.data.{key}: type={cp.get('checkpoint_type', cp.get('phase', 'unknown'))}")
                            break
                        # Also check for csod_planner_checkpoint in nested state
                        if "csod_planner_checkpoint" in event_data[key]:
                            csod_checkpoint = event_data[key]["csod_planner_checkpoint"]
                            if csod_checkpoint and isinstance(csod_checkpoint, dict) and csod_checkpoint.get("requires_user_input", False):
                                extracted = {
                                    "checkpoint_type": csod_checkpoint.get("phase", "unknown"),
                                    "phase": csod_checkpoint.get("phase"),
                                    "message": csod_checkpoint.get("message", ""),
                                    "options": csod_checkpoint.get("options", []),
                                    "data": csod_checkpoint,
                                }
                                checkpoints_this_turn.append(extracted)
                                logger.info(f"✓ Checkpoint found in step_final.data.{key}.csod_planner_checkpoint: phase={extracted.get('phase')}")
                                break
            
            elif event_type == "error":
                error = event_data.get("error", "Unknown error")
            
            elif event_type == "step_start":
                # Check if there's a checkpoint in the data
                if "checkpoint" in event_data:
                    checkpoints_this_turn.append(event_data["checkpoint"])
        
        # Use the FIRST checkpoint (the one the workflow paused on), not the last
        checkpoint = checkpoints_this_turn[0] if checkpoints_this_turn else None
        
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
            "reasoning_tokens": reasoning_tokens,
            "reasoning_done": reasoning_done_events,
        }
        
        # Store in history
        self.conversation_history.append(result)
        
        # Log summary
        logger.info(f"Received {len(events)} events")
        logger.info(f"Event types: {', '.join(set(result['event_types']))}")
        if final_answer:
            logger.info(f"Response: {final_answer[:200]}..." if len(final_answer) > 200 else f"Response: {final_answer}")
        if checkpoint:
            checkpoint_type = checkpoint.get("checkpoint_type") or checkpoint.get("phase", "unknown")
            logger.info(f"✓ Checkpoint detected: type={checkpoint_type}, node={checkpoint.get('node', 'N/A')}")
            if checkpoint.get("options"):
                logger.info(f"  Checkpoint has {len(checkpoint['options'])} options")
        else:
            logger.warning("⚠ No checkpoint detected in events (workflow may have completed without checkpoints)")
            # Log all event types to help debug
            logger.debug(f"All event types received: {result['event_types']}")
        if error:
            logger.error(f"Error: {error}")
        if reasoning_done_events:
            logger.info(f"Thinking panel: {len(reasoning_done_events)} step(s)")
            for i, r in enumerate(reasoning_done_events, 1):
                logger.info(f"  {i}. [{r.get('node')}] {r.get('text', '')[:120]}...")
        
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
            logger.info(f"\n{'='*60}")
            logger.info(f"Loop iteration: turn={turn}, max_turns={max_turns}, current_query='{current_query[:60]}...'")
            logger.info(f"{'='*60}")

            # ── Send the message ──────────────────────────────────────────────────
            result = self.send_message(current_query, step_index=turn)
            all_results.append(result)
            turn += 1  # INCREMENT HERE — once per send, unconditionally, before any branching
            # ─────────────────────────────────────────────────────────────────────

            if result["error"]:
                logger.error(f"Error in turn {turn}: {result['error']}")
                break

            if result["is_final"]:
                logger.info(f"\n✓ Conversation completed after {turn} turn(s)")
                break
            
            
            # ── Checkpoint handling ───────────────────────────────────────────────
            if result["checkpoint"]:
                checkpoint_info = result["checkpoint"]
                logger.info(f"\n⚠️  Checkpoint detected:")
                logger.info(f"  Type: {checkpoint_info.get('checkpoint_type', 'unknown')}")
                logger.info(f"  Message: {checkpoint_info.get('message', 'No message')}")
                logger.info(f"  Node: {checkpoint_info.get('node', 'unknown')}")
                logger.info(f"  auto_respond_checkpoints: {self.auto_respond_checkpoints}")

                if self.auto_respond_checkpoints:
                    logger.info("Auto-approving checkpoint (using default response)...")
                    logger.info(f"  turn after send: {turn}, max_turns: {max_turns}")

                    checkpoint_type = checkpoint_info.get("checkpoint_type", "")
                    checkpoint_phase = checkpoint_info.get("phase", "")
                    checkpoint_data = checkpoint_info.get("data", {})

                    if checkpoint_phase == "datasource_select" or checkpoint_type == "datasource_select":
                        identified_ds = checkpoint_data.get("identified_datasource")
                        selected_ds_id = None
                        selected_ds_label = None
                        if identified_ds:
                            selected_ds_id = identified_ds.get("id")
                            selected_ds_label = identified_ds.get("label", identified_ds.get("display_name", "this datasource"))
                        elif checkpoint_data.get("options"):
                            first_option = checkpoint_data["options"][0]
                            selected_ds_id = first_option.get("id")
                            selected_ds_label = first_option.get("label", first_option.get("display_name", "this datasource"))
                        elif checkpoint_info.get("options"):
                            first_option = checkpoint_info["options"][0]
                            selected_ds_id = first_option.get("id")
                            selected_ds_label = first_option.get("label", first_option.get("display_name", "this datasource"))

                        if selected_ds_id:
                            self._pending_checkpoint_response = {
                                "csod_selected_datasource": selected_ds_id,
                                "csod_datasource_confirmed": True,
                            }
                            current_query = f"Yes, use {selected_ds_label}"
                            logger.info(f"  Auto-selecting datasource: {selected_ds_id} ({selected_ds_label})")
                        else:
                            logger.warning("  No datasource ID found in checkpoint, using default 'cornerstone'")
                            self._pending_checkpoint_response = {
                                "csod_selected_datasource": "cornerstone",
                                "csod_datasource_confirmed": True,
                            }
                            current_query = "Yes, proceed"

                    elif checkpoint_phase == "scoping" or checkpoint_type == "scoping":
                        questions = checkpoint_data.get("questions") or checkpoint_info.get("questions", [])
                        scoping_answers = {}
                        for q in questions:
                            key = q.get("key") if isinstance(q, dict) else None
                            if key:
                                defaults = {
                                    "org_unit": "all",
                                    "time_period": "last 90 days",
                                    "training_type": "compliance",
                                    "persona": "learning_admin",
                                    "due_date_range": "next 30 days",
                                    "report_format": "PDF",
                                }
                                scoping_answers[key] = defaults.get(key, "default")
                        if scoping_answers:
                            self._pending_checkpoint_response = {"csod_scoping_answers": scoping_answers}
                            logger.info(f"  Auto-responding to scoping with: {list(scoping_answers.keys())}")
                        current_query = "Use defaults for all"

                    elif checkpoint_phase == "concept_select" or checkpoint_type == "concept_select":
                        options = checkpoint_data.get("options") or checkpoint_info.get("options", [])
                        if options:
                            logger.info(f"📋 Recommended concepts ({len(options)}):")
                            for idx, opt in enumerate(options, 1):
                                concept_id = opt.get("id", "N/A")
                                concept_label = opt.get("label", opt.get("display_name", "N/A"))
                                score = opt.get("score", opt.get("raw_score", 0))
                                confidence = opt.get("coverage_confidence", 0)
                                logger.info(
                                    f"  {idx}. {concept_label} (ID: {concept_id}, "
                                    f"score: {score:.4f}, confidence: {confidence:.2f})"
                                )
                            concept_ids = [opt.get("id") for opt in options if opt.get("id")]
                            if concept_ids:
                                concept_matches = [
                                    {
                                        "concept_id": opt.get("id"),
                                        "display_name": opt.get("label"),
                                        "score": opt.get("score", 0),
                                        "coverage_confidence": opt.get("coverage_confidence", 0),
                                    }
                                    for opt in options if opt.get("id")
                                ]
                                self._pending_checkpoint_response = {
                                    "csod_confirmed_concept_ids": concept_ids,
                                    "csod_concepts_confirmed": True,
                                    "csod_concept_matches": concept_matches,
                                }
                                concept_labels = [opt.get("label", opt.get("id")) for opt in options if opt.get("id") in concept_ids]
                                logger.info(f"✓ Auto-selecting {len(concept_ids)} concept(s): {', '.join(concept_labels)}")
                                logger.info(f"  Concept IDs: {concept_ids}")
                                logger.info(f"  Reconstructed {len(concept_matches)} concept matches for resume payload")
                                current_query = f"Yes, use all: {', '.join(concept_labels)}"
                            else:
                                logger.warning("No valid concept IDs found in options")
                                current_query = "Yes, proceed"
                        else:
                            logger.warning("No options available in concept selection checkpoint")
                            current_query = "Yes, proceed"

                    elif "approval" in checkpoint_type.lower() or "confirm" in checkpoint_type.lower():
                        current_query = "Yes, proceed"
                    else:
                        current_query = "Continue"

                    logger.info(f"  Prepared auto-response: '{current_query}'")
                    if self._pending_checkpoint_response:
                        logger.info(f"  Pending checkpoint response keys: {list(self._pending_checkpoint_response.keys())}")
                    continue  # skip "determine next query" — current_query already set

                elif interactive:
                    response = input("\nEnter response (or 'skip' to continue, 'auto' to auto-respond): ").strip()
                    if response.lower() == 'skip':
                        break
                    current_query = "Continue" if response.lower() == "auto" else response
                    continue

                else:
                    logger.warning("⚠️  Checkpoint detected but auto_respond_checkpoints is False!")
                    logger.warning("  Use --auto-respond-checkpoints flag to automatically respond to checkpoints")
                    break  # No handler — stop rather than spin
            # ─────────────────────────────────────────────────────────────────────

            # ── Determine next query for non-checkpoint turns ─────────────────────
            # Note: turn has already been incremented above, so follow_up index is turn-1
            follow_up_index = turn - 1
            if follow_up_queries and follow_up_index < len(follow_up_queries):
                current_query = follow_up_queries[follow_up_index]
            elif interactive:
                if result["final_answer"] and self._detect_question(result["final_answer"]):
                    logger.info("\n💬 Agent appears to be asking a question")
                    logger.info(f"Response: {result['final_answer'][:200]}...")
                    response = input("\nEnter your response (or 'done' to finish, 'auto' for auto-response): ").strip()
                    if response.lower() == 'done':
                        break
                    current_query = "Please continue" if response.lower() == "auto" else response
                else:
                    response = input("\nEnter follow-up query (or 'done' to finish): ").strip()
                    if response.lower() == 'done':
                        break
                    current_query = response
            else:
                if result["final_answer"] and self._detect_question(result["final_answer"]) and not result["is_final"]:
                    logger.info("\n💬 Agent appears to be asking a question, generating auto-response...")
                    current_query = "Please continue with your recommendation"
                elif result["is_final"]:
                    break
                elif result["final_answer"]:
                    logger.info("Received complete answer, ending conversation")
                    break
                # else: no answer yet, loop continues — turn already incremented
        # ─────────────────────────────────────────────────────────────────────

        if turn >= max_turns:
            logger.warning(f"Reached maximum turns ({max_turns})")

        # Compile final result
        final_result = {
            "agent_id": self.agent_id,
            "thread_id": self.thread_id,
            "turns": turn,
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
                # Filter out token events from event_types (keep only important event types)
                "event_types": [
                    et for et in turn_result.get("event_types", [])
                    if et not in ["token"]  # Remove token events
                ],
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
                if event_type in ["step_start", "step_final", "final", "error", "checkpoint"]:
                    # Keep essential fields only
                    important_event = {
                        "type": event_type,
                        "data": event.get("data", {}),
                    }
                    # Include checkpoint if present (checkpoint events have checkpoint data directly)
                    if event_type == "checkpoint":
                        # For checkpoint events, the data IS the checkpoint
                        important_event["checkpoint"] = event.get("data", {})
                    elif "checkpoint" in event.get("data", {}):
                        important_event["checkpoint"] = event["data"]["checkpoint"]
                    if "checkpoint" in event.get("metadata", {}):
                        important_event["checkpoint"] = event["metadata"]["checkpoint"]
                    # Include metadata if present
                    if event.get("metadata"):
                        important_event["metadata"] = event["metadata"]
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


def _extract_run_id_from_planner_results(results: List[Dict[str, Any]]) -> Optional[str]:
    for turn in reversed(results):
        for event in reversed(turn.get("events", [])):
            rid = event.get("run_id")
            if rid:
                return str(rid)
    return None


def _run_planner_then_agent_service_chain(
    query: str,
    target_agent_id: str,
    server_url: Optional[str],
    use_test_client: bool,
    auto_respond_checkpoints: bool,
    max_turns: int,
) -> Dict[str, Any]:
    """Single POST to csod-planner; stream includes service-driven chain to next agent."""
    logger.info("\n" + "=" * 80)
    logger.info("SERVICE CHAIN: csod-planner (stream includes chained agent)")
    logger.info("=" * 80)
    planner_client = AgentConversationClient(
        agent_id="csod-planner",
        server_url=server_url,
        use_test_client=use_test_client,
        auto_respond_checkpoints=auto_respond_checkpoints,
    )
    planner_result = planner_client.run_conversation(
        initial_query=query,
        max_turns=max_turns,
    )
    chained_events: List[Dict[str, Any]] = []
    planner_events: List[Dict[str, Any]] = []
    chained_agent_id: Optional[str] = None
    for turn in reversed(planner_result.get("results", [])):
        ev = turn.get("events", [])
        split_at: Optional[int] = None
        for i, e in enumerate(ev):
            if (e.get("metadata") or {}).get("chained_from") == "csod-planner":
                split_at = i
                break
        if split_at is not None:
            planner_events = ev[:split_at]
            chained_events = ev[split_at:]
            chained_agent_id = chained_events[0].get("agent_id") if chained_events else None
            break
    if not chained_events:
        return {
            "query": query,
            "planner_result": planner_result,
            "agent_result": None,
            "success": False,
            "error": "No chained agent in stream (planner checkpoint or no next_agent_id)",
            "use_service_chain": True,
        }
    if target_agent_id and chained_agent_id and chained_agent_id != target_agent_id:
        logger.warning(
            "Planner chained to %s, test expected %s — reporting chained agent result",
            chained_agent_id,
            target_agent_id,
        )
    final_answer = ""
    for e in reversed(chained_events):
        if e.get("type") == "final":
            final_answer = (e.get("data") or {}).get("response", "") or final_answer
            break
    if not final_answer:
        for e in reversed(chained_events):
            if e.get("type") == "step_final" and (e.get("data") or {}).get("response"):
                final_answer = str((e.get("data") or {}).get("response", ""))
                break
    agent_conversation_result = {
        "agent_id": chained_agent_id or target_agent_id,
        "thread_id": planner_result.get("thread_id"),
        "turns": 1,
        "results": [{"events": chained_events, "final_answer": final_answer, "is_final": bool(final_answer)}],
        "final_answer": final_answer,
        "conversation_complete": bool(final_answer),
    }
    return {
        "query": query,
        "planner_result": planner_result,
        "agent_result": agent_conversation_result,
        "success": agent_conversation_result["conversation_complete"],
        "turns": planner_result.get("turns", 0) + 1,
        "final_answer": final_answer,
        "thread_id": planner_result.get("thread_id"),
        "has_checkpoints": any(r.get("checkpoint") for r in planner_result.get("results", [])),
        "chained_agent_id": chained_agent_id,
        "use_service_chain": True,
    }


def _ensure_planner_next_agent_id(
    planner_output: Dict[str, Any],
    default_agent_id: str,
) -> str:
    nid = planner_output.get("next_agent_id")
    if nid:
        return nid
    try:
        from app.agents.csod.skills_config_helpers import (
            load_skills_config,
            get_agent_for_skill,
            get_agent_id_from_workflow,
        )

        sc = load_skills_config()
        wf = planner_output.get("csod_target_workflow")
        if wf:
            return get_agent_id_from_workflow(str(wf), sc)
        sk = planner_output.get("csod_primary_skill")
        if sk:
            wf = get_agent_for_skill(str(sk), sc)
            return get_agent_id_from_workflow(wf, sc)
    except Exception as e:
        logger.warning("Could not resolve next_agent_id from skills_config: %s", e)
    return default_agent_id


def _best_planner_final_state(planner_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Largest / richest final_state from planner stream (no active user checkpoint)."""
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for turn_result in planner_result.get("results", []):
        for event in turn_result.get("events", []):
            if event.get("type") != "step_final":
                continue
            fs = (event.get("data") or {}).get("final_state")
            if not isinstance(fs, dict) or not fs:
                continue
            cp = fs.get("csod_planner_checkpoint")
            if isinstance(cp, dict) and cp.get("requires_user_input"):
                continue
            score = sum(
                1 for k in (
                    "csod_target_workflow",
                    "compliance_profile",
                    "csod_selected_concepts",
                    "next_agent_id",
                )
                if fs.get(k)
            )
            score = score * 10000 + len(fs)
            if score > best_score:
                best_score = score
                best = fs
    return best


def _extract_planner_output_from_results(
    planner_result: Dict[str, Any],
    target_agent_id: str,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Resolve planner LangGraph final state + next agent for manual chain (non-service-chain path).
    Primary: step_final with is_planner_output. Fallbacks: completed final_state, reasoning_done, token JSON.
    """
    planner_output: Optional[Dict[str, Any]] = None
    next_agent_id: Optional[str] = None

    for turn_result in planner_result.get("results", []):
        events = turn_result.get("events", [])
        for event in events:
            if event.get("type") != "step_final":
                continue
            event_data = event.get("data") or {}
            fs = event_data.get("final_state")
            if event_data.get("is_planner_output") and isinstance(fs, dict) and fs:
                planner_output = fs
                next_agent_id = event_data.get("next_agent_id") or fs.get("next_agent_id")
                logger.info("✓ Planner output from step_final.is_planner_output: next=%s", next_agent_id)
                return planner_output, next_agent_id
            if isinstance(fs, dict) and fs.get("is_planner_output"):
                planner_output = fs
                next_agent_id = fs.get("next_agent_id") or event_data.get("next_agent_id")
                logger.info("✓ Planner output from final_state.is_planner_output: next=%s", next_agent_id)
                return planner_output, next_agent_id

        for ie in turn_result.get("important_events") or []:
            if ie.get("type") != "step_final":
                continue
            idata = ie.get("data") or {}
            ifs = idata.get("final_state")
            if idata.get("is_planner_output") and isinstance(ifs, dict) and ifs:
                planner_output = ifs
                next_agent_id = idata.get("next_agent_id") or ifs.get("next_agent_id")
                logger.info("✓ Planner output from important_events: next=%s", next_agent_id)
                return planner_output, next_agent_id

    best_fs: Optional[Dict[str, Any]] = None
    best_next: Optional[str] = None
    for turn_result in planner_result.get("results", []):
        for event in turn_result.get("events", []):
            if event.get("type") != "step_final":
                continue
            event_data = event.get("data") or {}
            fs = event_data.get("final_state")
            if not isinstance(fs, dict):
                continue
            cp = fs.get("csod_planner_checkpoint")
            if isinstance(cp, dict) and cp.get("requires_user_input"):
                continue
            if fs.get("csod_target_workflow") or fs.get("is_planner_output"):
                best_fs = fs
                best_next = fs.get("next_agent_id") or event_data.get("next_agent_id")

    if best_fs:
        logger.info("✓ Planner output from step_final final_state (router fields): next=%s", best_next)
        return best_fs, best_next

    logger.info("Trying reasoning_done / csod_workflow_router fallback...")
    for turn_result in reversed(planner_result.get("results", [])):
        for done in reversed(turn_result.get("reasoning_done") or []):
            if done.get("node") != "csod_workflow_router":
                continue
            no = done.get("node_output") or {}
            findings = no.get("findings") if isinstance(no, dict) else {}
            if isinstance(findings, dict) and findings.get("next_agent_id"):
                next_agent_id = findings.get("next_agent_id")
                full = _best_planner_final_state(planner_result)
                if full:
                    full = dict(full)
                    full["next_agent_id"] = next_agent_id
                    logger.info("✓ Planner state from best final_state + reasoning_done router")
                    return full, next_agent_id
                logger.warning(
                    "reasoning_done has next_agent_id=%s but no final_state; chain may lack context",
                    next_agent_id,
                )
                return {"next_agent_id": next_agent_id}, next_agent_id

    logger.info("Trying final_answer JSON fallback...")
    for turn_result in reversed(planner_result.get("results", [])):
        raw = (turn_result.get("final_answer") or "").strip()
        if not raw:
            continue
        parsed: Dict[str, Any] = {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
        if not isinstance(parsed, dict):
            continue
        if not (
            parsed.get("primary_skill")
            or parsed.get("next_agent_id")
            or parsed.get("csod_primary_skill")
        ):
            continue
        logger.info("✓ Parsed planner hints from final_answer tokens")
        merged = {**parsed}
        if parsed.get("primary_skill") and not merged.get("csod_primary_skill"):
            merged["csod_primary_skill"] = parsed["primary_skill"]
        next_agent_id = _ensure_planner_next_agent_id(merged, target_agent_id)
        return merged, next_agent_id

    plan_fields = {"csod_primary_skill", "csod_target_workflow", "csod_selected_datasource"}
    for turn_result in reversed(planner_result.get("results", [])):
        for event in reversed(turn_result.get("events", [])):
            if event.get("type") != "step_final":
                continue
            fs = (event.get("data") or {}).get("final_state")
            if not isinstance(fs, dict):
                continue
            if plan_fields & fs.keys():
                cp = fs.get("csod_planner_checkpoint")
                if isinstance(cp, dict) and cp.get("requires_user_input"):
                    continue
                logger.info("✓ Planner output from step_final field-match")
                return fs, fs.get("next_agent_id") or (event.get("data") or {}).get("next_agent_id")

    return None, None


def run_planner_then_agent(
    query: str,
    target_agent_id: str,
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
    use_service_chain: bool = False,
) -> Dict[str, Any]:
    """
    Run planner first, show output, then chain to target agent.

    If use_service_chain=True, a single csod-planner invoke is used (same as production);
    the HTTP stream includes the chained agent. target_agent_id is only validated when
    chained events appear.
    
    Args:
        query: User query
        target_agent_id: Agent to chain to after planner (e.g., "csod-metric-advisor", "csod-workflow")
        server_url: Optional server URL
        use_test_client: Use test client
        auto_respond_checkpoints: Auto-respond to checkpoints
        max_turns: Max conversation turns
        use_service_chain: One planner POST; consume planner + auto-chained SSE (production path)
    
    Returns:
        Combined result with planner and agent outputs
    """
    if use_service_chain:
        return _run_planner_then_agent_service_chain(
            query=query,
            target_agent_id=target_agent_id,
            server_url=server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=auto_respond_checkpoints,
            max_turns=max_turns,
        )

    logger.info("\n" + "="*80)
    logger.info("STEP 1: Running CSOD Planner")
    logger.info("="*80)
    
    # Step 1: Run planner
    planner_client = AgentConversationClient(
        agent_id="csod-planner",
        server_url=server_url,
        use_test_client=use_test_client,
        auto_respond_checkpoints=auto_respond_checkpoints,
    )
    
    planner_result = planner_client.run_conversation(
        initial_query=query,
        max_turns=max_turns,
    )

    logger.info("Searching for planner output in events...")
    planner_output, next_agent_id = _extract_planner_output_from_results(
        planner_result, target_agent_id
    )
    if planner_output and not next_agent_id:
        next_agent_id = _ensure_planner_next_agent_id(planner_output, target_agent_id)
        logger.info("Resolved next_agent_id via skills_config: %s", next_agent_id)

    # Show planner output
    logger.info("\n" + "="*80)
    logger.info("PLANNER OUTPUT SUMMARY")
    logger.info("="*80)
    if planner_output:
        logger.info(f"✓ Datasource: {planner_output.get('csod_selected_datasource', 'N/A')}")
        logger.info(f"✓ Concepts: {len(planner_output.get('csod_selected_concepts', []))} selected")
        logger.info(f"✓ Areas: {len(planner_output.get('csod_area_matches', []))} matched")
        logger.info(f"✓ Primary Skill: {planner_output.get('csod_primary_skill', 'N/A')}")
        logger.info(f"✓ Target Workflow: {planner_output.get('csod_target_workflow', 'N/A')}")
        logger.info(f"✓ Next Agent: {next_agent_id or 'N/A'}")
    else:
        logger.warning("⚠ No planner output detected - planner may not have completed")
    
    # Verify next agent matches target
    if next_agent_id and next_agent_id != target_agent_id:
        logger.warning(
            f"⚠ Planner routed to {next_agent_id}, but test expects {target_agent_id}. "
            f"Using planner's routing: {next_agent_id}"
        )
        target_agent_id = next_agent_id
    
    if not planner_output:
        logger.error("Cannot chain to agent - no planner output available")
        return {
            "planner_result": planner_result,
            "agent_result": None,
            "success": False,
            "error": "Planner did not produce output",
        }
    
    # Step 2: Chain to target agent
    logger.info("\n" + "="*80)
    logger.info(f"STEP 2: Chaining to {target_agent_id}")
    logger.info("="*80)
    
    # Use same thread_id; second POST uses same payload shape as _chain_to_next_agent
    agent_client = AgentConversationClient(
        agent_id=target_agent_id,
        server_url=server_url,
        use_test_client=use_test_client,
        auto_respond_checkpoints=auto_respond_checkpoints,
    )
    
    agent_client.thread_id = planner_client.thread_id
    agent_client.planner_output = planner_output
    agent_client._planner_chain_run_id = _extract_run_id_from_planner_results(
        planner_result.get("results", [])
    )
    
    # Manually send message with planner output in the payload
    # The adapter will detect planner_output and use it to build initial state
    agent_result = agent_client.send_message(query, step_index=0)
    
    # If there are more turns needed, continue the conversation
    if not agent_result.get("is_final") and agent_result.get("checkpoint"):
        # Handle checkpoint if needed
        if auto_respond_checkpoints:
            # Auto-respond and continue
            follow_up = "Continue"
            agent_result = agent_client.send_message(follow_up, step_index=1)
    
    # Build result in same format as run_conversation
    agent_conversation_result = {
        "agent_id": target_agent_id,
        "thread_id": agent_client.thread_id,
        "turns": 1 if agent_result.get("is_final") else 2,
        "results": [agent_result],
        "final_answer": agent_result.get("final_answer", ""),
        "conversation_complete": agent_result.get("is_final", False),
    }
    
    # Combine results
    combined_result = {
        "query": query,
        "planner_result": planner_result,
        "agent_result": agent_conversation_result,
        "success": agent_conversation_result.get("conversation_complete", False),
        "turns": planner_result.get("turns", 0) + agent_conversation_result.get("turns", 0),
        "final_answer": agent_conversation_result.get("final_answer", ""),
        "thread_id": agent_conversation_result.get("thread_id", planner_result.get("thread_id")),
        "has_checkpoints": any(
            r.get("checkpoint") for r in planner_result.get("results", [])
        ) or any(
            r.get("checkpoint") for r in agent_conversation_result.get("results", [])
        ),
    }
    
    return combined_result


def test_metric_advisor(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
    use_service_chain: bool = False,
) -> Dict[str, Any]:
    """
    Test CSOD Metric Advisor agent with planner first.
    
    Uses test queries from test_metric_advisor.py to validate the metric advisor
    workflow with planner chaining.
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD METRIC ADVISOR WITH PLANNER")
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
        
        try:
            combined_result = run_planner_then_agent(
                query=query,
                target_agent_id="csod-metric-advisor",
                server_url=server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=auto_respond_checkpoints,
                max_turns=max_turns,
                use_service_chain=use_service_chain,
            )
            
            results.append({
                "query": query,
                "success": combined_result.get("success", False),
                "turns": combined_result.get("turns", 0),
                "final_answer": combined_result.get("final_answer", ""),
                "thread_id": combined_result.get("thread_id"),
                "has_checkpoints": combined_result.get("has_checkpoints", False),
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "metric_advisor"
            # Save combined result
            combined_result["agent_id"] = combined_result.get(
                "chained_agent_id", "csod-metric-advisor"
            )
            combined_result["conversation_complete"] = combined_result.get("success", False)
            agent_client = AgentConversationClient(
                agent_id="csod-metric-advisor",
                server_url=server_url,
                use_test_client=use_test_client,
            )
            agent_client.save_conversation(combined_result, output_dir)
            
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


def test_planner(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
) -> Dict[str, Any]:
    """
    Test CSOD Planner agent.
    
    Tests the planner workflow to ensure it correctly identifies datasources,
    concepts, areas, and skills, then routes to appropriate agents.
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD PLANNER")
    logger.info("="*80)
    
    test_queries = [
        "I want to create a metrics dashboard for learning and development",
        "What metrics should I track for compliance training?",
        "Show me SQL queries for training completion data",
    ]
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Query {i}/{len(test_queries)}")
        logger.info(f"{'='*80}")
        
        client = AgentConversationClient(
            agent_id="csod-planner",
            server_url=server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=auto_respond_checkpoints,
        )
        
        try:
            result = client.run_conversation(
                initial_query=query,
                max_turns=max_turns,
            )
            
            # Extract planner output summary
            planner_summary = {}
            for turn_result in result.get("results", []):
                for event in turn_result.get("events", []):
                    if event.get("type") == "step_final":
                        event_data = event.get("data", {})
                        if event_data.get("is_planner_output"):
                            final_state = event_data.get("final_state", {})
                            planner_summary = {
                                "datasource": final_state.get("csod_selected_datasource"),
                                "concepts_count": len(final_state.get("csod_selected_concepts", [])),
                                "areas_count": len(final_state.get("csod_area_matches", [])),
                                "primary_skill": final_state.get("csod_primary_skill"),
                                "target_workflow": final_state.get("csod_target_workflow"),
                                "next_agent": event_data.get("next_agent_id"),
                            }
                            break
            
            results.append({
                "query": query,
                "success": result.get("conversation_complete", False),
                "turns": result.get("turns", 0),
                "final_answer": result.get("final_answer", ""),
                "thread_id": result.get("thread_id"),
                "planner_summary": planner_summary,
                "has_checkpoints": any(
                    r.get("checkpoint") for r in result.get("results", [])
                ),
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "planner"
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
    logger.info("PLANNER TEST SUMMARY")
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
        if result.get("planner_summary"):
            summary = result["planner_summary"]
            logger.info(f"    Datasource: {summary.get('datasource', 'N/A')}")
            logger.info(f"    Skill: {summary.get('primary_skill', 'N/A')}")
            logger.info(f"    Next Agent: {summary.get('next_agent', 'N/A')}")
        if result.get("error"):
            logger.info(f"    Error: {result['error']}")
    
    logger.info("="*80)
    
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def test_workflow(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
    use_service_chain: bool = False,
) -> Dict[str, Any]:
    """
    Test CSOD Workflow agent with planner first.
    
    Tests the main CSOD workflow with planner chaining.
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD WORKFLOW WITH PLANNER")
    logger.info("="*80)
    
    test_queries = [
        "I want to create a metrics dashboard for learning and development",
        "Generate SQL queries for training completion analysis",
        "Create a dashboard for compliance training metrics",
    ]
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Query {i}/{len(test_queries)}")
        logger.info(f"{'='*80}")
        
        try:
            combined_result = run_planner_then_agent(
                query=query,
                target_agent_id="csod-workflow",
                server_url=server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=auto_respond_checkpoints,
                max_turns=max_turns,
                use_service_chain=use_service_chain,
            )
            
            results.append({
                "query": query,
                "success": combined_result.get("success", False),
                "turns": combined_result.get("turns", 0),
                "final_answer": combined_result.get("final_answer", ""),
                "thread_id": combined_result.get("thread_id"),
                "has_checkpoints": combined_result.get("has_checkpoints", False),
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "workflow"
            combined_result["agent_id"] = combined_result.get(
                "chained_agent_id", "csod-workflow"
            )
            combined_result["conversation_complete"] = combined_result.get("success", False)
            agent_client = AgentConversationClient(
                agent_id="csod-workflow",
                server_url=server_url,
                use_test_client=use_test_client,
            )
            agent_client.save_conversation(combined_result, output_dir)
            
        except Exception as e:
            logger.error(f"Test query {i} failed: {e}", exc_info=True)
            results.append({
                "query": query,
                "success": False,
                "error": str(e),
            })
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("WORKFLOW TEST SUMMARY")
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
    
    logger.info("="*80)
    
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def test_planner_both_modes(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 15,
) -> Dict[str, Any]:
    """
    Test CSOD Planner agent with both workflow modes.
    
    Mode 1: Full flow (no datasource) - should go through datasource selection checkpoint
    Mode 2: Skip datasource (datasource provided) - should skip datasource and go directly to concept selection
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD PLANNER - BOTH WORKFLOW MODES")
    logger.info("="*80)
    
    test_cases = [
        {
            "name": "Full Flow (No Datasource)",
            "query": "I want to create a metrics dashboard for learning and development",
            "initial_state": {},  # No datasource provided
            "expected_checkpoints": ["concept_select"],  # Concept first; datasource inferred from domain
            "expected_flow": "concept → skill → scoping (if any) → area → workflow",
        },
        {
            "name": "Skip Datasource (Datasource Provided)",
            "query": "What metrics should I track for compliance training?",
            "initial_state": {
                "csod_selected_datasource": "cornerstone",
                "csod_datasource_confirmed": True,
            },
            "expected_checkpoints": ["concept_select"],  # Should skip datasource checkpoint
            "expected_flow": "concept → skill → scoping (if any) → area → workflow",
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Case {i}/{len(test_cases)}: {test_case['name']}")
        logger.info(f"Query: {test_case['query']}")
        logger.info(f"Expected Flow: {test_case['expected_flow']}")
        logger.info(f"Expected Checkpoints: {', '.join(test_case['expected_checkpoints'])}")
        logger.info(f"{'='*80}")
        
        client = AgentConversationClient(
            agent_id="csod-planner",
            server_url=server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=auto_respond_checkpoints,
        )
        
        try:
            # Add initial state to first request if provided
            if test_case["initial_state"]:
                # Store initial state to be included in first request
                for key, value in test_case["initial_state"].items():
                    if not hasattr(client, '_initial_state'):
                        client._initial_state = {}
                    client._initial_state[key] = value
            
            result = client.run_conversation(
                initial_query=test_case["query"],
                max_turns=max_turns,
            )
            
            # Analyze checkpoints encountered
            checkpoint_phases = []
            for turn_result in result.get("results", []):
                checkpoint = turn_result.get("checkpoint")
                if checkpoint:
                    phase = checkpoint.get("phase") or checkpoint.get("checkpoint_type", "unknown")
                    checkpoint_phases.append(phase)
            
            # Extract planner output summary
            planner_summary = {}
            for turn_result in result.get("results", []):
                for event in turn_result.get("events", []):
                    if event.get("type") == "step_final":
                        event_data = event.get("data", {})
                        if event_data.get("is_planner_output"):
                            final_state = event_data.get("final_state", {})
                            planner_summary = {
                                "datasource": final_state.get("csod_selected_datasource"),
                                "concepts_count": len(final_state.get("csod_selected_concepts", [])),
                                "areas_count": len(final_state.get("csod_area_matches", [])),
                                "primary_skill": final_state.get("csod_primary_skill"),
                                "target_workflow": final_state.get("csod_target_workflow"),
                                "next_agent": event_data.get("next_agent_id"),
                            }
                            break
            
            # Validate expected checkpoints (encountered must include all expected; may also have scoping)
            expected_checkpoints_set = set(test_case["expected_checkpoints"])
            encountered_checkpoints_set = set(checkpoint_phases)
            checkpoints_match = expected_checkpoints_set <= encountered_checkpoints_set
            
            # For skip datasource mode, verify datasource was not selected via checkpoint
            datasource_skipped = False
            if "datasource_select" not in test_case["expected_checkpoints"]:
                datasource_skipped = "datasource_select" not in encountered_checkpoints_set
                if not datasource_skipped:
                    logger.warning(f"  ⚠️ Expected to skip datasource checkpoint but encountered it")
            
            # Determine success
            success = (
                result.get("conversation_complete", False) and
                checkpoints_match and
                (datasource_skipped if "datasource_select" not in test_case["expected_checkpoints"] else True)
            )
            
            results.append({
                "test_name": test_case["name"],
                "query": test_case["query"],
                "success": success,
                "turns": result.get("turns", 0),
                "final_answer": result.get("final_answer", ""),
                "thread_id": result.get("thread_id"),
                "planner_summary": planner_summary,
                "expected_checkpoints": test_case["expected_checkpoints"],
                "encountered_checkpoints": checkpoint_phases,
                "checkpoints_match": checkpoints_match,
                "datasource_skipped": datasource_skipped if "datasource_select" not in test_case["expected_checkpoints"] else None,
                "has_checkpoints": any(
                    r.get("checkpoint") for r in result.get("results", [])
                ),
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "planner" / "both_modes"
            result["test_case"] = test_case["name"]
            client.save_conversation(result, output_dir)
            
        except Exception as e:
            logger.error(f"Test case {i} failed: {e}", exc_info=True)
            results.append({
                "test_name": test_case["name"],
                "query": test_case["query"],
                "success": False,
                "error": str(e),
            })
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("PLANNER BOTH MODES TEST SUMMARY")
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
        logger.info(f"{status} Test {i}: {result.get('test_name', 'Unknown')}")
        logger.info(f"    Query: {result.get('query', 'N/A')[:60]}...")
        if result.get("turns"):
            logger.info(f"    Turns: {result['turns']}")
        if result.get("planner_summary"):
            summary = result["planner_summary"]
            logger.info(f"    Datasource: {summary.get('datasource', 'N/A')}")
            logger.info(f"    Concepts: {summary.get('concepts_count', 0)}")
            logger.info(f"    Skill: {summary.get('primary_skill', 'N/A')}")
        if result.get("expected_checkpoints"):
            logger.info(f"    Expected checkpoints: {', '.join(result['expected_checkpoints'])}")
            logger.info(f"    Encountered checkpoints: {', '.join(result.get('encountered_checkpoints', []))}")
            if not result.get("checkpoints_match", True):
                logger.warning(f"    ⚠️ Checkpoint mismatch!")
        if result.get("datasource_skipped") is False:
            logger.warning(f"    ⚠️ Datasource was not skipped as expected!")
        if result.get("error"):
            logger.info(f"    Error: {result['error']}")
    
    logger.info("="*80)
    
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def test_planner_concept_selection(
    server_url: Optional[str] = None,
    use_test_client: bool = False,
    auto_respond_checkpoints: bool = True,
    max_turns: int = 10,
) -> Dict[str, Any]:
    """
    Simple test for CSOD Planner starting with datasource already selected.
    
    This test verifies that:
    1. Datasource selection is skipped when datasource is provided in initial state
    2. Workflow goes directly to concept selection checkpoint
    3. Concept selection checkpoint appears with options
    4. Auto-responding to concept selection allows workflow to complete
    
    This is a simpler test case focused on concept selection checkpoint behavior.
    """
    logger.info("\n" + "="*80)
    logger.info("TESTING CSOD PLANNER - CONCEPT SELECTION (Datasource Pre-selected)")
    logger.info("="*80)
    
    test_queries = [
        "What metrics should I track for compliance training?",
        "I want to create a metrics dashboard for learning effectiveness",
        "Show me SQL queries for training completion analysis",
    ]
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Query {i}/{len(test_queries)}")
        logger.info(f"Query: {query}")
        logger.info(f"Initial State: datasource=cornerstone, confirmed=True")
        logger.info(f"{'='*80}")
        
        client = AgentConversationClient(
            agent_id="csod-planner",
            server_url=server_url,
            use_test_client=use_test_client,
            auto_respond_checkpoints=auto_respond_checkpoints,
        )
        
        try:
            # Set initial state with datasource already selected
            client._initial_state = {
                "csod_selected_datasource": "cornerstone",
                "csod_datasource_confirmed": True,
            }
            
            result = client.run_conversation(
                initial_query=query,
                max_turns=max_turns,
            )
            
            # Analyze checkpoints encountered
            checkpoint_phases = []
            datasource_checkpoint_seen = False
            concept_checkpoint_seen = False
            
            for turn_result in result.get("results", []):
                checkpoint = turn_result.get("checkpoint")
                if checkpoint:
                    phase = checkpoint.get("phase") or checkpoint.get("checkpoint_type", "unknown")
                    checkpoint_phases.append(phase)
                    if phase == "datasource_select":
                        datasource_checkpoint_seen = True
                    elif phase == "concept_select":
                        concept_checkpoint_seen = True
            
            # Extract planner output summary
            planner_summary = {}
            for turn_result in result.get("results", []):
                for event in turn_result.get("events", []):
                    if event.get("type") == "step_final":
                        event_data = event.get("data", {})
                        if event_data.get("is_planner_output"):
                            final_state = event_data.get("final_state", {})
                            planner_summary = {
                                "datasource": final_state.get("csod_selected_datasource"),
                                "concepts_count": len(final_state.get("csod_selected_concepts", [])),
                                "areas_count": len(final_state.get("csod_area_matches", [])),
                                "primary_skill": final_state.get("csod_primary_skill"),
                                "target_workflow": final_state.get("csod_target_workflow"),
                                "next_agent": event_data.get("next_agent_id"),
                            }
                            break
            
            # Determine success criteria
            # 1. Should NOT see datasource checkpoint (datasource was pre-selected)
            # 2. Should see concept checkpoint
            # 3. Workflow should complete
            datasource_skipped = not datasource_checkpoint_seen
            concept_seen = concept_checkpoint_seen
            workflow_complete = result.get("conversation_complete", False)
            
            success = (
                datasource_skipped and
                concept_seen and
                workflow_complete
            )
            
            results.append({
                "query": query,
                "success": success,
                "turns": result.get("turns", 0),
                "final_answer": result.get("final_answer", ""),
                "thread_id": result.get("thread_id"),
                "planner_summary": planner_summary,
                "checkpoint_phases": checkpoint_phases,
                "datasource_skipped": datasource_skipped,
                "concept_seen": concept_seen,
                "workflow_complete": workflow_complete,
            })
            
            # Save individual result
            output_dir = base_dir / "tests" / "outputs" / "automated_conversations" / "planner" / "concept_selection"
            result["test_name"] = f"Concept Selection Test {i}"
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
    logger.info("CONCEPT SELECTION TEST SUMMARY")
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
        if result.get("planner_summary"):
            summary = result["planner_summary"]
            logger.info(f"    Datasource: {summary.get('datasource', 'N/A')}")
            logger.info(f"    Concepts: {summary.get('concepts_count', 0)}")
            logger.info(f"    Skill: {summary.get('primary_skill', 'N/A')}")
            logger.info(f"    Next Agent: {summary.get('next_agent', 'N/A')}")
        if result.get("checkpoint_phases"):
            logger.info(f"    Checkpoints: {', '.join(result['checkpoint_phases'])}")
        if result.get("datasource_skipped") is False:
            logger.warning(f"    ⚠️ Datasource checkpoint was NOT skipped (expected to skip)")
        if result.get("concept_seen") is False:
            logger.warning(f"    ⚠️ Concept checkpoint was NOT seen (expected to see)")
        if result.get("workflow_complete") is False:
            logger.warning(f"    ⚠️ Workflow did NOT complete")
        if result.get("error"):
            logger.info(f"    Error: {result['error']}")
    
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
        help="Run metric advisor test suite with planner (uses predefined test queries). Requires --server-url or --use-test-client.",
    )
    
    parser.add_argument(
        "--test-planner",
        action="store_true",
        help="Run planner test suite (uses predefined test queries). Requires --server-url or --use-test-client.",
    )
    
    parser.add_argument(
        "--test-planner-both-modes",
        action="store_true",
        help="Test planner with both workflow modes (full flow and skip datasource). Requires --server-url or --use-test-client.",
    )
    
    parser.add_argument(
        "--test-planner-concept-selection",
        action="store_true",
        help="Simple test for planner concept selection (datasource pre-selected). Requires --server-url or --use-test-client.",
    )
    
    parser.add_argument(
        "--test-workflow",
        action="store_true",
        help="Run workflow test suite with planner (uses predefined test queries). Requires --server-url or --use-test-client.",
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
        "--use-service-chain",
        action="store_true",
        help="For --test-metric-advisor / --test-workflow: single csod-planner invoke (stream includes chained agent, production path)",
    )
    
    parser.add_argument(
        "--output-dir",
        help="Directory to save conversation output (default: tests/outputs/automated_conversations)",
    )
    
    args = parser.parse_args()
    
    # Determine test mode
    test_mode = None
    if args.test_metric_advisor:
        test_mode = "metric_advisor"
    elif args.test_planner_both_modes:
        test_mode = "planner_both_modes"
    elif args.test_planner_concept_selection:
        test_mode = "planner_concept_selection"
    elif args.test_planner:
        test_mode = "planner"
    elif args.test_workflow:
        test_mode = "workflow"
    
    # If test mode is set, run the test suite
    if test_mode:
        use_test_client = args.use_test_client or not args.server_url
        if not use_test_client and not args.server_url:
            parser.error(f"--test-{test_mode.replace('_', '-')} requires either --server-url or --use-test-client")
        
        if test_mode == "metric_advisor":
            result = test_metric_advisor(
                server_url=args.server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=args.auto_respond_checkpoints or True,
                max_turns=args.max_turns,
                use_service_chain=args.use_service_chain,
            )
        elif test_mode == "planner_both_modes":
            result = test_planner_both_modes(
                server_url=args.server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=args.auto_respond_checkpoints or True,
                max_turns=args.max_turns,
            )
        elif test_mode == "planner_concept_selection":
            result = test_planner_concept_selection(
                server_url=args.server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=args.auto_respond_checkpoints or True,
                max_turns=args.max_turns,
            )
        elif test_mode == "planner":
            result = test_planner(
                server_url=args.server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=args.auto_respond_checkpoints or True,
                max_turns=args.max_turns,
            )
        elif test_mode == "workflow":
            result = test_workflow(
                server_url=args.server_url,
                use_test_client=use_test_client,
                auto_respond_checkpoints=args.auto_respond_checkpoints or True,
                max_turns=args.max_turns,
                use_service_chain=args.use_service_chain,
            )
        
        return 0 if result["passed"] == result["total"] else 1
    
    # Otherwise, run normal conversation
    if not args.agent_id:
        parser.error("--agent-id is required unless a test mode (--test-planner, --test-metric-advisor, --test-workflow) is used")
    if not args.query:
        parser.error("--query is required unless a test mode (--test-planner, --test-metric-advisor, --test-workflow) is used")
    
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
