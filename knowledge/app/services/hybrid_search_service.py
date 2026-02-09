"""
Hybrid Search Service for Metadata Generation Agents

Implements hybrid search combining:
1. Dense vector similarity (semantic understanding)
2. BM25 sparse retrieval (keyword matching)
3. Metadata filtering (structured constraints)

Based on the hybrid search architecture described in docs/hybrid_search.md
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from collections import defaultdict
from langchain_openai import OpenAIEmbeddings
import numpy as np

if TYPE_CHECKING:
    from app.storage.vector_store import VectorStoreClient

logger = logging.getLogger(__name__)


class BM25Ranker:
    """
    BM25 ranking implementation for keyword-based document retrieval.
    
    BM25 is a ranking function used to estimate the relevance of documents
    to a given search query. It combines term frequency (TF) with inverse
    document frequency (IDF) in a way that handles term saturation better
    than traditional TF-IDF.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 ranker.
        
        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.doc_freqs = defaultdict(int)  # Document frequency for each term
        self.idf = {}  # Inverse document frequency
        self.doc_lens = []  # Document lengths
        self.avgdl = 0  # Average document length
        self.doc_count = 0
        self.vocab = {}  # Vocabulary mapping terms to indices
        self._documents = []  # Store documents for scoring
        self._all_terms = []  # Store tokenized documents
        
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Simple tokenization: lowercase and split on non-word characters
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def fit(self, documents: List[str]):
        """
        Fit the BM25 ranker on a collection of documents.
        
        Args:
            documents: List of document strings to index
        """
        if not documents:
            return
        
        self._documents = documents
        self.doc_count = len(documents)
        self.doc_lens = []
        self._all_terms = []
        self.doc_freqs = defaultdict(int)  # Reset document frequencies
        
        # Tokenize all documents and build vocabulary
        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_lens.append(len(tokens))
            self._all_terms.append(tokens)
            
            # Count document frequency for each term
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1
        
        # Calculate average document length
        self.avgdl = sum(self.doc_lens) / self.doc_count if self.doc_count > 0 else 0
        
        # Calculate IDF for each term
        self.idf = {}
        for term, df in self.doc_freqs.items():
            # IDF = log((N - df + 0.5) / (df + 0.5))
            # where N is total number of documents
            self.idf[term] = np.log((self.doc_count - df + 0.5) / (df + 0.5))
    
    def get_scores(self, query: str) -> List[float]:
        """
        Calculate BM25 scores for all documents given a query.
        
        Args:
            query: Search query string
            
        Returns:
            List of BM25 scores for each document
        """
        if self.doc_count == 0 or not self._all_terms:
            return []
        
        query_terms = self._tokenize(query)
        scores = []
        
        for i, doc_tokens in enumerate(self._all_terms):
            score = 0.0
            
            # Calculate term frequency in document
            term_freqs = defaultdict(int)
            for term in doc_tokens:
                term_freqs[term] += 1
            
            # Calculate BM25 score for this document
            for term in query_terms:
                if term in term_freqs:
                    tf = term_freqs[term]
                    idf = self.idf.get(term, 0)
                    
                    # BM25 formula: IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avgdl)))
                    doc_len = self.doc_lens[i]
                    length_norm = (1 - self.b + self.b * (doc_len / self.avgdl)) if self.avgdl > 0 else 1
                    score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * length_norm)
            
            scores.append(score)
        
        return scores
    
    def rank(self, query: str, documents: Optional[List[str]] = None, k: Optional[int] = None) -> List[Tuple[int, float]]:
        """
        Rank documents based on BM25 score for a query.
        
        Args:
            query: Search query string
            documents: Optional list of document strings to rank (uses fitted documents if None)
            k: Number of top results to return (None for all)
            
        Returns:
            List of (document_index, score) tuples, sorted by score descending
        """
        # Re-fit if new documents provided
        if documents is not None:
            self.fit(documents)
        
        if self.doc_count == 0:
            return []
        
        scores = self.get_scores(query)
        
        # Create list of (index, score) tuples
        ranked = [(i, score) for i, score in enumerate(scores)]
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k if specified
        if k is not None:
            return ranked[:k]
        
        return ranked


