"""
Unified Contextual Graph Service
Consolidates all storage and query services following the pipeline architecture pattern
"""
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import asyncpg
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from .base import BaseService, ServiceRequest, ServiceResponse
from .models import (
    ContextSearchRequest, ContextSearchResponse,
    ContextSaveRequest, ContextSaveResponse,
    ControlSaveRequest, ControlSaveResponse,
    ControlSearchRequest, ControlSearchResponse,
    MeasurementSaveRequest, MeasurementSaveResponse,
    MeasurementQueryRequest, MeasurementQueryResponse,
    MultiHopQueryRequest, MultiHopQueryResponse,
    PriorityControlsRequest, PriorityControlsResponse
)

# Import storage services
from .contextual_graph_storage import ContextualGraphStorage
from app.storage.models import Control, Requirement, EvidenceType, ComplianceMeasurement
from .storage.control_service import ControlStorageService
from .storage.requirement_service import RequirementStorageService
from .storage.evidence_service import EvidenceStorageService
from .storage.measurement_service import MeasurementStorageService
from app.storage.query.query_engine import ContextualGraphQueryEngine

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


class ContextualGraphService(BaseService[ServiceRequest, ServiceResponse]):
    """
    Unified service for contextual graph operations.
    
    Provides async interface for:
    - Context management (search, save)
    - Control management (save, search)
    - Measurement management (save, query)
    - Query operations (multi-hop, priority controls)
    
    Follows the pipeline architecture pattern with async invocations.
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        vector_store_client: "VectorStoreClient",
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        llm: Optional[ChatOpenAI] = None,
        collection_prefix: str = "",
        **kwargs
    ):
        """
        Initialize unified contextual graph service
        
        Args:
            db_pool: PostgreSQL connection pool
            vector_store_client: VectorStoreClient instance (supports ChromaDB, Qdrant, etc.)
            embeddings_model: Optional embeddings model (will use vector_store_client's if None)
            llm: Optional LLM instance
            collection_prefix: Optional prefix for collection names (e.g., "comprehensive_index")
                              If provided, collections will be named "{prefix}_context_definitions", etc.
            **kwargs: Additional arguments for BaseService
        """
        super().__init__(**kwargs)
        
        self.db_pool = db_pool
        self.vector_store_client = vector_store_client
        self.collection_prefix = collection_prefix
        
        # Initialize storage services
        self.control_service = ControlStorageService(db_pool)
        self.requirement_service = RequirementStorageService(db_pool)
        self.evidence_service = EvidenceStorageService(db_pool)
        self.measurement_service = MeasurementStorageService(db_pool)
        
        # Initialize query engine with collection prefix (creates CollectionFactory)
        self.query_engine = ContextualGraphQueryEngine(
            vector_store_client=vector_store_client,
            db_pool=db_pool,
            embeddings_model=embeddings_model,
            llm=llm,
            collection_prefix=collection_prefix
        )
        
        # Initialize vector storage with collection prefix and CollectionFactory
        # This allows it to search both dedicated context collections and indexed collections
        self.vector_storage = ContextualGraphStorage(
            vector_store_client=vector_store_client,
            embeddings_model=embeddings_model,
            collection_prefix=collection_prefix,
            collection_factory=self.query_engine.collection_factory
        )
        
        logger.info(f"Initialized ContextualGraphService (collection_prefix: '{collection_prefix or 'none'}')")
    
    # ============================================================================
    # Context Operations
    # ============================================================================
    
    async def search_contexts(self, request: ContextSearchRequest) -> ContextSearchResponse:
        """Search for relevant contexts"""
        try:
            contexts = await self.vector_storage.find_relevant_contexts(
                description=request.description,
                top_k=request.top_k,
                filters=request.filters
            )
            
            results = []
            for ctx in contexts:
                results.append({
                    "context_id": ctx.context_id,
                    "document": ctx.document,
                    "metadata": {
                        "industry": ctx.industry,
                        "organization_size": ctx.organization_size,
                        "maturity_level": ctx.maturity_level,
                        "regulatory_frameworks": ctx.regulatory_frameworks
                    }
                })
            
            return ContextSearchResponse(
                success=True,
                data={"contexts": results},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error searching contexts: {str(e)}", exc_info=True)
            return ContextSearchResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def save_context(self, request: ContextSaveRequest) -> ContextSaveResponse:
        """Save a context definition"""
        try:
            from .contextual_graph_storage import ContextDefinition
            
            # Create ContextDefinition with only fields it accepts
            # Extra metadata (like document_type, process_name) will be stored in ChromaDB metadata
            context = ContextDefinition(
                context_id=request.context_id,
                document=request.document,
                context_type=request.context_type,
                industry=request.industry,
                organization_size=request.organization_size,
                maturity_level=request.maturity_level,
                regulatory_frameworks=request.regulatory_frameworks
            )
            
            # Save context with extra metadata if provided
            extra_metadata = request.metadata or {}
            context_id = await self.vector_storage.save_context_definition(context, extra_metadata=extra_metadata)
            
            return ContextSaveResponse(
                success=True,
                data={"context_id": context_id},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error saving context: {str(e)}", exc_info=True)
            return ContextSaveResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    # ============================================================================
    # Control Operations
    # ============================================================================
    
    async def save_control(self, request: ControlSaveRequest) -> ControlSaveResponse:
        """Save a control with optional vector document"""
        try:
            control = Control(
                control_id=request.control_id,
                framework=request.framework,
                control_name=request.control_name,
                control_description=request.control_description,
                category=request.category
            )
            
            control_id = await self.control_service.save_control(control)
            
            # Save vector document if provided
            if request.context_document:
                from .contextual_graph_storage import ControlContextProfile
                
                profile_id = f"profile_{control.control_id}"
                if request.context_metadata and "context_id" in request.context_metadata:
                    profile_id = f"profile_{control.control_id}_{request.context_metadata['context_id']}"
                
                profile = ControlContextProfile(
                    profile_id=profile_id,
                    document=request.context_document,
                    control_id=control.control_id,
                    context_id=request.context_metadata.get("context_id") if request.context_metadata else None,
                    framework=control.framework,
                    control_category=control.category
                )
                
                # Save to control_context_profiles (for context-specific profiles)
                await self.vector_storage.save_control_profile(profile)
                
                # Also save to fixed controls collection with metadata.type
                try:
                    control_metadata = {
                        "framework": control.framework,
                        "category": control.category,
                        "control_name": control.control_name,
                    }
                    if request.context_metadata:
                        control_metadata.update(request.context_metadata)
                    
                    await self.vector_storage.save_control_document(
                        document=request.context_document,
                        control_id=control.control_id,
                        control_type="compliance_control",  # Use metadata.type to distinguish
                        metadata=control_metadata
                    )
                except Exception as e:
                    logger.warning(f"Could not save to controls collection: {e}")
                
                await self.control_service.update_vector_doc_id(control_id, profile_id)
            
            return ControlSaveResponse(
                success=True,
                data={"control_id": control_id},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error saving control: {str(e)}", exc_info=True)
            return ControlSaveResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def search_controls(self, request: ControlSearchRequest) -> ControlSearchResponse:
        """Search for controls"""
        try:
            if request.query:
                # Use query engine for semantic search
                controls = await self.query_engine.get_priority_controls_for_context(
                    context_id=request.context_id or "",
                    query=request.query,
                    filters=request.filters,
                    top_k=request.top_k
                )
            else:
                # Get controls for context
                controls = await self._get_controls_for_context(
                    context_id=request.context_id or "",
                    framework=request.framework,
                    top_k=request.top_k
                )
            
            return ControlSearchResponse(
                success=True,
                data={"controls": controls},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error searching controls: {str(e)}", exc_info=True)
            return ControlSearchResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def _get_controls_for_context(
        self,
        context_id: str,
        framework: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Get controls for a context"""
        profiles = await self.vector_storage.get_control_profiles_for_context(
            context_id=context_id,
            framework=framework,
            top_k=top_k
        )
        
        control_ids = [p.control_id for p in profiles]
        analytics = await self.measurement_service.get_risk_analytics_batch(control_ids)
        
        results = []
        for profile in profiles:
            control = await self.control_service.get_control(profile.control_id)
            analytic = analytics.get(profile.control_id)
            
            results.append({
                "control": control.__dict__ if control else None,
                "profile": {
                    "risk_level": profile.risk_level,
                    "estimated_effort_hours": profile.estimated_effort_hours,
                    "implementation_feasibility": profile.implementation_feasibility
                },
                "analytics": analytic.__dict__ if analytic else None
            })
        
        return results
    
    # ============================================================================
    # Measurement Operations
    # ============================================================================
    
    async def save_measurement(self, request: MeasurementSaveRequest) -> MeasurementSaveResponse:
        """Save a compliance measurement"""
        try:
            measurement = ComplianceMeasurement(
                control_id=request.control_id,
                measured_value=request.measured_value,
                passed=request.passed,
                context_id=request.context_id,
                data_source=request.data_source,
                measurement_method=request.measurement_method,
                quality_score=request.quality_score
            )
            
            measurement_id = await self.measurement_service.save_measurement(measurement)
            
            return MeasurementSaveResponse(
                success=True,
                data={"measurement_id": measurement_id},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error saving measurement: {str(e)}", exc_info=True)
            return MeasurementSaveResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def query_measurements(self, request: MeasurementQueryRequest) -> MeasurementQueryResponse:
        """Query measurements with analytics"""
        try:
            measurements = await self.measurement_service.get_measurements_for_control(
                control_id=request.control_id,
                context_id=request.context_id,
                days=request.days
            )
            
            analytics = await self.measurement_service.get_risk_analytics(request.control_id)
            
            return MeasurementQueryResponse(
                success=True,
                data={
                    "measurements": [m.__dict__ for m in measurements],
                    "analytics": analytics.__dict__ if analytics else None
                },
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error querying measurements: {str(e)}", exc_info=True)
            return MeasurementQueryResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    # ============================================================================
    # Query Operations
    # ============================================================================
    
    async def multi_hop_query(self, request: MultiHopQueryRequest) -> MultiHopQueryResponse:
        """Perform multi-hop contextual search"""
        try:
            result = await self.query_engine.multi_hop_contextual_search(
                initial_query=request.query,
                context_id=request.context_id,
                max_hops=request.max_hops
            )
            
            return MultiHopQueryResponse(
                success=True,
                data=result,
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error in multi-hop query: {str(e)}", exc_info=True)
            return MultiHopQueryResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    async def get_priority_controls(self, request: PriorityControlsRequest) -> PriorityControlsResponse:
        """Get priority controls for a context"""
        try:
            controls = await self.query_engine.get_priority_controls_for_context(
                context_id=request.context_id,
                query=request.query,
                filters=request.filters,
                top_k=request.top_k
            )
            
            return PriorityControlsResponse(
                success=True,
                data={"controls": controls},
                request_id=request.request_id
            )
            
        except Exception as e:
            logger.error(f"Error getting priority controls: {str(e)}", exc_info=True)
            return PriorityControlsResponse(
                success=False,
                error=str(e),
                request_id=request.request_id
            )
    
    # ============================================================================
    # BaseService Implementation
    # ============================================================================
    
    async def _process_request_impl(self, request) -> ServiceResponse:
        """
        Route requests to appropriate handlers.
        This allows the service to be used with BaseService.process_request()
        """
        if isinstance(request, ContextSearchRequest):
            return await self.search_contexts(request)
        elif isinstance(request, ContextSaveRequest):
            return await self.save_context(request)
        elif isinstance(request, ControlSaveRequest):
            return await self.save_control(request)
        elif isinstance(request, ControlSearchRequest):
            return await self.search_controls(request)
        elif isinstance(request, MeasurementSaveRequest):
            return await self.save_measurement(request)
        elif isinstance(request, MeasurementQueryRequest):
            return await self.query_measurements(request)
        elif isinstance(request, MultiHopQueryRequest):
            return await self.multi_hop_query(request)
        elif isinstance(request, PriorityControlsRequest):
            return await self.get_priority_controls(request)
        else:
            return ServiceResponse(
                success=False,
                error=f"Unknown request type: {type(request)}",
                request_id=getattr(request, 'request_id', None)
            )

