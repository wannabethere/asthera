"""
Langfuse compatibility layer for handling API changes between versions.

This module provides a compatibility layer for the langfuse observe decorator
that has changed its API structure in newer versions.
"""

import logging

logger = logging.getLogger(__name__)

# Langfuse compatibility layer
try:
    from langfuse import observe
    logger.info("Using langfuse observe decorator from langfuse package")
except ImportError:
    try:
        from langfuse import Langfuse
        # Create a dummy observe decorator if the new API is used
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        logger.info("Using dummy observe decorator for new langfuse API")
    except ImportError:
        # If langfuse is not available at all, create a no-op decorator
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        logger.warning("Langfuse not available, using no-op observe decorator")

# Export the observe decorator
__all__ = ['observe']
