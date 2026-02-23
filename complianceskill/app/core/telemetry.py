"""
OpenTelemetry Configuration and Setup

Configures OpenTelemetry tracing, metrics, and logging for the application.
"""
import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace, metrics
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not available - install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")


def setup_telemetry(
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    enable_console_exporter: Optional[bool] = None,
    instrument_fastapi: Optional[bool] = None,
    instrument_asyncpg: Optional[bool] = None
) -> bool:
    """
    Setup OpenTelemetry tracing and instrumentation.
    
    Configuration is read from settings (via .env) with parameter overrides.
    
    Args:
        service_name: Name of the service for tracing (default: from settings)
        otlp_endpoint: OTLP collector endpoint (default: from settings or localhost:4317)
        enable_console_exporter: Also export to console for debugging (default: from settings)
        instrument_fastapi: Automatically instrument FastAPI (default: from settings)
        instrument_asyncpg: Automatically instrument asyncpg (default: from settings)
        
    Returns:
        True if setup successful, False otherwise
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - tracing disabled")
        return False
    
    # Import settings to get configuration
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        
        # Check if telemetry is enabled
        if not settings.OPENTELEMETRY_ENABLED:
            logger.info("OpenTelemetry tracing is disabled via OPENTELEMETRY_ENABLED setting")
            return False
        
        # Use settings values with parameter overrides
        service_name = service_name or settings.OTEL_SERVICE_NAME
        otlp_endpoint = otlp_endpoint or settings.OTEL_EXPORTER_OTLP_ENDPOINT or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        enable_console_exporter = enable_console_exporter if enable_console_exporter is not None else settings.OTEL_CONSOLE_EXPORTER_ENABLED
        instrument_fastapi = instrument_fastapi if instrument_fastapi is not None else settings.OTEL_INSTRUMENT_FASTAPI
        instrument_asyncpg = instrument_asyncpg if instrument_asyncpg is not None else settings.OTEL_INSTRUMENT_ASYNCPG
        insecure = settings.OTEL_EXPORTER_OTLP_INSECURE
        
    except Exception as e:
        logger.warning(f"Could not load settings for telemetry config: {e}, using defaults")
        # Fallback to defaults if settings not available
        service_name = service_name or "compliance-skill-api"
        if otlp_endpoint is None:
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        enable_console_exporter = enable_console_exporter if enable_console_exporter is not None else False
        instrument_fastapi = instrument_fastapi if instrument_fastapi is not None else True
        instrument_asyncpg = instrument_asyncpg if instrument_asyncpg is not None else False
        insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    
    try:
        
        logger.info(f"Setting up OpenTelemetry tracing for service: {service_name}")
        logger.info(f"OTLP endpoint: {otlp_endpoint}")
        
        # Create resource
        resource = Resource(attributes={
            SERVICE_NAME: service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development")
        })
        
        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter (with timeout to prevent hanging)
        try:
            # Check if endpoint is reachable (non-blocking check)
            import socket
            from urllib.parse import urlparse
            
            parsed = urlparse(otlp_endpoint)
            host = parsed.hostname or "localhost"
            port = parsed.port or 4317
            
            # Quick connectivity check with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 2 second timeout
            try:
                sock.connect((host, port))
                sock.close()
                endpoint_reachable = True
            except (socket.timeout, socket.error, OSError):
                endpoint_reachable = False
                logger.warning(f"OTLP endpoint {otlp_endpoint} not reachable - spans will be buffered but may not export")
            
            # OTLPSpanExporter doesn't support timeout in constructor
            # BatchSpanProcessor handles buffering, so it won't block
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=insecure  # Use False in production with TLS
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(span_processor)
            logger.info(f"✓ OTLP span exporter configured (endpoint reachable: {endpoint_reachable})")
        except Exception as e:
            logger.warning(f"Could not setup OTLP exporter: {e}")
        
        # Add console exporter for debugging
        if enable_console_exporter:
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            tracer_provider.add_span_processor(console_processor)
            logger.info("✓ Console span exporter configured")
        
        # Set tracer provider
        trace.set_tracer_provider(tracer_provider)
        logger.info("✓ Tracer provider set")
        
        # Instrument FastAPI
        if instrument_fastapi:
            try:
                FastAPIInstrumentor().instrument()
                logger.info("✓ FastAPI instrumentation enabled")
            except Exception as e:
                logger.warning(f"Could not instrument FastAPI: {e}")
        
        # Instrument AsyncPG
        if instrument_asyncpg:
            try:
                AsyncPGInstrumentor().instrument()
                logger.info("✓ AsyncPG instrumentation enabled")
            except Exception as e:
                logger.warning(f"Could not instrument AsyncPG: {e}")
        
        logger.info("=" * 80)
        logger.info("OpenTelemetry Setup Complete")
        logger.info(f"Service: {service_name}")
        logger.info(f"Endpoint: {otlp_endpoint}")
        logger.info(f"Console Export: {enable_console_exporter}")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting up OpenTelemetry: {e}", exc_info=True)
        return False


def get_tracer(name: str = __name__):
    """
    Get a tracer instance
    
    Args:
        name: Tracer name (typically __name__)
        
    Returns:
        Tracer instance or None if OpenTelemetry not available
    """
    if not OTEL_AVAILABLE:
        return None
    
    return trace.get_tracer(name)


def create_span(
    name: str,
    attributes: Optional[dict] = None
):
    """
    Create a manual span
    
    Usage:
        with create_span("operation_name", {"key": "value"}):
            # Your code here
            pass
    
    Args:
        name: Span name
        attributes: Optional span attributes
        
    Returns:
        Span context manager or no-op if OpenTelemetry not available
    """
    if not OTEL_AVAILABLE:
        from contextlib import nullcontext
        return nullcontext()
    
    tracer = trace.get_tracer(__name__)
    span = tracer.start_as_current_span(name)
    
    if attributes and span:
        for key, value in attributes.items():
            span.set_attribute(key, str(value))
    
    return span


async def async_create_span(
    name: str,
    attributes: Optional[dict] = None
):
    """
    Async version of create_span
    
    Usage:
        async with async_create_span("operation_name", {"key": "value"}):
            # Your async code here
            pass
    """
    return create_span(name, attributes)


def is_telemetry_enabled() -> bool:
    """Check if OpenTelemetry is available and configured"""
    return OTEL_AVAILABLE and trace.get_tracer_provider() is not None


# ============================================================================
# LLM Call Tracking Utilities
# ============================================================================

def extract_llm_token_usage(response: Any) -> dict:
    """
    Extract token usage from LLM response.
    
    Supports:
    - LangChain BaseMessage with response_metadata
    - Direct response_metadata dict
    - Anthropic/OpenAI response objects
    
    Args:
        response: LLM response object
    
    Returns:
        Dict with prompt_tokens, completion_tokens, total_tokens
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
    
    if not response:
        return usage
    
    # Try to get from response_metadata (LangChain standard)
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata and isinstance(metadata, dict):
            token_usage = metadata.get('token_usage', {})
            if isinstance(token_usage, dict):
                usage["prompt_tokens"] = token_usage.get('prompt_tokens', 0)
                usage["completion_tokens"] = token_usage.get('completion_tokens', 0)
                usage["total_tokens"] = token_usage.get('total_tokens', 0)
    
    # Try direct token_usage attribute (some LLM implementations)
    if usage["total_tokens"] == 0 and hasattr(response, 'token_usage'):
        token_usage = response.token_usage
        if isinstance(token_usage, dict):
            usage["prompt_tokens"] = token_usage.get('prompt_tokens', 0)
            usage["completion_tokens"] = token_usage.get('completion_tokens', 0)
            usage["total_tokens"] = token_usage.get('total_tokens', 0)
    
    # Try usage_metadata (alternative format)
    if usage["total_tokens"] == 0 and hasattr(response, 'usage_metadata'):
        usage_metadata = response.usage_metadata
        if usage_metadata:
            usage["prompt_tokens"] = getattr(usage_metadata, 'input_tokens', 0) or getattr(usage_metadata, 'prompt_tokens', 0)
            usage["completion_tokens"] = getattr(usage_metadata, 'output_tokens', 0) or getattr(usage_metadata, 'completion_tokens', 0)
            usage["total_tokens"] = getattr(usage_metadata, 'total_tokens', 0) or (usage["prompt_tokens"] + usage["completion_tokens"])
    
    # Calculate total if we have prompt and completion but no total
    if usage["total_tokens"] == 0 and (usage["prompt_tokens"] > 0 or usage["completion_tokens"] > 0):
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    
    return usage


