"""
OpenTelemetry Configuration and Setup

Configures OpenTelemetry tracing, metrics, and logging for the application.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace, metrics
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
    service_name: str = "knowledge-service",
    otlp_endpoint: Optional[str] = None,
    enable_console_exporter: bool = False,
    instrument_fastapi: bool = True,
    instrument_asyncpg: bool = True
) -> bool:
    """
    Setup OpenTelemetry tracing and instrumentation
    
    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP collector endpoint (default: env var or localhost:4317)
        enable_console_exporter: Also export to console for debugging
        instrument_fastapi: Automatically instrument FastAPI
        instrument_asyncpg: Automatically instrument asyncpg
        
    Returns:
        True if setup successful, False otherwise
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - tracing disabled")
        return False
    
    try:
        # Get endpoint from env or parameter
        if otlp_endpoint is None:
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        
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
        
        # Add OTLP exporter
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True  # Use False in production with TLS
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            tracer_provider.add_span_processor(span_processor)
            logger.info("✓ OTLP span exporter configured")
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
