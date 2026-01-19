"""
Standalone dependencies for API to MDL converter with agent integration
Simplified version that works independently
"""
from typing import Optional
import logging
from functools import lru_cache
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from standalone_settings import get_settings

logger = logging.getLogger(__name__)

# Global cache for LLM and embeddings
_llm_cache: Optional[ChatOpenAI] = None
_embeddings_cache: Optional[OpenAIEmbeddings] = None


def get_llm(
    temperature: Optional[float] = None,
    model: Optional[str] = None
) -> ChatOpenAI:
    """
    Get LLM instance with caching
    
    Args:
        temperature: Temperature for the model (defaults to settings)
        model: Model name (defaults to settings)
        
    Returns:
        ChatOpenAI instance configured with settings
    """
    global _llm_cache
    
    settings = get_settings()
    model = model or settings.LLM_MODEL
    temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
    
    # Check if we need to recreate the LLM
    if _llm_cache is None or (
        hasattr(_llm_cache, 'model_name') and _llm_cache.model_name != model
    ) or (
        hasattr(_llm_cache, 'temperature') and _llm_cache.temperature != temperature
    ):
        logger.info(f"Creating new LLM: {model}, temperature: {temperature}")
        
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not configured. "
                "Please set OPENAI_API_KEY in your environment variables or .env file."
            )
        
        _llm_cache = ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=settings.OPENAI_API_KEY
        )
    else:
        logger.debug("Returning cached LLM instance")
    
    return _llm_cache


def get_embeddings(
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> OpenAIEmbeddings:
    """
    Get embeddings model with caching
    
    Args:
        model: Model name (defaults to settings)
        api_key: API key (defaults to settings)
        
    Returns:
        OpenAIEmbeddings instance
    """
    global _embeddings_cache
    
    settings = get_settings()
    model = model or settings.EMBEDDING_MODEL
    api_key = api_key or settings.OPENAI_API_KEY
    
    # Check if we need to recreate the embeddings model
    if _embeddings_cache is None or (
        hasattr(_embeddings_cache, 'model') and _embeddings_cache.model != model
    ):
        logger.info(f"Creating new embeddings model: {model}")
        
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured. "
                "Please set OPENAI_API_KEY in your environment variables or .env file."
            )
        
        _embeddings_cache = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key
        )
    else:
        logger.debug("Returning cached embeddings model")
    
    return _embeddings_cache


def clear_caches():
    """Clear all cached instances"""
    global _llm_cache, _embeddings_cache
    _llm_cache = None
    _embeddings_cache = None
    logger.info("Cleared all cached dependencies")