def extract_llm_status_code(response: Any) -> Optional[str]:
    """
    Extract status code from LLM response.
    
    Args:
        response: LLM response object
    
    Returns:
        Status code string or None
    """
    if not response:
        return None
    
    # Try response_metadata
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata and isinstance(metadata, dict):
            # Check for HTTP status code
            status_code = metadata.get('http_status', metadata.get('status_code'))
            if status_code:
                return str(status_code)
            
            # Check for response status
            response_status = metadata.get('response_status')
            if response_status:
                return str(response_status)
    
    # Try direct status_code attribute
    if hasattr(response, 'status_code'):
        return str(response.status_code)
    
    # Try HTTP status
    if hasattr(response, 'http_status'):
        return str(response.http_status)
    
    return None


def track_llm_call_in_span(span, response: Any, llm_model: Optional[str] = None):
    """
    Track LLM call information in an OpenTelemetry span.
    
    Args:
        span: OpenTelemetry span
        response: LLM response object
        llm_model: Optional model name/identifier
    """
    if not span or not response:
        return
    
    # Extract token usage
    token_usage = extract_llm_token_usage(response)
    if token_usage["total_tokens"] > 0:
        span.set_attribute("llm.prompt_tokens", token_usage["prompt_tokens"])
        span.set_attribute("llm.completion_tokens", token_usage["completion_tokens"])
        span.set_attribute("llm.total_tokens", token_usage["total_tokens"])
    
    # Extract status code
    status_code = extract_llm_status_code(response)
    if status_code:
        span.set_attribute("llm.status_code", status_code)
    
    # Add model information if available
    if llm_model:
        span.set_attribute("llm.model", str(llm_model))
    elif hasattr(response, 'model'):
        span.set_attribute("llm.model", str(response.model))
    elif hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata and isinstance(metadata, dict):
            model = metadata.get('model')
            if model:
                span.set_attribute("llm.model", str(model))
    
    # Add response ID if available (for correlation)
    if hasattr(response, 'response_metadata'):
        metadata = response.response_metadata
        if metadata and isinstance(metadata, dict):
            response_id = metadata.get('id', metadata.get('response_id'))
            if response_id:
                span.set_attribute("llm.response_id", str(response_id))


