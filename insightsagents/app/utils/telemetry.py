import asyncio
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import Status, StatusCode
from functools import wraps
from typing import Optional, Callable
from app.core.settings import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def setup_telemetry():
    """Initialize OpenTelemetry configuration."""
    if not settings.OPENTELEMETRY_ENABLED:
        logger.info("OpenTelemetry tracing is disabled")
        return

    # Create resource
    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME
    })

    # Create TracerProvider
    trace_provider = TracerProvider(resource=resource)

    # Create OTLP Exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=True  # Set to False in production with proper certificates
    )

    # Add BatchSpanProcessor to the TracerProvider
    trace_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # Set the TracerProvider as the global default
    trace.set_tracer_provider(trace_provider)

def traced(
    name: Optional[str] = None,
    attributes: Optional[dict] = None
) -> Callable:
    """
    Decorator to add OpenTelemetry tracing to a function.
    
    Args:
        name: Optional name for the span
        attributes: Optional attributes to add to the span
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not settings.OPENTELEMETRY_ENABLED:
                return await func(*args, **kwargs)

            tracer = trace.get_tracer(__name__)
            span_name = name or func.__name__

            with tracer.start_as_current_span(
                span_name,
                attributes=attributes
            ) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not settings.OPENTELEMETRY_ENABLED:
                return func(*args, **kwargs)

            tracer = trace.get_tracer(__name__)
            span_name = name or func.__name__

            with tracer.start_as_current_span(
                span_name,
                attributes=attributes
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator