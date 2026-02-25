"""
LLM Tracing Utility with OpenTelemetry Integration

Provides standardized chain-style LLM calls with detailed tracing for OpenTelemetry.
All LLM calls should use this utility for consistent tracing and monitoring.
"""
import logging
import time
import json
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
from contextlib import asynccontextmanager, contextmanager

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
    tracer = trace.get_tracer(__name__)
except ImportError:
    OTEL_AVAILABLE = False
    tracer = None
    logger.warning("OpenTelemetry not available - tracing will use logging only")


class LLMTracer:
    """
    Centralized LLM call wrapper with OpenTelemetry tracing
    
    Usage:
        tracer = LLMTracer()
        
        # Simple call with chain
        result = await tracer.ainvoke_chain(
            llm=llm,
            prompt=prompt_template,
            inputs={"query": "..."},
            operation_name="intent_understanding",
            parse_json=True
        )
        
        # Or use context manager for custom logic
        async with tracer.trace_llm_call("custom_operation") as span:
            result = await llm.ainvoke(...)
            span.set_attribute("result_length", len(result))
    """
    
    def __init__(self, enable_detailed_logging: bool = True):
        """
        Initialize LLM tracer
        
        Args:
            enable_detailed_logging: Enable detailed input/output logging
        """
        self.enable_detailed_logging = enable_detailed_logging
        self.tracer = tracer if OTEL_AVAILABLE else None
    
    async def ainvoke_chain(
        self,
        llm: ChatOpenAI,
        prompt: ChatPromptTemplate,
        inputs: Dict[str, Any],
        operation_name: str,
        parse_json: bool = False,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Invoke LLM using chain pattern with OpenTelemetry tracing
        
        Args:
            llm: ChatOpenAI instance
            prompt: ChatPromptTemplate
            inputs: Prompt inputs
            operation_name: Name of the operation (e.g., "intent_understanding")
            parse_json: Whether to parse response as JSON
            timeout: Optional timeout in seconds
            metadata: Optional metadata to include in trace
            
        Returns:
            Parsed response (str or dict if parse_json=True)
        """
        span_name = f"llm.{operation_name}"
        
        if self.tracer:
            # OpenTelemetry tracing
            with self.tracer.start_as_current_span(span_name) as span:
                return await self._execute_chain(
                    llm=llm,
                    prompt=prompt,
                    inputs=inputs,
                    operation_name=operation_name,
                    parse_json=parse_json,
                    timeout=timeout,
                    metadata=metadata,
                    span=span
                )
        else:
            # Logging-only fallback
            return await self._execute_chain(
                llm=llm,
                prompt=prompt,
                inputs=inputs,
                operation_name=operation_name,
                parse_json=parse_json,
                timeout=timeout,
                metadata=metadata,
                span=None
            )
    
    def invoke_chain(
        self,
        llm: ChatOpenAI,
        prompt: ChatPromptTemplate,
        inputs: Dict[str, Any],
        operation_name: str,
        parse_json: bool = False,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Synchronous version of ainvoke_chain
        
        Args:
            Same as ainvoke_chain
            
        Returns:
            Parsed response (str or dict if parse_json=True)
        """
        span_name = f"llm.{operation_name}"
        
        if self.tracer:
            with self.tracer.start_as_current_span(span_name) as span:
                return self._execute_chain_sync(
                    llm=llm,
                    prompt=prompt,
                    inputs=inputs,
                    operation_name=operation_name,
                    parse_json=parse_json,
                    timeout=timeout,
                    metadata=metadata,
                    span=span
                )
        else:
            return self._execute_chain_sync(
                llm=llm,
                prompt=prompt,
                inputs=inputs,
                operation_name=operation_name,
                parse_json=parse_json,
                timeout=timeout,
                metadata=metadata,
                span=None
            )
    
    async def _execute_chain(
        self,
        llm: ChatOpenAI,
        prompt: ChatPromptTemplate,
        inputs: Dict[str, Any],
        operation_name: str,
        parse_json: bool,
        timeout: Optional[float],
        metadata: Optional[Dict[str, Any]],
        span: Optional[Any]
    ) -> Union[str, Dict[str, Any]]:
        """Internal async chain execution with tracing"""
        start_time = time.time()
        
        try:
            # Log start
            self._log_llm_start(operation_name, inputs, metadata)
            
            # Set span attributes
            if span:
                self._set_span_attributes(span, operation_name, inputs, metadata, llm)
            
            # Build chain
            if parse_json:
                parser = JsonOutputParser()
                chain = prompt | llm | parser
            else:
                parser = StrOutputParser()
                chain = prompt | llm | parser
            
            # Execute chain with optional timeout
            if timeout:
                import asyncio
                result = await asyncio.wait_for(
                    chain.ainvoke(inputs),
                    timeout=timeout
                )
            else:
                result = await chain.ainvoke(inputs)
            
            # Calculate metrics
            duration = time.time() - start_time
            
            # Log result
            self._log_llm_success(operation_name, result, duration, metadata)
            
            # Update span
            if span:
                self._set_span_success(span, result, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            self._log_llm_error(operation_name, e, duration, metadata)
            
            # Update span
            if span:
                self._set_span_error(span, e, duration)
            
            raise
    
    def _execute_chain_sync(
        self,
        llm: ChatOpenAI,
        prompt: ChatPromptTemplate,
        inputs: Dict[str, Any],
        operation_name: str,
        parse_json: bool,
        timeout: Optional[float],
        metadata: Optional[Dict[str, Any]],
        span: Optional[Any]
    ) -> Union[str, Dict[str, Any]]:
        """Internal sync chain execution with tracing"""
        start_time = time.time()
        
        try:
            # Log start
            self._log_llm_start(operation_name, inputs, metadata)
            
            # Set span attributes
            if span:
                self._set_span_attributes(span, operation_name, inputs, metadata, llm)
            
            # Build chain
            if parse_json:
                parser = JsonOutputParser()
                chain = prompt | llm | parser
            else:
                parser = StrOutputParser()
                chain = prompt | llm | parser
            
            # Execute chain
            result = chain.invoke(inputs)
            
            # Calculate metrics
            duration = time.time() - start_time
            
            # Log result
            self._log_llm_success(operation_name, result, duration, metadata)
            
            # Update span
            if span:
                self._set_span_success(span, result, duration)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            self._log_llm_error(operation_name, e, duration, metadata)
            
            # Update span
            if span:
                self._set_span_error(span, e, duration)
            
            raise
    
    @asynccontextmanager
    async def trace_llm_call(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager for custom LLM calls with tracing
        
        Usage:
            async with tracer.trace_llm_call("custom_operation") as span:
                result = await llm.ainvoke(...)
                span.set_attribute("result_length", len(result))
        """
        span_name = f"llm.{operation_name}"
        
        if self.tracer:
            with self.tracer.start_as_current_span(span_name) as span:
                start_time = time.time()
                
                # Set basic attributes
                span.set_attribute("llm.operation", operation_name)
                span.set_attribute("llm.start_time", datetime.utcnow().isoformat())
                
                if metadata:
                    for key, value in metadata.items():
                        span.set_attribute(f"llm.metadata.{key}", str(value))
                
                try:
                    yield span
                    duration = time.time() - start_time
                    span.set_attribute("llm.duration_seconds", duration)
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    duration = time.time() - start_time
                    span.set_attribute("llm.duration_seconds", duration)
                    span.set_attribute("llm.error", str(e))
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        else:
            # Logging-only fallback
            start_time = time.time()
            self._log_llm_start(operation_name, {}, metadata)
            
            try:
                yield None
                duration = time.time() - start_time
                self._log_llm_success(operation_name, None, duration, metadata)
            except Exception as e:
                duration = time.time() - start_time
                self._log_llm_error(operation_name, e, duration, metadata)
                raise
    
    @contextmanager
    def trace_llm_call_sync(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Synchronous version of trace_llm_call"""
        span_name = f"llm.{operation_name}"
        
        if self.tracer:
            with self.tracer.start_as_current_span(span_name) as span:
                start_time = time.time()
                
                span.set_attribute("llm.operation", operation_name)
                span.set_attribute("llm.start_time", datetime.utcnow().isoformat())
                
                if metadata:
                    for key, value in metadata.items():
                        span.set_attribute(f"llm.metadata.{key}", str(value))
                
                try:
                    yield span
                    duration = time.time() - start_time
                    span.set_attribute("llm.duration_seconds", duration)
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    duration = time.time() - start_time
                    span.set_attribute("llm.duration_seconds", duration)
                    span.set_attribute("llm.error", str(e))
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        else:
            start_time = time.time()
            self._log_llm_start(operation_name, {}, metadata)
            
            try:
                yield None
                duration = time.time() - start_time
                self._log_llm_success(operation_name, None, duration, metadata)
            except Exception as e:
                duration = time.time() - start_time
                self._log_llm_error(operation_name, e, duration, metadata)
                raise
    
    def _set_span_attributes(
        self,
        span: Any,
        operation_name: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
        llm: ChatOpenAI
    ) -> None:
        """Set OpenTelemetry span attributes"""
        try:
            # Basic attributes
            span.set_attribute("llm.operation", operation_name)
            span.set_attribute("llm.model", llm.model_name)
            span.set_attribute("llm.temperature", llm.temperature)
            span.set_attribute("llm.start_time", datetime.utcnow().isoformat())
            
            # Input attributes (sanitized)
            if self.enable_detailed_logging:
                for key, value in inputs.items():
                    if isinstance(value, (str, int, float, bool)):
                        value_str = str(value)
                        # Truncate long strings
                        if len(value_str) > 500:
                            value_str = value_str[:500] + "..."
                        span.set_attribute(f"llm.input.{key}", value_str)
                    elif isinstance(value, (list, dict)):
                        span.set_attribute(f"llm.input.{key}.type", type(value).__name__)
                        span.set_attribute(f"llm.input.{key}.size", len(value))
            
            # Metadata
            if metadata:
                for key, value in metadata.items():
                    span.set_attribute(f"llm.metadata.{key}", str(value))
                    
        except Exception as e:
            logger.warning(f"Error setting span attributes: {str(e)}")
    
    def _set_span_success(
        self,
        span: Any,
        result: Union[str, Dict[str, Any]],
        duration: float
    ) -> None:
        """Set span attributes for successful execution"""
        try:
            span.set_attribute("llm.duration_seconds", duration)
            span.set_attribute("llm.success", True)
            
            # Result attributes
            if isinstance(result, str):
                span.set_attribute("llm.result.type", "string")
                span.set_attribute("llm.result.length", len(result))
                if self.enable_detailed_logging and len(result) <= 500:
                    span.set_attribute("llm.result.content", result)
            elif isinstance(result, dict):
                span.set_attribute("llm.result.type", "dict")
                span.set_attribute("llm.result.keys", ",".join(result.keys()))
                if self.enable_detailed_logging:
                    result_json = json.dumps(result, default=str)
                    if len(result_json) <= 1000:
                        span.set_attribute("llm.result.content", result_json)
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            logger.warning(f"Error setting span success attributes: {str(e)}")
    
    def _set_span_error(
        self,
        span: Any,
        error: Exception,
        duration: float
    ) -> None:
        """Set span attributes for failed execution"""
        try:
            span.set_attribute("llm.duration_seconds", duration)
            span.set_attribute("llm.success", False)
            span.set_attribute("llm.error", str(error))
            span.set_attribute("llm.error.type", type(error).__name__)
            
            span.set_status(Status(StatusCode.ERROR, str(error)))
            
        except Exception as e:
            logger.warning(f"Error setting span error attributes: {str(e)}")
    
    def _log_llm_start(
        self,
        operation_name: str,
        inputs: Dict[str, Any],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Log LLM call start in OpenTelemetry format"""
        log_data = {
            "event": "llm.start",
            "operation": operation_name,
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": self._get_trace_id(),
            "span_id": self._get_span_id()
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        if self.enable_detailed_logging:
            # Sanitize inputs for logging
            sanitized_inputs = {}
            for key, value in inputs.items():
                if isinstance(value, str):
                    sanitized_inputs[key] = value[:200] + "..." if len(value) > 200 else value
                elif isinstance(value, (int, float, bool)):
                    sanitized_inputs[key] = value
                elif isinstance(value, (list, dict)):
                    sanitized_inputs[key] = f"<{type(value).__name__} size={len(value)}>"
                else:
                    sanitized_inputs[key] = f"<{type(value).__name__}>"
            
            log_data["inputs"] = sanitized_inputs
        
        logger.info(f"OTEL_TRACE: {json.dumps(log_data, default=str)}")
    
    def _log_llm_success(
        self,
        operation_name: str,
        result: Union[str, Dict[str, Any], None],
        duration: float,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Log LLM call success in OpenTelemetry format"""
        log_data = {
            "event": "llm.success",
            "operation": operation_name,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": round(duration, 3),
            "trace_id": self._get_trace_id(),
            "span_id": self._get_span_id()
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        if self.enable_detailed_logging and result is not None:
            if isinstance(result, str):
                log_data["result_type"] = "string"
                log_data["result_length"] = len(result)
                if len(result) <= 200:
                    log_data["result_preview"] = result
                else:
                    log_data["result_preview"] = result[:200] + "..."
            elif isinstance(result, dict):
                log_data["result_type"] = "dict"
                log_data["result_keys"] = list(result.keys())
                result_json = json.dumps(result, default=str)
                if len(result_json) <= 500:
                    log_data["result"] = result
                else:
                    log_data["result_preview"] = result_json[:500] + "..."
        
        logger.info(f"OTEL_TRACE: {json.dumps(log_data, default=str)}")
    
    def _log_llm_error(
        self,
        operation_name: str,
        error: Exception,
        duration: float,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Log LLM call error in OpenTelemetry format"""
        log_data = {
            "event": "llm.error",
            "operation": operation_name,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": round(duration, 3),
            "error": str(error),
            "error_type": type(error).__name__,
            "trace_id": self._get_trace_id(),
            "span_id": self._get_span_id()
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        logger.error(f"OTEL_TRACE: {json.dumps(log_data, default=str)}")
    
    def _get_trace_id(self) -> Optional[str]:
        """Get current trace ID from OpenTelemetry context"""
        if not OTEL_AVAILABLE:
            return None
        
        try:
            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().trace_id, '032x')
        except Exception:
            pass
        
        return None
    
    def _get_span_id(self) -> Optional[str]:
        """Get current span ID from OpenTelemetry context"""
        if not OTEL_AVAILABLE:
            return None
        
        try:
            span = trace.get_current_span()
            if span and span.get_span_context().is_valid:
                return format(span.get_span_context().span_id, '016x')
        except Exception:
            pass
        
        return None


# Global tracer instance
_global_tracer = LLMTracer()


def get_llm_tracer() -> LLMTracer:
    """Get global LLM tracer instance"""
    return _global_tracer


async def traced_llm_call(
    llm: ChatOpenAI,
    prompt: ChatPromptTemplate,
    inputs: Dict[str, Any],
    operation_name: str,
    parse_json: bool = False,
    timeout: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Union[str, Dict[str, Any]]:
    """
    Convenience function for traced LLM calls
    
    Usage:
        result = await traced_llm_call(
            llm=llm,
            prompt=prompt_template,
            inputs={"query": "..."},
            operation_name="intent_understanding",
            parse_json=True
        )
    
    Args:
        llm: ChatOpenAI instance
        prompt: ChatPromptTemplate
        inputs: Prompt inputs
        operation_name: Name of the operation
        parse_json: Whether to parse response as JSON
        timeout: Optional timeout in seconds
        metadata: Optional metadata to include in trace
        
    Returns:
        Parsed response (str or dict if parse_json=True)
    """
    tracer = get_llm_tracer()
    return await tracer.ainvoke_chain(
        llm=llm,
        prompt=prompt,
        inputs=inputs,
        operation_name=operation_name,
        parse_json=parse_json,
        timeout=timeout,
        metadata=metadata
    )


def traced_llm_call_sync(
    llm: ChatOpenAI,
    prompt: ChatPromptTemplate,
    inputs: Dict[str, Any],
    operation_name: str,
    parse_json: bool = False,
    timeout: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Union[str, Dict[str, Any]]:
    """
    Synchronous version of traced_llm_call
    
    Args:
        Same as traced_llm_call
        
    Returns:
        Parsed response (str or dict if parse_json=True)
    """
    tracer = get_llm_tracer()
    return tracer.invoke_chain(
        llm=llm,
        prompt=prompt,
        inputs=inputs,
        operation_name=operation_name,
        parse_json=parse_json,
        timeout=timeout,
        metadata=metadata
    )