def instrument_llm_call(llm, call_name: str = "llm.invoke", workflow_name: str = "compliance"):
    """
    Wrap an LLM object to automatically track calls in OpenTelemetry spans.
    
    This creates a wrapper around the LLM's invoke/ainvoke methods to capture
    token usage and status codes automatically.
    
    Args:
        llm: LLM object (LangChain BaseChatModel or similar)
        call_name: Name for the LLM call span
        workflow_name: Workflow name for context
    
    Returns:
        Wrapped LLM object with telemetry
    """
    if not OTEL_AVAILABLE or not llm:
        return llm
    
    tracer = get_tracer(f"langgraph.{workflow_name}.llm")
    
    # Store original methods
    original_invoke = getattr(llm, 'invoke', None)
    original_ainvoke = getattr(llm, 'ainvoke', None)
    
    # Wrap invoke (synchronous)
    if original_invoke:
        def wrapped_invoke(messages, **kwargs):
            with tracer.start_as_current_span(f"{call_name}") as span:
                if span:
                    # Get model name
                    model_name = getattr(llm, 'model_name', None) or getattr(llm, 'model', None)
                    if model_name:
                        span.set_attribute("llm.model", str(model_name))
                    
                    span.set_attribute("llm.call_type", "invoke")
                
                try:
                    response = original_invoke(messages, **kwargs)
                    
                    if span:
                        track_llm_call_in_span(span, response, model_name)
                        span.set_status(Status(StatusCode.OK))
                    
                    return response
                except Exception as e:
                    if span:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        span.set_attribute("error", True)
                        span.set_attribute("error.message", str(e))
                    raise
        
        llm.invoke = wrapped_invoke
    
    # Wrap ainvoke (asynchronous)
    if original_ainvoke:
        async def wrapped_ainvoke(messages, **kwargs):
            with tracer.start_as_current_span(f"{call_name}") as span:
                if span:
                    # Get model name
                    model_name = getattr(llm, 'model_name', None) or getattr(llm, 'model', None)
                    if model_name:
                        span.set_attribute("llm.model", str(model_name))
                    
                    span.set_attribute("llm.call_type", "ainvoke")
                
                try:
                    response = await original_ainvoke(messages, **kwargs)
                    
                    if span:
                        track_llm_call_in_span(span, response, model_name)
                        span.set_status(Status(StatusCode.OK))
                    
                    return response
                except Exception as e:
                    if span:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        span.set_attribute("error", True)
                        span.set_attribute("error.message", str(e))
                    raise
        
        llm.ainvoke = wrapped_ainvoke
    
    return llm


