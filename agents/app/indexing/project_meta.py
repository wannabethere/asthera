import logging
import uuid
from typing import Any, Dict, Optional

from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

logger = logging.getLogger("genieml-agents")


class ProjectMeta:
    def __init__(
        self,
        document_store: DocumentChromaStore,
    ) -> None:
        """Initialize the ProjectMeta processor.
        
        Args:
            document_store: The Chroma document store instance
        """
        self._document_store = document_store
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )

    async def run(
        self, mdl_str: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process and index project metadata."""
        logger.info(f"Starting project metadata processing for project: {project_id}")
        
        try:
            # Parse MDL string
            logger.info("Parsing MDL string")
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully")
            
            # Extract query patterns and use cases from MDL (project_metadata.json)
            # If not present, use defaults with project_id substitution
            query_patterns_raw = mdl.get("queryPatterns", [])
            use_cases_raw = mdl.get("useCases", [])
            
            # Process query patterns: replace project_id placeholder if present
            if query_patterns_raw:
                query_patterns = [
                    pattern.replace("{project_id}", project_id) if project_id and "{project_id}" in pattern
                    else pattern.replace("hr_compliance_risk", project_id) if project_id and "hr_compliance_risk" in pattern
                    else pattern
                    for pattern in query_patterns_raw
                ]
            else:
                # Fallback to default patterns
                query_patterns = [
                    f"What is the metadata for project {project_id}?",
                    f"Show me project information for {project_id}",
                    f"What is the data source for {project_id}?",
                    f"When was project {project_id} created?",
                    "What are the project details?",
                    "Show me project metadata"
                ]
            
            # Use cases from MDL or defaults
            if use_cases_raw:
                use_cases = use_cases_raw
            else:
                use_cases = [
                    "Project information retrieval",
                    "Data source identification",
                    "Project metadata lookup",
                    "Project lifecycle tracking"
                ]
            
            # Create enriched content
            page_content = json.dumps({
                "type": "PROJECT_META",
                "data_source": mdl.get("data_source", ""),
                "created_at": mdl.get("created_at", ""),
                "updated_at": mdl.get("updated_at", "")
            })
            
            # Build enriched text
            enriched_text_parts = [page_content]
            
            if query_patterns:
                enriched_text_parts.append("\n\nANSWERS THESE QUESTIONS:")
                for pattern in query_patterns:
                    enriched_text_parts.append(f"  • {pattern}")
            
            if use_cases:
                enriched_text_parts.append("\n\nUSE CASES AND APPLICATIONS:")
                for use_case in use_cases:
                    enriched_text_parts.append(f"  • {use_case}")
            
            enriched_text = "\n".join(enriched_text_parts)
            
            # Create point data for Qdrant
            point_data = {
                "id": str(uuid.uuid4()),
                "text": enriched_text,
                "page_content": page_content,
                "metadata": {
                    "type": "PROJECT_META",
                    "project_id": project_id,
                    "data_source": mdl.get("data_source", ""),
                    "created_at": mdl.get("created_at", ""),
                    "updated_at": mdl.get("updated_at", ""),
                    "query_patterns": query_patterns,
                    "use_cases": use_cases,
                }
            }
            
            # Create document for compatibility
            document = LangchainDocument(
                page_content=page_content,
                metadata=point_data["metadata"]
            )
            
            logger.info("Document created successfully")
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for project metadata")
                write_result = self._document_store.add_points_direct(
                    points_data=[point_data],
                    log_schema=True
                )
                logger.info(f"Successfully wrote {write_result['documents_written']} points to Qdrant")
            else:
                # Use standard document writer for ChromaDB
                logger.info("Writing document to store")
                write_result = await self._writer.run(documents=[document])
                logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Project metadata processing completed successfully: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing project metadata: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error("Traceback: %s", traceback.format_exc())
            return {
                "documents_written": 0,
                "project_id": project_id,
                "error": str(e)
            }

    async def clean(self, project_id: Optional[str] = None) -> None:
        """Clean documents for the specified project.
        
        Args:
            project_id: Optional project ID to clean documents for
        """
        try:
            # Delete documents with the specified project_id
            if project_id:
                self._document_store.collection.delete(
                    where={"project_id": project_id}
                )
                logger.info(f"Cleaned documents for project ID: {project_id}")
            else:
                # Delete all documents if no project_id specified
                self._document_store.collection.delete()
                logger.info("Cleaned all documents")
                
        except Exception as e:
            logger.error(f"Error cleaning documents: {str(e)}")
            raise


if __name__ == "__main__":
    # Example usage
    import chromadb
    from agents.app.settings import get_settings
    
    settings = get_settings()
    
    # Initialize document store and processor
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="project_meta"
    )
    
    processor = ProjectMeta(
        document_store=doc_store
    )
    
    # Example MDL string
    mdl_str = '{"data_source": "local_file"}'
    
    # Process the metadata
    import asyncio
    result = asyncio.run(processor.run(mdl_str, project_id="test"))
    print(f"Processed project metadata: {result}")
