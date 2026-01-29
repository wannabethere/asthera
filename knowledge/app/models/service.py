"""
Request and Response models for Knowledge App services
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.base import ServiceRequest, ServiceResponse


# ============================================================================
# Context Request/Response Models
# ============================================================================

class ContextSearchRequest(ServiceRequest):
    """Request for context search"""
    description: str = Field(..., description="Natural language description of context")
    top_k: int = Field(5, ge=1, le=100, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")


class ContextSearchResponse(ServiceResponse):
    """Response for context search"""
    data: Optional[Dict[str, Any]] = Field(None, description="Search results")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "contexts": [
                        {
                            "context_id": "ctx_001",
                            "combined_score": 0.892,
                            "metadata": {}
                        }
                    ]
                }
            }
        }


class ContextSaveRequest(ServiceRequest):
    """Request to save a context"""
    context_id: str
    document: str
    context_type: str = "organizational_situational"
    industry: Optional[str] = None
    organization_size: Optional[str] = None
    maturity_level: Optional[str] = None
    regulatory_frameworks: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ContextSaveResponse(ServiceResponse):
    """Response for context save"""
    data: Optional[Dict[str, Any]] = Field(None, description="Saved context info")


# ============================================================================
# Control Request/Response Models
# ============================================================================

class ControlSaveRequest(ServiceRequest):
    """Request to save a control"""
    control_id: str
    framework: str
    control_name: str
    control_description: Optional[str] = None
    category: Optional[str] = None
    context_document: Optional[str] = None
    context_metadata: Optional[Dict[str, Any]] = None


class ControlSaveResponse(ServiceResponse):
    """Response for control save"""
    data: Optional[Dict[str, Any]] = Field(None, description="Saved control info")


class ControlSearchRequest(ServiceRequest):
    """Request to search controls"""
    query: Optional[str] = None
    context_id: Optional[str] = None
    framework: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(10, ge=1, le=100)


class ControlSearchResponse(ServiceResponse):
    """Response for control search"""
    data: Optional[Dict[str, Any]] = Field(None, description="Search results")


# ============================================================================
# Measurement Request/Response Models
# ============================================================================

class MeasurementSaveRequest(ServiceRequest):
    """Request to save a measurement"""
    control_id: str
    measured_value: Optional[float] = None
    passed: Optional[bool] = None
    context_id: Optional[str] = None
    data_source: Optional[str] = None
    measurement_method: Optional[str] = None
    quality_score: Optional[float] = None


class MeasurementSaveResponse(ServiceResponse):
    """Response for measurement save"""
    data: Optional[Dict[str, Any]] = Field(None, description="Saved measurement info")


class MeasurementQueryRequest(ServiceRequest):
    """Request to query measurements"""
    control_id: str
    context_id: Optional[str] = None
    days: Optional[int] = None


class MeasurementQueryResponse(ServiceResponse):
    """Response for measurement query"""
    data: Optional[Dict[str, Any]] = Field(None, description="Measurement data and analytics")


# ============================================================================
# Query Request/Response Models
# ============================================================================

class MultiHopQueryRequest(ServiceRequest):
    """Request for multi-hop contextual search"""
    query: str = Field(..., description="Initial query")
    context_id: str = Field(..., description="Context ID")
    max_hops: int = Field(3, ge=1, le=5, description="Maximum number of hops")


class MultiHopQueryResponse(ServiceResponse):
    """Response for multi-hop query"""
    data: Optional[Dict[str, Any]] = Field(None, description="Reasoning path and final answer")


class PriorityControlsRequest(ServiceRequest):
    """Request for priority controls"""
    context_id: str
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(10, ge=1, le=100)


class PriorityControlsResponse(ServiceResponse):
    """Response for priority controls"""
    data: Optional[Dict[str, Any]] = Field(None, description="Priority controls with analytics")


# ============================================================================
# Extraction Request/Response Models
# ============================================================================

class ExtractionRequest(ServiceRequest):
    """Request for extraction operations"""
    extraction_type: str = Field(..., description="Type: control, context, requirement, evidence, fields, entities")
    inputs: Dict[str, Any] = Field(..., description="Pipeline-specific inputs")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Optional configuration including rules override")


class BatchExtractionRequest(ServiceRequest):
    """Request for batch extraction operations"""
    extraction_type: str = Field(..., description="Type: control, context, requirement, evidence, fields, entities")
    inputs_list: List[Dict[str, Any]] = Field(..., description="List of pipeline-specific inputs")
    max_concurrent: int = Field(5, ge=1, le=50, description="Maximum concurrent extractions")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Optional configuration including rules override")


class ExtractionResponse(ServiceResponse):
    """Response from extraction operations"""
    extraction_type: Optional[str] = Field(None, description="Type of extraction performed")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted data")


class BatchExtractionResponse(ServiceResponse):
    """Response from batch extraction operations"""
    extraction_type: Optional[str] = Field(None, description="Type of extraction performed")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="List of extraction results")
    total: int = Field(0, description="Total number of extractions")
    successful: int = Field(0, description="Number of successful extractions")
    failed: int = Field(0, description="Number of failed extractions")


# ============================================================================
# Metadata Transfer Learning Request/Response Models
# ============================================================================

class ReasoningPlanRequest(ServiceRequest):
    """Request for creating a reasoning plan based on contexts"""
    user_action: str = Field(..., description="User action or query")
    target_domain: Optional[str] = Field(None, description="Target domain if applicable")
    context_ids: Optional[List[str]] = Field(None, description="Specific context IDs to consider")
    include_all_contexts: bool = Field(True, description="Whether to consider all available contexts")


class ReasoningPlanResponse(ServiceResponse):
    """Response with reasoning plan"""
    data: Optional[Dict[str, Any]] = Field(None, description="Reasoning plan with steps and context information")


class ExplanationRequest(ServiceRequest):
    """Request for generating explanations for user actions"""
    user_action: str = Field(..., description="User action to explain")
    action_type: Optional[str] = Field(None, description="Type of action (e.g., 'metadata_generation', 'risk_assessment')")
    context_ids: Optional[List[str]] = Field(None, description="Context IDs relevant to the action")
    include_reasoning: bool = Field(True, description="Whether to include reasoning steps")


class ExplanationResponse(ServiceResponse):
    """Response with explanation"""
    data: Optional[Dict[str, Any]] = Field(None, description="Explanation with reasoning and context details")


class MetadataGenerationActionRequest(ServiceRequest):
    """Request for generating metadata based on user action and contexts"""
    user_action: str = Field(..., description="User action description")
    target_domain: str = Field(..., description="Target domain for metadata generation")
    target_documents: List[str] = Field(..., description="Target domain documents")
    source_domains: Optional[List[str]] = Field(None, description="Source domains for transfer learning")
    target_framework: Optional[str] = Field(None, description="Target framework if applicable")
    context_ids: Optional[List[str]] = Field(None, description="Specific context IDs to use")
    use_all_contexts: bool = Field(True, description="Whether to use all available contexts")


class MetadataGenerationActionResponse(ServiceResponse):
    """Response with generated metadata for user action"""
    data: Optional[Dict[str, Any]] = Field(None, description="Generated metadata entries and reasoning")

