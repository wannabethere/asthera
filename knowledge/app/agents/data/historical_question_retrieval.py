import logging
from typing import Any, Dict, List, Optional
import orjson

from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import DocumentChromaStore

logger = logging.getLogger("genieml-agents")


class OutputFormatter:
    """Formats retrieved documents into a standardized output format."""
    
    def run(self, documents: List[LangchainDocument]) -> Dict[str, List[Dict[str, Any]]]:
        """Format documents into a standardized output format.
        
        Args:
            documents: List of LangchainDocument objects to format
            
        Returns:
            Dictionary containing formatted documents
        """
        formatted_docs = [
            {
                "question": doc.page_content,
                "summary": doc.metadata.get("summary", ""),
                "statement": doc.metadata.get("statement") or doc.metadata.get("sql"),
                "viewId": doc.metadata.get("viewId", ""),
            }
            for doc in documents
        ]

        return {"documents": formatted_docs}


class HistoricalQuestionRetrieval:
    """Retrieves historical questions based on semantic similarity."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        similarity_threshold: float = 0.9,
    ) -> None:
        """Initialize the Historical Question Retrieval processor.
        
        Args:
            document_store: The Chroma document store instance
            embedder: The text embedder instance
            similarity_threshold: Minimum similarity score for retrieved documents
        """
        self._document_store = document_store
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._formatter = OutputFormatter()

    async def run(
        self,
        query: str,
        project_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve and format historical questions.
        
        Args:
            query: The query string to search for similar questions
            project_id: Optional project ID to filter results
            
        Returns:
            Dictionary containing formatted retrieved documents
        """
        logger.info("HistoricalQuestion Retrieval is running...")
        
        try:
            
            # Generate query embedding
            embedding_result = await self._embedder.aembed_query(query)
            if not embedding_result:
                return {"documents": []}
            
            # Retrieve similar documents
            retrieved_docs = await self._retrieve_documents(
                query,
                embedding_result,
                project_id
            )
            if not retrieved_docs:
                return {"documents": []}
            
            # Filter by similarity score
            filtered_docs = self._filter_by_score(retrieved_docs)
            if not filtered_docs:
                return {"documents": []}
            
            # Format output
            return self._formatter.run(filtered_docs)
            
        except Exception as e:
            logger.error(f"Error retrieving historical questions: {str(e)}")
            return {"documents": []}

    async def _count_documents(self, project_id: Optional[str] = None) -> int:
        """Count documents in the store.
        
        Args:
            project_id: Optional project ID to filter count
            
        Returns:
            Number of documents matching the filter
        """
        return self._document_store.collection.count()
       
    async def _retrieve_documents(
        self,
        query: str,
        query_embedding: List[float],
        project_id: Optional[str] = None
    ) -> List[LangchainDocument]:
        """Retrieve similar documents from the store.
        
        Args:
            query_embedding: The query embedding vector
            project_id: Optional project ID to filter results
            
        Returns:
            List of retrieved LangchainDocument objects
        """
        # Only add project_id filter if it's not "default"
        where = {"project_id": project_id} if project_id and project_id != "default" else None
        
        results = self._document_store.semantic_search(
            query=query,
            query_embedding=[query_embedding],
            where=where,
            k=10  # Adjust as needed
        )
        
        if not results or not results.get("documents"):
            return []
        
        # Convert results to LangchainDocument objects
        documents = []
        for doc, metadata in zip(results["documents"][0], results["metadatas"][0]):
            try:
                # Parse the JSON document
                doc_content = orjson.loads(doc)
                
                # Create the document with proper content and metadata
                documents.append(LangchainDocument(
                    page_content=doc_content.get("question", ""),
                    metadata={
                        "statement": doc_content.get("statement", ""),
                        "type": doc_content.get("type", ""),
                        "viewId": metadata.get("viewId", ""),
                        "summary": metadata.get("summary", ""),
                        "project_id": metadata.get("project_id", ""),
                        "id": metadata.get("id", "")
                    }
                ))
            except Exception as e:
                logger.warning(f"Failed to process document: {str(e)}")
                continue
        
        return documents

    def _filter_by_score(self, documents: List[LangchainDocument]) -> List[LangchainDocument]:
        """Filter documents by similarity score.
        
        Args:
            documents: List of documents to filter
            
        Returns:
            List of documents that meet the similarity threshold
        """
        return [
            doc for doc in documents
            if doc.metadata.get("score", 0) >= self._similarity_threshold
        ]


if __name__ == "__main__":
    # Example usage
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    from app.core.settings import get_settings
    
    settings = get_settings()
    
    # Initialize embeddings
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.OPENAI_API_KEY
    )
    
    # Initialize document store and processor
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="historical_questions"
    )
    
    processor = HistoricalQuestionRetrieval(
        document_store=doc_store,
        embedder=embeddings,
        similarity_threshold=0.9
    )
    
    # Example query
    query = "this is a test query"
    
    # Process the query
    import asyncio
    result = asyncio.run(processor.run(query, project_id="test"))
    print(f"Retrieved historical questions: {result}")