def track_llm_response_in_current_span(response: Any, llm_model: Optional[str] = None):
    """
    Track LLM response in the current OpenTelemetry span.
    
    This is a convenience function that nodes can call to explicitly track
    LLM responses. It will add token usage and status codes to the current span.
    
    Usage in nodes:
        response = llm.invoke(messages)
        track_llm_response_in_current_span(response)
    
    Args:
        response: LLM response object
        llm_model: Optional model name/identifier
    """
    if not OTEL_AVAILABLE:
        return
    
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span:
            track_llm_call_in_span(span, response, llm_model)
    except Exception:
        # Silently fail if no span context
        pass


def track_agent_executor_call(agent_executor, input_data: dict, call_name: str = "agent_executor.invoke", workflow_name: str = "compliance"):
    """
    Wrap an agent executor call to track LLM usage.
    
    Agent executors make multiple LLM calls internally. This wrapper captures
    aggregate token usage from all LLM calls made during execution.
    
    Args:
        agent_executor: Agent executor object
        input_data: Input data for the executor
        call_name: Name for the call span
        workflow_name: Workflow name for context
    
    Returns:
        Wrapped invoke function
    """
    if not OTEL_AVAILABLE:
        return agent_executor.invoke
    
    tracer = get_tracer(f"langgraph.{workflow_name}.agent")
    
    def wrapped_invoke(input_dict: dict):
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        llm_calls = 0
        status_codes = []
        
        with tracer.start_as_current_span(call_name) as span:
            if span:
                span.set_attribute("agent.call_type", "invoke")
            
            try:
                # Execute the agent
                result = agent_executor.invoke(input_dict)
                
                # Try to extract LLM usage from intermediate steps
                # Agent executors often store intermediate steps with LLM responses
                if hasattr(agent_executor, 'intermediate_steps') or isinstance(result, dict):
                    # Check result for intermediate steps
                    if isinstance(result, dict):
                        intermediate_steps = result.get('intermediate_steps', [])
                        for step in intermediate_steps:
                            if isinstance(step, tuple) and len(step) >= 2:
                                # Step format: (tool_call, tool_result)
                                # Tool calls may contain LLM responses
                                tool_result = step[1] if len(step) > 1 else None
                                if tool_result:
                                    # Check if tool result contains LLM response
                                    if hasattr(tool_result, 'response_metadata'):
                                        usage = extract_llm_token_usage(tool_result)
                                        total_prompt_tokens += usage["prompt_tokens"]
                                        total_completion_tokens += usage["completion_tokens"]
                                        total_tokens += usage["total_tokens"]
                                        llm_calls += 1
                    
                    # Check for LLM response in result
                    if 'output' in result or 'response' in result:
                        response_obj = result.get('output') or result.get('response')
                        if response_obj:
                            usage = extract_llm_token_usage(response_obj)
                            if usage["total_tokens"] > 0:
                                total_prompt_tokens += usage["prompt_tokens"]
                                total_completion_tokens += usage["completion_tokens"]
                                total_tokens += usage["total_tokens"]
                                llm_calls += 1
                            
                            status_code = extract_llm_status_code(response_obj)
                            if status_code:
                                status_codes.append(status_code)
                
                # Add aggregate metrics to span
                if span:
                    if total_tokens > 0:
                        span.set_attribute("llm.prompt_tokens", total_prompt_tokens)
                        span.set_attribute("llm.completion_tokens", total_completion_tokens)
                        span.set_attribute("llm.total_tokens", total_tokens)
                        span.set_attribute("llm.call_count", llm_calls)
                    
                    if status_codes:
                        # Use the most common status code or last one
                        span.set_attribute("llm.status_code", status_codes[-1])
                        if len(set(status_codes)) > 1:
                            span.set_attribute("llm.status_codes", ",".join(set(status_codes)))
                    
                    span.set_status(Status(StatusCode.OK))
                
                return result
                
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                raise
    
    return wrapped_invoke


