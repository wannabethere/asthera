"""
Transformation Pipeline Module

This module provides the transformation pipeline architecture for feature
recommendation and transformation generation. It wraps the feature engineering
agent and provides a clean interface for chat-based interactions.
"""

from app.agents.pipelines.transform.transformation_pipeline import (
    TransformationPipeline,
    FeatureRecommendationRequest,
    FeatureRecommendationResponse,
    PipelineGenerationRequest,
    PipelineGenerationResponse,
    FeatureRegistryEntry,
    ConversationContext,
    FeatureStatus
)

__all__ = [
    "TransformationPipeline",
    "FeatureRecommendationRequest",
    "FeatureRecommendationResponse",
    "PipelineGenerationRequest",
    "PipelineGenerationResponse",
    "FeatureRegistryEntry",
    "ConversationContext",
    "FeatureStatus"
]

