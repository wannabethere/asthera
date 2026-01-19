"""
Extraction Service
Unified service for all extraction pipelines with async batch processing
"""
import logging
import json
from typing import Dict, Any, Optional, List
from uuid import uuid4
import asyncpg
from langchain_openai import ChatOpenAI

from .base import BaseService, ServiceRequest, ServiceResponse
from .models import (
    ExtractionRequest,
    BatchExtractionRequest,
    ExtractionResponse,
    BatchExtractionResponse
)
# Lazy import to avoid circular dependency with app.agents.pipelines
# from app.agents.pipelines import (
#     ControlExtractionPipeline,
#     ContextExtractionPipeline,
#     RequirementExtractionPipeline,
#     EvidenceExtractionPipeline,
#     FieldsExtractionPipeline,
#     EntitiesExtractionPipeline
# )

logger = logging.getLogger(__name__)


class ExtractionService(BaseService[ServiceRequest, ServiceResponse]):
    """
    Unified extraction service that orchestrates all extraction pipelines.
    Supports both single and batch extraction with async processing.
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        db_pool: Optional[asyncpg.Pool] = None,
        maxsize: int = 1_000_000,
        ttl: int = 120
    ):
        """Initialize extraction service with all pipelines
        
        Args:
            llm: Optional LLM instance
            model_name: Model name for LLM
            db_pool: Optional database pool for saving doc insights
            maxsize: Cache max size
            ttl: Cache TTL in seconds
        """
        super().__init__(maxsize=maxsize, ttl=ttl)
        
        self._llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self._db_pool = db_pool
        
        # Lazy import to avoid circular dependency
        from app.agents.pipelines import (
            ControlExtractionPipeline,
            ContextExtractionPipeline,
            RequirementExtractionPipeline,
            EvidenceExtractionPipeline,
            FieldsExtractionPipeline,
            EntitiesExtractionPipeline
        )
        
        # Initialize all extraction pipelines
        self._control_pipeline = ControlExtractionPipeline(llm=self._llm, model_name=model_name)
        self._context_pipeline = ContextExtractionPipeline(llm=self._llm, model_name=model_name)
        self._requirement_pipeline = RequirementExtractionPipeline(llm=self._llm, model_name=model_name)
        self._evidence_pipeline = EvidenceExtractionPipeline(llm=self._llm, model_name=model_name)
        self._fields_pipeline = FieldsExtractionPipeline(llm=self._llm, model_name=model_name)
        self._entities_pipeline = EntitiesExtractionPipeline(llm=self._llm, model_name=model_name)
        
        # Store pipelines in a dict for easy access
        self._pipelines = {
            "control": self._control_pipeline,
            "context": self._context_pipeline,
            "requirement": self._requirement_pipeline,
            "evidence": self._evidence_pipeline,
            "fields": self._fields_pipeline,
            "entities": self._entities_pipeline
        }
    
    async def initialize(self) -> None:
        """Initialize all pipelines"""
        await self._control_pipeline.initialize()
        await self._context_pipeline.initialize()
        await self._requirement_pipeline.initialize()
        await self._evidence_pipeline.initialize()
        await self._fields_pipeline.initialize()
        await self._entities_pipeline.initialize()
        logger.info("ExtractionService initialized with all pipelines")
    
    async def _save_doc_insight(
        self,
        doc_id: str,
        document_content: str,
        extraction_type: str,
        extracted_data: Dict[str, Any],
        context_id: Optional[str] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save document insight to PostgreSQL document_kg_insights table.
        
        Args:
            doc_id: ChromaDB document ID (matches the ID used in ChromaDB)
            document_content: Original document text that was processed
            extraction_type: Type of extraction ('context', 'control', 'fields', 'entities', 'requirement', 'evidence')
            extracted_data: Dictionary containing the extracted structured data
            context_id: Optional context ID if the extraction is context-specific
            extraction_metadata: Optional metadata about the extraction
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self._db_pool:
            logger.debug("No database pool provided, skipping doc insight save")
            return False
        
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO document_kg_insights (
                        doc_id, document_content, extraction_type, extracted_data,
                        context_id, extraction_metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        document_content = EXCLUDED.document_content,
                        extraction_type = EXCLUDED.extraction_type,
                        extracted_data = EXCLUDED.extracted_data,
                        context_id = EXCLUDED.context_id,
                        extraction_metadata = EXCLUDED.extraction_metadata,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    doc_id,
                    document_content,
                    extraction_type,
                    json.dumps(extracted_data),
                    context_id,
                    json.dumps(extraction_metadata) if extraction_metadata else None
                )
                logger.debug(f"Saved doc insight: {doc_id} (type: {extraction_type})")
                return True
        except Exception as e:
            logger.error(f"Failed to save doc insight {doc_id}: {str(e)}", exc_info=True)
            return False
    
    async def _process_request_impl(self, request: ServiceRequest) -> ServiceResponse:
        """
        Process extraction requests.
        Routes to appropriate handler based on request type.
        """
        if isinstance(request, ExtractionRequest):
            return await self._handle_single_extraction(request)
        elif isinstance(request, BatchExtractionRequest):
            return await self._handle_batch_extraction(request)
        else:
            return ServiceResponse(
                success=False,
                error=f"Unknown request type: {type(request).__name__}",
                request_id=request.request_id if hasattr(request, 'request_id') else None
            )
    
    async def _handle_single_extraction(self, request: ExtractionRequest) -> ExtractionResponse:
        """Handle single extraction request"""
        extraction_type = request.extraction_type.lower()
        
        if extraction_type not in self._pipelines:
            return ExtractionResponse(
                success=False,
                error=f"Unknown extraction type: {extraction_type}",
                request_id=request.request_id,
                extraction_type=extraction_type
            )
        
        pipeline = self._pipelines[extraction_type]
        
        try:
            # Get configuration from request (supports passing rules)
            configuration = None
            if hasattr(request, 'configuration') and request.configuration:
                configuration = request.configuration
            elif hasattr(request, 'rules') and request.rules:
                # Support passing rules directly for backward compatibility
                configuration = {"rules": request.rules}
            
            result = await pipeline.run(
                inputs=request.inputs,
                status_callback=None,  # Could add callback support
                configuration=configuration
            )
            
            # Save doc insight if extraction was successful
            if result.get("success", False) and self._db_pool:
                extracted_data = result.get("data", {})
                inputs = request.inputs
                
                # Determine doc_id and document_content based on extraction type
                doc_id = None
                document_content = None
                context_id = None
                extraction_metadata = {}
                
                if extraction_type == "context":
                    doc_id = inputs.get("context_id") or extracted_data.get("context_id")
                    document_content = inputs.get("description", "")
                    context_id = doc_id
                    extraction_metadata = {
                        "context_type": extracted_data.get("context_type"),
                        "industry": extracted_data.get("industry"),
                        "organization_size": extracted_data.get("organization_size"),
                        "maturity_level": extracted_data.get("maturity_level"),
                        "regulatory_frameworks": extracted_data.get("regulatory_frameworks", [])
                    }
                elif extraction_type == "control":
                    # For controls, doc_id will be set when control is saved
                    # We'll save it with a temporary ID and update later if needed
                    control_id = extracted_data.get("control_id") or inputs.get("control_id")
                    context_metadata = inputs.get("context_metadata", {})
                    context_id = context_metadata.get("context_id")
                    if control_id and context_id:
                        doc_id = f"profile_{control_id}_{context_id}"
                    elif control_id:
                        doc_id = f"control_{control_id}"
                    document_content = inputs.get("text", "")
                    extraction_metadata = {
                        "framework": inputs.get("framework", ""),
                        "control_id": control_id,
                        "control_name": extracted_data.get("control_name"),
                        "category": extracted_data.get("category")
                    }
                elif extraction_type == "requirement":
                    requirement_id = extracted_data.get("requirement_id")
                    doc_id = requirement_id or f"requirement_{request.request_id}"
                    document_content = inputs.get("requirement_text", "")
                    context_metadata = inputs.get("context_metadata", {})
                    context_id = context_metadata.get("context_id")
                    extraction_metadata = {
                        "control_id": inputs.get("control_id", ""),
                        "requirement_type": extracted_data.get("requirement_type")
                    }
                elif extraction_type == "evidence":
                    evidence_id = extracted_data.get("evidence_id")
                    doc_id = evidence_id or f"evidence_{request.request_id}"
                    document_content = inputs.get("evidence_name", "")
                    context_metadata = inputs.get("context_metadata", {})
                    context_id = context_metadata.get("context_id")
                    extraction_metadata = {
                        "requirement_id": inputs.get("requirement_id", ""),
                        "evidence_category": extracted_data.get("evidence_category")
                    }
                elif extraction_type == "fields":
                    source_entity_id = inputs.get("source_entity_id")
                    context_id = inputs.get("context_id")
                    if source_entity_id and context_id:
                        doc_id = f"{source_entity_id}_{context_id}_fields"
                    elif context_id:
                        doc_id = f"{context_id}_fields"
                    else:
                        doc_id = f"fields_{request.request_id}"
                    document_content = inputs.get("text", "")
                    extraction_metadata = {
                        "source_entity_id": source_entity_id,
                        "source_entity_type": inputs.get("source_entity_type"),
                        "field_definitions": inputs.get("field_definitions", [])
                    }
                elif extraction_type == "entities":
                    context_id = inputs.get("context_id")
                    source_entity_id = inputs.get("source_entity_id") or inputs.get("control_id")
                    if source_entity_id and context_id:
                        doc_id = f"{source_entity_id}_{context_id}_entities"
                    elif context_id:
                        doc_id = f"{context_id}_entities"
                    else:
                        doc_id = f"entities_{request.request_id}"
                    document_content = inputs.get("text", "")
                    extraction_metadata = {
                        "entity_types": inputs.get("entity_types", []),
                        "entities_count": len(extracted_data.get("entities", [])),
                        "edges_count": extracted_data.get("edges_count", 0)
                    }
                
                # Save doc insight if we have a doc_id
                if doc_id and document_content:
                    await self._save_doc_insight(
                        doc_id=doc_id,
                        document_content=document_content,
                        extraction_type=extraction_type,
                        extracted_data=extracted_data,
                        context_id=context_id,
                        extraction_metadata=extraction_metadata
                    )
            
            return ExtractionResponse(
                success=result.get("success", False),
                data=result.get("data"),
                extracted_data=result.get("data"),
                request_id=request.request_id,
                extraction_type=extraction_type,
                status="completed"
            )
            
        except Exception as e:
            logger.error(f"Error in {extraction_type} extraction: {str(e)}", exc_info=True)
            return ExtractionResponse(
                success=False,
                error=str(e),
                request_id=request.request_id,
                extraction_type=extraction_type,
                status="error"
            )
    
    async def _handle_batch_extraction(self, request: BatchExtractionRequest) -> BatchExtractionResponse:
        """Handle batch extraction request"""
        extraction_type = request.extraction_type.lower()
        
        if extraction_type not in self._pipelines:
            return BatchExtractionResponse(
                success=False,
                error=f"Unknown extraction type: {extraction_type}",
                request_id=request.request_id,
                extraction_type=extraction_type
            )
        
        pipeline = self._pipelines[extraction_type]
        
        try:
            # Get configuration from request (supports passing rules)
            configuration = None
            if hasattr(request, 'configuration') and request.configuration:
                configuration = request.configuration
            elif hasattr(request, 'rules') and request.rules:
                # Support passing rules directly for backward compatibility
                configuration = {"rules": request.rules}
            
            results = await pipeline.run_batch(
                inputs_list=request.inputs_list,
                max_concurrent=request.max_concurrent,
                status_callback=None,  # Could add callback support
                configuration=configuration
            )
            
            # Count successes and failures
            successful = sum(1 for r in results if r.get("success", False))
            failed = len(results) - successful
            
            return BatchExtractionResponse(
                success=True,
                data={"results": results},
                results=results,
                request_id=request.request_id,
                extraction_type=extraction_type,
                status="completed",
                total=len(results),
                successful=successful,
                failed=failed
            )
            
        except Exception as e:
            logger.error(f"Error in batch {extraction_type} extraction: {str(e)}", exc_info=True)
            return BatchExtractionResponse(
                success=False,
                error=str(e),
                request_id=request.request_id,
                extraction_type=extraction_type,
                status="error",
                total=len(request.inputs_list),
                successful=0,
                failed=len(request.inputs_list)
            )
    
    # Convenience methods for direct usage
    async def extract_control(
        self,
        text: str,
        framework: str,
        context_metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract control from text
        
        Args:
            text: Regulatory text to extract from
            framework: Framework name (e.g., "HIPAA")
            context_metadata: Optional context metadata
            configuration: Optional configuration including rules override
            request_id: Optional request ID
        """
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="control",
            inputs={
                "text": text,
                "framework": framework,
                "context_metadata": context_metadata or {}
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)
    
    async def extract_context(
        self,
        description: str,
        context_id: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract context from description
        
        Args:
            description: Organizational/situational description
            context_id: Optional context ID
            configuration: Optional configuration including rules override
            request_id: Optional request ID
        """
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="context",
            inputs={
                "description": description,
                "context_id": context_id
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)
    
    async def extract_requirement(
        self,
        requirement_text: str,
        control_id: str,
        context_metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract requirement document
        
        Args:
            requirement_text: Requirement text
            control_id: Control ID this requirement belongs to
            context_metadata: Optional context metadata
            configuration: Optional configuration including rules override
            request_id: Optional request ID
        """
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="requirement",
            inputs={
                "requirement_text": requirement_text,
                "control_id": control_id,
                "context_metadata": context_metadata or {}
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)
    
    async def extract_evidence(
        self,
        evidence_name: str,
        requirement_id: str,
        context_metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract evidence document
        
        Args:
            evidence_name: Evidence name/description
            requirement_id: Requirement ID this evidence supports
            context_metadata: Optional context metadata
            configuration: Optional configuration including rules override
            request_id: Optional request ID
        """
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="evidence",
            inputs={
                "evidence_name": evidence_name,
                "requirement_id": requirement_id,
                "context_metadata": context_metadata or {}
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)
    
    async def batch_extract_controls(
        self,
        texts: List[Dict[str, Any]],  # List of {"text": str, "framework": str, "context_metadata": dict}
        max_concurrent: int = 5,
        request_id: Optional[str] = None
    ) -> BatchExtractionResponse:
        """Batch extract controls"""
        request = BatchExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="control",
            inputs_list=texts,
            max_concurrent=max_concurrent
        )
        return await self._handle_batch_extraction(request)
    
    async def batch_extract_contexts(
        self,
        descriptions: List[Dict[str, Any]],  # List of {"description": str, "context_id": Optional[str]}
        max_concurrent: int = 5,
        request_id: Optional[str] = None
    ) -> BatchExtractionResponse:
        """Batch extract contexts"""
        request = BatchExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="context",
            inputs_list=descriptions,
            max_concurrent=max_concurrent
        )
        return await self._handle_batch_extraction(request)
    
    async def extract_fields(
        self,
        text: str,
        context_id: str,
        source_entity_id: Optional[str] = None,
        source_entity_type: Optional[str] = None,
        field_definitions: Optional[List[Dict[str, Any]]] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract fields from text and create contextual edges"""
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="fields",
            inputs={
                "text": text,
                "context_id": context_id,
                "source_entity_id": source_entity_id,
                "source_entity_type": source_entity_type,
                "field_definitions": field_definitions or [],
                "context_metadata": context_metadata or {}
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)
    
    async def extract_entities(
        self,
        text: str,
        context_id: str,
        entity_types: Optional[List[str]] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> ExtractionResponse:
        """Extract entities and relationships from text and create contextual edges"""
        request = ExtractionRequest(
            request_id=request_id or str(uuid4()),
            extraction_type="entities",
            inputs={
                "text": text,
                "context_id": context_id,
                "entity_types": entity_types or [],
                "context_metadata": context_metadata or {}
            },
            configuration=configuration
        )
        return await self._handle_single_extraction(request)