# ============================================================================
# LangGraph Node Instrumentation
# ============================================================================

def instrument_langgraph_node(
    node_func,
    node_name: str,
    workflow_name: str = "compliance"
):
    """
    Wrap a LangGraph node function with OpenTelemetry tracing.
    
    This decorator:
    - Creates a span for each node execution
    - Adds session_id and other state attributes to the span
    - Records execution time and errors
    - Links spans to the workflow trace via session_id
    
    Args:
        node_func: The node function to instrument
        node_name: Name of the node (e.g., "intent_classifier", "dt_planner")
        workflow_name: Name of the workflow (e.g., "compliance", "detection_triage")
    
    Returns:
        Wrapped node function with telemetry
    """
    if not OTEL_AVAILABLE:
        # Return original function if telemetry not available
        return node_func
    
    # Check if telemetry is enabled in settings
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        if not settings.OPENTELEMETRY_ENABLED:
            return node_func
    except Exception:
        # If settings not available, continue (might be in test environment)
        pass
    
    tracer = get_tracer(f"langgraph.{workflow_name}")
    
    def wrapped_node(state):
        """Wrapped node with telemetry"""
        # Extract session_id and other relevant state fields
        session_id = state.get("session_id", "unknown")
        intent = state.get("intent")
        framework_id = state.get("framework_id")
        iteration_count = state.get("iteration_count", 0)
        validation_iteration = state.get("dt_validation_iteration", 0)
        
        # Create span name
        span_name = f"{workflow_name}.{node_name}"
        
        # Start span with attributes
        with tracer.start_as_current_span(span_name) as span:
            if span:
                # Add standard attributes
                span.set_attribute("langgraph.node.name", node_name)
                span.set_attribute("langgraph.workflow.name", workflow_name)
                span.set_attribute("session.id", str(session_id))
                
                # Add optional state attributes
                if intent:
                    span.set_attribute("workflow.intent", str(intent))
                if framework_id:
                    span.set_attribute("workflow.framework_id", str(framework_id))
                if iteration_count > 0:
                    span.set_attribute("workflow.iteration_count", iteration_count)
                if validation_iteration > 0:
                    span.set_attribute("workflow.validation_iteration", validation_iteration)
                
                # Add node-specific attributes from state
                if "user_query" in state:
                    # Truncate long queries for span attributes
                    query = str(state["user_query"])
                    if len(query) > 200:
                        query = query[:200] + "..."
                    span.set_attribute("workflow.user_query", query)
            
            try:
                # Execute the node
                result = node_func(state)
                
                # Record success
                if span:
                    span.set_status(Status(StatusCode.OK))
                    
                    # Track LLM call information if available in state
                    # Nodes often store llm_response in state after LLM calls
                    if isinstance(result, dict):
                        llm_response = result.get("llm_response")
                        if llm_response:
                            # Try to extract LLM info from stored response
                            # This could be a string, dict, or LangChain message object
                            if hasattr(llm_response, 'response_metadata') or hasattr(llm_response, 'token_usage'):
                                track_llm_call_in_span(span, llm_response)
                            elif isinstance(llm_response, dict) and 'response_metadata' in llm_response:
                                # Handle dict-wrapped response
                                track_llm_call_in_span(span, llm_response)
                        
                        # Also check for LLM response in messages (LangChain pattern)
                        messages = result.get("messages", [])
                        if messages:
                            # Get the last AI message which should have the LLM response
                            from langchain_core.messages import AIMessage
                            for msg in reversed(messages):
                                if isinstance(msg, AIMessage):
                                    track_llm_call_in_span(span, msg)
                                    break
                        
                        # Add counts of generated artifacts
                        for artifact_type in ["siem_rules", "playbooks", "test_scripts", 
                                            "controls", "risks", "scenarios"]:
                            if artifact_type in result:
                                count = len(result[artifact_type]) if isinstance(result[artifact_type], list) else 0
                                if count > 0:
                                    span.set_attribute(f"workflow.artifacts.{artifact_type}.count", count)
                
                return result
                
            except Exception as e:
                # Record error
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                
                # Re-raise the exception
                raise
    
    # Preserve function metadata
    wrapped_node.__name__ = node_func.__name__
    wrapped_node.__doc__ = node_func.__doc__
    wrapped_node.__module__ = node_func.__module__
    
    return wrapped_node


