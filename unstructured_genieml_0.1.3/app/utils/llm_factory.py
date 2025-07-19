"""
Factory utility for creating LLM instances based on configuration.
"""
import logging
import json
from typing import Any, Dict, Optional, Literal

from langchain_openai import ChatOpenAI
#from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from app.config.settings import get_settings
from app.config.agent_config import ModelType, ModelProvider, ModelConfig

# Set up logging
logger = logging.getLogger("LLMFactory")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== LLMFactory Logger Initialized ===")

def create_llm(
    model_config: Optional[ModelConfig] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    model_type: Optional[ModelType] = None,
    provider: Optional[ModelProvider] = None,
    task_name: str = "general",
    **kwargs
) -> BaseChatModel:
    """
    Create an LLM instance based on configuration.
    
    Args:
        model_config: ModelConfig object with model settings
        temperature: Override temperature (if provided)
        max_tokens: Override max tokens (if provided)
        model_type: Override model type (if provided)
        provider: Override provider (if provided)
        task_name: Name of the task for logging purposes
        **kwargs: Additional keyword arguments to pass to the LLM
        
    Returns:
        LLM instance
    """
    settings = get_settings()
    
    # Use provided config or create default
    if model_config is None:
        from app.config.agent_config import model_task_assignment
        model_config = model_task_assignment.default
    
    # Override config values if provided
    provider_to_use = provider or model_config.provider
    model_type_to_use = model_type or model_config.model_type
    temperature_to_use = temperature if temperature is not None else model_config.temperature
    max_tokens_to_use = max_tokens if max_tokens is not None else model_config.max_tokens
    
    # Log the model configuration
    logger.info(f"[{task_name}] Creating LLM with provider={provider_to_use}, model={model_type_to_use}, temperature={temperature_to_use}")
    
    try:
        # Create LLM based on provider
        if provider_to_use == ModelProvider.GOOGLE:
            if not settings.GOOGLE_API_KEY:
                logger.error(f"[{task_name}] Google API key not found! Falling back to OpenAI.")
                # Fall back to OpenAI
                provider_to_use = ModelProvider.OPENAI
                model_type_to_use = ModelType.GPT_4O_MINI
            else:
                logger.info(f"[{task_name}] Using Google Gemini LLM model {model_type_to_use}")
                return ChatGoogleGenerativeAI(
                    model=model_type_to_use,
                    temperature=temperature_to_use,
                    max_tokens=max_tokens_to_use,
                    api_key=SecretStr(settings.GOOGLE_API_KEY),
                    **kwargs
                )
        
        # Default to OpenAI or if Google failed
        logger.info(f"[{task_name}] Using OpenAI LLM model {model_type_to_use}")
        return ChatOpenAI(
            model=model_type_to_use,
            temperature=temperature_to_use,
            max_tokens=max_tokens_to_use,
            api_key=SecretStr(settings.OPENAI_API_KEY),
            **kwargs
        )
    except Exception as e:
        logger.error(f"[{task_name}] Error creating LLM: {str(e)}")
        # Always fall back to OpenAI in case of errors
        logger.info(f"[{task_name}] Falling back to OpenAI default model due to error")
        return ChatOpenAI(
            model="gpt-4o",
            temperature=0.0,
            **kwargs
        )

def get_splitter_llm(**kwargs) -> BaseChatModel:
    """
    Get LLM for query splitting.
    
    Args:
        **kwargs: Additional keyword arguments to pass to the LLM
        
    Returns:
        LLM instance configured for query splitting
    """
    from app.config.agent_config import model_task_assignment
    logger.info("Creating LLM for query splitting task")
    # return create_llm(model_config=model_task_assignment.splitter, task_name="query_splitting", **kwargs)
    return create_llm(model_config=None, task_name="query_splitting", **kwargs)

def get_answer_generation_llm(**kwargs) -> BaseChatModel:
    """
    Get LLM for answer generation.
    
    Args:
        **kwargs: Additional keyword arguments to pass to the LLM
        
    Returns:
        LLM instance configured for answer generation
    """
    from app.config.agent_config import ModelType, ModelProvider, ModelConfig
    logger.info("Creating LLM for answer generation task - Using GPT-4o-mini") 
    # Create a custom model config for GPT-4o-mini
    model_config = ModelConfig(
        provider=ModelProvider.OPENAI,
        model_type=ModelType.GPT_4O_MINI,
        temperature=0.0
    )
    # Use the custom model config
    return create_llm(model_config=model_config, task_name="answer_generation", **kwargs)

def get_default_llm(**kwargs) -> BaseChatModel:
    """
    Get default LLM for other tasks.
    
    Args:
        **kwargs: Additional keyword arguments to pass to the LLM
        
    Returns:
        Default LLM instance
    """
    from app.config.agent_config import model_task_assignment
    task_name = kwargs.pop("task_name", "default")
    logger.info(f"Creating default LLM for {task_name} task")
    return create_llm(model_config=model_task_assignment.default, task_name=task_name, **kwargs)
