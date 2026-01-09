"""
Services module for Universal Metadata Framework

Unified service architecture following pipeline pattern with async invocations.

Structure:
- Main services: contextual_graph_service, metadata_service, hybrid_search_service
- Storage services: app/services/storage/ (PostgreSQL operations)
- Vector storage: contextual_graph_storage (ChromaDB operations)
"""
from .metadata_service import MetadataService
from .hybrid_search_service import HybridSearchService, BM25Ranker
from .contextual_graph_storage import (
    ContextualGraphStorage,
    ContextDefinition,
    ContextualEdge,
    ControlContextProfile
)
from .base import BaseService, ServiceRequest, ServiceResponse
from .contextual_graph_service import ContextualGraphService
from .extraction_service import ExtractionService
from .reasoning_plan_service import ReasoningPlanService
from .explanation_service import ExplanationService
from .metadata_generation_action_service import MetadataGenerationActionService

# Storage services (PostgreSQL operations)
from .storage import (
    ControlStorageService,
    RequirementStorageService,
    EvidenceStorageService,
    MeasurementStorageService,
    ContextualGraphStorageService as StorageService
)

from .models import (
    ContextSearchRequest, ContextSearchResponse,
    ContextSaveRequest, ContextSaveResponse,
    ControlSaveRequest, ControlSaveResponse,
    ControlSearchRequest, ControlSearchResponse,
    MeasurementSaveRequest, MeasurementSaveResponse,
    MeasurementQueryRequest, MeasurementQueryResponse,
    MultiHopQueryRequest, MultiHopQueryResponse,
    PriorityControlsRequest, PriorityControlsResponse,
    ExtractionRequest, ExtractionResponse,
    BatchExtractionRequest, BatchExtractionResponse,
    ReasoningPlanRequest, ReasoningPlanResponse,
    ExplanationRequest, ExplanationResponse,
    MetadataGenerationActionRequest, MetadataGenerationActionResponse
)

__all__ = [
    # Base classes
    "BaseService",
    "ServiceRequest",
    "ServiceResponse",
    # Unified service (main entry point)
    "ContextualGraphService",
    # Storage services (PostgreSQL operations)
    "ControlStorageService",
    "RequirementStorageService",
    "EvidenceStorageService",
    "MeasurementStorageService",
    "StorageService",  # Legacy ContextualGraphStorageService
    # Legacy services
    "MetadataService",
    "HybridSearchService",
    "BM25Ranker",
    "ContextualGraphStorage",
    "ContextDefinition",
    "ContextualEdge",
    "ControlContextProfile",
    # Request/Response models
    "ContextSearchRequest",
    "ContextSearchResponse",
    "ContextSaveRequest",
    "ContextSaveResponse",
    "ControlSaveRequest",
    "ControlSaveResponse",
    "ControlSearchRequest",
    "ControlSearchResponse",
    "MeasurementSaveRequest",
    "MeasurementSaveResponse",
    "MeasurementQueryRequest",
    "MeasurementQueryResponse",
    "MultiHopQueryRequest",
    "MultiHopQueryResponse",
    "PriorityControlsRequest",
    "PriorityControlsResponse",
    # Extraction service
    "ExtractionService",
    "ExtractionRequest",
    "ExtractionResponse",
    "BatchExtractionRequest",
    "BatchExtractionResponse",
    # Metadata transfer learning services
    "ReasoningPlanService",
    "ExplanationService",
    "MetadataGenerationActionService",
    "ReasoningPlanRequest",
    "ReasoningPlanResponse",
    "ExplanationRequest",
    "ExplanationResponse",
    "MetadataGenerationActionRequest",
    "MetadataGenerationActionResponse",
]
