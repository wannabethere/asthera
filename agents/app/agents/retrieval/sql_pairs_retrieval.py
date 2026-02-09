import logging
from typing import Any, Dict, List, Optional
import json

from app.storage.documents import DocumentChromaStore

logger = logging.getLogger("genieml-agents")


class SqlPairsRetrieval:
    """Retrieves and processes SQL pairs based on queries."""
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        similarity_threshold: float = 0.3,  # Threshold for normalized similarity
        max_retrieval_size: int = 10,
    ) -> None:
        """Initialize the SQL pairs retrieval processor.
        
        Args:
            document_store: The Chroma document store instance
            embedder: The text embedder instance
            similarity_threshold: Minimum similarity score for retrieved documents
            max_retrieval_size: Maximum number of documents to retrieve
        """
        self._document_store = document_store
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._max_retrieval_size = max_retrieval_size

    def _count_documents(self, project_id: Optional[str] = None) -> int:
        """Count documents in the store.
        
        Args:
            project_id: Optional project ID to filter by
            
        Returns:
            Number of documents
        """
        try:
            # Get total count first
            total_count = self._document_store.collection.count()
            
            # If no project_id filter, return total count
            if not project_id:
                return total_count
                
            # If project_id filter, get filtered count
            where = {"project_id": {"$eq": project_id}}
            filtered_docs = self._document_store.collection.get(
                where=where,
                limit=total_count
            )
            return len(filtered_docs.get("documents", []))
        except Exception as e:
            logger.error(f"Error counting documents: {str(e)}")
            return 0

    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Get embedding for the query.
        
        Args:
            query: The query string to embed
            
        Returns:
            List of floats representing the embedding vector or None if failed
        """
        try:
            return await self._embedder.aembed_query(query)
        except Exception as e:
            logger.error(f"Error getting query embedding: {str(e)}")
            return None

    def _retrieve_documents(
        self,
        query: str,
        query_embedding: List[float],
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve documents using query embedding.
        
        Args:
            query_embedding: The query embedding vector
            project_id: Optional project ID to filter by
            
        Returns:
            List of retrieved documents
        """
        try:
            # Only add project_id filter if it's not "default"
            where = None
            if project_id and project_id != "default":
                where = {"project_id": {"$eq": project_id}}
            
            logger.info(f"DEBUG: SQL pairs search with filter: project_id={project_id}")
            results = self._document_store.semantic_search(
                query=query,
                query_embedding=[query_embedding],
                where=where,
                k=self._max_retrieval_size
            )
           
            if not results:
                print(f"results in sql_pairs_retrieval: no results")
                return []
            
            # Process results as a list
            processed_results = []
            for result in results:
                try:
                    content = result.get('content', '')
                    if not content:
                        continue
                        
                    # Parse content as JSON
                    try:
                        content_dict = json.loads(content)
                    except:
                        continue
                        
                    if not isinstance(content_dict, dict):
                        continue
                        
                    # Get SQL pair information
                    sql_pair = {
                        'question': content_dict.get('question', ''),
                        'sql': content_dict.get('sql', ''),
                        'instructions': content_dict.get('instructions', ''),
                        'chain_of_thought': content_dict.get('chain_of_thought'),
                        'score': result.get('score', 0.0)  # Add score from result
                    }
                    
                    # Add metadata if available
                    metadata = result.get('metadata', {})
                    if metadata:
                        sql_pair.update({
                            'sql_pair_id': metadata.get('sql_pair_id'),
                            'project_id': metadata.get('project_id')
                        })
                    
                    processed_results.append(sql_pair)
                    
                except Exception as e:
                    logger.warning(f"Error processing result: {str(e)}")
                    continue
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []

    def _normalize_distance(self, distance: float) -> float:
        """Normalize distance to similarity score.
        
        Args:
            distance: The raw distance from the embedding model
            
        Returns:
            Normalized similarity score between 0 and 1
        """
        # Normalize distance to [0, 1] range
        # Assuming distances are typically between 0 and 2
        normalized_distance = min(max(distance, 0), 2) / 2
        # Convert to similarity score (1 - normalized_distance)
        return 1.0 - normalized_distance

    def _filter_by_score(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter documents by similarity score.
        
        Args:
            documents: List of documents with scores
            
        Returns:
            Filtered list of documents
        """
        try:
            filtered = []
            for doc in documents:
                # Get score directly from the document
                score = doc.get("score", 0.0)
               
                
                if score >= self._similarity_threshold:
                    filtered.append({
                        "question": doc.get("question", ""),
                        "sql": doc.get("sql", ""),
                        "instructions": doc.get("instructions", ""),
                        "score": score,
                        "sql_pair_id": doc.get("sql_pair_id"),
                        "project_id": doc.get("project_id")
                    })
                    
            # Sort by score in descending order
            filtered.sort(key=lambda x: x["score"], reverse=True)
            return filtered[:self._max_retrieval_size]
        except Exception as e:
            logger.error(f"Error filtering documents by score: {str(e)}")
            return []

    async def run(
        self,
        query: str,
        project_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, str]]]:
        """Retrieve and process SQL pairs.
        
        Args:
            query: The query string to search for similar SQL pairs
            project_id: Optional project ID to filter results
            
        Returns:
            Dictionary containing formatted results
            
        Raises:
            Exception: If retrieval process fails
        """
        logger.info("SQL pairs retrieval is running...")
        
        try:
            # Get query embedding
            embedding_result = await self._get_query_embedding(query)
            if not embedding_result:
                return {"documents": []}
                
            # Retrieve documents
            documents = self._retrieve_documents(
                query=query,
                query_embedding=embedding_result,  # Pass the embedding vector directly
                project_id=project_id
            )
            
            # Filter by score and format output
            filtered_docs = self._filter_by_score(documents)
            
            return {"documents": filtered_docs}
            
        except Exception as e:
            logger.error(f"Error in SQL pairs retrieval: {str(e)}")
            return {"documents": []}


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
    
    # Initialize document store
    persistent_client = chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
    doc_store = DocumentChromaStore(
        persistent_client=persistent_client,
        collection_name="sql_pairs"
    )
    
    # Initialize processor
    processor = SqlPairsRetrieval(
        document_store=doc_store,
        embedder=embeddings,
        similarity_threshold=0.3,
        max_retrieval_size=10
    )
    
    # Example query
    query = "Show me sales data for last month"
    
    # Process the query
    import asyncio
    result = asyncio.run(processor.run(query, project_id="test"))
    print(f"Retrieved SQL pairs: {result}")
