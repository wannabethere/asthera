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
        formatted_docs = []
        for doc in documents:
            formatted = {
                "instruction": doc.metadata.get("instruction", ""),
                "question": doc.page_content,
                "instruction_id": doc.metadata.get("instruction_id", ""),
            }
            formatted_docs.append(formatted)

        return {"documents": formatted_docs}


class Instructions:
    """Retrieves and formats instructions based on semantic similarity."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        similarity_threshold: float = 0.7,
        top_k: int = 10,
    ) -> None:
        """Initialize the Instructions processor.
        
        Args:
            document_store: The Chroma document store instance
            embedder: The text embedder instance
            similarity_threshold: Minimum similarity score for retrieved documents
            top_k: Maximum number of documents to retrieve
        """
        self._document_store = document_store
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._top_k = top_k
        self._formatter = OutputFormatter()

    async def run(
        self,
        query: str,
        project_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve and format instructions.
        
        Args:
            query: The query string to search for similar instructions
            project_id: Optional project ID to filter results
            
        Returns:
            Dictionary containing formatted retrieved documents
        """
        logger.info("Instructions Retrieval is running...")
        
        try:
            # Count documents to check if we have any to search
            count = self._count_documents(project_id)
            if not count:
                return {"documents": []}
            
            # Get default instructions
            default_docs = self._get_default_instructions(project_id)
            
            # Get custom instructions if query is provided
            custom_docs = []
            if query:
                # Generate query embedding
                embedding_result = await self._embedder.aembed_query(query)
                if embedding_result:
                    # Retrieve similar documents
                    custom_docs = self._retrieve_documents(
                        query=query,
                        query_embedding=embedding_result,
                        project_id=project_id
                    )
                    # Filter by similarity score
                    custom_docs = self._filter_by_score(custom_docs)
            
            # Merge and format results
            all_docs = default_docs + custom_docs
            return self._formatter.run(all_docs)
            
        except Exception as e:
            logger.error(f"Error retrieving instructions : {str(e)}")
            return {"documents": []}

    def _count_documents(self, project_id: Optional[str] = None) -> int:
        """Count documents in the store.
        
        Args:
            project_id: Optional project ID to filter count
            
        Returns:
            Number of documents matching the filter
        """
        # Get total count first
        total_count = self._document_store.collection.count()
        
        # If no project_id filter, return total count
        if not project_id:
            return total_count
            
        # If project_id filter, get filtered count
        if project_id:
            where = {"project_id": {"$eq": project_id}}
            filtered_docs = self._document_store.collection.get(
                where=where,
                limit=total_count
            )
        else:
            filtered_docs = self._document_store.collection.get(
                limit=total_count
            )
               
        
        return len(filtered_docs.get("documents", []))

    def _get_default_instructions(
        self,
        project_id: Optional[str] = None
    ) -> List[LangchainDocument]:
        """Retrieve default instructions from the store.
        
        Args:
            project_id: Optional project ID to filter results
            
        Returns:
            List of default instruction documents
        """
        try:
            if project_id:
                where = {"project_id": {"$eq": project_id}}    
                results = self._document_store.collection.get(
                    where=where,
                    limit=self._top_k
                )
            else:
                results = self._document_store.collection.get(
                    limit=self._top_k
                )
            
            if not results or not results.get("documents"):
                return []
                
            # Combine documents with their metadata
            combined_docs = []
            for doc, metadata in zip(results["documents"], results["metadatas"]):
                # Create document with text and metadata
                combined_docs.append({
                    "text": doc,  # Keep original text
                    "metadata": {
                        **metadata,
                        "instruction": metadata.get("instruction", ""),
                        "instruction_id": metadata.get("instruction_id", ""),
                        "chain_of_thought": metadata.get("chain_of_thought", ""),
                        "sql": metadata.get("sql", ""),
                        "is_default": metadata.get("is_default", False)
                    }
                })
            
            return [
                LangchainDocument(
                    page_content=doc["text"],
                    metadata=doc["metadata"]
                )
                for doc in combined_docs
            ]
        except Exception as e:
            logger.error(f"Error retrieving default instructions: {str(e)}")
            return []

    def _retrieve_documents(
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
        try:
            if project_id:
                where = {"project_id": {"$eq": project_id}}
                results = self._document_store.semantic_search(
                    query=query,
                    query_embedding=[query_embedding],
                    where=where,
                    k=self._top_k
                )
            else:
                results = self._document_store.semantic_search(
                    query=query,
                    query_embedding=[query_embedding],
                    k=self._top_k
                )
            print(f"results in instructions: {results}")
            if not results or not results.get("documents"):
                return []
                
            # Get documents from first query result
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            
            # Combine documents with their metadata and distances
            combined_docs = []
            for doc, metadata, distance in zip(documents, metadatas, distances):
                # Create document with text and metadata
                combined_docs.append({
                    "text": doc,  # Keep original text
                    "metadata": {
                        **metadata,
                        "score": 1.0 - distance,
                        "instruction": metadata.get("instruction", ""),
                        "instruction_id": metadata.get("instruction_id", ""),
                        "chain_of_thought": metadata.get("chain_of_thought", ""),
                        "sql": metadata.get("sql", ""),
                        "is_default": metadata.get("is_default", False)
                    }
                })
            print(f"combined_docs in instructions: {combined_docs}")
            return [
                LangchainDocument(
                    page_content=doc["text"],
                    metadata=doc["metadata"]
                )
                for doc in combined_docs
            ]
        except Exception as e:
            logger.error(f"Error retrieving similar documents: {str(e)}")
            return []

    def _filter_by_score(self, documents: List[LangchainDocument]) -> List[LangchainDocument]:
        """Filter documents by similarity score.
        
        Args:
            documents: List of documents to filter
            
        Returns:
            List of documents that meet the similarity threshold
        """
        try:
            return [
                doc for doc in documents
                if doc.metadata.get("score", 0) >= self._similarity_threshold
            ]
        except Exception as e:
            logger.error(f"Error filtering documents by score: {str(e)}")
            return []


if __name__ == "__main__":
    # Example usage
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    from agents.app.settings import get_settings
    
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
        collection_name="instructions"
    )
    
    processor = Instructions(
        document_store=doc_store,
        embedder=embeddings,
        similarity_threshold=0.7,
        top_k=10
    )
    
    # Example query
    query = "hello"
    
    # Process the query
    import asyncio
    result = asyncio.run(processor.run(query, project_id="test"))
    print(f"Retrieved instructions: {result}")
