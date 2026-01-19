"""
Pipeline Orchestrator
Orchestrates multiple extraction pipelines to create comprehensive indexed content.
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

from app.agents.pipelines import (
    EntitiesExtractionPipeline,
    EvidenceExtractionPipeline,
    FieldsExtractionPipeline,
    MetadataGenerationPipeline,
    PatternRecognitionPipeline
)

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates extraction pipelines for comprehensive content processing."""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        enable_entities: bool = True,
        enable_evidence: bool = True,
        enable_fields: bool = True,
        enable_metadata: bool = True,
        enable_patterns: bool = False
    ):
        """
        Initialize pipeline orchestrator.
        
        Args:
            llm: LLM instance
            enable_entities: Enable entities extraction
            enable_evidence: Enable evidence extraction
            enable_fields: Enable fields extraction
            enable_metadata: Enable metadata generation
            enable_patterns: Enable pattern recognition
        """
        self.llm = llm
        self.pipelines = {}
        
        if enable_entities:
            self.pipelines["entities"] = EntitiesExtractionPipeline(llm=llm)
        if enable_evidence:
            self.pipelines["evidence"] = EvidenceExtractionPipeline(llm=llm)
        if enable_fields:
            self.pipelines["fields"] = FieldsExtractionPipeline(llm=llm)
        if enable_metadata:
            self.pipelines["metadata"] = MetadataGenerationPipeline(llm=llm)
        if enable_patterns:
            self.pipelines["patterns"] = PatternRecognitionPipeline(llm=llm)
        
        logger.info(f"PipelineOrchestrator initialized with {len(self.pipelines)} pipelines")
    
    async def initialize(self):
        """Initialize all pipelines."""
        for name, pipeline in self.pipelines.items():
            try:
                await pipeline.initialize()
                logger.info(f"Initialized pipeline: {name}")
            except Exception as e:
                logger.warning(f"Failed to initialize pipeline {name}: {e}")
    
    async def process_document(
        self,
        document: Document,
        context_id: Optional[str] = None,
        domain: Optional[str] = None,
        product_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a document through all enabled pipelines.
        
        Args:
            document: Document to process
            context_id: Optional context ID
            domain: Optional domain filter
            product_name: Optional product name
            
        Returns:
            Dictionary with processing results
        """
        if not context_id:
            context_id = f"doc_{uuid4()}"
        
        results = {
            "context_id": context_id,
            "original_content": document.page_content,
            "original_metadata": document.metadata,
            "pipeline_results": {},
            "extracted_data": {
                "entities": [],
                "fields": [],
                "evidence": [],
                "metadata": [],
                "patterns": []
            },
            "enhanced_content": document.page_content,
            "enhanced_metadata": document.metadata.copy()
        }
        
        # Process through entities pipeline
        if "entities" in self.pipelines:
            try:
                entities_result = await self.pipelines["entities"].run(
                    inputs={
                        "text": document.page_content,
                        "context_id": context_id,
                        "context_metadata": {
                            **document.metadata,
                            "domain": domain,
                            "product_name": product_name
                        }
                    }
                )
                results["pipeline_results"]["entities"] = entities_result
                if entities_result.get("success"):
                    entities = entities_result.get("data", {}).get("entities", [])
                    results["extracted_data"]["entities"] = entities
                    results["enhanced_metadata"]["entities_count"] = len(entities)
            except Exception as e:
                logger.warning(f"Error in entities pipeline: {e}")
                results["pipeline_results"]["entities"] = {"success": False, "error": str(e)}
        
        # Process through fields pipeline
        if "fields" in self.pipelines:
            try:
                fields_result = await self.pipelines["fields"].run(
                    inputs={
                        "text": document.page_content,
                        "context_id": context_id,
                        "context_metadata": {
                            **document.metadata,
                            "domain": domain,
                            "product_name": product_name
                        }
                    }
                )
                results["pipeline_results"]["fields"] = fields_result
                if fields_result.get("success"):
                    fields = fields_result.get("data", {}).get("extracted_fields", [])
                    results["extracted_data"]["fields"] = fields
                    results["enhanced_metadata"]["fields_count"] = len(fields)
            except Exception as e:
                logger.warning(f"Error in fields pipeline: {e}")
                results["pipeline_results"]["fields"] = {"success": False, "error": str(e)}
        
        # Process through evidence pipeline (if applicable)
        if "evidence" in self.pipelines and domain:
            try:
                evidence_result = await self.pipelines["evidence"].run(
                    inputs={
                        "evidence_name": f"{domain}_evidence",
                        "requirement_id": context_id,
                        "context_metadata": {
                            **document.metadata,
                            "domain": domain,
                            "product_name": product_name
                        }
                    }
                )
                results["pipeline_results"]["evidence"] = evidence_result
                if evidence_result.get("success"):
                    evidence = evidence_result.get("data", {}).get("document", {})
                    results["extracted_data"]["evidence"] = evidence
            except Exception as e:
                logger.warning(f"Error in evidence pipeline: {e}")
                results["pipeline_results"]["evidence"] = {"success": False, "error": str(e)}
        
        # Enhance content with extracted information
        enhanced_parts = [document.page_content]
        
        if results["extracted_data"]["entities"]:
            enhanced_parts.append(f"\n\n## Extracted Entities\n{self._format_entities(results['extracted_data']['entities'])}")
        
        if results["extracted_data"]["fields"]:
            enhanced_parts.append(f"\n\n## Extracted Fields\n{self._format_fields(results['extracted_data']['fields'])}")
        
        results["enhanced_content"] = "\n".join(enhanced_parts)
        
        # Create enhanced document
        enhanced_doc = Document(
            page_content=results["enhanced_content"],
            metadata=results["enhanced_metadata"]
        )
        results["enhanced_document"] = enhanced_doc
        
        return results
    
    async def process_batch(
        self,
        documents: List[Document],
        domain: Optional[str] = None,
        product_name: Optional[str] = None,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of documents.
        
        Args:
            documents: List of documents to process
            domain: Optional domain filter
            product_name: Optional product name
            max_concurrent: Maximum concurrent processing
            
        Returns:
            List of processing results
        """
        import asyncio
        
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(doc):
            async with semaphore:
                return await self.process_document(
                    document=doc,
                    domain=domain,
                    product_name=product_name
                )
        
        tasks = [process_with_semaphore(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing document {i}: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "document_index": i
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def _format_entities(self, entities: List[Dict[str, Any]]) -> str:
        """Format entities for display."""
        if not entities:
            return "No entities extracted"
        
        lines = []
        for entity in entities:
            entity_type = entity.get("entity_type", "unknown")
            entity_value = entity.get("entity_value", "unknown")
            lines.append(f"- {entity_type}: {entity_value}")
        
        return "\n".join(lines)
    
    def _format_fields(self, fields: List[Dict[str, Any]]) -> str:
        """Format fields for display."""
        if not fields:
            return "No fields extracted"
        
        lines = []
        for field in fields:
            field_name = field.get("field_name", "unknown")
            field_type = field.get("field_type", "unknown")
            field_value = field.get("field_value", "")
            lines.append(f"- {field_name} ({field_type}): {field_value}")
        
        return "\n".join(lines)
    
    async def cleanup(self):
        """Clean up all pipelines."""
        for name, pipeline in self.pipelines.items():
            try:
                await pipeline.cleanup()
                logger.info(f"Cleaned up pipeline: {name}")
            except Exception as e:
                logger.warning(f"Error cleaning up pipeline {name}: {e}")

