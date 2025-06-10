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
            
            # Create document from metadata
            logger.info("Creating document from metadata")
            document = LangchainDocument(
                page_content=json.dumps({"type":"PROJECT_META", "data_source": mdl.get("data_source", ""), "created_at": mdl.get("created_at", ""), "updated_at": mdl.get("updated_at", "")}),
                metadata={
                    "type": "PROJECT_META",
                    "project_id": project_id,
                    "data_source": mdl.get("data_source", ""),
                    "created_at": mdl.get("created_at", ""),
                    "updated_at": mdl.get("updated_at", ""),
                }
            )
            logger.info("Document created successfully")
            print("document in project_meta: ", document)
            # Write document to store
            logger.info("Writing document to store")
            
            write_result = await self._writer.run(documents=[document])
            logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Project metadata processing completed successfully: {result}")
            
            result = {
                "documents_written": 0,
                "project_id": project_id
            }
            return result
            
        except Exception as e:
            error_msg = f"Error processing project metadata: {str(e)}"
            logger.error(error_msg)
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