def instrument_workflow_invocation(
    workflow_app,
    initial_state: dict,
    config: dict = None,
    workflow_name: str = "compliance"
):
    """
    Instrument a workflow invocation with a top-level trace.
    
    This creates a root span for the entire workflow execution,
    which all node spans will be children of.
    
    Args:
        workflow_app: The compiled LangGraph application
        initial_state: Initial state for the workflow
        config: LangGraph config (with thread_id)
        workflow_name: Name of the workflow
    
    Returns:
        Workflow result with tracing
    """
    if not OTEL_AVAILABLE:
        # Return original invocation if telemetry not available
        return workflow_app.invoke(initial_state, config)
    
    # Check if telemetry is enabled in settings
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        if not settings.OPENTELEMETRY_ENABLED:
            return workflow_app.invoke(initial_state, config)
    except Exception:
        # If settings not available, continue (might be in test environment)
        pass
    
    tracer = get_tracer(f"langgraph.{workflow_name}")
    session_id = initial_state.get("session_id", "unknown")
    user_query = initial_state.get("user_query", "")
    
    # Create root span for workflow execution
    span_name = f"{workflow_name}.workflow.execute"
    
    with tracer.start_as_current_span(span_name) as span:
        if span:
            span.set_attribute("langgraph.workflow.name", workflow_name)
            span.set_attribute("session.id", str(session_id))
            span.set_attribute("workflow.type", workflow_name)
            
            # Truncate long queries
            if user_query:
                query = str(user_query)
                if len(query) > 500:
                    query = query[:500] + "..."
                span.set_attribute("workflow.user_query", query)
            
            # Add thread_id if available
            if config and "configurable" in config:
                thread_id = config["configurable"].get("thread_id")
                if thread_id:
                    span.set_attribute("langgraph.thread_id", str(thread_id))
        
        try:
            # Invoke workflow (all node spans will be children of this span)
            result = workflow_app.invoke(initial_state, config)
            
            if span:
                span.set_status(Status(StatusCode.OK))
                
                # Add result summary attributes
                if isinstance(result, dict):
                    # Count artifacts in final state
                    for artifact_type in ["siem_rules", "playbooks", "test_scripts",
                                        "controls", "risks", "scenarios"]:
                        if artifact_type in result:
                            count = len(result[artifact_type]) if isinstance(result[artifact_type], list) else 0
                            if count > 0:
                                span.set_attribute(f"workflow.result.{artifact_type}.count", count)
            
            return result
            
        except Exception as e:
            if span:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
            raise


