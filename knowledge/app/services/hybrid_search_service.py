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
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import chromadb
from chromadb.errors import UniqueConstraintError
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

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
        chroma_client: chromadb.PersistentClient,
        collection_name: str,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3
    ):
        """
        Initialize hybrid search service.
        
        Args:
            chroma_client: ChromaDB persistent client
            collection_name: Name of the ChromaDB collection
            embeddings_model: Optional embeddings model (defaults to OpenAI)
            dense_weight: Weight for dense vector similarity (default: 0.7)
            sparse_weight: Weight for BM25 sparse retrieval (default: 0.3)
        """
        self.chroma_client = chroma_client
        self.collection_name = collection_name
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        
        # Ensure weights sum to 1.0
        total_weight = dense_weight + sparse_weight
        if total_weight != 1.0:
            logger.warning(f"Weights sum to {total_weight}, normalizing to 1.0")
            self.dense_weight = dense_weight / total_weight
            self.sparse_weight = sparse_weight / total_weight
        
        self.collection = None
        self.vectorstore = None
        self.bm25_ranker = BM25Ranker()
        
        self._initialize()
    
    def _initialize(self):
        """Initialize ChromaDB collection and vectorstore."""
        try:
            logger.info(f"Initializing hybrid search service with collection: {self.collection_name}")
            
            # Get embedding dimension from the current embeddings model
            test_embedding = self.embeddings_model.embed_query("test")
            embedding_dimension = len(test_embedding)
            logger.info(f"Using embeddings model with dimension: {embedding_dimension}")
            
            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(name=self.collection_name)
                logger.info(f"Retrieved existing collection: {self.collection_name}")
                
                # Check if collection has documents and verify dimension compatibility
                collection_count = self.collection.count()
                if collection_count > 0:
                    # Try to get collection metadata to check dimension
                    try:
                        # Get a sample to check dimensions
                        sample = self.collection.get(limit=1, include=["embeddings"])
                        if sample.get("embeddings") and len(sample["embeddings"]) > 0:
                            existing_dim = len(sample["embeddings"][0])
                            if existing_dim != embedding_dimension:
                                logger.warning(
                                    f"Embedding dimension mismatch in collection '{self.collection_name}': "
                                    f"existing={existing_dim}, current={embedding_dimension}. "
                                    f"Collection may need to be recreated or use matching embedding model."
                                )
                                # Note: We'll continue but queries may fail - user should recreate collection
                    except Exception as dim_check_error:
                        logger.warning(f"Could not verify embedding dimensions: {dim_check_error}")
            except Exception as e:
                logger.info(f"Collection '{self.collection_name}' does not exist, creating it...")
                try:
                    # Create collection with explicit embedding function to ensure dimension consistency
                    self.collection = self.chroma_client.create_collection(
                        name=self.collection_name,
                        metadata={"embedding_dimension": embedding_dimension}
                    )
                    logger.info(f"Created new collection: {self.collection_name} with dimension {embedding_dimension}")
                except UniqueConstraintError:
                    # Collection was created between check and create
                    self.collection = self.chroma_client.get_collection(name=self.collection_name)
                    logger.info(f"Retrieved collection after race condition: {self.collection_name}")
            
            # Initialize Langchain Chroma wrapper
            self.vectorstore = Chroma(
                client=self.chroma_client,
                collection_name=self.collection_name,
                embedding_function=self.embeddings_model,
            )
            
            logger.info(f"Successfully initialized hybrid search service")
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid search service: {str(e)}")
            raise
    
    def hybrid_search(
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
        if not self.collection:
            logger.warning("Collection not initialized")
            return []
        
        try:
            # Step 1: Dense vector search (semantic similarity)
            # Get more candidates for re-ranking
            candidate_k = top_k * candidate_multiplier
            
            # Generate embeddings using the current embeddings model to ensure dimension consistency
            query_embedding = self.embeddings_model.embed_query(query)
            
            query_kwargs = {
                "query_embeddings": [query_embedding],  # Use explicit embeddings instead of query_texts
                "n_results": candidate_k,
                "include": ["documents", "metadatas", "distances"]
            }
            
            # Add metadata filter if provided
            if where is not None and isinstance(where, dict) and where:
                # Filter out None values
                filtered_where = {k: v for k, v in where.items() if v is not None}
                if filtered_where:
                    query_kwargs["where"] = filtered_where
            
            dense_results = self.collection.query(**query_kwargs)
            
            if not dense_results or not dense_results.get("ids") or not dense_results["ids"][0]:
                logger.info(f"No results found for query: {query}")
                return []
            
            # Extract results
            documents = dense_results["documents"][0]
            metadatas = dense_results["metadatas"][0]
            distances = dense_results["distances"][0]
            ids = dense_results["ids"][0]
            
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
            # ChromaDB uses cosine distance, so we convert to similarity
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
                    "id": ids[i],
                    "content": documents[i],
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
    
    def find_relevant_contexts(
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
        return self.hybrid_search(
            query=context_description,
            top_k=top_k,
            where=where
        )
    
    def context_aware_retrieval(
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
        
        return self.hybrid_search(
            query=query,
            top_k=top_k,
            where=where_clause if where_clause else None
        )
    
    def add_documents(
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
        
        try:
            # Use Langchain Chroma wrapper for adding documents
            from langchain_core.documents import Document as LangchainDocument
            
            langchain_docs = []
            for i, doc_text in enumerate(documents):
                metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                doc_id = ids[i] if ids and i < len(ids) else None
                
                langchain_doc = LangchainDocument(
                    page_content=doc_text,
                    metadata=metadata
                )
                langchain_docs.append(langchain_doc)
            
            # Sanitize metadata in LangchainDocument objects to ensure ChromaDB compatibility
            # ChromaDB only accepts str, int, float, bool - not lists or dicts
            import json
            for doc in langchain_docs:
                sanitized_metadata = {}
                for key, value in doc.metadata.items():
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
                doc.metadata = sanitized_metadata
            
            # Add documents with optional IDs
            if ids:
                self.vectorstore.add_documents(langchain_docs, ids=ids)
            else:
                self.vectorstore.add_documents(langchain_docs)
            
            added_ids = ids if ids else [doc.metadata.get("id") for doc in langchain_docs]
            logger.info(f"Added {len(documents)} documents to collection")
            
            return added_ids
            
        except Exception as e:
            logger.error(f"Error adding documents: {str(e)}", exc_info=True)
            return []
    
    def delete_by_metadata(self, where: Dict[str, Any]) -> int:
        """
        Delete documents matching metadata filters.
        
        Args:
            where: Metadata filter dictionary
            
        Returns:
            Number of documents deleted
        """
        if not self.collection:
            logger.warning("Collection not initialized")
            return 0
        
        try:
            # Get documents matching filter
            results = self.collection.get(where=where)
            
            if not results or not results.get("ids"):
                return 0
            
            ids_to_delete = results["ids"]
            
            # Delete documents
            self.collection.delete(ids=ids_to_delete)
            
            logger.info(f"Deleted {len(ids_to_delete)} documents matching filter")
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}", exc_info=True)
            return 0

