"""
Utility functions for creating LangChain agents.

This module provides a centralized way to create LangChain agents using the modern
create_react_agent pattern, with fallbacks for compatibility.
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = logging.getLogger("lexy-ai-service")

# Import modern LangChain agent components with fallbacks
# Try multiple import paths to handle different LangChain versions
AgentExecutor = None
create_react_agent = None
create_tool_calling_agent = None
hub = None

# Try langchain_classic first (newer LangChain versions)
try:
    from langchain_classic.agents import AgentExecutor, create_react_agent, create_tool_calling_agent
    from langchain_classic import hub
    logger.info("Using langchain_classic for agent components")
except ImportError:
    # Try standard langchain.agents
    try:
        from langchain.agents import AgentExecutor, create_react_agent, create_tool_calling_agent
        from langchain import hub
        logger.info("Using langchain.agents for agent components")
    except ImportError:
        # Try alternative import paths
        try:
            from langchain.agents.agent import AgentExecutor
            from langchain.agents import create_react_agent, create_tool_calling_agent
            from langchain import hub
            logger.info("Using langchain.agents.agent for AgentExecutor")
        except ImportError:
            # If still fails, try to import individually
            try:
                from langchain.agents import create_react_agent, create_tool_calling_agent
                from langchain import hub
                try:
                    from langchain.agents.agent import AgentExecutor
                except ImportError:
                    try:
                        from langchain_classic.agents import AgentExecutor
                    except ImportError:
                        AgentExecutor = None
            except ImportError:
                AgentExecutor = None
                create_react_agent = None
                create_tool_calling_agent = None
                hub = None
                logger.warning("Failed to import agent components from all known paths")

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langchain_core.prompts import ChatPromptTemplate

def create_agent_with_executor(
    llm: Any,
    tools: List[Any],
    prompt: Optional["ChatPromptTemplate"] = None,
    use_react_agent: bool = True,
    executor_kwargs: Optional[Dict[str, Any]] = None
) -> Optional[AgentExecutor]:
    """
    Create a LangChain agent with AgentExecutor using the modern pattern.
    
    This function tries to create an agent using create_react_agent (preferred)
    or create_tool_calling_agent (fallback), then wraps it in an AgentExecutor.
    
    Args:
        llm: Language model instance
        tools: List of tools for the agent
        prompt: Optional custom prompt (only used with create_tool_calling_agent)
        use_react_agent: If True, prefer create_react_agent; if False, use create_tool_calling_agent
        executor_kwargs: Additional kwargs to pass to AgentExecutor (e.g., verbose, max_iterations)
    
    Returns:
        AgentExecutor instance, or None if agent creation fails
    
    Raises:
        RuntimeError: If agent creation fails and no fallback is available
    """
    if not tools:
        logger.warning("No tools available for agent initialization")
        return None
    
    executor_kwargs = executor_kwargs or {}
    
    # Default executor kwargs
    default_kwargs = {
        "verbose": True,
        "handle_parsing_errors": True,
        "max_iterations": 5,
        "early_stopping_method": "generate"
    }
    default_kwargs.update(executor_kwargs)
    
    # Prefer create_react_agent (modern pattern)
    if use_react_agent:
        try:
            react_prompt = hub.pull("hwchase17/react")
            agent = create_react_agent(llm, tools, react_prompt)
            logger.info("Created agent using create_react_agent")
            return AgentExecutor(
                agent=agent,
                tools=tools,
                **default_kwargs
            )
        except Exception as e:
            logger.warning(f"Failed to create agent using create_react_agent: {e}. Trying create_tool_calling_agent.")
    
    # Fallback to create_tool_calling_agent if create_react_agent fails or use_react_agent is False
    if prompt is not None:
        try:
            agent = create_tool_calling_agent(
                llm=llm,
                tools=tools,
                prompt=prompt
            )
            logger.info("Created agent using create_tool_calling_agent")
            return AgentExecutor(
                agent=agent,
                tools=tools,
                **default_kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create agent using create_tool_calling_agent: {e}")
            raise RuntimeError(
                f"Failed to create agent: {e}. "
                "Please ensure LangChain is properly installed with create_react_agent or create_tool_calling_agent support."
            )
    else:
        error_msg = (
            "Cannot create agent: create_react_agent failed and no custom prompt provided "
            "for create_tool_calling_agent fallback."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def create_agent_only(
    llm: Any,
    tools: List[Any],
    prompt: Optional["ChatPromptTemplate"] = None,
    use_react_agent: bool = True
) -> Optional[Any]:
    """
    Create a LangChain agent without wrapping it in AgentExecutor.
    
    This is useful when you want to create the AgentExecutor yourself with custom settings.
    
    Args:
        llm: Language model instance
        tools: List of tools for the agent
        prompt: Optional custom prompt (only used with create_tool_calling_agent)
        use_react_agent: If True, prefer create_react_agent; if False, use create_tool_calling_agent
    
    Returns:
        Agent instance, or None if agent creation fails
    
    Raises:
        RuntimeError: If agent creation fails and no fallback is available
    """
    if not tools:
        logger.warning("No tools available for agent initialization")
        return None
    
    # Prefer create_react_agent (modern pattern)
    if use_react_agent:
        try:
            react_prompt = hub.pull("hwchase17/react")
            agent = create_react_agent(llm, tools, react_prompt)
            logger.info("Created agent using create_react_agent")
            return agent
        except Exception as e:
            logger.warning(f"Failed to create agent using create_react_agent: {e}. Trying create_tool_calling_agent.")
    
    # Fallback to create_tool_calling_agent if create_react_agent fails or use_react_agent is False
    if prompt is not None:
        try:
            agent = create_tool_calling_agent(
                llm=llm,
                tools=tools,
                prompt=prompt
            )
            logger.info("Created agent using create_tool_calling_agent")
            return agent
        except Exception as e:
            logger.error(f"Failed to create agent using create_tool_calling_agent: {e}")
            raise RuntimeError(
                f"Failed to create agent: {e}. "
                "Please ensure LangChain is properly installed with create_react_agent or create_tool_calling_agent support."
            )
    else:
        error_msg = (
            "Cannot create agent: create_react_agent failed and no custom prompt provided "
            "for create_tool_calling_agent fallback."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
