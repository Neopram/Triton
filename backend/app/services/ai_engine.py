"""
AI Engine Module - Central hub for AI model interactions.

This module provides a unified interface to interact with different AI models.
It supports:
- Dynamic registration of AI engines
- Easy switching between models
- Context augmentation
- Standardized error handling
- Performance monitoring

Usage:
    result = await query_ai_engine(
        prompt="Summarize this text",
        engine="phi3",  # Optional, defaults to config
        context="Additional context",  # Optional
        temperature=0.7  # Optional
    )

Available engines:
- phi3: Local Phi-3 model
- deepseek: DeepSeek API

To add a new engine:
1. Create a new module with a query function
2. Use @register_ai_engine decorator or add to _ENGINE_REGISTRY
"""

import os
import time
import importlib
from typing import Dict, Any, Optional, Callable, List
from functools import lru_cache
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import ai_logger
from app.services.context_augmentor import get_context_augmentor

# Type alias for engine factory functions
AIEngineFactory = Callable[[], Any]

# Engine registry - maps engine names to factory functions
_ENGINE_REGISTRY: Dict[str, AIEngineFactory] = {}

def register_ai_engine(name: str):
    """
    Decorator to register an AI engine factory function.
    
    Args:
        name: The name of the engine to register
        
    Returns:
        Decorator function
    """
    def decorator(factory_func: AIEngineFactory) -> AIEngineFactory:
        if name in _ENGINE_REGISTRY:
            ai_logger.warning(f"Overwriting existing AI engine: {name}")
        _ENGINE_REGISTRY[name] = factory_func
        ai_logger.info(f"Registered AI engine: {name}")
        return factory_func
    return decorator

def _load_engines():
    """Load all available AI engine modules."""
    try:
        # Import engine modules to register them
        from app.services.phi3_engine import query_phi3
        from app.services.deepseek_engine import query_deepseek
        
        # You can add more engine imports here in the future
        ai_logger.info(f"Loaded AI engines: {list(_ENGINE_REGISTRY.keys())}")
    except Exception as e:
        ai_logger.error(f"Error loading AI engines: {str(e)}")

# Initialize engine registry
_load_engines()

@lru_cache(maxsize=1)
def get_available_engines() -> List[str]:
    """
    Get names of all available AI engines.
    
    Returns:
        List of engine names
    """
    return list(_ENGINE_REGISTRY.keys())

@register_ai_engine("phi3")
def get_phi3_engine():
    """Factory function for Phi-3 engine."""
    from app.services.phi3_engine import query_phi3
    return query_phi3

@register_ai_engine("deepseek")
def get_deepseek_engine():
    """Factory function for DeepSeek engine."""
    from app.services.deepseek_engine import query_deepseek
    return query_deepseek

async def query_ai_engine(
    prompt: str,
    engine: Optional[str] = None,
    context: Optional[str] = None,
    use_rag: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    prompt_template: Optional[str] = None
) -> dict:
    """
    Query the AI engine with the given prompt.
    
    Args:
        prompt: The prompt to send to the AI engine
        engine: The engine to use (default: from settings)
        context: Optional context to prepend to the prompt
        use_rag: Whether to augment the prompt with relevant context from RAG
        temperature: Temperature parameter for generation
        max_tokens: Maximum number of tokens to generate
        prompt_template: Optional custom prompt template
        
    Returns:
        Dictionary with generated text and context metadata if RAG was used
    """
    # Start timing
    start_time = time.time()
    
    # Determine which engine to use
    engine_name = engine or settings.AI_ENGINE
    
    if engine_name not in _ENGINE_REGISTRY:
        available = ", ".join(get_available_engines())
        ai_logger.error(f"Unknown AI engine: {engine_name}. Available: {available}")
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown AI engine: {engine_name}. Available: {available}"
        )
    
    # Get the engine function
    try:
        engine_func = _ENGINE_REGISTRY[engine_name]()
    except Exception as e:
        ai_logger.error(f"Error creating AI engine {engine_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error initializing AI engine: {str(e)}"
        )
    
    # Enhance the prompt with RAG context if enabled
    context_metadata = []
    enhanced_prompt = prompt
    
    if use_rag:
        try:
            augmentor = get_context_augmentor()
            enhanced_prompt, context_metadata = await augmentor.augment_prompt(prompt)
        except Exception as e:
            ai_logger.warning(f"Error augmenting prompt with RAG: {str(e)}")
            # Continue with original prompt on error
    
    # Enhance the prompt with explicit context if provided
    if context:
        if prompt_template:
            # Use custom template if provided
            enhanced_prompt = prompt_template.format(context=context, prompt=enhanced_prompt)
        else:
            # Use default template
            enhanced_prompt = f"Additional context information:\n{context}\n\nBased on the additional context and any context retrieved, {enhanced_prompt}"
    
    # Log the request
    ai_logger.info(f"Querying {engine_name} engine", extra={
        "engine": engine_name,
        "prompt_length": len(enhanced_prompt),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "rag_enabled": use_rag,
        "contexts_used": len(context_metadata)
    })
    
    # Query the engine
    try:
        if engine_name == "phi3":
            # Synchronous function
            result = engine_func(enhanced_prompt)
        else:
            # Async function
            result = await engine_func(enhanced_prompt)
        
        # Calculate tokens and processing time
        tokens = len(enhanced_prompt.split()) + len(result.split())
        processing_time = time.time() - start_time
        
        # Log the successful response
        ai_logger.info(
            f"AI response from {engine_name}", 
            extra={
                "engine": engine_name,
                "tokens": tokens,
                "processing_time_ms": round(processing_time * 1000, 2),
                "rag_enabled": use_rag,
                "contexts_used": len(context_metadata)
            }
        )
        
        # Return result with context metadata
        return {
            "text": result,
            "context_metadata": context_metadata if context_metadata else None
        }
    except Exception as e:
        # Log the error
        processing_time = time.time() - start_time
        ai_logger.error(
            f"AI engine error: {str(e)}", 
            extra={
                "engine": engine_name,
                "error": str(e),
                "processing_time_ms": round(processing_time * 1000, 2)
            }
        )
        
        # Re-raise as HTTP exception
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=f"AI engine error: {str(e)}")

async def get_current_ai_engine() -> Dict[str, Any]:
    """
    Get information about the current AI engine configuration.
    
    Returns:
        Dict with engine information
    """
    engine = settings.AI_ENGINE
    available_engines = get_available_engines()
    
    return {
        "current_engine": engine,
        "available_engines": available_engines,
        "is_valid": engine in available_engines
    }