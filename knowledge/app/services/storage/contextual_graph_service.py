"""
Unified storage service combining database and vector store for contextual graph
"""
import logging
from typing import List, Optional, Dict, Any
from langchain_openai import OpenAIEmbeddings

from app.services.contextual_graph_storage import ContextualGraphStorage
from app.storage.models import Control, Requirement, EvidenceType, ComplianceMeasurement
from app.storage.database import DatabaseClient
from app.storage.vector_store import VectorStoreClient
from app.storage.cache import CacheClient
from app.services.storage.control_service import ControlStorageService
from app.services.storage.requirement_service import RequirementStorageService
from app.services.storage.evidence_service import EvidenceStorageService
from app.services.storage.measurement_service import MeasurementStorageService

logger = logging.getLogger(__name__)


class ContextualGraphStorageService:
    """
    Unified service that combines database (structured data) and vector store
    for the contextual graph architecture.
    """
    
    def __init__(
        self,
        db_client: DatabaseClient,
        vector_store_client: VectorStoreClient,
        cache_client: Optional[CacheClient] = None,
        embeddings_model: Optional[OpenAIEmbeddings] = None
    ):
        """Initialize unified storage service"""
        self.db_client = db_client
        self.vector_store_client = vector_store_client
        self.cache_client = cache_client
        
        # Storage services
        self.control_service = ControlStorageService(db_client)
        self.requirement_service = RequirementStorageService(db_client)
        self.evidence_service = EvidenceStorageService(db_client)
        self.measurement_service = MeasurementStorageService(db_client)
        
        # Vector store (wraps vector_store_client for backward compatibility)
        # Note: ContextualGraphStorage expects chromadb client, so we need to adapt
        # For now, we'll keep using ContextualGraphStorage but pass the underlying client
        if hasattr(vector_store_client, 'client'):
            # ChromaDB client
            from app.services.contextual_graph_storage import ContextualGraphStorage
            self.vector_storage = ContextualGraphStorage(
                chroma_client=vector_store_client.client,
                embeddings_model=embeddings_model
            )
        else:
            # For other vector stores, we'll need to refactor ContextualGraphStorage
            # For now, raise an error
            raise NotImplementedError("Only ChromaDB is currently supported for ContextualGraphStorage")
        
        logger.info("Initialized ContextualGraphStorageService")
    
    # ============================================================================
    # Control Management
    # ============================================================================
    
    async def save_control_with_vector(
        self,
        control: Control,
        context_document: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a control to PostgreSQL and optionally create vector store document.
        
        Args:
            control: Control entity
            context_document: Optional rich text document for vector store
            context_metadata: Optional metadata for vector store
            
        Returns:
            Control ID
        """
        # Save to PostgreSQL
        control_id = await self.control_service.save_control(control)
        
        # If vector document provided, save to vector store
        if context_document:
            from app.services.contextual_graph_storage import ControlContextProfile
            
            profile_id = f"profile_{control.control_id}"
            if context_metadata and "context_id" in context_metadata:
                profile_id = f"profile_{control.control_id}_{context_metadata['context_id']}"
            
            profile = ControlContextProfile(
                profile_id=profile_id,
                document=context_document,
                control_id=control.control_id,
                context_id=context_metadata.get("context_id") if context_metadata else None,
                framework=control.framework,
                control_category=control.category
            )
            
            self.vector_storage.save_control_profile(profile)
            
            # Update PostgreSQL with vector doc ID
            await self.control_service.update_vector_doc_id(control_id, profile_id)
        
        return control_id
    
    # ============================================================================
    # Requirement Management
    # ============================================================================
    
    async def save_requirement_with_vector(
        self,
        requirement: Requirement,
        context_document: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a requirement to PostgreSQL and optionally create vector store document"""
        # Save to PostgreSQL
        req_id = await self.requirement_service.save_requirement(requirement)
        
        # If vector document provided, save to vector store as contextual edge
        if context_document and context_metadata:
            from app.services.contextual_graph_storage import ContextualEdge
            
            edge_id = f"edge_{requirement.requirement_id}"
            if "context_id" in context_metadata:
                edge_id = f"edge_{requirement.requirement_id}_{context_metadata['context_id']}"
            
            edge = ContextualEdge(
                edge_id=edge_id,
                document=context_document,
                source_entity_id=requirement.control_id,
                source_entity_type="control",
                target_entity_id=requirement.requirement_id,
                target_entity_type="requirement",
                edge_type="HAS_REQUIREMENT_IN_CONTEXT",
                context_id=context_metadata.get("context_id", "")
            )
            
            self.vector_storage.save_contextual_edge(edge)
            
            # Update database with vector doc ID
            # Note: requirements table has vector_doc_id field
            await self.db_client.execute("""
                UPDATE requirements
                SET vector_doc_id = $1
                WHERE requirement_id = $2
            """, edge_id, req_id)
        
        return req_id
    
    # ============================================================================
    # Measurement Management
    # ============================================================================
    
    async def save_measurement(self, measurement: ComplianceMeasurement) -> int:
        """Save a compliance measurement"""
        return await self.measurement_service.save_measurement(measurement)
    
    async def get_measurements_with_analytics(
        self,
        control_id: str,
        context_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get measurements with risk analytics"""
        measurements = await self.measurement_service.get_measurements_for_control(
            control_id=control_id,
            context_id=context_id
        )
        
        analytics = await self.measurement_service.get_risk_analytics(control_id)
        
        return {
            "measurements": measurements,
            "analytics": analytics
        }
    
    # ============================================================================
    # Context Management
    # ============================================================================
    
    def save_context_definition(self, context):
        """Save a context definition to vector store"""
        return self.vector_storage.save_context_definition(context)
    
    def find_relevant_contexts(self, description: str, top_k: int = 5):
        """Find relevant contexts using hybrid search"""
        return self.vector_storage.find_relevant_contexts(description, top_k)
    
    # ============================================================================
    # Query Methods
    # ============================================================================
    
    async def get_controls_for_context(
        self,
        context_id: str,
        framework: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get controls for a context, combining vector store profiles with PostgreSQL data.
        
        Returns enriched results with both context-specific info and current compliance status.
        """
        # Get profiles from vector store
        profiles = self.vector_storage.get_control_profiles_for_context(
            context_id=context_id,
            framework=framework,
            top_k=top_k
        )
        
        # Get control IDs
        control_ids = [p.control_id for p in profiles]
        
        # Get risk analytics from PostgreSQL
        analytics = await self.measurement_service.get_risk_analytics_batch(control_ids)
        
        # Combine results
        enriched_results = []
        for profile in profiles:
            control = await self.control_service.get_control(profile.control_id)
            analytic = analytics.get(profile.control_id)
            
            enriched_results.append({
                "control": control,
                "profile": profile,
                "analytics": analytic,
                "context_id": context_id
            })
        
        return enriched_results