async def instrument_workflow_stream(
    workflow_app,
    initial_state: dict,
    config: dict = None,
    workflow_name: str = "compliance"
):
    """
    Instrument a workflow stream invocation with a top-level trace.
    
    Similar to instrument_workflow_invocation but for streaming execution.
    
    Args:
        workflow_app: The compiled LangGraph application
        initial_state: Initial state for the workflow
        config: LangGraph config (with thread_id)
        workflow_name: Name of the workflow
    
    Yields:
        Workflow events with tracing
    """
    if not OTEL_AVAILABLE:
        # Return original stream if telemetry not available
        async for event in workflow_app.astream(initial_state, config):
            yield event
        return
    
    # Check if telemetry is enabled in settings
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        if not settings.OPENTELEMETRY_ENABLED:
            async for event in workflow_app.astream(initial_state, config):
                yield event
            return
    except Exception:
        # If settings not available, continue (might be in test environment)
        pass
    
    tracer = get_tracer(f"langgraph.{workflow_name}")
    session_id = initial_state.get("session_id", "unknown")
    user_query = initial_state.get("user_query", "")
    
    # Create root span for workflow execution
    span_name = f"{workflow_name}.workflow.stream"
    
    with tracer.start_as_current_span(span_name) as span:
        if span:
            span.set_attribute("langgraph.workflow.name", workflow_name)
            span.set_attribute("session.id", str(session_id))
            span.set_attribute("workflow.type", workflow_name)
            span.set_attribute("workflow.execution_mode", "stream")
            
            # Truncate long queries
            if user_query:
                query = str(user_query)
                if len(query) > 500:
                    query = query[:500] + "..."
                span.set_attribute("workflow.user_query", query)
            
            # Add thread_id if available
            if config and "configurable" in config:
                thread_id = config["configurable"].get("thread_id")
                if thread_id:
                    span.set_attribute("langgraph.thread_id", str(thread_id))
        
        try:
            # Stream workflow events (all node spans will be children of this span)
            async for event in workflow_app.astream(initial_state, config):
                yield event
            
            if span:
                span.set_status(Status(StatusCode.OK))
                
        except Exception as e:
            if span:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
            raise


async def instrument_workflow_stream_events(
    workflow_app,
    initial_state: dict,
    config: dict = None,
    workflow_name: str = "compliance",
    version: str = "v2"
):
    """
    Instrument a workflow astream_events invocation with a top-level trace.
    
    Similar to instrument_workflow_stream but for astream_events which provides
    more detailed event information.
    
    Args:
        workflow_app: The compiled LangGraph application
        initial_state: Initial state for the workflow
        config: LangGraph config (with thread_id)
        workflow_name: Name of the workflow
        version: Event stream version (default: "v2")
    
    Yields:
        Workflow events with tracing
    """
    if not OTEL_AVAILABLE:
        # Return original stream if telemetry not available
        async for event in workflow_app.astream_events(initial_state, config=config, version=version):
            yield event
        return
    
    # Check if telemetry is enabled in settings
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        if not settings.OPENTELEMETRY_ENABLED:
            async for event in workflow_app.astream_events(initial_state, config=config, version=version):
                yield event
            return
    except Exception:
        # If settings not available, continue (might be in test environment)
        pass
    
    tracer = get_tracer(f"langgraph.{workflow_name}")
    session_id = initial_state.get("session_id", "unknown")
    user_query = initial_state.get("user_query", "")
    
    # Create root span for workflow execution
    span_name = f"{workflow_name}.workflow.stream_events"
    
    with tracer.start_as_current_span(span_name) as span:
        if span:
            span.set_attribute("langgraph.workflow.name", workflow_name)
            span.set_attribute("session.id", str(session_id))
            span.set_attribute("workflow.type", workflow_name)
            span.set_attribute("workflow.execution_mode", "stream_events")
            span.set_attribute("workflow.event_version", version)
            
            # Truncate long queries
            if user_query:
                query = str(user_query)
                if len(query) > 500:
                    query = query[:500] + "..."
                span.set_attribute("workflow.user_query", query)
            
            # Add thread_id if available
            if config and "configurable" in config:
                thread_id = config["configurable"].get("thread_id")
                if thread_id:
                    span.set_attribute("langgraph.thread_id", str(thread_id))
        
        try:
            # Stream workflow events (all node spans will be children of this span)
            async for event in workflow_app.astream_events(initial_state, config=config, version=version):
                yield event
            
            if span:
                span.set_status(Status(StatusCode.OK))
                
        except Exception as e:
            if span:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
            raise
