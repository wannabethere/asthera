"""
Generic/Assistant Models Module
Centralized location for all generic and assistant-level models.

Organization:
- base.py: Base request/response models
- assistant.py: Assistant and streaming models (from streams/models, workforce_config)
- storage.py: Storage/database models (from storage/models)
- service.py: Service request/response models (from services/models)
- mdl.py: MDL edge types and definitions (from utils/mdl_edge_types)
- router.py: Router request/response models (from routers/*)
"""

from app.models.base import (
    ServiceRequest,
    ServiceResponse,
)

from app.models.assistant import (
    # Streaming models
    GraphInvokeRequest,
    AssistantCreateRequest,
    GraphRegisterRequest,
    AssistantInfo,
    GraphInfo,
    AssistantListResponse,
    GraphListResponse,
    AskRequest,
    AskResponse,
    MCPRequest,
    MCPResponse,
    MCPError,
    
    # Workforce models
    AssistantType,
    DataSourceConfig,
    AssistantConfig,
)

from app.models.storage import (
    Control,
    Requirement,
    EvidenceType,
    ControlRequirementMapping,
    ComplianceMeasurement,
    ControlRiskAnalytics,
)

from app.models.service import (
    # Context models
    ContextSearchRequest,
    ContextSearchResponse,
    ContextSaveRequest,
    ContextSaveResponse,
    
    # Control models
    ControlSaveRequest,
    ControlSaveResponse,
    ControlSearchRequest,
    ControlSearchResponse,
    
    # Measurement models
    MeasurementSaveRequest,
    MeasurementSaveResponse,
    MeasurementQueryRequest,
    MeasurementQueryResponse,
    
    # Query models
    MultiHopQueryRequest,
    MultiHopQueryResponse,
    PriorityControlsRequest,
    PriorityControlsResponse,
    
    # Extraction models
    ExtractionRequest,
    BatchExtractionRequest,
    ExtractionResponse,
    BatchExtractionResponse,
    
    # Metadata/Transfer Learning models
    ReasoningPlanRequest,
    ReasoningPlanResponse,
    ExplanationRequest,
    ExplanationResponse,
    MetadataGenerationActionRequest,
    MetadataGenerationActionResponse,
)

from app.models.mdl import (
    MDLEntityType,
    MDLEdgeType,
    MDLEdgeTypeDefinition,
)

from app.models.router import (
    ContextBreakdownRequest,
    SearchQuestion,
    ContextBreakdownResponse,
    ContextBreakdownSummary,
)

__all__ = [
    # Base models
    "ServiceRequest",
    "ServiceResponse",
    
    # Assistant/Streaming models
    "GraphInvokeRequest",
    "AssistantCreateRequest",
    "GraphRegisterRequest",
    "AssistantInfo",
    "GraphInfo",
    "AssistantListResponse",
    "GraphListResponse",
    "AskRequest",
    "AskResponse",
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    
    # Workforce models
    "AssistantType",
    "DataSourceConfig",
    "AssistantConfig",
    
    # Storage models
    "Control",
    "Requirement",
    "EvidenceType",
    "ControlRequirementMapping",
    "ComplianceMeasurement",
    "ControlRiskAnalytics",
    
    # Service models
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
    "ExtractionRequest",
    "BatchExtractionRequest",
    "ExtractionResponse",
    "BatchExtractionResponse",
    "ReasoningPlanRequest",
    "ReasoningPlanResponse",
    "ExplanationRequest",
    "ExplanationResponse",
    "MetadataGenerationActionRequest",
    "MetadataGenerationActionResponse",
    
    # MDL models
    "MDLEntityType",
    "MDLEdgeType",
    "MDLEdgeTypeDefinition",
    
    # Router models
    "ContextBreakdownRequest",
    "SearchQuestion",
    "ContextBreakdownResponse",
    "ContextBreakdownSummary",
]
