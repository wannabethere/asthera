"""Shared helpers for CSOD LangGraph nodes."""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core.dependencies import get_llm
from app.agents.shared.tool_integration import create_tool_calling_agent
from app.agents.csod.csod_state import CSODWorkflowState

CSOD_State = CSODWorkflowState
logger = logging.getLogger(__name__)


def _csod_log_step(
    state: CSOD_State,
    step_name: str,
    agent_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    status: str = "completed",
    error: Optional[str] = None,
) -> None:
    """Append a step record to state["execution_steps"] and trim heavy transient fields.

    Caps execution_steps at last 3 entries (already persisted to DB by the adapter).
    Clears messages, llm_response/llm_prompt, and context_cache to prevent
    memory accumulation across checkpoints.
    """
    if "execution_steps" not in state:
        state["execution_steps"] = []
    state["execution_steps"].append({
        "step_name": step_name,
        "agent_name": agent_name,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "error": error,
    })
    # Cap execution_steps (already persisted to DB via adapter events)
    if len(state["execution_steps"]) > 3:
        state["execution_steps"] = state["execution_steps"][-3:]
    # Clear transient heavy fields that don't need to persist across nodes
    state.pop("llm_response", None)
    state.pop("llm_prompt", None)
    state.pop("context_cache", None)
    # Cap messages to last 2 (causal_graph node may need recent context)
    msgs = state.get("messages")
    if isinstance(msgs, list) and len(msgs) > 2:
        state["messages"] = msgs[-2:]


def _parse_json_response(response_content: str, fallback: Any) -> Any:
    """Parse JSON from LLM response with ```json fence fallback."""
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r"```json\s*(\[.*?\])\s*```", response_content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return fallback


def _llm_invoke(
    state: CSOD_State,
    agent_name: str,
    prompt_text: str,
    human_message: str,
    tools: List[Any],
    use_tool_calling: bool,
    max_tool_iterations: int = 8,
) -> str:
    """Unified LLM invocation: tool-calling agent first, then simple chain."""
    llm = get_llm(temperature=0)

    if use_tool_calling and tools:
        try:
            system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            executor = create_tool_calling_agent(
                llm=llm,
                tools=tools,
                prompt=prompt,
                use_react_agent=False,
                executor_kwargs={"max_iterations": max_tool_iterations, "verbose": False},
            )
            if executor:
                response = executor.invoke({"input": human_message})
                return response.get("output", str(response)) if isinstance(response, dict) else str(response)
        except Exception as e:
            logger.warning(f"{agent_name}: tool-calling agent failed, falling back to simple chain: {e}")

    system_prompt = prompt_text.replace("{", "{{").replace("}", "}}")
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    chain = prompt | llm
    response = chain.invoke({"input": human_message})
    return response.content if hasattr(response, "content") else str(response)
