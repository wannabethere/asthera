"""
Contextual Graph Storage Layer

Manages storage and retrieval of contextual graph documents in ChromaDB:
1. Context Definitions - Organizational/situational contexts
2. Contextual Edges - Context-aware relationships between entities
3. Control-Context Profiles - Control implementation profiles for specific contexts

Based on the architecture described in docs/hybrid_search.md
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import chromadb
from langchain_openai import OpenAIEmbeddings

from .hybrid_search_service import HybridSearchService

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
    
    Manages three ChromaDB collections:
    1. context_definitions - Organizational/situational contexts
    2. contextual_edges - Context-aware relationships
    3. control_context_profiles - Control implementation profiles
    """
    
    def __init__(
        self,
        chroma_client: chromadb.PersistentClient,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        chroma_store_path: Optional[str] = None
    ):
        """
        Initialize contextual graph storage.
        
        Args:
            chroma_client: ChromaDB persistent client
            embeddings_model: Optional embeddings model
            chroma_store_path: Optional path for ChromaDB storage
        """
        self.chroma_client = chroma_client
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        
        # Initialize hybrid search services for each collection
        self.contexts_service = HybridSearchService(
            chroma_client=chroma_client,
            collection_name="context_definitions",
            embeddings_model=self.embeddings_model
        )
        
        self.edges_service = HybridSearchService(
            chroma_client=chroma_client,
            collection_name="contextual_edges",
            embeddings_model=self.embeddings_model
        )
        
        self.profiles_service = HybridSearchService(
            chroma_client=chroma_client,
            collection_name="control_context_profiles",
            embeddings_model=self.embeddings_model
        )
        
        logger.info("Initialized ContextualGraphStorage with three collections")
    
    # ============================================================================
    # Context Definitions Methods
    # ============================================================================
    
    def _sanitize_metadata_for_chromadb(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to ensure all values are ChromaDB-compatible.
        ChromaDB only accepts str, int, float, or bool - not lists or dicts.
        
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
    
    def save_context_definition(self, context: ContextDefinition, extra_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save a context definition.
        
        Args:
            context: ContextDefinition instance
            extra_metadata: Optional additional metadata to include in ChromaDB
            
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
        
        # Sanitize metadata to ensure ChromaDB compatibility (convert lists/dicts to JSON strings)
        metadata = self._sanitize_metadata_for_chromadb(metadata)
        
        ids = self.contexts_service.add_documents(
            documents=[context.document],
            metadatas=[metadata],
            ids=[context.context_id]
        )
        
        logger.info(f"Saved context definition: {context.context_id}")
        return ids[0] if ids else context.context_id
    
    def save_context_definition_with_metadata(self, context: ContextDefinition, metadata: Dict[str, Any]) -> str:
        """
        Save a context definition with custom metadata.
        
        Args:
            context: ContextDefinition instance
            metadata: Complete metadata dictionary to use
            
        Returns:
            Document ID that was saved
        """
        return self.save_context_definition(context, extra_metadata=metadata)
    
    def save_context_definitions(self, contexts: List[ContextDefinition]) -> List[str]:
        """Save multiple context definitions"""
        ids = []
        for context in contexts:
            try:
                doc_id = self.save_context_definition(context)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Error saving context {context.context_id}: {str(e)}")
        return ids
    
    def get_context_definition(self, context_id: str) -> Optional[ContextDefinition]:
        """Get a context definition by ID"""
        # Use hybrid_search with metadata filter for ID lookup
        results = self.contexts_service.hybrid_search(
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
    
    def find_relevant_contexts(
        self,
        description: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ContextDefinition]:
        """
        Find contexts relevant to a description using hybrid search.
        
        Args:
            description: Description of the context/situation
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of relevant ContextDefinition objects
        """
        results = self.contexts_service.find_relevant_contexts(
            context_description=description,
            top_k=top_k,
            where=filters
        )
        
        contexts = []
        for result in results:
            try:
                # hybrid_search returns dict with "content" key
                document = result.get("content") or ""
                metadata = result.get("metadata", {})
                context = ContextDefinition.from_metadata(
                    document=document,
                    metadata=metadata
                )
                contexts.append(context)
            except Exception as e:
                logger.warning(f"Error parsing context from result: {str(e)}")
        
        return contexts
    
    # ============================================================================
    # Contextual Edges Methods
    # ============================================================================
    
    def save_contextual_edge(self, edge: ContextualEdge) -> str:
        """Save a contextual edge"""
        if not edge.created_at:
            edge.created_at = datetime.utcnow().isoformat() + "Z"
        
        # Sanitize metadata to ensure ChromaDB compatibility
        metadata = self._sanitize_metadata_for_chromadb(edge.to_metadata())
        
        ids = self.edges_service.add_documents(
            documents=[edge.document],
            metadatas=[metadata],
            ids=[edge.edge_id]
        )
        
        logger.info(f"Saved contextual edge: {edge.edge_id}")
        return ids[0] if ids else edge.edge_id
    
    def save_contextual_edges(self, edges: List[ContextualEdge]) -> List[str]:
        """Save multiple contextual edges"""
        ids = []
        for edge in edges:
            try:
                doc_id = self.save_contextual_edge(edge)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Error saving edge {edge.edge_id}: {str(e)}")
        return ids
    
    def get_edges_for_context(
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
        results = self.edges_service.hybrid_search(
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
    
    def search_edges(
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
        
        results = self.edges_service.hybrid_search(
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
    
    def save_control_profile(self, profile: ControlContextProfile) -> str:
        """Save a control-context profile"""
        if not profile.created_at:
            profile.created_at = datetime.utcnow().isoformat() + "Z"
        profile.updated_at = datetime.utcnow().isoformat() + "Z"
        
        # Sanitize metadata to ensure ChromaDB compatibility
        metadata = self._sanitize_metadata_for_chromadb(profile.to_metadata())
        
        ids = self.profiles_service.add_documents(
            documents=[profile.document],
            metadatas=[metadata],
            ids=[profile.profile_id]
        )
        
        logger.info(f"Saved control profile: {profile.profile_id}")
        return ids[0] if ids else profile.profile_id
    
    def save_control_profiles(self, profiles: List[ControlContextProfile]) -> List[str]:
        """Save multiple control profiles"""
        ids = []
        for profile in profiles:
            try:
                doc_id = self.save_control_profile(profile)
                ids.append(doc_id)
            except Exception as e:
                logger.error(f"Error saving profile {profile.profile_id}: {str(e)}")
        return ids
    
    def get_control_profiles_for_context(
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
        results = self.profiles_service.hybrid_search(
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
    
    def search_control_profiles(
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
        
        results = self.profiles_service.hybrid_search(
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
    
    def delete_context(self, context_id: str) -> int:
        """Delete a context and all related edges/profiles"""
        deleted = 0
        
        # Delete context definition
        deleted += self.contexts_service.delete_by_metadata({"context_id": context_id})
        
        # Delete related edges
        deleted += self.edges_service.delete_by_metadata({"context_id": context_id})
        
        # Delete related profiles
        deleted += self.profiles_service.delete_by_metadata({"context_id": context_id})
        
        logger.info(f"Deleted context {context_id} and {deleted} related documents")
        return deleted
    
    def get_context_statistics(self, context_id: str) -> Dict[str, int]:
        """Get statistics for a context"""
        # Count edges
        edges = self.get_edges_for_context(context_id, top_k=1000)
        
        # Count profiles
        profiles = self.get_control_profiles_for_context(context_id, top_k=1000)
        
        return {
            "edges_count": len(edges),
            "profiles_count": len(profiles),
            "total_documents": len(edges) + len(profiles) + 1  # +1 for context definition
        }