class HybridSearchService:
    """
    Hybrid search service combining dense vector similarity and BM25 ranking.
    
    This service provides context-aware retrieval for metadata generation agents,
    combining semantic understanding (via embeddings) with keyword matching (via BM25).
    """
    
    def __init__(
        self,
        vector_store_client: "VectorStoreClient",
        collection_name: str,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3
    ):
        """
        Initialize hybrid search service.
        
        Args:
            vector_store_client: VectorStoreClient instance (supports ChromaDB, Qdrant, etc.)
            collection_name: Name of the collection
            embeddings_model: Optional embeddings model (defaults to OpenAI)
            dense_weight: Weight for dense vector similarity (default: 0.7)
            sparse_weight: Weight for BM25 sparse retrieval (default: 0.3)
        """
        self.vector_store_client = vector_store_client
        self.collection_name = collection_name
        # Get embeddings model from vector store client if not provided
        if embeddings_model is None:
            # We'll get it from vector_store_client when needed
            self.embeddings_model = None
        else:
            self.embeddings_model = embeddings_model
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        
        # Ensure weights sum to 1.0
        total_weight = dense_weight + sparse_weight
        if total_weight != 1.0:
            logger.warning(f"Weights sum to {total_weight}, normalizing to 1.0")
            self.dense_weight = dense_weight / total_weight
            self.sparse_weight = sparse_weight / total_weight
        
        self.bm25_ranker = BM25Ranker()
        
        # Collection will be accessed via vector_store_client
        self._initialized = False
    
    # Note: Filter normalization is now handled by vector_store_client.normalize_filter()
    # This ensures vector store-specific logic (ChromaDB $in conversion, etc.) is managed
    # externally in the vector store abstraction layer, not hardcoded here.
    
    async def _get_embeddings_model(self) -> OpenAIEmbeddings:
        """Get embeddings model from vector store client or use cached one"""
        if self.embeddings_model is None:
            self.embeddings_model = await self.vector_store_client.get_embeddings_model()
        return self.embeddings_model
    
    async def _ensure_initialized(self):
        """Ensure the service is initialized"""
        if not self._initialized:
            # Get embeddings model
            if self.embeddings_model is None:
                self.embeddings_model = await self.vector_store_client.get_embeddings_model()
            # Ensure collection exists
            await self.vector_store_client.get_collection(
                collection_name=self.collection_name,
                create_if_not_exists=True
            )
            self._initialized = True
            logger.info(f"Initialized hybrid search service with collection: {self.collection_name}")
    
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        candidate_multiplier: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining dense vector similarity and BM25 ranking.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            where: Optional metadata filter dictionary
            candidate_multiplier: Multiplier for initial candidate retrieval (default: 2)
            
        Returns:
            List of search results with combined scores
        """
        await self._ensure_initialized()
        
        try:
            # Log which collection is being queried
            logger.info(f"Querying collection: '{self.collection_name}' with query: '{query[:100]}...' (top_k={top_k})")
            
            # Try to get collection count for debugging
            try:
                collection = await self.vector_store_client.get_collection(
                    collection_name=self.collection_name,
                    create_if_not_exists=False
                )
                if hasattr(collection, 'count'):
                    count = collection.count()
                    logger.info(f"Collection '{self.collection_name}' has {count} documents")
                    if count == 0:
                        logger.warning(f"Collection '{self.collection_name}' is empty - no results will be returned")
                elif hasattr(collection, '__len__'):
                    count = len(collection)
                    logger.info(f"Collection '{self.collection_name}' has {count} documents")
                else:
                    logger.debug(f"Could not determine count for collection '{self.collection_name}'")
            except Exception as e:
                logger.debug(f"Could not get collection count for '{self.collection_name}': {e}")
            
            # Step 1: Dense vector search (semantic similarity)
            # Get more candidates for re-ranking
            candidate_k = top_k * candidate_multiplier
            
            # Get embeddings model
            embeddings_model = await self._get_embeddings_model()
            
            # Generate embeddings using the current embeddings model to ensure dimension consistency
            query_embedding = embeddings_model.embed_query(query)
            
            # Normalize filter using vector store client's normalize_filter method
            # This handles vector store-specific filter requirements (e.g., ChromaDB $in conversion)
            formatted_where = None
            if where is not None and isinstance(where, dict) and where:
                # Filter out None values
                filtered_where = {k: v for k, v in where.items() if v is not None}
                if filtered_where:
                    # Use vector store client's normalize_filter for store-specific normalization
                    formatted_where = self.vector_store_client.normalize_filter(filtered_where)
                    logger.debug(f"Using normalized filter for collection '{self.collection_name}': {formatted_where}")
            
            # Query using vector store client
            logger.debug(f"Querying collection '{self.collection_name}' with n_results={candidate_k}")
            dense_results = await self.vector_store_client.query(
                collection_name=self.collection_name,
                query_embeddings=[query_embedding],
                n_results=candidate_k,
                where=formatted_where
            )
            
            if not dense_results or not dense_results.get("ids") or not dense_results["ids"][0]:
                logger.info(f"No results found in collection '{self.collection_name}' for query: '{query[:100]}...'")
                return []
            
            # Extract results (handle both list of lists and flat lists)
            ids = dense_results["ids"][0] if isinstance(dense_results["ids"][0], list) else dense_results["ids"]
            documents = dense_results["documents"][0] if isinstance(dense_results["documents"][0], list) else dense_results["documents"]
            metadatas = dense_results["metadatas"][0] if isinstance(dense_results["metadatas"][0], list) else dense_results["metadatas"]
            distances = dense_results["distances"][0] if isinstance(dense_results["distances"][0], list) else dense_results["distances"]
            
            if not documents:
                return []
            
            # Step 2: BM25 ranking (keyword-based)
            self.bm25_ranker.fit(documents)
            bm25_ranked = self.bm25_ranker.rank(query, documents=None, k=None)
            # Create a list of scores in document order
            bm25_scores = [0.0] * len(documents)
            for idx, score in bm25_ranked:
                if idx < len(bm25_scores):
                    bm25_scores[idx] = score
            
            # Step 3: Hybrid scoring
            # Normalize dense scores (distance to similarity: lower distance = higher similarity)
            # Vector stores use cosine distance, so we convert to similarity
            dense_similarities = [1 / (1 + dist) for dist in distances]
            
            # Normalize BM25 scores to [0, 1] range
            max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1.0
            normalized_bm25 = [score / max_bm25 for score in bm25_scores] if max_bm25 > 0 else [0.0] * len(bm25_scores)
            
            # Combine scores
            combined_results = []
            for i in range(len(documents)):
                combined_score = (
                    self.dense_weight * dense_similarities[i] +
                    self.sparse_weight * normalized_bm25[i]
                )
                
                combined_results.append({
                    "id": ids[i] if i < len(ids) else f"doc_{i}",
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "dense_score": dense_similarities[i],
                    "bm25_score": normalized_bm25[i],
                    "combined_score": combined_score,
                    "distance": distances[i] if i < len(distances) else None
                })
            
            # Sort by combined score descending
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            
            # Return top k results
            top_results = combined_results[:top_k]
            
            logger.info(f"Hybrid search found {len(top_results)} results for query: {query[:50]}...")
            return top_results
            
        except Exception as e:
            logger.error(f"Error during hybrid search: {str(e)}", exc_info=True)
            return []
    
    async def find_relevant_contexts(
        self,
        context_description: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find contexts most relevant to a description using hybrid search.
        
        This is specifically designed for context matching as described in
        the hybrid search architecture.
        
        Args:
            context_description: Description of the context/situation
            top_k: Number of results to return
            where: Optional metadata filters (e.g., {"industry": "healthcare"})
            
        Returns:
            List of relevant contexts with scores
        """
        return await self.hybrid_search(
            query=context_description,
            top_k=top_k,
            where=where
        )
    
    async def context_aware_retrieval(
        self,
        query: str,
        context_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents prioritized for a specific context.
        
        Args:
            query: Natural language query
            context_id: Optional context ID to filter by
            filters: Additional metadata filters
            top_k: Number of results to return
            
        Returns:
            List of context-aware search results
        """
        # Build metadata filter
        where_clause = {}
        if context_id:
            where_clause["context_id"] = context_id
        if filters:
            where_clause.update(filters)
        
        return await self.hybrid_search(
            query=query,
            top_k=top_k,
            where=where_clause if where_clause else None
        )
    
    async def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the collection.
        
        Args:
            documents: List of document strings
            metadatas: Optional list of metadata dictionaries
            ids: Optional list of document IDs
            
        Returns:
            List of document IDs that were added
        """
        if not documents:
            logger.warning("No documents provided to add")
            return []
        
        await self._ensure_initialized()
        
        try:
            # Sanitize metadata to ensure vector store compatibility
            # Vector stores only accept str, int, float, bool - not lists or dicts
            import json
            sanitized_metadatas = []
            for metadata in (metadatas or [{}] * len(documents)):
                sanitized_metadata = {}
                for key, value in metadata.items():
                    if value is None:
                        continue  # Skip None values
                    elif isinstance(value, (str, int, float, bool)):
                        sanitized_metadata[key] = value
                    elif isinstance(value, list):
                        # Convert lists to JSON strings
                        sanitized_metadata[key] = json.dumps(value)
                    elif isinstance(value, dict):
                        # Convert dicts to JSON strings
                        sanitized_metadata[key] = json.dumps(value)
                    else:
                        # Convert any other type to string
                        sanitized_metadata[key] = str(value)
                sanitized_metadatas.append(sanitized_metadata)
            
            # Add documents using vector store client
            added_ids = await self.vector_store_client.add_documents(
                collection_name=self.collection_name,
                documents=documents,
                metadatas=sanitized_metadatas if sanitized_metadatas else None,
                ids=ids
            )
            
            logger.info(f"Added {len(documents)} documents to collection")
            return added_ids
            
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}", exc_info=True)
            return []
    
    async def delete_by_metadata(self, where: Dict[str, Any]) -> int:
        """
        Delete documents matching metadata filters.
        
        Args:
            where: Metadata filter dictionary
            
        Returns:
            Number of documents deleted
        """
        await self._ensure_initialized()
        
        try:
            # Format filter for vector store compatibility
            # Use vector store client's normalize_filter for store-specific normalization
            formatted_where = self.vector_store_client.normalize_filter(where)
            
            # Delete documents using vector store client
            success = await self.vector_store_client.delete(
                collection_name=self.collection_name,
                where=formatted_where
            )
            
            if success:
                logger.info(f"Deleted documents matching filter: {where}")
                # Note: We can't get exact count without querying first
                # Return 1 to indicate success
                return 1
            else:
                return 0
            
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}", exc_info=True)
            return 0

