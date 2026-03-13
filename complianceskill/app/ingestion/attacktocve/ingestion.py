"""
Ingestion Script for ATT&CK → CVE Enrichment
==============================================
Reads preview files from a preview directory and ingests the enriched data
into the vector store using centralized dependencies and collections.

Uses:
- app.core.dependencies for vector store client
- app.core.settings for configuration
- app.storage.collections for collection names
- app.storage.vector_store for vector store operations
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document as LangchainDocument

from app.core.dependencies import (
    get_vector_store_client,
    get_embeddings_model,
    get_settings,
)
from app.storage.collections import FrameworkCollections

logger = logging.getLogger(__name__)


class AttackEnrichmentIngester:
    """Ingests preview files into vector store."""
    
    def __init__(
        self,
        preview_dir: str | Path,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize ingester.
        
        Args:
            preview_dir: Directory containing preview JSON files
            collection_name: Vector store collection name (defaults to framework_controls)
        """
        self.preview_dir = Path(preview_dir)
        if not self.preview_dir.exists():
            raise FileNotFoundError(f"Preview directory not found: {preview_dir}")
        
        self.settings = get_settings()
        
        # Determine collection name
        if collection_name:
            self.collection_name = collection_name
        else:
            # Use framework_controls collection by default
            self.collection_name = FrameworkCollections.CONTROLS
        
        logger.info(f"Initializing ingester for collection: {self.collection_name}")
    
    async def initialize(self):
        """Initialize vector store client."""
        self.embeddings_model = get_embeddings_model()
        self.vector_store_client = await get_vector_store_client(
            embeddings_model=self.embeddings_model
        )
        logger.info("Vector store client initialized")
    
    def _load_preview_files(self) -> List[Path]:
        """Load all preview JSON files from preview directory."""
        preview_files = list(self.preview_dir.glob("*_preview.json"))
        # Exclude batch_summary.json
        preview_files = [f for f in preview_files if f.name != "batch_summary.json"]
        logger.info(f"Found {len(preview_files)} preview files")
        return preview_files
    
    def _parse_preview_file(self, preview_file: Path) -> Dict[str, Any]:
        """Parse a single preview JSON file."""
        try:
            data = json.loads(preview_file.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            logger.error(f"Failed to parse {preview_file}: {e}")
            return {}
    
    def _build_documents_from_preview(
        self,
        preview: Dict[str, Any],
    ) -> List[LangchainDocument]:
        """
        Build LangchainDocument objects from preview data.
        
        Creates documents for:
        1. ATT&CK technique details
        2. Mappings to CIS scenarios
        """
        documents = []
        technique_id = preview.get("technique_id", "unknown")
        attack_detail = preview.get("attack_detail")
        final_mappings = preview.get("final_mappings", [])
        
        if not attack_detail:
            logger.warning(f"No attack detail for {technique_id}, skipping")
            return documents
        
        # Document 1: ATT&CK technique detail
        technique_text = self._build_technique_text(attack_detail)
        technique_metadata = {
            "type": "attack_technique",
            "technique_id": technique_id,
            "name": attack_detail.get("name", ""),
            "tactics": ",".join(attack_detail.get("tactics", [])),
            "platforms": ",".join(attack_detail.get("platforms", [])),
            "data_sources": ",".join(attack_detail.get("data_sources", [])),
        }
        documents.append(
            LangchainDocument(
                page_content=technique_text,
                metadata=technique_metadata,
            )
        )
        
        # Document 2: Mappings (one document per mapping or combined)
        if final_mappings:
            mappings_text = self._build_mappings_text(technique_id, attack_detail, final_mappings)
            mappings_metadata = {
                "type": "attack_cis_mapping",
                "technique_id": technique_id,
                "mapping_count": len(final_mappings),
                "scenario_ids": ",".join([m.get("scenario_id", "") for m in final_mappings]),
            }
            documents.append(
                LangchainDocument(
                    page_content=mappings_text,
                    metadata=mappings_metadata,
                )
            )
        
        return documents
    
    def _build_technique_text(self, attack_detail: Dict[str, Any]) -> str:
        """Build text representation of ATT&CK technique."""
        parts = [
            f"ATT&CK Technique: {attack_detail.get('technique_id', '')}",
            f"Name: {attack_detail.get('name', '')}",
            f"Description: {attack_detail.get('description', '')}",
        ]
        
        if attack_detail.get("tactics"):
            parts.append(f"Tactics: {', '.join(attack_detail['tactics'])}")
        
        if attack_detail.get("platforms"):
            parts.append(f"Platforms: {', '.join(attack_detail['platforms'])}")
        
        if attack_detail.get("data_sources"):
            parts.append(f"Data Sources: {', '.join(attack_detail['data_sources'])}")
        
        if attack_detail.get("mitigations"):
            mitigations = [m.get("name", "") for m in attack_detail["mitigations"]]
            parts.append(f"Mitigations: {', '.join(mitigations)}")
        
        return "\n\n".join(parts)
    
    def _build_mappings_text(
        self,
        technique_id: str,
        attack_detail: Dict[str, Any],
        mappings: List[Dict[str, Any]],
    ) -> str:
        """Build text representation of mappings."""
        parts = [
            f"ATT&CK Technique {technique_id} ({attack_detail.get('name', '')})",
            f"Maps to {len(mappings)} CIS Control scenarios:",
            "",
        ]
        
        for mapping in mappings:
            parts.append(
                f"Scenario: {mapping.get('scenario_id', '')} - {mapping.get('scenario_name', '')}"
            )
            parts.append(f"  Relevance Score: {mapping.get('relevance_score', 0.0):.2f}")
            parts.append(f"  Confidence: {mapping.get('confidence', 'medium')}")
            parts.append(f"  Rationale: {mapping.get('rationale', '')}")
            parts.append("")
        
        return "\n".join(parts)
    
    async def ingest_preview_files(
        self,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Ingest all preview files into vector store.
        
        Args:
            limit: Optional limit on number of files to process
            
        Returns:
            Ingestion summary
        """
        if not hasattr(self, 'vector_store_client'):
            await self.initialize()
        
        preview_files = self._load_preview_files()
        if limit:
            preview_files = preview_files[:limit]
        
        logger.info(f"Ingesting {len(preview_files)} preview files into {self.collection_name}")
        
        all_documents = []
        all_ids = []
        stats = {
            "total_files": len(preview_files),
            "successful": 0,
            "failed": 0,
            "total_documents": 0,
            "errors": [],
        }
        
        for preview_file in preview_files:
            try:
                preview = self._parse_preview_file(preview_file)
                if not preview:
                    stats["failed"] += 1
                    continue
                
                documents = self._build_documents_from_preview(preview)
                if not documents:
                    logger.warning(f"No documents generated from {preview_file.name}")
                    continue
                
                # Generate IDs for documents
                technique_id = preview.get("technique_id", "unknown")
                for i, doc in enumerate(documents):
                    doc_id = f"{technique_id}_{doc.metadata.get('type', 'unknown')}_{i}"
                    doc.metadata["id"] = doc_id
                    all_documents.append(doc)
                    all_ids.append(doc_id)
                
                stats["successful"] += 1
                stats["total_documents"] += len(documents)
                
            except Exception as e:
                logger.error(f"Error processing {preview_file.name}: {e}")
                stats["failed"] += 1
                stats["errors"].append(f"{preview_file.name}: {str(e)}")
        
        # Ingest all documents at once
        if all_documents:
            try:
                # Use vector store client's add_documents method
                # Convert to format expected by vector store client
                documents_text = [doc.page_content for doc in all_documents]
                metadatas = [doc.metadata for doc in all_documents]
                
                result_ids = await self.vector_store_client.add_documents(
                    collection_name=self.collection_name,
                    documents=documents_text,
                    metadatas=metadatas,
                    ids=all_ids,
                )
                
                logger.info(
                    f"Successfully ingested {len(result_ids)} documents into {self.collection_name}"
                )
                stats["ingested_documents"] = len(result_ids)
                
            except Exception as e:
                logger.error(f"Error ingesting documents: {e}")
                stats["ingestion_error"] = str(e)
        
        return stats
    
    async def ingest_single_preview(
        self,
        preview_file: str | Path,
    ) -> Dict[str, Any]:
        """
        Ingest a single preview file.
        
        Args:
            preview_file: Path to preview JSON file
            
        Returns:
            Ingestion result
        """
        if not hasattr(self, 'vector_store_client'):
            await self.initialize()
        
        preview_file = Path(preview_file)
        preview = self._parse_preview_file(preview_file)
        
        if not preview:
            return {"success": False, "error": "Failed to parse preview file"}
        
        documents = self._build_documents_from_preview(preview)
        if not documents:
            return {"success": False, "error": "No documents generated"}
        
        # Generate IDs and prepare for ingestion
        technique_id = preview.get("technique_id", "unknown")
        documents_text = []
        metadatas = []
        ids = []
        
        for i, doc in enumerate(documents):
            doc_id = f"{technique_id}_{doc.metadata.get('type', 'unknown')}_{i}"
            doc.metadata["id"] = doc_id
            documents_text.append(doc.page_content)
            metadatas.append(doc.metadata)
            ids.append(doc_id)
        
        try:
            result_ids = await self.vector_store_client.add_documents(
                collection_name=self.collection_name,
                documents=documents_text,
                metadatas=metadatas,
                ids=ids,
            )
            
            return {
                "success": True,
                "technique_id": technique_id,
                "documents_ingested": len(result_ids),
            }
        except Exception as e:
            logger.error(f"Error ingesting {preview_file.name}: {e}")
            return {"success": False, "error": str(e)}


async def ingest_preview_directory(
    preview_dir: str | Path,
    collection_name: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Convenience function to ingest all preview files from a directory.
    
    Args:
        preview_dir: Directory containing preview JSON files
        collection_name: Optional collection name (defaults to framework_controls)
        limit: Optional limit on number of files to process
        
    Returns:
        Ingestion summary
    """
    ingester = AttackEnrichmentIngester(preview_dir, collection_name=collection_name)
    return await ingester.ingest_preview_files(limit=limit)
