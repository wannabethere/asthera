"""
Contextual Graph Storage Layer

Manages storage and retrieval of contextual graph documents in vector stores:
1. Context Definitions - Organizational/situational contexts
2. Contextual Edges - Context-aware relationships between entities
3. Control-Context Profiles - Control implementation profiles for specific contexts

Based on the architecture described in docs/hybrid_search.md
"""
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from langchain_openai import OpenAIEmbeddings

from app.services.hybrid_search_service import HybridSearchService

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


@dataclass
class ContextDefinition:
    """Represents an organizational/situational context definition"""
    context_id: str
    document: str  # Rich text description of the context
    context_type: str = "organizational_situational"
    industry: Optional[str] = None
    organization_size: Optional[str] = None
    employee_count_range: Optional[str] = None
    maturity_level: Optional[str] = None
    regulatory_frameworks: List[str] = field(default_factory=list)
    data_types: List[str] = field(default_factory=list)
    systems: List[str] = field(default_factory=list)
    automation_capability: Optional[str] = None
    current_situation: Optional[str] = None
    audit_timeline_days: Optional[int] = None
    active_status: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata format"""
        metadata = {
            "context_id": self.context_id,
            "context_type": self.context_type,
            "active_status": self.active_status,
        }
        
        # Add optional fields
        if self.industry:
            metadata["industry"] = self.industry
        if self.organization_size:
            metadata["organization_size"] = self.organization_size
        if self.employee_count_range:
            metadata["employee_count_range"] = self.employee_count_range
        if self.maturity_level:
            metadata["maturity_level"] = self.maturity_level
        if self.regulatory_frameworks:
            metadata["regulatory_frameworks"] = json.dumps(self.regulatory_frameworks)
        if self.data_types:
            metadata["data_types"] = json.dumps(self.data_types)
        if self.systems:
            metadata["systems"] = json.dumps(self.systems)
        if self.automation_capability:
            metadata["automation_capability"] = self.automation_capability
        if self.current_situation:
            metadata["current_situation"] = self.current_situation
        if self.audit_timeline_days is not None:
            metadata["audit_timeline_days"] = self.audit_timeline_days
        if self.created_at:
            metadata["created_at"] = self.created_at
        if self.updated_at:
            metadata["updated_at"] = self.updated_at
        
        return metadata
    
    @classmethod
    def from_metadata(cls, document: str, metadata: Dict[str, Any]) -> "ContextDefinition":
        """Create from ChromaDB metadata"""
        return cls(
            context_id=metadata.get("context_id", ""),
            document=document,
            context_type=metadata.get("context_type", "organizational_situational"),
            industry=metadata.get("industry"),
            organization_size=metadata.get("organization_size"),
            employee_count_range=metadata.get("employee_count_range"),
            maturity_level=metadata.get("maturity_level"),
            regulatory_frameworks=json.loads(metadata.get("regulatory_frameworks", "[]")),
            data_types=json.loads(metadata.get("data_types", "[]")),
            systems=json.loads(metadata.get("systems", "[]")),
            automation_capability=metadata.get("automation_capability"),
            current_situation=metadata.get("current_situation"),
            audit_timeline_days=metadata.get("audit_timeline_days"),
            active_status=metadata.get("active_status", True),
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at")
        )


@dataclass
class ContextualEdge:
    """Represents a context-aware relationship between entities"""
    edge_id: str
    document: str  # Rich text description of the edge relationship
    source_entity_id: str
    source_entity_type: str  # e.g., "control", "requirement", "evidence"
    target_entity_id: str
    target_entity_type: str
    edge_type: str  # e.g., "HAS_REQUIREMENT_IN_CONTEXT"
    context_id: str
    
    # Scores and priorities
    relevance_score: float = 0.0
    priority_in_context: Optional[int] = None
    risk_score_in_context: Optional[float] = None
    likelihood_in_context: Optional[int] = None
    impact_in_context: Optional[int] = None
    
    # Implementation details
    implementation_complexity: Optional[str] = None
    estimated_effort_hours: Optional[int] = None
    estimated_cost: Optional[float] = None
    
    # Conditional factors
    prerequisites: List[str] = field(default_factory=list)
    automation_possible: bool = False
    evidence_available: bool = False
    data_quality: Optional[str] = None
    
    # Temporal
    created_at: Optional[str] = None
    valid_until: Optional[str] = None
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata format"""
        metadata = {
            "edge_id": self.edge_id,
            "source_entity_id": self.source_entity_id,
            "source_entity_type": self.source_entity_type,
            "target_entity_id": self.target_entity_id,
            "target_entity_type": self.target_entity_type,
            "edge_type": self.edge_type,
            "context_id": self.context_id,
            "relevance_score": self.relevance_score,
            "automation_possible": self.automation_possible,
            "evidence_available": self.evidence_available,
        }
        
        # Add optional fields
        if self.priority_in_context is not None:
            metadata["priority_in_context"] = self.priority_in_context
        if self.risk_score_in_context is not None:
            metadata["risk_score_in_context"] = self.risk_score_in_context
        if self.likelihood_in_context is not None:
            metadata["likelihood_in_context"] = self.likelihood_in_context
        if self.impact_in_context is not None:
            metadata["impact_in_context"] = self.impact_in_context
        if self.implementation_complexity:
            metadata["implementation_complexity"] = self.implementation_complexity
        if self.estimated_effort_hours is not None:
            metadata["estimated_effort_hours"] = self.estimated_effort_hours
        if self.estimated_cost is not None:
            metadata["estimated_cost"] = self.estimated_cost
        if self.prerequisites:
            metadata["prerequisites"] = json.dumps(self.prerequisites)
        if self.data_quality:
            metadata["data_quality"] = self.data_quality
        if self.created_at:
            metadata["created_at"] = self.created_at
        if self.valid_until:
            metadata["valid_until"] = self.valid_until
        
        return metadata
    
    @classmethod
    def from_metadata(cls, document: str, metadata: Dict[str, Any]) -> "ContextualEdge":
        """Create from ChromaDB metadata"""
        return cls(
            edge_id=metadata.get("edge_id", ""),
            document=document,
            source_entity_id=metadata.get("source_entity_id", ""),
            source_entity_type=metadata.get("source_entity_type", ""),
            target_entity_id=metadata.get("target_entity_id", ""),
            target_entity_type=metadata.get("target_entity_type", ""),
            edge_type=metadata.get("edge_type", ""),
            context_id=metadata.get("context_id", ""),
            relevance_score=metadata.get("relevance_score", 0.0),
            priority_in_context=metadata.get("priority_in_context"),
            risk_score_in_context=metadata.get("risk_score_in_context"),
            likelihood_in_context=metadata.get("likelihood_in_context"),
            impact_in_context=metadata.get("impact_in_context"),
            implementation_complexity=metadata.get("implementation_complexity"),
            estimated_effort_hours=metadata.get("estimated_effort_hours"),
            estimated_cost=metadata.get("estimated_cost"),
            prerequisites=json.loads(metadata.get("prerequisites", "[]")),
            automation_possible=metadata.get("automation_possible", False),
            evidence_available=metadata.get("evidence_available", False),
            data_quality=metadata.get("data_quality"),
            created_at=metadata.get("created_at"),
            valid_until=metadata.get("valid_until")
        )


