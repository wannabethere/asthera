"""
LangGraph Adapter

Adapter for LangGraph-based agents that converts LangGraph events
to the standardized AgentEvent protocol.
"""

import logging
from typing import AsyncIterator, Dict, Any, Optional
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from app.adapters.base import AgentAdapter, AgentEvent, EventType, ComposedContext

# Note: In langgraph 0.4.3, compiled graphs don't have a specific type export.
# CompiledStateGraph doesn't exist, so we use Any for the type hint.
# The compiled graph is the result of StateGraph.compile()

logger = logging.getLogger(__name__)


class LangGraphAdapter(AgentAdapter):
    """
    Adapter for LangGraph workflows.
    
    Converts LangGraph astream_events output to AgentEvent protocol.
    """
    
    def __init__(
        self,
        graph: Any,  # Compiled LangGraph (result of StateGraph.compile())
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        """
        Initialize LangGraph adapter.
        
        Args:
            graph: Compiled LangGraph workflow
            checkpointer: Optional checkpointer for state persistence
        """
        self.graph = graph
        self.checkpointer = checkpointer
    
    async def stream(
        self,
        payload: Dict[str, Any],
        context: ComposedContext,
        config: Dict[str, Any]
    ) -> AsyncIterator[AgentEvent]:
        """
        Stream LangGraph execution events.
        
        Args:
            payload: Agent invocation payload
            context: Composed context
            config: Additional configuration
        
        Yields:
            AgentEvent: Standardized events
        """
        # Extract payload fields
        run_id = payload.get("run_id", str(uuid4()))
        step_id = payload.get("step_id", "step_1")
        tenant_id = payload.get("tenant_id", "default")
        agent_id = payload.get("agent_id", "unknown")
        thread_id = payload.get("thread_id", str(uuid4()))
        user_input = payload.get("input", "")
        
        # Build LangGraph input state
        graph_input = self._build_graph_input(payload, context)
        
        # Build LangGraph config
        graph_config = {
            "configurable": {
                "thread_id": thread_id,
                **config.get("configurable", {}),
            }
        }
        
        # Emit STEP_START event
        yield AgentEvent(
            type=EventType.STEP_START,
            agent_id=agent_id,
            run_id=run_id,
            step_id=step_id,
            tenant_id=tenant_id,
            data={"input": user_input},
            metadata={"thread_id": thread_id},
        )
        
        try:
            # Stream LangGraph events
            async for raw_event in self.graph.astream_events(
                graph_input,
                version="v2",
                config=graph_config,
            ):
                # Normalize and yield events
                event = self.normalize_event(raw_event)
                if event:
                    # Set standard fields
                    event.agent_id = agent_id
                    event.run_id = run_id
                    event.step_id = step_id
                    event.tenant_id = tenant_id
                    yield event
            
            # Emit STEP_FINAL event
            yield AgentEvent(
                type=EventType.STEP_FINAL,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={"status": "completed"},
                metadata={},
            )
            
        except Exception as e:
            logger.error(f"LangGraph execution error: {e}", exc_info=True)
            yield AgentEvent(
                type=EventType.STEP_ERROR,
                agent_id=agent_id,
                run_id=run_id,
                step_id=step_id,
                tenant_id=tenant_id,
                data={"error": str(e)},
                metadata={"error_type": type(e).__name__},
            )
            raise
    
    def normalize_event(self, raw_event: Dict[str, Any]) -> Optional[AgentEvent]:
        """
        Convert LangGraph event to AgentEvent protocol.
        
        LangGraph astream_events emits events like:
        {
            "event": "on_chat_model_stream",
            "name": "node_name",
            "data": {"chunk": AIMessageChunk(...)},
            ...
        }
        """
        event_type = raw_event.get("event", "")
        name = raw_event.get("name", "")
        data = raw_event.get("data", {})
        
        # Map LangGraph events to AgentEvent types
        if event_type == "on_chat_model_stream":
            # Streaming token
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                if content:
                    return AgentEvent(
                        type=EventType.TOKEN,
                        agent_id="",  # Will be set by caller
                        run_id="",
                        step_id="",
                        tenant_id="",
                        data={"text": content},
                        metadata={"node": name},
                    )
        
        elif event_type == "on_tool_start":
            # Tool invocation
            tool_name = data.get("name", name)
            tool_input = data.get("input", {})
            return AgentEvent(
                type=EventType.TOOL_START,
                agent_id="",
                run_id="",
                step_id="",
                tenant_id="",
                data={"tool": tool_name, "input": tool_input},
                metadata={"node": name},
            )
        
        elif event_type == "on_tool_end":
            # Tool completion
            tool_name = data.get("name", name)
            tool_output = data.get("output", "")
            return AgentEvent(
                type=EventType.TOOL_END,
                agent_id="",
                run_id="",
                step_id="",
                tenant_id="",
                data={"tool": tool_name, "output": str(tool_output)},
                metadata={"node": name},
            )
        
        elif event_type == "on_chain_end":
            # Chain/node completion
            output = data.get("output", {})
            if isinstance(output, dict):
                # Check if this is a final output
                if "output" in output or "messages" in output:
                    final_text = self._extract_final_text(output)
                    if final_text:
                        return AgentEvent(
                            type=EventType.FINAL,
                            agent_id="",
                            run_id="",
                            step_id="",
                            tenant_id="",
                            data={"text": final_text},
                            metadata={"node": name},
                        )
        
        # Filter out other event types
        return None
    
    def _build_graph_input(
        self,
        payload: Dict[str, Any],
        context: ComposedContext
    ) -> Dict[str, Any]:
        """
        Build LangGraph input state from payload and context.
        
        Args:
            payload: Agent invocation payload
            context: Composed context
        
        Returns:
            LangGraph input state dict
        """
        # Check if conversation state is available (from Phase 0)
        conversation_state = payload.get("conversation_state")
        
        # Start with user input
        graph_input = {
            "user_query": payload.get("input", ""),
        }
        
        # If conversation state is available, use it to build enriched initial state
        if conversation_state and conversation_state.get("is_complete"):
            # Use conversation state to build proper initial state
            # This ensures all conversation-resolved fields are included
            graph_input.update({
                "user_query": conversation_state.get("user_query", payload.get("input", "")),
                "session_id": conversation_state.get("session_id", payload.get("thread_id", "")),
                "active_project_id": conversation_state.get("active_project_id"),
                "selected_data_sources": conversation_state.get("selected_data_sources", []),
                "compliance_profile": conversation_state.get("compliance_profile", {}),
            })
            
            # Add CSOD-specific fields from conversation
            for key in [
                "csod_intent",
                "csod_resolved_project_ids",
                "csod_resolved_mdl_table_refs",
                "csod_selected_concepts",
                "csod_primary_area",
                "csod_target_workflow",
            ]:
                if key in conversation_state:
                    graph_input[key] = conversation_state[key]
        else:
            # No conversation state - use payload fields directly
            for key in ["session_id", "active_project_id", "selected_data_sources", "compliance_profile"]:
                if key in payload:
                    graph_input[key] = payload[key]
        
        # Add session context (messages)
        if context.session:
            messages = context.session.get("messages", [])
            if messages:
                graph_input["messages"] = self._convert_messages(messages)
        
        # Add turn context (recent messages)
        if context.turn:
            recent = context.turn.get("recent", [])
            if recent:
                if "messages" not in graph_input:
                    graph_input["messages"] = []
                graph_input["messages"].extend(self._convert_messages(recent))
        
        # Add system context
        if context.system:
            # Merge system context into graph input
            graph_input.update(context.system)
        
        # Add data scope from payload
        data_scope = payload.get("data_scope", {})
        if data_scope:
            graph_input["data_scope"] = data_scope
        
        return graph_input
    
    def _convert_messages(self, messages: list) -> list[BaseMessage]:
        """Convert message dicts to LangChain BaseMessage objects"""
        result = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                result.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "user":
                    result.append(HumanMessage(content=content))
                elif role == "assistant" or role == "agent":
                    result.append(AIMessage(content=content))
                elif role == "system":
                    result.append(SystemMessage(content=content))
        
        return result
    
    def _extract_final_text(self, output: Dict[str, Any]) -> Optional[str]:
        """Extract final text from LangGraph output"""
        # Try different output formats
        if "output" in output:
            output_val = output["output"]
            if isinstance(output_val, str):
                return output_val
            if isinstance(output_val, dict) and "output" in output_val:
                return str(output_val["output"])
        
        if "messages" in output:
            messages = output["messages"]
            if messages and isinstance(messages[-1], BaseMessage):
                return messages[-1].content
            if messages and isinstance(messages[-1], dict):
                return messages[-1].get("content", "")
        
        # Fallback: stringify the output
        return str(output)
