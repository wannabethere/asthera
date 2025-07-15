import json
import logging
import os
import uuid
from typing import List,Dict, Tuple,Any, Optional
from uuid import uuid4
from langchain.schema import Document as LangchainDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document as LangchainDocument
import chromadb
from app.settings import get_settings
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from enum import Enum, auto

import numpy as np
settings = get_settings()
logger = logging.getLogger(__name__)
embedding_provider: str = "openai"
embedding_model: str = "text-embedding-3-small"
embeddings_model = OpenAIEmbeddings(
            model= embedding_model, openai_api_key=settings.OPENAI_API_KEY
)
CHROMA_STORE_PATH = settings.CHROMA_STORE_PATH

class DuplicatePolicy(Enum):
    """Policy for handling duplicate documents in the store."""
    SKIP = auto()  # Skip duplicate documents
    OVERWRITE = auto()  # Overwrite existing documents
    FAIL = auto()  # Raise an error if duplicates are found

class BM25Ranker:
    """BM25 ranking implementation for document search."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            lowercase=True,
            ngram_range=(1, 2)
        )
        self.doc_freqs = None
        self.avgdl = 0
        self.doc_count = 0
        self.doc_lens = []
        self.doc_vectors = None
        
    def fit(self, documents: List[str]):
        """Fit the BM25 ranker on a collection of documents."""
        if not documents:
            return
            
        # Transform documents to TF-IDF vectors
        self.doc_vectors = self.vectorizer.fit_transform(documents)
        
        # Calculate document frequencies
        self.doc_freqs = self.vectorizer.idf_
        
        # Calculate average document length
        self.doc_lens = [len(doc.split()) for doc in documents]
        self.avgdl = sum(self.doc_lens) / len(documents)
        self.doc_count = len(documents)
        
    def rank(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        """Rank documents based on BM25 score for a query."""
        if not self.doc_vectors or not self.doc_freqs:
            return []
            
        # Transform query to TF-IDF vector
        query_vector = self.vectorizer.transform([query])
        
        # Calculate BM25 scores
        scores = []
        for i in range(self.doc_count):
            # Calculate term frequency in query
            query_tf = query_vector[0, i]
            
            # Calculate document length normalization
            doc_len = self.doc_lens[i]
            length_norm = (1 - self.b + self.b * doc_len / self.avgdl)
            
            # Calculate BM25 score
            score = query_tf * self.doc_freqs[i] * (self.k1 + 1) / (self.k1 + length_norm)
            scores.append((i, float(score)))
            
        # Sort by score and return top k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

class DocumentVectorstore:
    """Handle FAISS vectorstore operations."""

    def __init__(self, vectorstore_path: str, embeddings_model: OpenAIEmbeddings):
        self.vectorstore_path = vectorstore_path
        self.embeddings_model = embeddings_model
        self.vectorstore = None

    def initialize(self):
        """Initialize or load FAISS vectorstore."""
        if os.path.exists(self.vectorstore_path):
            logger.info(f"Loading FAISS vectorstore from {self.vectorstore_path}")
            self.vectorstore = FAISS.load_local(
                self.vectorstore_path, self.embeddings_model, allow_dangerous_deserialization=True
            )
        else:
            logger.info(f"Initializing new FAISS vectorstore at {self.vectorstore_path}")
            # Only initializes a new FAISS vectorstore when documents with embeddings are provided
            self.vectorstore = None

    def add_documents(self, documents: List[LangchainDocument]):
        """Add documents to the vectorstore."""
        if not documents:
            logger.warning("No documents provided to add to the vectorstore.")
            return

        if not self.vectorstore:
            logger.info("Initializing FAISS vectorstore.")
            self.vectorstore = FAISS.from_documents(documents, self.embeddings_model)
        else:
            logger.info("Adding documents to the existing vectorstore.")
            self.vectorstore.add_documents(documents)

        self.vectorstore.save_local(self.vectorstore_path)
        logger.info(f"Added {len(documents)} documents to the vectorstore.")

    

    def semantic_search(self, query: str, k: int = 5, where: Dict = None) -> List[Dict]:
        """Perform semantic search on the Chroma store.

        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            where: Optional metadata filter dictionary

        Returns:
            List of dictionaries containing search results with scores
        """
        if not self.vectorstore:
            logger.warning("Chroma store not initialized. Please initialize first.")
            return []

        try:
            # Perform similarity search with scores
            results = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter=where  # Apply metadata filters if provided
            )

            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),  # Convert numpy float to Python float
                    "id": doc.metadata.get("id", None)
                })

            # Sort results by score (lower is better for Chroma)
            formatted_results.sort(key=lambda x: x["score"])
            logger.info(f"Found {len(formatted_results)} results for query: {query}")
            return formatted_results

        except Exception as e:
            logger.error(f"Error during semantic search: {str(e)}")
            return []

    

    def bulk_add_data(self, data: List[Dict[str, Any]]):
        """Add multiple insights at once.
        
        Args:
            insights: List of insight dictionaries with keys:
                     title, content, scenario, tags (optional), metadata (optional)
        """
        documents = []
        for element in data:
            meta = element.get("metadata", {})
            for key in meta:
                meta.update({
                    key: element[key]
                })
            
            documents.append(LangchainDocument(
                page_content=element["content"],
                metadata=meta
            ))
        
        self.store.add_documents(documents)
        
    def delete_insights(self, ids: List[str]):
        """Delete insights by their IDs.
        
        Args:
            ids: List of document IDs to delete
        """
        self.store.delete(ids)

        
    def semantic_search_with_bm25(self, query: str, k: int = 5) -> List[Dict]:
        """Perform semantic search using both vector similarity and BM25 ranking.
        
        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            
        Returns:
            List of dictionaries containing search results with combined scores
        """
        if not self.vectorstore:
            logger.warning("Vectorstore not initialized. Please initialize first.")
            return []
            
        try:
            # Get vector similarity results
            vector_results = self.vectorstore.similarity_search_with_score(query, k=k)
            
            # Initialize BM25 ranker
            bm25 = BM25Ranker()
            
            # Prepare documents for BM25
            documents = [doc.page_content for doc, _ in vector_results]
            bm25.fit(documents)
            
            # Get BM25 scores
            bm25_scores = bm25.rank(query, k=k)
            
            # Combine scores
            combined_results = []
            for (doc, vector_score), (idx, bm25_score) in zip(vector_results, bm25_scores):
                # Normalize scores to [0, 1] range
                norm_vector_score = 1 / (1 + vector_score)  # Convert distance to similarity
                norm_bm25_score = bm25_score / max(score for _, score in bm25_scores)
                
                # Combine scores (weighted average)
                combined_score = 0.7 * norm_vector_score + 0.3 * norm_bm25_score
                
                combined_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "vector_score": float(vector_score),
                    "bm25_score": float(bm25_score),
                    "combined_score": float(combined_score),
                    "id": doc.metadata.get("id", None)
                })
            
            # Sort by combined score
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            
            logger.info(f"Found {len(combined_results)} results for query: {query}")
            return combined_results
            
        except Exception as e:
            logger.error(f"Error during semantic search with BM25: {str(e)}")
            return []



class DocumentChromaStore:
    """Handle Chroma vectorstore operations."""

    def __init__(self, persistent_client: chromadb.PersistentClient, collection_name: str, vectorstore_path: str = None, embeddings_model: OpenAIEmbeddings = embeddings_model, tf_idf:bool = False):
        """Initialize the Chroma store.
        
        Args:
            collection_name: Name of the collection to store documents
            vectorstore_path: Optional path to store the database. Defaults to CHROMA_STORE_PATH
            embeddings_model: Optional embeddings model. Defaults to global embeddings_model
        """
        self.collection_name = collection_name
        self.vectorstore_path = vectorstore_path or CHROMA_STORE_PATH
        self.embeddings_model = embeddings_model or embeddings_model
        self.persistent_client = persistent_client
        self.tf_idf = tf_idf
        self.vectorizer = TfidfVectorizer()
        self.vectorstore = None
        self.tfidf_vectorstore = None
        self.collection = None
        self.tfidf_collection_name = f"{self.collection_name}_tfidf"
        # Ensure the storage directory exists
        self.initialize()
        

    def initialize(self):
        """Initialize or load the Chroma vectorstore."""
        
        try:
            if self.collection:
                return
            logger.info(f"Initializing Chroma store at {self.vectorstore_path} with collection {self.collection_name}")
            print("initializing Chroma store at", self.vectorstore_path, self.collection_name)  
            # Initialize the persistent client with the specified path
            
            
            # Get or create the collection
            self.collection = self.persistent_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": f"Document collection for {self.collection_name}"}
            )
            if self.tf_idf:
                self.tfidf_collection = self.persistent_client.get_or_create_collection(
                    name=self.tfidf_collection_name,
                    metadata={"hnsw:space": "cosine", "description": f"TF-IDF collection for {self.collection_name}"}
                )
            # Initialize the Langchain Chroma wrapper
            self.vectorstore = Chroma(
                client=self.persistent_client,
                collection_name=self.collection_name,
                embedding_function=self.embeddings_model,
            )
            if self.tf_idf:
                self.tfidf_vectorstore = Chroma(
                    client=self.persistent_client,
                    collection_name=self.tfidf_collection_name,
                    embedding_function=self.embeddings_model,
                )
            
            logger.info(f"Successfully initialized Chroma store with collection {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chroma store: {str(e)}")
            raise

    def compute_document_embeddings(self, documents: List[LangchainDocument]) -> List[List[float]]:
        """Compute embeddings for a list of documents.
        
        Args:
            documents: List of LangchainDocument objects
            
        Returns:
            List of embedding vectors for each document
        """
        try:
            # Extract text content from documents
            texts = [doc.page_content for doc in documents]
            
            # Compute embeddings using the embeddings model
            embeddings = self.embeddings_model.embed_documents(texts)
            
            return embeddings
        except Exception as e:
            logger.error(f"Error computing document embeddings: {str(e)}")
            return []

    def add_documents(self, docs: List[Any]):
        """Add documents to the vectorstore.
        
        Args:
            docs: List of dictionaries containing 'metadata' and 'data' keys
        """
        if not docs:
            logger.warning("No documents provided to add to the vectorstore.")
            return
            
        documents, ids = [], []
        for doc in docs:
            if isinstance(doc, LangchainDocument):
                documents.append(doc)
                document_id = str(uuid4())
                if doc.metadata.get("id", None) is None:
                    doc.metadata["id"] = document_id
                ids.append(doc.metadata.get("id", document_id))
                continue
            else:
                if not isinstance(doc, dict):
                    logger.warning(f"Skipping invalid document format: {doc}")
                    continue
                    
                if 'metadata' not in doc or 'data' not in doc:
                    logger.warning(f"Skipping document missing required fields: {doc}")
                    continue    
              
                document_id, document = create_langchain_doc_util(metadata=doc['metadata'], data=doc['data'])    
                if document and document_id:
                    documents.append(document)
                    ids.append(document_id)
        
        if documents:
            # Compute embeddings for all documents
            embeddings = self.compute_document_embeddings(documents)
            
            if embeddings:
                # Add documents with pre-computed embeddings
                self.vectorstore.add_documents(
                    documents=documents,
                    ids=ids,
                    embeddings=embeddings
                )
                
                # Add TF-IDF vectors if enabled
                if self.tf_idf:
                    self.add_tfidf_vectors(documents=documents, ids=ids)
                
                logger.info(f"Added {len(documents)} documents with embeddings to the vectorstore.")
                print("documents added to the vectorstore", len(documents))
            else:
                # Fallback to regular document addition if embedding computation fails
                self.vectorstore.add_documents(documents=documents, ids=ids)
                if self.tf_idf:
                    self.add_tfidf_vectors(documents=documents, ids=ids)
                logger.info(f"Added {len(documents)} documents to the vectorstore (without pre-computed embeddings).")
        else:
            logger.warning("No valid documents were found to add to the vectorstore.")

    def add_tfidf_vectors(self, documents: List[LangchainDocument], ids: List[str]):
        if not self.tf_idf:
            return
        if documents:
            # TF-IDF indexing
            # Note: TfidfVectorizer().fit_transform(...) recomputes the TF-IDF each time. If your corpus grows dynamically, consider persisting the vectorizer using joblib or pickle.
            
            # Extract page contents
            texts = [doc.page_content for doc in documents]
            # Generate TF-IDF vectors
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            metadata_list = [doc.metadata for doc in documents]
            ids = [str(uuid.uuid4()) for _ in range(len(texts))]
            self.tfidf_collection.add(
                embeddings=tfidf_matrix.toarray(),
                ids=ids,
                metadatas=metadata_list
            )
            logger.info(f"Added {len(texts)} TF-IDF vectors to collection {self.tfidf_collection_name}")
        else:
            logger.warning("No documents provided to add to the vectorstore.")
        return

    def semantic_search(self, query: str, k: int = 5, where: Dict = None, query_embedding: List[float] = None) -> List[Dict]:
        """Perform semantic search on the Chroma store.
        
        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            where: Optional metadata filter dictionary
            query_embedding: Optional pre-computed query embedding vector
            
        Returns:
            List of dictionaries containing search results with scores
        """
        if not self.vectorstore:
            logger.warning("Chroma store not initialized. Please initialize first.")
            return []
            
        try:
            logger.info(f"query in semantic_search for {self.collection_name}: {query}")
                # Otherwise perform regular similarity search
            results = self.vectorstore.similarity_search_with_score(
                query,
                k=k
            )
            logger.info(f"results in semantic_search for {self.collection_name}: {results}")
           
            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),  # Convert numpy float to Python float
                    "id": doc.metadata.get("id", None)
                })
            
            # Sort results by score (lower is better for Chroma)
            formatted_results.sort(key=lambda x: x["score"])
            
            logger.info(f"Found {len(formatted_results)}  {self.collection_name} results for query: {query}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during semantic search: {str(e)}")
            return []

    def semantic_searches(self, query_texts: List[str], n_results: int = 5, where: Dict = None) -> Dict[str, Any]:
        """Perform semantic search for multiple query texts.

        Args:
            query_texts: List of query strings
            n_results: Number of results to return per query (default: 5)
            where: Optional metadata filter dictionary

        Returns:
            Dictionary containing documents, distances and metadatas for the search results
        """
        if not self.vectorstore:
            logger.warning("Chroma store not initialized. Please initialize first.")
            return {
                "documents": [],
                "distances": [],
                "metadatas": []
            }

        try:
            # Perform similarity search for each query
            results = self.vectorstore.similarity_search_with_relevance_scores(
                query_texts[0] if len(query_texts) == 1 else query_texts,
                k=n_results,
                filter=where
            )
            
            # Format results
            documents = []
            distances = []
            metadatas = []

            for doc, score in results:
                documents.append(doc.page_content)
                distances.append(float(score))
                metadatas.append(doc.metadata)

            return {
                "documents": [documents],
                "distances": [distances],
                "metadatas": [metadatas]
            }

        except Exception as e:
            logger.error(f"Error during multi-query semantic search: {str(e)}")
            return {
                "documents": [],
                "distances": [],
                "metadatas": []
            }
        
    def semantic_search_with_bm25(self, query: str, k: int = 5, where: Dict = None, query_embedding: List[float] = None) -> List[Dict]:
        """Perform semantic search using both vector similarity and BM25 ranking.
        
        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            where: Optional metadata filter dictionary
            query_embedding: Optional pre-computed query embedding vector
            
        Returns:
            List of dictionaries containing search results with combined scores
        """
        if not self.vectorstore:
            logger.warning("Chroma store not initialized. Please initialize first.")
            return []
            
        try:
            # Get vector similarity results using query embedding if provided
            vector_results = self.vectorstore.similarity_search_with_score(
                    query,
                    k=k,
                    filter=where
                )
            
                
            
            # Initialize BM25 ranker
            bm25 = BM25Ranker()
            
            # Prepare documents for BM25
            documents = [doc.page_content for doc, _ in vector_results]
            bm25.fit(documents)
            
            # Get BM25 scores
            bm25_scores = bm25.rank(query, k=k)
            
            # Combine scores
            combined_results = []
            for (doc, vector_score), (idx, bm25_score) in zip(vector_results, bm25_scores):
                # Normalize scores to [0, 1] range
                norm_vector_score = 1 / (1 + vector_score)  # Convert distance to similarity
                norm_bm25_score = bm25_score / max(score for _, score in bm25_scores)
                
                # Combine scores (weighted average)
                combined_score = 0.7 * norm_vector_score + 0.3 * norm_bm25_score
                
                combined_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "vector_score": float(vector_score),
                    "bm25_score": float(bm25_score),
                    "combined_score": float(combined_score),
                    "id": doc.metadata.get("id", None)
                })
            
            # Sort by combined score
            combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
            
            logger.info(f"Found {len(combined_results)} results for query: {query}")
            return combined_results
            
        except Exception as e:
            logger.error(f"Error during semantic search with BM25: {str(e)}")
            return []

    def semantic_search_with_tfidf(self, query: str, k: int = 5, where: Dict = None, query_embedding: List[float] = None) -> List[Dict]:
        """Perform semantic search combined with TF-IDF ranking.
        If TF-IDF calculation fails, falls back to semantic search results.
        
        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            where: Optional metadata filter dictionary
            query_embedding: Optional pre-computed query embedding vector
            
        Returns:
            List of dictionaries containing search results with combined scores
        """
        try:
            # Semantic search using query embedding if provided
            if query_embedding is not None:
                sem_results = self.vectorstore.similarity_search_by_vector(
                    query_embedding,
                    k=k,
                    filter=where
                )
            else:
                sem_results = self.vectorstore.similarity_search_with_score(
                    query,
                    k=k,
                    filter=where
                )
            
            sem_docs = [doc for doc, _ in sem_results]
            sem_scores = [score for _, score in sem_results]
            
            # If we have no semantic results, return empty list
            if not sem_docs:
                logger.info(f"No semantic search results found for query: {query}")
                return []

            try:
                # TF-IDF vector for query
                all_docs = [doc.page_content for doc in sem_docs]
                tfidf_vectorizer = TfidfVectorizer()
                tfidf_matrix = tfidf_vectorizer.fit_transform(all_docs + [query])
                query_vector = tfidf_matrix[-1].toarray()[0]

                # TF-IDF similarity scores (cosine)
                tfidf_doc_vectors = tfidf_matrix[:-1].toarray()
                cosine_scores = np.dot(tfidf_doc_vectors, query_vector) / (
                    np.linalg.norm(tfidf_doc_vectors, axis=1) * np.linalg.norm(query_vector) + 1e-10)

                # Combine scores
                results = []
                for i, doc in enumerate(sem_docs):
                    norm_sem = 1 / (1 + sem_scores[i])  # Chroma score is distance
                    norm_tfidf = cosine_scores[i]
                    combined_score = 0.7 * norm_sem + 0.3 * norm_tfidf
                    results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "semantic_score": float(sem_scores[i]),
                        "tfidf_score": float(norm_tfidf),
                        "combined_score": float(combined_score),
                        "id": doc.metadata.get("id", None)
                    })

                # Sort by combined score descending
                results.sort(key=lambda x: x["combined_score"], reverse=True)
                logger.info(f"Found {len(results)} combined semantic+TF-IDF results for query: {query}")
                return results
                
            except Exception as e:
                # TF-IDF calculation failed, fall back to semantic search results
                logger.warning(f"TF-IDF calculation failed, falling back to semantic results: {str(e)}")
                # Format semantic results only
                results = []
                for i, (doc, score) in enumerate(sem_results):
                    results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "semantic_score": float(score),
                        "tfidf_score": None,
                        "combined_score": None,
                        "id": doc.metadata.get("id", None)
                    })
                logger.info(f"Returning {len(results)} semantic-only results for query: {query}")
                return results
                
        except Exception as e:
            # If semantic search itself fails
            logger.error(f"Error during semantic search with TF-IDF: {str(e)}")
            return []
    
    def tfidf_search(self, query: str, k: int = 5, where: Dict = None) -> List[Dict]:
        """Perform search using only TF-IDF vectors.
        
        Args:
            query: The search query string
            k: Number of results to return (default: 5)
            where: Optional metadata filter dictionary
            
        Returns:
            List of dictionaries containing search results with scores
        """
        if not self.tf_idf or not self.tfidf_collection:
            logger.warning("TF-IDF search not enabled or collection not initialized.")
            return []
            
        try:
            # Convert query to TF-IDF vector
            query_vector = self.vectorizer.transform([query]).toarray()[0]
            
            # Query the TF-IDF collection
            results = self.tfidf_collection.query(
                query_embeddings=query_vector.reshape(1, -1),
                n_results=k,
                where=where
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "content": results.get('documents', [[None]])[0][i],
                    "metadata": results['metadatas'][0][i],
                    "score": float(results['distances'][0][i]),
                    "id": results['ids'][0][i]
                })
            
            # Sort results by score (higher is better for cosine similarity)
            formatted_results.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"Found {len(formatted_results)} TF-IDF results for query: {query}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error during TF-IDF search: {str(e)}")
            return []

def create_langchain_doc_util(metadata: Dict, data: Dict) -> tuple[str, LangchainDocument]:
    """Create a Langchain document from metadata and data.
    
    Args:
        metadata: Dictionary containing document metadata
        data: Dictionary containing document content
        
    Returns:
        Tuple of (document_id, LangchainDocument) or (None, None) if invalid
    """
    try:
        
       
        document_id = str(uuid4())
        document = LangchainDocument(
            page_content=str(data),  # Convert data dict to string representation
            metadata=metadata,
            id=document_id
        )
        
        return document_id, document
    except Exception as e:
        logger.error(f"Error creating Langchain document: {str(e)}")
        return None, None

class AsyncDocumentWriter:
    """Asynchronous document writer for Chroma document store."""
    
    def __init__(self, document_store: DocumentChromaStore, policy: Optional[DuplicatePolicy] = None):
        """Initialize the async document writer.
        
        Args:
            document_store: The Chroma document store instance
            policy: Optional duplicate policy (SKIP, OVERWRITE, or FAIL)
        """
        self.document_store = document_store
        self.policy = policy or DuplicatePolicy.OVERWRITE

    async def run(self, documents: List[LangchainDocument], policy: Optional[DuplicatePolicy] = None) -> Dict[str, int]:
        """Write documents to the Chroma store asynchronously.
        
        Args:
            documents: List of LangchainDocument to write
            policy: Optional duplicate policy (SKIP, OVERWRITE, or FAIL)
            
        Returns:
            Dictionary containing the number of documents written
        """
        if not documents:
            logger.warning("No documents provided to write")
            return {"documents_written": 0}

        try:
            # Handle duplicates based on policy
            if policy == DuplicatePolicy.SKIP:
                # Filter out documents that already exist
                existing_ids = set(self.document_store.collection.get()['ids'])
                documents = [doc for doc in documents if doc.metadata.get('id') not in existing_ids]
            elif policy == DuplicatePolicy.FAIL:
                # Check if any documents already exist
                existing_ids = set(self.document_store.collection.get()['ids'])
                duplicate_ids = [doc.metadata.get('id') for doc in documents if doc.metadata.get('id') in existing_ids]
                if duplicate_ids:
                    raise ValueError(f"Duplicate documents found with IDs: {duplicate_ids}")

            # Add documents to the store
            if documents:
                self.document_store.add_documents(documents)
                logger.info(f"Successfully wrote {len(documents)} documents to Chroma store")
                return {"documents_written": len(documents)}
            else:
                logger.info("No documents to write after applying duplicate policy")
                return {"documents_written": 0}
            
        except Exception as e:
            logger.error(f"Error writing documents to Chroma store: {str(e)}")
            return {"documents_written": 0}

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Initialize the persistent client
        logger.info(f"Initializing persistent client at {CHROMA_STORE_PATH}")
        client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
        
        # Create a test collection
        collection_name = "test_collection"
        doc_store = DocumentChromaStore(
            persistent_client=client,
            collection_name=collection_name
        )
        
        # Initialize the store
        doc_store.initialize()
        
        # Create some example documents
        example_docs = [
            {
                "metadata": {
                    "source": "test_doc_1",
                    "author": "John Doe",
                    "date": "2024-03-20",
                    "category": "AI"
                },
                "data": {
                    "title": "Sample Document 1",
                    "content": "This is a test document about artificial intelligence and machine learning.",
                    "tags": ["AI", "ML"]
                }
            },
            {
                "metadata": {
                    "source": "test_doc_2",
                    "author": "Jane Smith",
                    "date": "2024-03-21",
                    "category": "NLP"
                },
                "data": {
                    "title": "Sample Document 2",
                    "content": "This document discusses natural language processing and its applications.",
                    "tags": ["NLP", "AI"]
                }
            }
        ]
        
        # Add documents to the store
        logger.info("Adding example documents to the store")
        doc_store.add_documents(example_docs)
        
        # Test semantic search
        logger.info("Testing semantic search...")
        search_query = "What are the applications of artificial intelligence?"
        results = doc_store.semantic_search(search_query, k=2)
        
        # Print search results
        logger.info(f"\nSearch results for query: {search_query}")
        for idx, result in enumerate(results, 1):
            logger.info(f"\nResult {idx}:")
            logger.info(f"Score: {result['score']}")
            logger.info(f"Content: {result['content']}")
            logger.info(f"Metadata: {result['metadata']}")
        
        # Test semantic search with metadata filter
        logger.info("\nTesting semantic search with metadata filter...")
        filter_query = "What are the applications of artificial intelligence?"
        filter_results = doc_store.semantic_search(
            filter_query,
            k=2,
            where={"category": "AI"}
        )
        
        # Print filtered search results
        logger.info(f"\nFiltered search results for query: {filter_query}")
        for idx, result in enumerate(filter_results, 1):
            logger.info(f"\nResult {idx}:")
            logger.info(f"Score: {result['score']}")
            logger.info(f"Content: {result['content']}")
            logger.info(f"Metadata: {result['metadata']}")
        
        # Test semantic search with BM25
        logger.info("\nTesting semantic search with BM25 ranking...")
        bm25_query = "What are the applications of artificial intelligence?"
        bm25_results = doc_store.semantic_search_with_bm25(bm25_query, k=2)
        
        # Print BM25 search results
        logger.info(f"\nBM25 search results for query: {bm25_query}")
        for idx, result in enumerate(bm25_results, 1):
            logger.info(f"\nResult {idx}:")
            logger.info(f"Combined Score: {result['combined_score']}")
            logger.info(f"Vector Score: {result['vector_score']}")
            logger.info(f"BM25 Score: {result['bm25_score']}")
            logger.info(f"Content: {result['content']}")
            logger.info(f"Metadata: {result['metadata']}")
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
        raise