@dataclass
class ControlContextProfile:
    """Represents a control implementation profile for a specific context"""
    profile_id: str
    document: str  # Rich text description of the control in context
    control_id: str
    context_id: str
    framework: Optional[str] = None
    control_category: Optional[str] = None
    
    # Risk scores
    inherent_risk_score: Optional[float] = None
    current_control_effectiveness: Optional[float] = None
    residual_risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    
    # Implementation
    implementation_complexity: Optional[str] = None
    estimated_effort_hours: Optional[int] = None
    estimated_cost: Optional[float] = None
    success_probability: Optional[float] = None
    implementation_feasibility: Optional[str] = None
    timeline_weeks: Optional[int] = None
    
    # Automation
    automation_possible: bool = False
    automation_coverage: Optional[float] = None
    manual_effort_remaining: Optional[float] = None
    
    # Evidence
    evidence_available: bool = False
    evidence_quality: Optional[str] = None
    evidence_gaps: List[str] = field(default_factory=list)
    
    # Current state
    systems_in_scope: List[str] = field(default_factory=list)
    systems_count: Optional[int] = None
    users_in_scope: Optional[int] = None
    integration_maturity: Optional[float] = None
    
    # Metrics
    metrics_defined: bool = False
    metrics_count: Optional[int] = None
    metrics_automated: Optional[float] = None
    
    # Temporal
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata format"""
        metadata = {
            "profile_id": self.profile_id,
            "control_id": self.control_id,
            "context_id": self.context_id,
            "automation_possible": self.automation_possible,
            "evidence_available": self.evidence_available,
            "metrics_defined": self.metrics_defined,
        }
        
        # Add optional fields
        if self.framework:
            metadata["framework"] = self.framework
        if self.control_category:
            metadata["control_category"] = self.control_category
        if self.inherent_risk_score is not None:
            metadata["inherent_risk_score"] = self.inherent_risk_score
        if self.current_control_effectiveness is not None:
            metadata["current_control_effectiveness"] = self.current_control_effectiveness
        if self.residual_risk_score is not None:
            metadata["residual_risk_score"] = self.residual_risk_score
        if self.risk_level:
            metadata["risk_level"] = self.risk_level
        if self.implementation_complexity:
            metadata["implementation_complexity"] = self.implementation_complexity
        if self.estimated_effort_hours is not None:
            metadata["estimated_effort_hours"] = self.estimated_effort_hours
        if self.estimated_cost is not None:
            metadata["estimated_cost"] = self.estimated_cost
        if self.success_probability is not None:
            metadata["success_probability"] = self.success_probability
        if self.implementation_feasibility:
            metadata["implementation_feasibility"] = self.implementation_feasibility
        if self.timeline_weeks is not None:
            metadata["timeline_weeks"] = self.timeline_weeks
        if self.automation_coverage is not None:
            metadata["automation_coverage"] = self.automation_coverage
        if self.manual_effort_remaining is not None:
            metadata["manual_effort_remaining"] = self.manual_effort_remaining
        if self.evidence_quality:
            metadata["evidence_quality"] = self.evidence_quality
        if self.evidence_gaps:
            metadata["evidence_gaps"] = json.dumps(self.evidence_gaps)
        if self.systems_in_scope:
            metadata["systems_in_scope"] = json.dumps(self.systems_in_scope)
        if self.systems_count is not None:
            metadata["systems_count"] = self.systems_count
        if self.users_in_scope is not None:
            metadata["users_in_scope"] = self.users_in_scope
        if self.integration_maturity is not None:
            metadata["integration_maturity"] = self.integration_maturity
        if self.metrics_count is not None:
            metadata["metrics_count"] = self.metrics_count
        if self.metrics_automated is not None:
            metadata["metrics_automated"] = self.metrics_automated
        if self.created_at:
            metadata["created_at"] = self.created_at
        if self.updated_at:
            metadata["updated_at"] = self.updated_at
        
        return metadata
    
    @classmethod
    def from_metadata(cls, document: str, metadata: Dict[str, Any]) -> "ControlContextProfile":
        """Create from ChromaDB metadata"""
        return cls(
            profile_id=metadata.get("profile_id", ""),
            document=document,
            control_id=metadata.get("control_id", ""),
            context_id=metadata.get("context_id", ""),
            framework=metadata.get("framework"),
            control_category=metadata.get("control_category"),
            inherent_risk_score=metadata.get("inherent_risk_score"),
            current_control_effectiveness=metadata.get("current_control_effectiveness"),
            residual_risk_score=metadata.get("residual_risk_score"),
            risk_level=metadata.get("risk_level"),
            implementation_complexity=metadata.get("implementation_complexity"),
            estimated_effort_hours=metadata.get("estimated_effort_hours"),
            estimated_cost=metadata.get("estimated_cost"),
            success_probability=metadata.get("success_probability"),
            implementation_feasibility=metadata.get("implementation_feasibility"),
            timeline_weeks=metadata.get("timeline_weeks"),
            automation_possible=metadata.get("automation_possible", False),
            automation_coverage=metadata.get("automation_coverage"),
            manual_effort_remaining=metadata.get("manual_effort_remaining"),
            evidence_available=metadata.get("evidence_available", False),
            evidence_quality=metadata.get("evidence_quality"),
            evidence_gaps=json.loads(metadata.get("evidence_gaps", "[]")),
            systems_in_scope=json.loads(metadata.get("systems_in_scope", "[]")),
            systems_count=metadata.get("systems_count"),
            users_in_scope=metadata.get("users_in_scope"),
            integration_maturity=metadata.get("integration_maturity"),
            metrics_defined=metadata.get("metrics_defined", False),
            metrics_count=metadata.get("metrics_count"),
            metrics_automated=metadata.get("metrics_automated"),
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at")
        )


class ContextualGraphStorage:
    """
    Storage layer for contextual graph documents.
    
    Manages three vector store collections:
    1. context_definitions - Organizational/situational contexts
    2. contextual_edges - Context-aware relationships
    3. control_context_profiles - Control implementation profiles
    """
    
    def __init__(
        self,
        vector_store_client: "VectorStoreClient",
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        collection_prefix: str = "",
        collection_factory: Optional[Any] = None
    ):
        """
        Initialize contextual graph storage.
        
        Args:
            vector_store_client: VectorStoreClient instance (supports ChromaDB, Qdrant, etc.)
            embeddings_model: Optional embeddings model (will use vector_store_client's if None)
            collection_prefix: Optional prefix for collection names (e.g., "comprehensive_index")
                              If provided, collections will be named "{prefix}_context_definitions", etc.
            collection_factory: Optional CollectionFactory instance for searching indexed collections
        """
        self.vector_store_client = vector_store_client
        self.embeddings_model = embeddings_model  # Will be set from vector_store_client if None
        self.collection_prefix = collection_prefix
        self.collection_factory = collection_factory
        
        # Build collection names with prefix if provided
        from app.storage.documents import sanitize_collection_name
        
        def _get_collection_name(base_name: str) -> str:
            if collection_prefix:
                full_name = f"{collection_prefix}_{base_name}"
            else:
                full_name = base_name
            return sanitize_collection_name(full_name)
        
        # Initialize hybrid search services for each collection
        self.contexts_service = HybridSearchService(
            vector_store_client=vector_store_client,
            collection_name=_get_collection_name("context_definitions"),
            embeddings_model=embeddings_model
        )
        
        self.edges_service = HybridSearchService(
            vector_store_client=vector_store_client,
            collection_name=_get_collection_name("contextual_edges"),
            embeddings_model=embeddings_model
        )
        
        self.profiles_service = HybridSearchService(
            vector_store_client=vector_store_client,
            collection_name=_get_collection_name("control_context_profiles"),
            embeddings_model=embeddings_model
        )
        
        # Initialize general collections for entities, evidence, fields, controls
        # These use fixed collections with metadata.type for filtering
        # Use collection_factory if available, otherwise create directly
        if collection_factory:
            # Use collections from factory to ensure consistency
            self.entities_service = collection_factory.get_collection_by_store_name("entities")
            self.evidence_service = collection_factory.get_collection_by_store_name("evidence")
            self.fields_service = collection_factory.get_collection_by_store_name("fields")
            self.controls_service = collection_factory.get_collection_by_store_name("controls")
            
            # Log if any services are None (collection not found in factory)
            if not self.entities_service:
                logger.warning("Entities collection not found in collection_factory")
            if not self.evidence_service:
                logger.warning("Evidence collection not found in collection_factory")
            if not self.fields_service:
                logger.warning("Fields collection not found in collection_factory")
            if not self.controls_service:
                logger.warning("Controls collection not found in collection_factory")
        else:
            # Create directly if no factory (for backward compatibility)
            self.entities_service = HybridSearchService(
                vector_store_client=vector_store_client,
                collection_name=_get_collection_name("entities"),
                embeddings_model=embeddings_model
            )
            self.evidence_service = HybridSearchService(
                vector_store_client=vector_store_client,
                collection_name=_get_collection_name("evidence"),
                embeddings_model=embeddings_model
            )
            self.fields_service = HybridSearchService(
                vector_store_client=vector_store_client,
                collection_name=_get_collection_name("fields"),
                embeddings_model=embeddings_model
            )
            self.controls_service = HybridSearchService(
                vector_store_client=vector_store_client,
                collection_name=_get_collection_name("controls"),
                embeddings_model=embeddings_model
            )
        
        logger.info(f"Initialized ContextualGraphStorage with collections (prefix: '{collection_prefix or 'none'}')")
    
    # ============================================================================
    # General Document Storage Methods (entities, evidence, fields, controls)
    # ============================================================================
    
    async def save_entity_document(
        self,
        document: str,
        entity_id: str,
        entity_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save an entity document to the entities collection.
        
        Args:
            document: Document content
            entity_id: Entity identifier
            entity_type: Type of entity (e.g., "policy_entity", "control", etc.)
            metadata: Optional metadata (will include type=entity_type)
            
        Returns:
            Document ID
        """
        if not self.entities_service:
            raise ValueError("Entities service not initialized. Provide collection_factory to enable.")
        
        doc_metadata = metadata.copy() if metadata else {}
        doc_metadata["type"] = entity_type
        doc_metadata["entity_id"] = entity_id
        doc_metadata = self._sanitize_metadata_for_vector_store(doc_metadata)
        
        ids = await self.entities_service.add_documents(
            documents=[document],
            metadatas=[doc_metadata],
            ids=[entity_id]
        )
        
        logger.info(f"Saved entity document: {entity_id} (type: {entity_type})")
        return ids[0] if ids else entity_id
    
    async def save_evidence_document(
        self,
        document: str,
        evidence_id: str,
        evidence_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save an evidence document to the evidence collection.
        
        Args:
            document: Document content
            evidence_id: Evidence identifier
            evidence_type: Type of evidence (e.g., "policy_evidence", "requirement_evidence", etc.)
            metadata: Optional metadata (will include type=evidence_type)
            
        Returns:
            Document ID
        """
        if not self.evidence_service:
            raise ValueError("Evidence service not initialized. Provide collection_factory to enable.")
        
        doc_metadata = metadata.copy() if metadata else {}
        doc_metadata["type"] = evidence_type
        doc_metadata["evidence_id"] = evidence_id
        doc_metadata = self._sanitize_metadata_for_vector_store(doc_metadata)
        
        ids = await self.evidence_service.add_documents(
            documents=[document],
            metadatas=[doc_metadata],
            ids=[evidence_id]
        )
        
        logger.info(f"Saved evidence document: {evidence_id} (type: {evidence_type})")
        return ids[0] if ids else evidence_id
    
    async def save_field_document(
        self,
        document: str,
        field_id: str,
        field_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a field document to the fields collection.
        
        Args:
            document: Document content
            field_id: Field identifier
            field_type: Type of field (e.g., "policy_field", "requirement_field", etc.)
            metadata: Optional metadata (will include type=field_type)
            
        Returns:
            Document ID
        """
        if not self.fields_service:
            raise ValueError("Fields service not initialized. Provide collection_factory to enable.")
        
        doc_metadata = metadata.copy() if metadata else {}
        doc_metadata["type"] = field_type
        doc_metadata["field_id"] = field_id
        doc_metadata = self._sanitize_metadata_for_vector_store(doc_metadata)
        
        ids = await self.fields_service.add_documents(
            documents=[document],
            metadatas=[doc_metadata],
            ids=[field_id]
        )
        
        logger.info(f"Saved field document: {field_id} (type: {field_type})")
        return ids[0] if ids else field_id
    
    async def save_control_document(
        self,
        document: str,
        control_id: str,
        control_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a control document to the controls collection.
        
        Args:
            document: Document content
            control_id: Control identifier
            control_type: Type of control (e.g., "compliance_control", "risk_control", etc.)
            metadata: Optional metadata (will include type=control_type)
            
        Returns:
            Document ID
        """
        if not self.controls_service:
            raise ValueError("Controls service not initialized. Provide collection_factory to enable.")
        
        doc_metadata = metadata.copy() if metadata else {}
        doc_metadata["type"] = control_type
        doc_metadata["control_id"] = control_id
        doc_metadata = self._sanitize_metadata_for_vector_store(doc_metadata)
        
        ids = await self.controls_service.add_documents(
            documents=[document],
            metadatas=[doc_metadata],
            ids=[control_id]
        )
        
        logger.info(f"Saved control document: {control_id} (type: {control_type})")
        return ids[0] if ids else control_id
    
    # ============================================================================
    # Context Definitions Methods
    # ============================================================================
    
    def _sanitize_metadata_for_vector_store(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to ensure all values are vector store-compatible.
        Vector stores only accept str, int, float, or bool - not lists or dicts.
        
        Args:
            metadata: Metadata dictionary that may contain lists or dicts
            
        Returns:
            Sanitized metadata with all lists/dicts converted to JSON strings
        """
        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                # Skip None values or convert to empty string
                continue
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                # Convert lists to JSON strings
                sanitized[key] = json.dumps(value)
            elif isinstance(value, dict):
                # Convert dicts to JSON strings
                sanitized[key] = json.dumps(value)
            else:
                # Convert any other type to string
                sanitized[key] = str(value)
        return sanitized
    
    async def save_context_definition(self, context: ContextDefinition, extra_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save a context definition.
        
        Args:
            context: ContextDefinition instance
            extra_metadata: Optional additional metadata to include
            
        Returns:
            Document ID that was saved
        """
        if not context.created_at:
            context.created_at = datetime.utcnow().isoformat() + "Z"
        context.updated_at = datetime.utcnow().isoformat() + "Z"
        
        # Get base metadata from context
        metadata = context.to_metadata()
        # Merge with extra metadata if provided
        if extra_metadata:
            metadata.update(extra_metadata)
        
        # Sanitize metadata to ensure vector store compatibility (convert lists/dicts to JSON strings)
        metadata = self._sanitize_metadata_for_vector_store(metadata)
        
        ids = await self.contexts_service.add_documents(
            documents=[context.document],
            metadatas=[metadata],
            ids=[context.context_id]
        )
        
        logger.info(f"Saved context definition: {context.context_id}")
        return ids[0] if ids else context.context_id
    
    async def save_context_definition_with_metadata(self, context: ContextDefinition, metadata: Dict[str, Any]) -> str:
        """
        Save a context definition with custom metadata.
        
        Args:
            context: ContextDefinition instance
            metadata: Complete metadata dictionary to use
            
        Returns:
            Document ID that was saved
        """
        return await self.save_context_definition(context, extra_metadata=metadata)
    
    async def save_context_definitions(self, contexts: List[ContextDefinition]) -> List[str]:
        """Save multiple context definitions"""
        ids = []
        for context in contexts:
            try:
                doc_id = await self.save_context_definition(context)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Error saving context {context.context_id}: {str(e)}")
        return ids
    
    async def get_context_definition(self, context_id: str) -> Optional[ContextDefinition]:
        """Get a context definition by ID"""
        # Use hybrid_search with metadata filter for ID lookup
        results = await self.contexts_service.hybrid_search(
            query="context",  # Minimal query for metadata-only filtering
            top_k=1,
            where={"context_id": context_id}
        )
        
        if results:
            result = results[0]
            # hybrid_search returns dict with "content" or "document" key
            document = result.get("content") or result.get("document") or ""
            metadata = result.get("metadata", {})
            return ContextDefinition.from_metadata(
                document=document,
                metadata=metadata
            )
        return None
    
    async def find_relevant_contexts(
        self,
        description: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ContextDefinition]:
        """
        Find contexts relevant to a description using hybrid search.
        
        Searches both:
        1. context_definitions collection (dedicated contextual graph contexts)
        2. Indexed collections via CollectionFactory (policy_context, domain_knowledge, etc.)
        
        Args:
            description: Description of the context/situation
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of relevant ContextDefinition objects
        """
        all_results = []
        
        # Search dedicated context_definitions collection
        results = await self.contexts_service.find_relevant_contexts(
            context_description=description,
            top_k=top_k,
            where=filters
        )
        all_results.extend(results)
        
        # Also search indexed collections if CollectionFactory is available
        if self.collection_factory:
            try:
                # Search domain collections (policy_context, domain_knowledge)
                domain_results = await self.collection_factory.search_domains(
                    query=description,
                    top_k=top_k,
                    filters=filters
                )
                
                # Convert indexed collection results to context-like format
                for result in domain_results:
                    # Add collection name to result for identification
                    result["source_collection"] = result.get("collection_name", "unknown")
                    all_results.append(result)
                
                logger.info(f"Found {len(domain_results)} contexts from indexed collections")
            except Exception as e:
                logger.warning(f"Error searching indexed collections for contexts: {str(e)}")
        
        # Deduplicate by context_id if present, or by content similarity
        seen_ids = set()
        unique_results = []
        for result in all_results:
            context_id = result.get("metadata", {}).get("context_id") or result.get("id")
            if context_id and context_id not in seen_ids:
                seen_ids.add(context_id)
                unique_results.append(result)
            elif not context_id:
                # If no context_id, include it (might be from indexed collections)
                unique_results.append(result)
        
        # Sort by combined_score if available, limit to top_k
        if unique_results:
            unique_results.sort(
                key=lambda x: x.get("combined_score", x.get("distance", float("inf"))),
                reverse=True
            )
            unique_results = unique_results[:top_k]
        
        contexts = []
        for result in unique_results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or result.get("document") or ""
                metadata = result.get("metadata", {})
                
                # If from indexed collection, try to create context from metadata
                if result.get("source_collection"):
                    # Create a context from indexed collection result
                    # Use document as context_id if no context_id in metadata
                    context_id = metadata.get("context_id") or result.get("id") or f"indexed_{result.get('source_collection')}"
                    context = ContextDefinition(
                        context_id=context_id,
                        document=document,
                        context_type=metadata.get("context_type", "organizational_situational"),
                        industry=metadata.get("industry"),
                        organization_size=metadata.get("organization_size"),
                        maturity_level=metadata.get("maturity_level"),
                        regulatory_frameworks=json.loads(metadata.get("regulatory_frameworks", "[]")) if isinstance(metadata.get("regulatory_frameworks"), str) else metadata.get("regulatory_frameworks", []),
                        data_types=json.loads(metadata.get("data_types", "[]")) if isinstance(metadata.get("data_types"), str) else metadata.get("data_types", []),
                        systems=json.loads(metadata.get("systems", "[]")) if isinstance(metadata.get("systems"), str) else metadata.get("systems", [])
                    )
                else:
                    # Use standard from_metadata for dedicated context_definitions
                    context = ContextDefinition.from_metadata(
                        document=document,
                        metadata=metadata
                    )
                contexts.append(context)
            except Exception as e:
                logger.warning(f"Error parsing context from result: {str(e)}")
        
        logger.info(f"Found {len(contexts)} unique contexts (from {len(all_results)} total results)")
        return contexts
    
    # ============================================================================
    # Contextual Edges Methods
    # ============================================================================
    
    async def save_contextual_edge(self, edge: ContextualEdge) -> str:
        """Save a contextual edge"""
        if not edge.created_at:
            edge.created_at = datetime.utcnow().isoformat() + "Z"
        
        # Sanitize metadata to ensure vector store compatibility
        metadata = self._sanitize_metadata_for_vector_store(edge.to_metadata())
        
        ids = await self.edges_service.add_documents(
            documents=[edge.document],
            metadatas=[metadata],
            ids=[edge.edge_id]
        )
        
        logger.info(f"Saved contextual edge: {edge.edge_id}")
        return ids[0] if ids else edge.edge_id
    
    async def save_contextual_edges(self, edges: List[ContextualEdge], batch_size: int = 500) -> List[str]:
        """
        Save multiple contextual edges in batches for better performance.
        
        Args:
            edges: List of ContextualEdge objects to save
            batch_size: Number of edges to process in each batch (default: 500)
            
        Returns:
            List of saved edge IDs
        """
        if not edges:
            return []
        
        ids = []
        total_edges = len(edges)
        logger.info(f"Saving {total_edges} contextual edges in batches of {batch_size}")
        
        # Process edges in batches
        for i in range(0, total_edges, batch_size):
            batch = edges[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_edges + batch_size - 1) // batch_size
            
            try:
                # Prepare batch data
                documents = []
                metadatas = []
                edge_ids = []
                
                for edge in batch:
                    if not edge.created_at:
                        edge.created_at = datetime.utcnow().isoformat() + "Z"
                    
                    # Sanitize metadata
                    metadata = self._sanitize_metadata_for_vector_store(edge.to_metadata())
                    
                    documents.append(edge.document)
                    metadatas.append(metadata)
                    edge_ids.append(edge.edge_id)
                
                # Batch insert to vector store
                batch_ids = await self.edges_service.add_documents(
                    documents=documents,
                    metadatas=metadatas,
                    ids=edge_ids
                )
                
                ids.extend(batch_ids)
                logger.info(f"  ✓ Saved batch {batch_num}/{total_batches} ({len(batch)} edges)")
                
            except Exception as e:
                logger.error(f"Error saving batch {batch_num}/{total_batches}: {str(e)}")
                # Fall back to individual saves for this batch
                logger.info(f"  Falling back to individual saves for batch {batch_num}")
                for edge in batch:
                    try:
                        doc_id = await self.save_contextual_edge(edge)
                        ids.append(doc_id)
                    except Exception as edge_error:
                        logger.error(f"Error saving edge {edge.edge_id}: {str(edge_error)}")
        
        logger.info(f"Successfully saved {len(ids)}/{total_edges} contextual edges")
        return ids
    
    async def get_edges_for_context(
        self,
        context_id: str,
        source_entity_id: Optional[str] = None,
        edge_type: Optional[str] = None,
        top_k: int = 10
    ) -> List[ContextualEdge]:
        """
        Get contextual edges for a specific context.
        
        Args:
            context_id: Context ID to filter by
            source_entity_id: Optional source entity ID filter
            edge_type: Optional edge type filter
            top_k: Number of results to return
            
        Returns:
            List of ContextualEdge objects
        """
        where_clause = {"context_id": context_id}
        if source_entity_id:
            where_clause["source_entity_id"] = source_entity_id
        if edge_type:
            where_clause["edge_type"] = edge_type
        
        # Use hybrid_search for metadata-only filtering
        results = await self.edges_service.hybrid_search(
            query="edge",  # Minimal query for metadata-only filtering
            top_k=top_k,
            where=where_clause
        )
        
        edges = []
        for result in results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or ""
                metadata = result.get("metadata", {})
                edge = ContextualEdge.from_metadata(
                    document=document,
                    metadata=metadata
                )
                edges.append(edge)
            except Exception as e:
                logger.warning(f"Error parsing edge from result: {str(e)}")
        
        return edges
    
    async def search_edges(
        self,
        query: str,
        context_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """Search contextual edges using hybrid search"""
        where_clause = filters or {}
        if context_id:
            where_clause["context_id"] = context_id
        
        results = await self.edges_service.hybrid_search(
            query=query,
            top_k=top_k,
            where=where_clause if where_clause else None
        )
        
        edges = []
        for result in results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or ""
                metadata = result.get("metadata", {})
                edge = ContextualEdge.from_metadata(
                    document=document,
                    metadata=metadata
                )
                edges.append(edge)
            except Exception as e:
                logger.warning(f"Error parsing edge from result: {str(e)}")
        
        return edges
    
    # ============================================================================
    # Control-Context Profiles Methods
    # ============================================================================
    
    async def save_control_profile(self, profile: ControlContextProfile) -> str:
        """Save a control-context profile"""
        if not profile.created_at:
            profile.created_at = datetime.utcnow().isoformat() + "Z"
        profile.updated_at = datetime.utcnow().isoformat() + "Z"
        
        # Sanitize metadata to ensure vector store compatibility
        metadata = self._sanitize_metadata_for_vector_store(profile.to_metadata())
        
        ids = await self.profiles_service.add_documents(
            documents=[profile.document],
            metadatas=[metadata],
            ids=[profile.profile_id]
        )
        
        logger.info(f"Saved control profile: {profile.profile_id}")
        return ids[0] if ids else profile.profile_id
    
    async def save_control_profiles(self, profiles: List[ControlContextProfile]) -> List[str]:
        """Save multiple control profiles"""
        ids = []
        for profile in profiles:
            try:
                doc_id = await self.save_control_profile(profile)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Error saving profile {profile.profile_id}: {str(e)}")
        return ids
    
    async def get_control_profiles_for_context(
        self,
        context_id: str,
        control_id: Optional[str] = None,
        framework: Optional[str] = None,
        top_k: int = 10
    ) -> List[ControlContextProfile]:
        """
        Get control profiles for a specific context.
        
        Args:
            context_id: Context ID to filter by
            control_id: Optional control ID filter
            framework: Optional framework filter
            top_k: Number of results to return
            
        Returns:
            List of ControlContextProfile objects
        """
        where_clause = {"context_id": context_id}
        if control_id:
            where_clause["control_id"] = control_id
        if framework:
            where_clause["framework"] = framework
        
        # Use hybrid_search for metadata-only filtering
        results = await self.profiles_service.hybrid_search(
            query="profile",  # Minimal query for metadata-only filtering
            top_k=top_k,
            where=where_clause
        )
        
        profiles = []
        for result in results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or ""
                metadata = result.get("metadata", {})
                profile = ControlContextProfile.from_metadata(
                    document=document,
                    metadata=metadata
                )
                profiles.append(profile)
            except Exception as e:
                logger.warning(f"Error parsing profile from result: {str(e)}")
        
        return profiles
    
    async def search_control_profiles(
        self,
        query: str,
        context_id: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ControlContextProfile]:
        """Search control profiles using hybrid search"""
        where_clause = filters or {}
        if context_id:
            where_clause["context_id"] = context_id
        
        results = await self.profiles_service.hybrid_search(
            query=query,
            top_k=top_k,
            where=where_clause if where_clause else None
        )
        
        profiles = []
        for result in results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or ""
                metadata = result.get("metadata", {})
                profile = ControlContextProfile.from_metadata(
                    document=document,
                    metadata=metadata
                )
                profiles.append(profile)
            except Exception as e:
                logger.warning(f"Error parsing profile from result: {str(e)}")
        
        return profiles
    
    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    async def delete_context(self, context_id: str) -> int:
        """Delete a context and all related edges/profiles"""
        deleted = 0
        
        # Delete context definition
        deleted += await self.contexts_service.delete_by_metadata({"context_id": context_id})
        
        # Delete related edges
        deleted += await self.edges_service.delete_by_metadata({"context_id": context_id})
        
        # Delete related profiles
        deleted += await self.profiles_service.delete_by_metadata({"context_id": context_id})
        
        logger.info(f"Deleted context {context_id} and {deleted} related documents")
        return deleted
    
    async def get_context_statistics(self, context_id: str) -> Dict[str, int]:
        """Get statistics for a context"""
        # Count edges
        edges = await self.get_edges_for_context(context_id, top_k=1000)
        
        # Count profiles
        profiles = await self.get_control_profiles_for_context(context_id, top_k=1000)
        
        return {
            "edges_count": len(edges),
            "profiles_count": len(profiles),
            "total_documents": len(edges) + len(profiles) + 1  # +1 for context definition
        }
    
    # ============================================================================
    # Knowledge Graph Building Methods
    # ============================================================================
    
    async def build_hierarchical_edges(
        self,
        context_id: str,
        connector_ids: List[str],
        domain_ids: List[str],
        compliance_ids: List[str],
        risk_ids: List[str],
        additional_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Build contextual edges following the hierarchy:
        Connector -> Domain -> Compliance -> Risks -> Additionals
        
        Args:
            context_id: Context ID
            connector_ids: List of connector entity IDs
            domain_ids: List of domain entity IDs
            compliance_ids: List of compliance entity IDs
            risk_ids: List of risk entity IDs
            additional_ids: Optional list of additional entity IDs
            
        Returns:
            List of edge IDs that were created
        """
        edges_created = []
        
        # 1. Connector -> Domain edges
        for connector_id in connector_ids:
            for domain_id in domain_ids:
                edge = ContextualEdge(
                    edge_id=f"{context_id}_{connector_id}_to_{domain_id}",
                    document=f"Connector {connector_id} provides data for domain {domain_id} in context {context_id}",
                    source_entity_id=connector_id,
                    source_entity_type="connector",
                    target_entity_id=domain_id,
                    target_entity_type="domain",
                    edge_type="PROVIDES_DATA_FOR",
                    context_id=context_id,
                    relevance_score=0.8
                )
                edge_id = await self.save_contextual_edge(edge)
                edges_created.append(edge_id)
        
        # 2. Domain -> Compliance edges
        for domain_id in domain_ids:
            for compliance_id in compliance_ids:
                edge = ContextualEdge(
                    edge_id=f"{context_id}_{domain_id}_to_{compliance_id}",
                    document=f"Domain {domain_id} is governed by compliance control {compliance_id} in context {context_id}",
                    source_entity_id=domain_id,
                    source_entity_type="domain",
                    target_entity_id=compliance_id,
                    target_entity_type="compliance",
                    edge_type="GOVERNED_BY",
                    context_id=context_id,
                    relevance_score=0.85
                )
                edge_id = await self.save_contextual_edge(edge)
                edges_created.append(edge_id)
        
        # 3. Compliance -> Risks edges
        for compliance_id in compliance_ids:
            for risk_id in risk_ids:
                edge = ContextualEdge(
                    edge_id=f"{context_id}_{compliance_id}_to_{risk_id}",
                    document=f"Compliance control {compliance_id} addresses risk {risk_id} in context {context_id}",
                    source_entity_id=compliance_id,
                    source_entity_type="compliance",
                    target_entity_id=risk_id,
                    target_entity_type="risk",
                    edge_type="ADDRESSES_RISK",
                    context_id=context_id,
                    relevance_score=0.9
                )
                edge_id = await self.save_contextual_edge(edge)
                edges_created.append(edge_id)
        
        # 4. Compliance -> Additionals edges (if provided)
        if additional_ids:
            for compliance_id in compliance_ids:
                for additional_id in additional_ids:
                    edge = ContextualEdge(
                        edge_id=f"{context_id}_{compliance_id}_to_{additional_id}",
                        document=f"Compliance control {compliance_id} requires additional resource {additional_id} in context {context_id}",
                        source_entity_id=compliance_id,
                        source_entity_type="compliance",
                        target_entity_id=additional_id,
                        target_entity_type="additional",
                        edge_type="REQUIRES",
                        context_id=context_id,
                        relevance_score=0.75
                    )
                    edge_id = await self.save_contextual_edge(edge)
                    edges_created.append(edge_id)
        
        logger.info(f"Created {len(edges_created)} hierarchical edges for context {context_id}")
        return edges_created
    
    async def build_schema_connections(
        self,
        context_id: str,
        entity_id: str,
        entity_type: str,
        schema_ids: List[str],
        connection_type: str = "USES_SCHEMA"
    ) -> List[str]:
        """
        Build connections between entities and schemas (tables, columns).
        Schemas are separate from the main hierarchy.
        
        Args:
            context_id: Context ID
            entity_id: Entity ID (connector, domain, compliance, etc.)
            entity_type: Entity type
            schema_ids: List of schema/table/column IDs
            connection_type: Type of connection (USES_SCHEMA, QUERIES_TABLE, etc.)
            
        Returns:
            List of edge IDs that were created
        """
        edges_created = []
        
        for schema_id in schema_ids:
            edge = ContextualEdge(
                edge_id=f"{context_id}_{entity_id}_to_{schema_id}",
                document=f"{entity_type} {entity_id} uses schema {schema_id} in context {context_id}",
                source_entity_id=entity_id,
                source_entity_type=entity_type,
                target_entity_id=schema_id,
                target_entity_type="schema",
                edge_type=connection_type,
                context_id=context_id,
                relevance_score=0.7
            )
            edge_id = await self.save_contextual_edge(edge)
            edges_created.append(edge_id)
        
        logger.info(f"Created {len(edges_created)} schema connections for {entity_type} {entity_id}")
        return edges_created
    
    async def build_knowledge_graph_from_stores(
        self,
        context_id: str,
        collection_factory: Any,
        query: Optional[str] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Build knowledge graph by querying all stores and creating connections.
        
        Args:
            context_id: Context ID
            collection_factory: CollectionFactory instance
            query: Optional query to filter entities
            top_k: Number of entities to retrieve per store
            
        Returns:
            Dictionary with statistics about the knowledge graph built
        """
        from app.storage.query.collection_factory import CollectionFactory
        
        if not isinstance(collection_factory, CollectionFactory):
            raise ValueError("collection_factory must be a CollectionFactory instance")
        
        # Search all stores
        all_results = collection_factory.search_all(
            query=query or "",
            top_k=top_k,
            include_schemas=True
        )
        
        # Extract entity IDs by type
        connector_ids = [r.get("id") or r.get("document_id") for r in all_results.get("connectors", [])]
        domain_ids = [r.get("id") or r.get("document_id") for r in all_results.get("domains", [])]
        compliance_ids = [r.get("id") or r.get("document_id") for r in all_results.get("compliance", [])]
        risk_ids = [r.get("id") or r.get("document_id") for r in all_results.get("risks", [])]
        additional_ids = [r.get("id") or r.get("document_id") for r in all_results.get("additionals", [])]
        schema_ids = [r.get("id") or r.get("document_id") for r in all_results.get("schemas", [])]
        
        # Build hierarchical edges
        hierarchical_edges = await self.build_hierarchical_edges(
            context_id=context_id,
            connector_ids=connector_ids,
            domain_ids=domain_ids,
            compliance_ids=compliance_ids,
            risk_ids=risk_ids,
            additional_ids=additional_ids
        )
        
        # Build schema connections for each entity type
        schema_edges = []
        
        # Connect connectors to schemas
        for connector_id in connector_ids:
            edges = await self.build_schema_connections(
                context_id=context_id,
                entity_id=connector_id,
                entity_type="connector",
                schema_ids=schema_ids,
                connection_type="PROVIDES_SCHEMA"
            )
            schema_edges.extend(edges)
        
        # Connect domains to schemas
        for domain_id in domain_ids:
            edges = await self.build_schema_connections(
                context_id=context_id,
                entity_id=domain_id,
                entity_type="domain",
                schema_ids=schema_ids,
                connection_type="USES_SCHEMA"
            )
            schema_edges.extend(edges)
        
        # Connect compliance to schemas (for data-driven controls)
        for compliance_id in compliance_ids:
            edges = await self.build_schema_connections(
                context_id=context_id,
                entity_id=compliance_id,
                entity_type="compliance",
                schema_ids=schema_ids,
                connection_type="MONITORS_VIA_SCHEMA"
            )
            schema_edges.extend(edges)
        
        return {
            "context_id": context_id,
            "entities_found": {
                "connectors": len(connector_ids),
                "domains": len(domain_ids),
                "compliance": len(compliance_ids),
                "risks": len(risk_ids),
                "additionals": len(additional_ids),
                "schemas": len(schema_ids)
            },
            "edges_created": {
                "hierarchical": len(hierarchical_edges),
                "schema_connections": len(schema_edges),
                "total": len(hierarchical_edges) + len(schema_edges)
            },
            "hierarchical_edges": hierarchical_edges,
            "schema_edges": schema_edges
        }
    
    # ============================================================================
    # Edge Discovery and Pruning Methods
    # ============================================================================
    
    async def discover_edges_by_context(
        self,
        context_query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ContextualEdge]:
        """
        Discover edges using vector similarity search based on context query.
        
        Args:
            context_query: Context-based query string (from context breakdown)
            top_k: Number of edges to retrieve
            filters: Optional metadata filters
            
        Returns:
            List of discovered ContextualEdge objects
        """
        try:
            # Use hybrid search to find relevant edges
            where_clause = filters or {}
            
            # Log the full query (not truncated) for debugging
            logger.debug(f"discover_edges_by_context: Full query: '{context_query}' (length: {len(context_query)})")
            logger.debug(f"discover_edges_by_context: Filters: {where_clause}")
            
            results = await self.edges_service.hybrid_search(
                query=context_query,
                top_k=top_k,
                where=where_clause if where_clause else None
            )
            
            logger.info(f"discover_edges_by_context: Hybrid search returned {len(results)} results for query: '{context_query[:100]}...'")
            
            edges = []
            for result in results:
                try:
                    document = result.get("content") or result.get("document") or ""
                    metadata = result.get("metadata", {})
                    edge = ContextualEdge.from_metadata(
                        document=document,
                        metadata=metadata
                    )
                    # Add search score to relevance_score if available
                    if "score" in result or "distance" in result:
                        search_score = result.get("score", 0.0)
                        if "distance" in result:
                            # Convert distance to score (lower distance = higher score)
                            distance = result.get("distance", 1.0)
                            search_score = 1.0 / (1.0 + distance)
                        edge.relevance_score = max(edge.relevance_score, search_score)
                    edges.append(edge)
                except Exception as e:
                    logger.warning(f"Error parsing edge from discovery result: {str(e)}")
            
            logger.info(f"Discovered {len(edges)} edges for context query: {context_query[:50]}")
            return edges
            
        except Exception as e:
            logger.error(f"Error discovering edges: {str(e)}", exc_info=True)
            return []
    
    async def save_edge_to_postgres(
        self,
        edge: ContextualEdge,
        db_pool: Optional[Any] = None
    ) -> bool:
        """
        Save a contextual edge to PostgreSQL contextual_relationships table.
        
        Args:
            edge: ContextualEdge to save
            db_pool: Optional database pool (will be fetched if not provided)
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            if db_pool is None:
                from app.core.dependencies import get_database_pool
                db_pool = await get_database_pool()
            
            if db_pool is None:
                logger.warning("Database pool not available, skipping postgres save")
                return False
            
            # Check if context_id exists in contexts table
            async with db_pool.acquire() as conn:
                # Check if tables exist, if not, skip PostgreSQL save gracefully
                try:
                    table_check = await conn.fetchrow("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'contexts'
                        )
                    """)
                    if not table_check or not table_check['exists']:
                        logger.warning("PostgreSQL table 'contexts' does not exist. Skipping PostgreSQL save. Run create_contextual_graph_tables.py to create tables.")
                        return False
                except Exception as check_error:
                    logger.warning(f"Could not check if tables exist: {check_error}. Skipping PostgreSQL save.")
                    return False
                # First, try to get context_id from contexts table
                # If context_id is a string, we need to find or create it
                context_db_id = None
                if edge.context_id:
                    # Try to find context by context_id field in contexts table
                    context_row = await conn.fetchrow("""
                        SELECT context_id FROM contexts 
                        WHERE context_id::text = $1 OR context_name = $1
                        LIMIT 1
                    """, edge.context_id)
                    
                    if context_row:
                        context_db_id = context_row["context_id"]
                    else:
                        # Create a new context entry if it doesn't exist
                        # This is a simplified version - you may want to enhance this
                        context_row = await conn.fetchrow("""
                            INSERT INTO contexts (context_type, context_name, context_definition)
                            VALUES ('organizational_situational', $1, $2::jsonb)
                            RETURNING context_id
                        """, edge.context_id, json.dumps({"context_id": edge.context_id}))
                        if context_row:
                            context_db_id = context_row["context_id"]
                
                if context_db_id is None:
                    logger.warning(f"Could not resolve context_id {edge.context_id} for postgres save")
                    return False
                
                # Insert or update edge in contextual_relationships table
                await conn.execute("""
                    INSERT INTO contextual_relationships (
                        source_entity_id,
                        relationship_type,
                        target_entity_id,
                        context_id,
                        strength,
                        confidence,
                        reasoning,
                        valid_from
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (source_entity_id, relationship_type, target_entity_id, context_id)
                    DO UPDATE SET
                        strength = EXCLUDED.strength,
                        confidence = EXCLUDED.confidence,
                        reasoning = EXCLUDED.reasoning,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    edge.source_entity_id,
                    edge.edge_type,
                    edge.target_entity_id,
                    context_db_id,
                    edge.relevance_score,  # Use relevance_score as strength
                    edge.relevance_score,  # Use relevance_score as confidence
                    edge.document[:500],  # Use document as reasoning (truncated)
                    datetime.utcnow() if edge.created_at else None
                )
                
                logger.info(f"Saved edge {edge.edge_id} to PostgreSQL")
                return True
                
        except Exception as e:
            logger.error(f"Error saving edge to postgres: {str(e)}", exc_info=True)
            return False
    
    async def save_edges_to_postgres(
        self,
        edges: List[ContextualEdge],
        db_pool: Optional[Any] = None,
        batch_size: int = 1000
    ) -> int:
        """
        Save multiple edges to PostgreSQL in batches for better performance.
        
        Args:
            edges: List of ContextualEdge objects
            db_pool: Optional database pool
            batch_size: Number of edges to process in each batch (default: 1000)
            
        Returns:
            Number of edges successfully saved
        """
        if not edges:
            return 0
            
        if db_pool is None:
            from app.core.dependencies import get_database_pool
            db_pool = await get_database_pool()
        
        if db_pool is None:
            logger.warning("Database pool not available, skipping postgres save")
            return 0
        
        # Check if tables exist before processing
        try:
            async with db_pool.acquire() as conn:
                table_check = await conn.fetchrow("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'contexts'
                    )
                """)
                if not table_check or not table_check['exists']:
                    logger.warning("PostgreSQL table 'contexts' does not exist. Skipping PostgreSQL save. Run create_contextual_graph_tables.py to create tables.")
                    return 0
        except Exception as check_error:
            logger.warning(f"Could not check if tables exist: {check_error}. Skipping PostgreSQL save.")
            return 0
        
        total_edges = len(edges)
        saved_count = 0
        logger.info(f"Saving {total_edges} edges to PostgreSQL in batches of {batch_size}")
        
        # First, collect all unique context_ids and ensure they exist in contexts table
        context_ids = set()
        for edge in edges:
            if edge.context_id:
                context_ids.add(edge.context_id)
        
        # Batch create contexts if they don't exist
        if context_ids:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    for context_id in context_ids:
                        try:
                            # Check if context exists
                            existing = await conn.fetchrow("""
                                SELECT context_id FROM contexts 
                                WHERE context_id::text = $1 OR context_name = $1
                                LIMIT 1
                            """, context_id)
                            
                            if not existing:
                                # Create context if it doesn't exist
                                await conn.execute("""
                                    INSERT INTO contexts (context_type, context_name, context_definition)
                                    VALUES ('organizational_situational', $1, $2::jsonb)
                                    ON CONFLICT (context_name) DO NOTHING
                                """, context_id, json.dumps({"context_id": context_id}))
                        except Exception as e:
                            logger.warning(f"Error ensuring context {context_id} exists: {e}")
        
        # Process edges in batches
        for i in range(0, total_edges, batch_size):
            batch = edges[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_edges + batch_size - 1) // batch_size
            
            try:
                async with db_pool.acquire() as conn:
                    async with conn.transaction():
                        # Prepare batch insert data
                        batch_data = []
                        for edge in batch:
                            if not edge.context_id:
                                continue
                            
                            # Get context_db_id
                            context_row = await conn.fetchrow("""
                                SELECT context_id FROM contexts 
                                WHERE context_id::text = $1 OR context_name = $1
                                LIMIT 1
                            """, edge.context_id)
                            
                            if not context_row:
                                logger.warning(f"Context {edge.context_id} not found, skipping edge {edge.edge_id}")
                                continue
                            
                            context_db_id = context_row["context_id"]
                            
                            batch_data.append((
                                edge.source_entity_id,
                                edge.edge_type,
                                edge.target_entity_id,
                                context_db_id,
                                edge.relevance_score,
                                edge.relevance_score,
                                edge.document[:500] if edge.document else "",
                                datetime.utcnow() if edge.created_at else None
                            ))
                        
                        if batch_data:
                            # Batch insert using executemany
                            await conn.executemany("""
                                INSERT INTO contextual_relationships (
                                    source_entity_id,
                                    relationship_type,
                                    target_entity_id,
                                    context_id,
                                    strength,
                                    confidence,
                                    reasoning,
                                    valid_from
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                ON CONFLICT (source_entity_id, relationship_type, target_entity_id, context_id)
                                DO UPDATE SET
                                    strength = EXCLUDED.strength,
                                    confidence = EXCLUDED.confidence,
                                    reasoning = EXCLUDED.reasoning,
                                    updated_at = CURRENT_TIMESTAMP
                            """, batch_data)
                            
                            saved_count += len(batch_data)
                            logger.info(f"  ✓ Saved batch {batch_num}/{total_batches} ({len(batch_data)} edges)")
                        else:
                            logger.warning(f"  No valid edges in batch {batch_num}/{total_batches}")
                            
            except Exception as e:
                logger.error(f"Error saving batch {batch_num}/{total_batches} to PostgreSQL: {str(e)}")
                logger.debug(f"  Batch error details: {type(e).__name__}: {str(e)}", exc_info=True)
                # Fall back to individual saves for this batch
                logger.info(f"  Falling back to individual saves for batch {batch_num}")
                for edge in batch:
                    try:
                        if await self.save_edge_to_postgres(edge, db_pool):
                            saved_count += 1
                    except Exception as edge_error:
                        logger.error(f"Error saving edge {edge.edge_id}: {str(edge_error)}")
        
        logger.info(f"Successfully saved {saved_count}/{total_edges} edges to PostgreSQL")
        return saved_count

