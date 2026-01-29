"""
Services module for Universal Metadata Framework

Unified service architecture following pipeline pattern with async invocations.

Structure:
- Main services: contextual_graph_service, metadata_service, hybrid_search_service
- Storage services: app/services/storage/ (PostgreSQL operations)
- Vector storage: contextual_graph_storage (ChromaDB operations)
"""

from app.models.service import (
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

from app.services.metadata_service import MetadataService
from app.services.hybrid_search_service import HybridSearchService, BM25Ranker
from app.services.contextual_graph_storage import (
    ContextualGraphStorage,
    ContextDefinition,
    ContextualEdge,
    ControlContextProfile
)
from app.services.base import BaseService
from app.models.base import ServiceRequest, ServiceResponse
from app.services.contextual_graph_service import ContextualGraphService
from app.services.extraction_service import ExtractionService
from app.services.reasoning_plan_service import ReasoningPlanService
from app.services.explanation_service import ExplanationService
from app.services.metadata_generation_action_service import MetadataGenerationActionService

# Storage services (PostgreSQL operations)
from app.services.storage import (
    ControlStorageService,
    RequirementStorageService,
    EvidenceStorageService,
    MeasurementStorageService,
    ContextualGraphStorageService as StorageService
)


# Pipeline service
from app.services.pipeline_service import (
    PipelineService,
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    get_pipeline_service
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
    # Pipeline service
    "PipelineService",
    "PipelineExecutionRequest",
    "PipelineExecutionResponse",
    "get_pipeline_service",
]
