"""
Graph Streaming Service for LangGraph execution with SSE
"""
import asyncio
import json
import time
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from datetime import datetime
import logging

from langchain_core.runnables import RunnableConfig

from app.streams.events import (
    GraphStartedEvent,
    GraphCompletedEvent,
    GraphErrorEvent,
    NodeStartedEvent,
    NodeCompletedEvent,
    NodeErrorEvent,
    StateUpdateEvent,
    ProgressEvent,
    ResultEvent,
    KeepAliveEvent,
    format_sse_event,
    EventType
)
from app.streams.graph_registry import GraphRegistry, GraphConfig

logger = logging.getLogger(__name__)


class GraphStreamingService:
    """Service for streaming LangGraph execution via SSE"""
    
    def __init__(self, registry: Optional[GraphRegistry] = None):
        self.registry = registry or GraphRegistry()
        self._active_streams: Dict[str, asyncio.Task] = {}
    
    async def stream_graph_execution(
        self,
        assistant_id: str,
        graph_id: Optional[str],
        input_data: Dict[str, Any],
        session_id: str,
        config: Optional[RunnableConfig] = None,
        result_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream graph execution and yield SSE-formatted events
        
        Args:
            assistant_id: ID of the assistant
            graph_id: ID of the graph (uses default if None)
            input_data: Input data for the graph
            session_id: Session/thread ID for checkpointing
            config: LangGraph RunnableConfig
            result_extractor: Optional function to extract result from final state
        
        Yields:
            SSE-formatted event strings
        """
        stream_key = f"{assistant_id}:{graph_id}:{session_id}"
        start_time = time.time()
        
        logger.info(f"Starting graph execution: assistant_id={assistant_id}, graph_id={graph_id}, session_id={session_id}")
        
        try:
            # Get graph configuration
            graph_config = self.registry.get_assistant_graph(assistant_id, graph_id)
            if not graph_config:
                logger.error(f"Graph not found: assistant_id={assistant_id}, graph_id={graph_id}")
                error_event = GraphErrorEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    error=f"Graph not found: assistant_id={assistant_id}, graph_id={graph_id}",
                    error_type="GraphNotFoundError"
                )
                yield format_sse_event(error_event)
                return
            
            graph = graph_config.graph
            logger.debug(f"Graph retrieved: {graph_config.name if hasattr(graph_config, 'name') else graph_id}")
            
            # Check if graph has required methods (duck typing instead of type check)
            if not hasattr(graph, 'astream_events') or not hasattr(graph, 'get_state'):
                logger.error(f"Graph missing required methods: has astream_events={hasattr(graph, 'astream_events')}, has get_state={hasattr(graph, 'get_state')}")
                error_event = GraphErrorEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    error="Graph is not a compiled LangGraph (missing required methods)",
                    error_type="InvalidGraphError"
                )
                yield format_sse_event(error_event)
                return
            
            # Prepare config
            if config is None:
                config = {"configurable": {"thread_id": session_id}}
            elif "configurable" not in config:
                config["configurable"] = {"thread_id": session_id}
            else:
                config["configurable"]["thread_id"] = session_id
            
            # Emit graph started event
            logger.info(f"Emitting graph_started event for session_id={session_id}")
            started_event = GraphStartedEvent(
                session_id=session_id,
                assistant_id=assistant_id,
                graph_id=graph_id,
                query=input_data.get("query", str(input_data)),
                config=config
            )
            yield format_sse_event(started_event, event_id=1)
            
            # Track state for progress
            last_state: Optional[Dict[str, Any]] = None
            node_count = 0
            event_count = 0
            total_nodes = getattr(graph, "_nodes", {}).__len__() if hasattr(graph, "_nodes") else None
            logger.info(f"Starting astream_events with input_data keys: {list(input_data.keys())}, total_nodes: {total_nodes}")
            
            # Stream graph execution using astream_events
            try:
                logger.info(f"Invoking graph.astream_events with input_data: {input_data}")
                logger.info(f"Graph type: {type(graph)}, has astream_events: {hasattr(graph, 'astream_events')}")
                
                # Try to get graph structure info
                try:
                    if hasattr(graph, 'nodes'):
                        nodes_info = graph.nodes if callable(graph.nodes) else getattr(graph, '_nodes', {})
                        logger.info(f"Graph nodes: {list(nodes_info.keys()) if isinstance(nodes_info, dict) else 'N/A'}")
                except Exception as e:
                    logger.debug(f"Could not get graph nodes info: {e}")
                
                # Use astream_events without include_names to get all events
                # include_names can filter out important events
                async for event in graph.astream_events(
                    input_data,
                    version="v2",  # Use v2 for better event structure
                    config=config
                    # Removed include_names - it was filtering out events
                ):
                    event_count += 1
                    event_kind = event.get("event")
                    node_name = event.get("name", "unknown")
                    
                    # Only log important events at INFO level, stream events at DEBUG
                    # This reduces log noise from thousands of on_chat_model_stream events
                    if event_kind in ["on_chain_start", "on_chain_end", "on_chain_error", "on_tool_start", "on_tool_end"]:
                        logger.info(f"Received event #{event_count}: {event_kind}, node: {node_name}")
                        logger.info(f"Event details - kind: {event_kind}, name: {node_name}, run_id: {event.get('run_id', 'N/A')}, parent_run_id: {event.get('parent_run_id', 'N/A')}")
                        if "data" in event:
                            data = event.get("data", {})
                            logger.debug(f"Event data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    else:
                        # Stream events (on_chat_model_stream, etc.) logged at DEBUG level
                        logger.debug(f"Received event #{event_count}: {event_kind}, node: {node_name}")
                    
                    logger.debug(f"Full event data: {event}")
                    
                    # Handle different event types
                    if event_kind == "on_chain_start":
                        # Node started
                        node_name = event.get("name", "unknown")
                        
                        # Log reasoning plan before data_knowledge_retrieval node executes
                        if node_name == "data_knowledge_retrieval":
                            try:
                                # Get current state to access reasoning_plan
                                current_state_obj = graph.get_state(config=config)
                                current_state = current_state_obj.values if hasattr(current_state_obj, "values") else None
                                if callable(current_state):
                                    current_state = current_state()
                                if not isinstance(current_state, dict):
                                    current_state = current_state_obj.model_dump() if hasattr(current_state_obj, "model_dump") else {}
                                
                                reasoning_plan = current_state.get("reasoning_plan")
                                if reasoning_plan:
                                    logger.info("=" * 80)
                                    logger.info("CONTEXTUAL GRAPH REASONING PLAN (before data_knowledge_retrieval)")
                                    logger.info("=" * 80)
                                    logger.info(f"Full reasoning plan:\n{json.dumps(reasoning_plan, indent=2, default=str)}")
                                    logger.info("=" * 80)
                                else:
                                    logger.warning("data_knowledge_retrieval node starting but no reasoning_plan found in state")
                            except Exception as e:
                                logger.warning(f"Could not retrieve reasoning plan for logging: {e}", exc_info=True)
                        
                        node_started = NodeStartedEvent(
                            session_id=session_id,
                            assistant_id=assistant_id,
                            graph_id=graph_id,
                            node_name=node_name
                        )
                        yield format_sse_event(node_started)
                        node_count += 1
                        
                        # Emit progress if we can estimate
                        if total_nodes:
                            progress = min(1.0, node_count / total_nodes)
                            progress_event = ProgressEvent(
                                session_id=session_id,
                                assistant_id=assistant_id,
                                graph_id=graph_id,
                                progress=progress,
                                current_step=node_name,
                                total_steps=total_nodes
                            )
                            yield format_sse_event(progress_event)
                    
                    elif event_kind == "on_chain_end":
                        # Node completed
                        node_name = event.get("name", "unknown")
                        output = event.get("data", {}).get("output")
                        
                        node_completed = NodeCompletedEvent(
                            session_id=session_id,
                            assistant_id=assistant_id,
                            graph_id=graph_id,
                            node_name=node_name,
                            output_state=output if isinstance(output, dict) else None
                        )
                        yield format_sse_event(node_completed)
                    
                    elif event_kind == "on_chain_error":
                        # Node error
                        node_name = event.get("name", "unknown")
                        error = event.get("error", {})
                        error_msg = str(error) if error else "Unknown error"
                        
                        node_error = NodeErrorEvent(
                            session_id=session_id,
                            assistant_id=assistant_id,
                            graph_id=graph_id,
                            node_name=node_name,
                            error=error_msg,
                            error_type=type(error).__name__ if error else None
                        )
                        yield format_sse_event(node_error)
                    
                    # Try to extract state updates
                    if "data" in event:
                        data = event["data"]
                        if isinstance(data, dict) and "output" in data:
                            current_state = data.get("output")
                            if isinstance(current_state, dict):
                                # Emit state update
                                changed_keys = []
                                if last_state:
                                    changed_keys = [
                                        k for k in current_state.keys()
                                        if k not in last_state or current_state[k] != last_state[k]
                                    ]
                                else:
                                    changed_keys = list(current_state.keys())
                                
                                if changed_keys:
                                    state_update = StateUpdateEvent(
                                        session_id=session_id,
                                        assistant_id=assistant_id,
                                        graph_id=graph_id,
                                        state_snapshot=current_state,
                                        changed_keys=changed_keys
                                    )
                                    yield format_sse_event(state_update)
                                
                                last_state = current_state.copy()
                
                # Graph completed successfully
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"Graph execution completed in {duration_ms:.2f}ms: session_id={session_id}, total_events={event_count}, nodes_executed={node_count}")
                
                # Check for issues
                if event_count == 0:
                    logger.error(f"CRITICAL: No events received from graph - graph may not be executing properly")
                elif event_count < 5:
                    logger.warning(f"Only {event_count} events received - graph may have stopped early. Expected many more events for full execution.")
                
                if node_count == 0:
                    logger.error(f"CRITICAL: No nodes executed - graph may be empty or not properly configured")
                elif node_count < 3:
                    logger.warning(f"Only {node_count} nodes executed - graph may have stopped early. Expected at least: intent_understanding, retrieve_context, data_knowledge_retrieval, etc.")
                
                # Warn if execution was too fast (suggests nodes didn't actually run)
                if duration_ms < 1000 and node_count > 0:
                    logger.warning(f"Graph completed very quickly ({duration_ms:.2f}ms) with {node_count} nodes - nodes may not have actually executed (LLM calls should take seconds)")
                
                # Get final state
                try:
                    final_state_obj = graph.get_state(config=config)
                    final_state = final_state_obj.values if hasattr(final_state_obj, "values") else None
                    if callable(final_state):
                        final_state = final_state()
                    if not isinstance(final_state, dict):
                        final_state = final_state_obj.model_dump() if hasattr(final_state_obj, "model_dump") else {}
                    logger.debug(f"Retrieved final state with keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'not a dict'}")
                except Exception as e:
                    logger.warning(f"Could not get final state: {e}", exc_info=True)
                    final_state = last_state or {}
                
                # Extract result using custom extractor or default
                result_data = final_state
                if result_extractor:
                    try:
                        result_data = result_extractor(final_state)
                    except Exception as e:
                        logger.warning(f"Result extractor failed: {e}")
                
                # Log what we're sending in the result event
                logger.info(f"Emitting result event with result_data keys: {list(result_data.keys()) if isinstance(result_data, dict) else 'not a dict'}")
                logger.info(f"Result event final_answer present: {bool(result_data.get('final_answer') if isinstance(result_data, dict) else False)}")
                logger.info(f"Result event final_answer length: {len(result_data.get('final_answer', '')) if isinstance(result_data, dict) and result_data.get('final_answer') else 0}")
                logger.info(f"Result event final_answer preview: {result_data.get('final_answer', '')[:200] if isinstance(result_data, dict) and result_data.get('final_answer') else 'None'}...")
                
                # Emit result event
                result_event = ResultEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    result=result_data,
                    metadata={
                        "duration_ms": duration_ms,
                        "node_count": node_count,
                        "graph_name": graph_config.name
                    }
                )
                logger.info(f"Emitting result event: {result_event.event_type}, result keys: {list(result_event.result.keys()) if isinstance(result_event.result, dict) else 'not a dict'}")
                yield format_sse_event(result_event)
                logger.info("Result event emitted successfully")
                
                # Emit completion event
                logger.info(f"Emitting graph_completed event with final_state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'not a dict'}")
                final_answer_present = bool(final_state.get('final_answer')) if isinstance(final_state, dict) else False
                final_answer_length = len(final_state.get('final_answer', '')) if (isinstance(final_state, dict) and final_state.get('final_answer')) else 0
                logger.info(f"Graph completed final_answer present: {final_answer_present}")
                logger.info(f"Graph completed final_answer length: {final_answer_length}")
                
                completed_event = GraphCompletedEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    final_state=final_state,
                    duration_ms=duration_ms
                )
                logger.info(f"Emitting graph_completed event: {completed_event.event_type}")
                yield format_sse_event(completed_event)
                logger.info("Graph completed event emitted successfully")
                
            except asyncio.TimeoutError as e:
                # Timeout waiting for next event
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Graph execution timed out after {duration_ms:.2f}ms: {e}", exc_info=True)
                logger.error(f"Events received before timeout: {event_count}, Nodes executed: {node_count}")
                logger.error(f"Last event was: event_count={event_count}, node_count={node_count}")
                error_event = GraphErrorEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    error=f"Graph execution timed out waiting for next event after {duration_ms:.2f}ms. This may indicate a node is hanging or the LLM call is taking too long.",
                    error_type="TimeoutError",
                    traceback=None
                )
                yield format_sse_event(error_event)
            except Exception as e:
                # Graph execution error
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Graph execution error after {duration_ms:.2f}ms: {e}", exc_info=True)
                logger.error(f"Events received before error: {event_count}, Nodes executed: {node_count}")
                error_event = GraphErrorEvent(
                    session_id=session_id,
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    traceback=str(e.__traceback__) if hasattr(e, "__traceback__") else None
                )
                yield format_sse_event(error_event)
        
        except Exception as e:
            # Service-level error
            error_event = GraphErrorEvent(
                session_id=session_id,
                assistant_id=assistant_id,
                graph_id=graph_id,
                error=str(e),
                error_type=type(e).__name__
            )
            yield format_sse_event(error_event)
            logger.error(f"Streaming service error: {e}", exc_info=True)
    
    async def stream_with_keepalive(
        self,
        assistant_id: str,
        graph_id: Optional[str],
        input_data: Dict[str, Any],
        session_id: str,
        config: Optional[RunnableConfig] = None,
        result_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        keepalive_interval: float = 30.0
    ) -> AsyncGenerator[str, None]:
        """
        Stream graph execution with keep-alive events
        
        Args:
            keepalive_interval: Seconds between keep-alive events
        """
        last_event_time = time.time()
        last_keepalive_time = time.time()
        event_count = 0
        stream_started = False
        graph_completed = False
        
        async def event_generator():
            nonlocal last_event_time, event_count, stream_started, graph_completed
            
            try:
                logger.info(f"Starting graph execution stream: assistant_id={assistant_id}, graph_id={graph_id}, session_id={session_id}")
                stream_started = True
                
                async for event in self.stream_graph_execution(
                    assistant_id=assistant_id,
                    graph_id=graph_id,
                    input_data=input_data,
                    session_id=session_id,
                    config=config,
                    result_extractor=result_extractor
                ):
                    last_event_time = time.time()
                    event_count += 1
                    
                    # Check if this is a completion event
                    if isinstance(event, str):
                        # Parse event to check type
                        try:
                            import json
                            event_data = json.loads(event.split('data: ')[-1] if 'data: ' in event else event)
                            if event_data.get('event_type') in ['graph_completed', 'graph_error']:
                                graph_completed = True
                        except:
                            pass
                    
                    yield event
                    
            except Exception as e:
                logger.error(f"Error in event generator: {e}", exc_info=True)
                # Re-raise to be caught by outer handler
                raise
        
        # Start event generator
        event_gen = event_generator()
        
        try:
            # Give the stream a chance to start and yield the first event (graph_started)
            # This ensures we don't timeout before the graph even starts
            initial_timeout = 10.0  # 10 seconds for initial event
            max_initial_wait = 60.0  # Maximum time to wait for first event
            initial_wait_start = time.time()
            
            # Use a very long timeout for subsequent events - we'll rely on keep-alive instead
            # This prevents premature timeouts while still allowing keep-alive to maintain connection
            subsequent_timeout = 300.0  # 5 minutes - very long to prevent premature timeouts
            
            while True:
                # Send keep-alive if enough time has passed since last event or last keep-alive
                current_time = time.time()
                time_since_last_event = current_time - last_event_time
                time_since_last_keepalive = current_time - last_keepalive_time
                
                # Send keep-alive if:
                # 1. Stream has started and we haven't sent keep-alive in a while
                # 2. OR we're waiting for an event and it's been longer than keepalive_interval
                if stream_started and (time_since_last_keepalive >= keepalive_interval or time_since_last_event >= keepalive_interval):
                    keepalive = KeepAliveEvent(
                        session_id=session_id,
                        assistant_id=assistant_id,
                        graph_id=graph_id
                    )
                    yield format_sse_event(keepalive, event_id=event_count)
                    last_keepalive_time = current_time
                    logger.debug(f"Sent keep-alive event (time since last event: {time_since_last_event:.1f}s)")
                
                # Check if we've been waiting too long for initial event
                if not stream_started:
                    wait_elapsed = current_time - initial_wait_start
                    if wait_elapsed > max_initial_wait:
                        logger.error(f"Timeout waiting for graph to start: waited {wait_elapsed}s")
                        error_event = GraphErrorEvent(
                            session_id=session_id,
                            assistant_id=assistant_id,
                            graph_id=graph_id,
                            error=f"Graph execution did not start within {max_initial_wait}s",
                            error_type="TimeoutError"
                        )
                        yield format_sse_event(error_event)
                        break
                    
                    # Send keep-alive while waiting for initial event
                    if time_since_last_keepalive >= keepalive_interval:
                        keepalive = KeepAliveEvent(
                            session_id=session_id,
                            assistant_id=assistant_id,
                            graph_id=graph_id
                        )
                        yield format_sse_event(keepalive, event_id=0)
                        last_keepalive_time = current_time
                
                # Try to get next event with timeout
                # Use a timeout that allows for keep-alive checks but is long enough for LLM calls
                try:
                    # Use a timeout that's long enough for LLM calls but allows periodic keep-alive checks
                    # For initial event, use shorter timeout
                    # For subsequent events, use a longer timeout (120s) but we'll break out periodically for keep-alive
                    if not stream_started:
                        timeout_to_use = initial_timeout
                    else:
                        # Use a timeout that's long enough for LLM calls (2 minutes)
                        # But we check for keep-alive before this, so we'll send keep-alive every 30s
                        timeout_to_use = 120.0  # 2 minutes - long enough for most LLM calls
                    
                    event = await asyncio.wait_for(
                        event_gen.__anext__(),
                        timeout=timeout_to_use
                    )
                    yield event
                except asyncio.TimeoutError:
                    # Timeout occurred - this is expected during long waits
                    # Don't treat it as an error, just continue the loop to send keep-alive
                    if not stream_started:
                        wait_elapsed = current_time - initial_wait_start
                        if wait_elapsed % 10 < 1:  # Log every ~10 seconds
                            logger.info(f"Waiting for graph to start (waited {wait_elapsed:.1f}s). Sending keep-alive...")
                        # Continue loop to send keep-alive
                        continue
                    else:
                        # Stream has started - this timeout is expected during long LLM calls
                        # Continue loop to send keep-alive and wait for next event
                        logger.debug(f"Timeout waiting for next event (last event was {time_since_last_event:.1f}s ago). Sending keep-alive and continuing...")
                        continue
                except StopAsyncIteration:
                    # Generator exhausted - stream completed
                    logger.info(f"Graph execution stream completed: assistant_id={assistant_id}, graph_id={graph_id}, session_id={session_id}")
                    graph_completed = True
                    break
        
        except Exception as e:
            logger.error(f"Error in keep-alive stream: {e}", exc_info=True)
            error_event = GraphErrorEvent(
                session_id=session_id,
                assistant_id=assistant_id,
                graph_id=graph_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=str(e.__traceback__) if hasattr(e, "__traceback__") else None
            )
            yield format_sse_event(error_event)

