import logging
import uuid
from typing import Any, Dict, List, Optional

from tqdm import tqdm
from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

logger = logging.getLogger("genieml-agents")


class ViewChunker:
    """
    A component that processes views from an MDL (Model Definition Language) file and converts them into Document objects.

    The component takes views in the following MDL format:
    {
        "views": [
            {
                "statement": "SELECT * FROM employees",
                "properties": {
                    "historical_queries": [], # List of previous related queries
                    "question": "What is the average salary of employees?", # Current query
                    "summary": "The average salary of employees is $50,000.", # Summary for the query
                    "viewId": "1234567890" # Unique identifier
                }
            }
        ]
    }

    And converts each view into a Document with:
    - page_content: Concatenated string of historical queries and current question
    - metadata: Dictionary containing:
        {
            "summary": "Generated description/answer",
            "statement": "SQL statement",
            "viewId": "Unique view identifier",
            "project_id": "Optional project identifier"
        }

    The Documents are then stored in the document store for later retrieval.
    """

    async def run(self, mdl: Dict[str, Any], project_id: Optional[str] = None) -> Dict[str, Any]:
        def _get_content(view: Dict[str, Any]) -> str:
            properties = view.get("properties", {})
            historical_queries = properties.get("historical_queries", [])
            question = properties.get("question", "")
            statement = view.get("statement", "")
            import json
            return json.dumps({"type":"HISTORY", "historical_queries": historical_queries, "question": question, "statement": statement})

        def _get_meta(view: Dict[str, Any]) -> Dict[str, Any]:
            print("view in historical_question: ", view)
            properties = view.get("properties", {})
            return {
                "summary": properties.get("summary", ""),
                "type": "HISTORY",
                "viewId": properties.get("viewId", ""),
            }

        def _additional_meta() -> Dict[str, Any]:
            return {"project_id": project_id} if project_id else {}

        chunks = [
            {
                "id": str(uuid.uuid4()),
                "page_content": _get_content(view),
                "metadata": {**_get_meta(view), **_additional_meta()},
            }
            for view in mdl["views"]
        ]

        return {
            "documents": [
                LangchainDocument(**chunk)
                for chunk in tqdm(
                    chunks,
                    desc=f"Project ID: {project_id}, Chunking views into documents",
                )
            ]
        }


class HistoricalQuestion:
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
    ) -> None:
        """Initialize the HistoricalQuestion processor.
        
        Args:
            document_store: The Chroma document store instance
            embedder: The document embedder instance
        """
        self._document_store = document_store
        self._embedder = embedder
        self._chunker = ViewChunker()
        self._writer = AsyncDocumentWriter(
            document_store=document_store,
            policy=DuplicatePolicy.OVERWRITE,
        )

    async def run(
        self, mdl_str: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process and index historical questions."""
        logger.info(f"Starting historical questions processing for project: {project_id}")
        
        try:
            # Parse MDL string
            logger.info("Parsing MDL string")
            import json
            mdl = json.loads(mdl_str)
            logger.info("MDL string parsed successfully")
            
            # Convert to documents
            logger.info("Converting MDL to documents")
            doc_result = await self._chunker.run(
                mdl=mdl,
                project_id=project_id,
            )
            logger.info(f"Created {len(doc_result['documents'])} documents")
            
            # Generate embeddings
            logger.info("Generating embeddings for documents")
            texts = [doc.page_content for doc in doc_result["documents"]]
            embeddings = await self._embedder.aembed_documents(texts)
            
            # Prepare documents for ChromaDB
            logger.info("Preparing documents for ChromaDB")
            documents = []
            for doc, embedding in zip(doc_result["documents"], embeddings):
                # Create a new LangchainDocument with the embedding
                new_doc = LangchainDocument(
                    page_content=doc.page_content,
                    metadata=doc.metadata
                )
                print("new_doc in historical_question: ", new_doc)
                #new_doc.metadata["embedding"] = embedding
                documents.append(new_doc)
                
            logger.info(f"Prepared {len(documents)} documents with embeddings")
            
            # Write documents to store
            logger.info("Writing documents to store")
            write_result = await self._writer.run(documents=documents)
            logger.info(f"Successfully wrote {write_result['documents_written']} documents to store")
            
            result = {
                "documents_written": write_result["documents_written"],
                "project_id": project_id
            }
            logger.info(f"Historical questions processing completed successfully: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing historical questions: {str(e)}"
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
    """
    from src.pipelines.common import dry_run_pipeline

    dry_run_pipeline(
        HistoricalQuestion,
        "historical_question_indexing",
        mdl_str='{"models": [], "views": [], "relationships": [], "metrics": []}',
    )
    """
