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
            properties = view.get("properties", {})
            return {
                "summary": properties.get("summary", ""),
                "type": "HISTORY",
                "viewId": properties.get("viewId", ""),
            }

        def _extract_query_patterns(view: Dict[str, Any]) -> List[str]:
            """Extract query patterns from historical question."""
            query_patterns = []
            properties = view.get("properties", {})
            question = properties.get("question", "")
            historical_queries = properties.get("historical_queries", [])
            
            if question:
                query_patterns.append(question)
            
            # Add patterns based on historical queries
            for hq in historical_queries[:3]:  # Limit to first 3
                if isinstance(hq, str):
                    query_patterns.append(hq)
            
            # Add generic patterns
            query_patterns.extend([
                "What are similar queries that have been asked?",
                "Show me historical questions related to this",
                "What questions have been asked before?",
                "Find similar past queries"
            ])
            
            return query_patterns

        def _extract_use_cases(view: Dict[str, Any]) -> List[str]:
            """Extract use cases from historical question."""
            use_cases = [
                "Query pattern discovery and reuse",
                "Historical question retrieval",
                "Similar query matching",
                "Past query analysis",
                "Question recommendation based on history"
            ]
            return use_cases

        def _additional_meta() -> Dict[str, Any]:
            return {"project_id": project_id} if project_id else {}

        chunks = []
        for view in mdl["views"]:
            content = _get_content(view)
            meta = _get_meta(view)
            query_patterns = _extract_query_patterns(view)
            use_cases = _extract_use_cases(view)
            
            # Build enriched text
            enriched_text_parts = [content]
            
            if query_patterns:
                enriched_text_parts.append("\n\nANSWERS THESE QUESTIONS:")
                for pattern in query_patterns:
                    enriched_text_parts.append(f"  • {pattern}")
            
            if use_cases:
                enriched_text_parts.append("\n\nUSE CASES AND APPLICATIONS:")
                for use_case in use_cases:
                    enriched_text_parts.append(f"  • {use_case}")
            
            enriched_text = "\n".join(enriched_text_parts)
            
            chunk = {
                "id": str(uuid.uuid4()),
                "text": enriched_text,
                "page_content": content,
                "metadata": {
                    **meta,
                    "query_patterns": query_patterns,
                    "use_cases": use_cases,
                    **_additional_meta()
                },
            }
            chunks.append(chunk)

        return {
            "documents": [
                LangchainDocument(
                    page_content=chunk["page_content"],
                    metadata=chunk["metadata"]
                )
                for chunk in tqdm(
                    chunks,
                    desc=f"Project ID: {project_id}, Chunking views into documents",
                )
            ],
            "points_data": chunks  # Also return points_data for direct Qdrant insertion
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
            
            # Check if document_store is Qdrant-based and use direct points
            from app.storage.qdrant_store import DocumentQdrantStore
            if isinstance(self._document_store, DocumentQdrantStore):
                logger.info("Using direct Qdrant points insertion for historical questions")
                points_data = doc_result.get("points_data", [])
                if points_data:
                    write_result = self._document_store.add_points_direct(
                        points_data=points_data,
                        log_schema=True
                    )
                    logger.info(f"Successfully wrote {write_result['documents_written']} points to Qdrant")
                else:
                    # Fallback to documents if points_data not available
                    logger.warning("points_data not available, falling back to documents")
                    write_result = await self._writer.run(documents=doc_result["documents"])
            else:
                # Use standard document writer for ChromaDB
                logger.info("Using standard document writer for ChromaDB")
                documents = []
                for doc in doc_result["documents"]:
                    new_doc = LangchainDocument(
                        page_content=doc.page_content,
                        metadata=doc.metadata
                    )
                    documents.append(new_doc)
                
                logger.info(f"Prepared {len(documents)} documents")
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
    """
    from src.pipelines.common import dry_run_pipeline

    dry_run_pipeline(
        HistoricalQuestion,
        "historical_question_indexing",
        mdl_str='{"models": [], "views": [], "relationships": [], "metrics": []}',
    )
    """
