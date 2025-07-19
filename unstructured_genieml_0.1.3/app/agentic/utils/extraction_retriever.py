import logging
import time
import asyncio
import hashlib
import json
import pickle
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import chromadb
from chromadb.api.types import Where
import numpy as np
from chromadb.config import Settings

from app.config.agent_config import get_agent_config, chroma_collections
from app.config.settings import get_settings

# Dataclasses for extraction and caching
@dataclass
class ExtractionResult:
    """Structured extraction from documents"""
    entities: List[str]
    keywords: List[str]
    topics: List[str]
    categories: List[str]
    summary: str
    metadata: Dict[str, Any]

@dataclass
class CachedResult:
    """Cached search result with TTL"""
    query_hash: str
    results: List[Dict]
    timestamp: datetime
    categories: List[str]
    ttl_seconds: int = 3600

# Set up logging
logger = logging.getLogger("ExtractionRetriever")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.info("=== ExtractionRetriever Logger Initialized ===")

class ExtractionBasedRetriever:
    def __init__(self, collection_name: str, use_remote_chroma: bool = True):
        """
        Initialize the retriever with either remote ChromaDB server or local persistent client
        
        Args:
            collection_name: Name prefix for the collections
            use_remote_chroma: If True, connect to remote ChromaDB server from settings
        """
        self.settings = get_settings()
        
        if use_remote_chroma:
            # Connect to remote ChromaDB server using settings
            try:
                self.client = chromadb.HttpClient(
                    host=self.settings.CHROMA_HOST,
                    port=self.settings.CHROMA_PORT,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info(f"Connected to remote ChromaDB server at {self.settings.CHROMA_HOST}:{self.settings.CHROMA_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to remote ChromaDB server: {e}")
                logger.info("Falling back to local persistent client")
                self.client = chromadb.PersistentClient(
                    path="./chroma_db",
                    settings=Settings(anonymized_telemetry=False)
                )
        else:
            # Use local persistent client
            self.client = chromadb.PersistentClient(
                path="./chroma_db",
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info("Using local ChromaDB persistent client")
        
        # Test connection
        try:
            self.client.heartbeat()
            logger.info("ChromaDB connection successful")
        except Exception as e:
            logger.error(f"ChromaDB connection test failed: {e}")
            raise
        
        # Use collections from agent_config instead of creating with suffixes
        self.chunks_collection = self.client.get_or_create_collection(
            name=chroma_collections.chunks_collection,
            metadata={"hnsw:space": "cosine", "hnsw:M": 32}
        )
        
        # Index collection for fast lookup - DISABLED
        # self.index_collection = self.client.get_or_create_collection(
        #     name=chroma_collections.cache_collection,
        #     metadata={"hnsw:space": "cosine", "hnsw:M": 16}
        # )
        
        # Save the collection name for reference
        self.collection_name = collection_name
        
        # In-memory caches
        self.query_cache = {}
        self.entity_index = defaultdict(set)  # entity -> set of chunk_ids
        self.keyword_index = defaultdict(set)  # keyword -> set of chunk_ids
        self.category_index = defaultdict(set)  # category -> set of chunk_ids
        self.conversation_cache = {}  # conversation_id -> cached context
        
        # Load existing indexes
        # self._load_indexes()
        
        logger.info(f"Initialized ExtractionBasedRetriever with collection: {chroma_collections.chunks_collection} (cache disabled)")
    
    def extract_features(self, text: str, categories: Optional[List[str]] = None) -> ExtractionResult:
        """
        Extract structured features from text for indexing
        """
        # Simple extraction (replace with your preferred NLP pipeline)
        # For production, use spacy, transformers, or custom extractors
        
        # Extract entities (simplified - use NER in production)
        entities = self._extract_entities_simple(text)
        
        # Extract keywords (simplified - use TF-IDF, YAKE, or KeyBERT in production)
        keywords = self._extract_keywords_simple(text)
        
        # Extract topics (simplified - use topic modeling in production)
        topics = self._extract_topics_simple(text)
        
        # Generate summary (simplified - use summarization models in production)
        summary = self._generate_summary_simple(text)
        
        return ExtractionResult(
            entities=entities,
            keywords=keywords,
            topics=topics,
            categories=categories or [],
            summary=summary,
            metadata={
                "length": len(text),
                "word_count": len(text.split()),
                "has_numbers": bool(re.search(r'\d+', text)),
                "has_dates": bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', text))
            }
        )
    
    def _extract_entities_simple(self, text: str) -> List[str]:
        """Simple entity extraction - replace with proper NER"""
        # This is a placeholder - use spacy NER or transformers in production
        entities = []
        # Simple pattern matching for common entities
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'
        
        entities.extend(re.findall(email_pattern, text))
        entities.extend(re.findall(phone_pattern, text))
        
        return list(set(entities))
    
    def _extract_keywords_simple(self, text: str) -> List[str]:
        """Simple keyword extraction - replace with proper keyword extraction"""
        # Remove common words and extract meaningful terms
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'men', 'too', 'any', 'say', 'let', 'put', 'try', 'why', 'ask', 'run', 'own', 'few', 'lot', 'big', 'end', 'far', 'off', 'got', 'yet', 'set', 'act', 'age', 'air', 'art', 'bad', 'box', 'car', 'eat', 'eye', 'fun', 'got', 'gun', 'hit', 'job', 'lot', 'man', 'new', 'oil', 'run', 'sea', 'six', 'ten', 'top', 'war', 'win', 'yes'}
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Get most frequent keywords
        from collections import Counter
        keyword_counts = Counter(keywords)
        return [word for word, count in keyword_counts.most_common(10)]
    
    def _extract_topics_simple(self, text: str) -> List[str]:
        """Simple topic extraction - replace with topic modeling"""
        # Simple rule-based topic detection
        topics = []
        text_lower = text.lower()
        
        topic_keywords = {
            'technology': ['software', 'computer', 'algorithm', 'programming', 'data', 'api', 'database'],
            'business': ['revenue', 'profit', 'customer', 'market', 'sales', 'strategy', 'company'],
            'science': ['research', 'study', 'analysis', 'experiment', 'hypothesis', 'conclusion'],
            'health': ['medical', 'patient', 'treatment', 'diagnosis', 'healthcare', 'medicine'],
            'education': ['student', 'teacher', 'learning', 'course', 'university', 'academic']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _generate_summary_simple(self, text: str) -> str:
        """Simple summary generation - replace with proper summarization"""
        sentences = re.split(r'[.!?]+', text)
        if len(sentences) <= 2:
            return text
        # Return first two sentences as summary
        return '. '.join(sentences[:2]).strip() + '.'
    
    def preprocess_and_chunk_documents(self, documents: List[Dict], chunk_size: int = 512, overlap: int = 50):
        """
        Preprocess documents, extract features, and create optimized chunks
        """
        all_chunks = []
        # all_index_entries = []
        
        for doc_id, doc in enumerate(documents):
            text = doc.get('content', '')
            categories = doc.get('categories', [])
            doc_metadata = doc.get('metadata', {})
            
            # Extract features from full document
            extraction = self.extract_features(text, categories)
            
            # Create chunks with overlap
            chunks = self._create_overlapping_chunks(text, chunk_size, overlap)
            
            for chunk_id, chunk_text in enumerate(chunks):
                chunk_doc_id = f"{doc_id}_{chunk_id}"
                
                # Extract features from chunk
                chunk_extraction = self.extract_features(chunk_text, categories)
                
                # Combine document and chunk features
                combined_metadata = {
                    **doc_metadata,
                    **asdict(chunk_extraction),
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "parent_entities": extraction.entities,
                    "parent_keywords": extraction.keywords,
                    "parent_topics": extraction.topics,
                    "chunk_size": len(chunk_text),
                    "overlap_start": max(0, chunk_id * (chunk_size - overlap)),
                    "overlap_end": min(len(text), (chunk_id + 1) * chunk_size - chunk_id * overlap)
                }
                
                # Create searchable flags for fast filtering
                for entity in chunk_extraction.entities + extraction.entities:
                    combined_metadata[f"has_entity_{entity.lower().replace(' ', '_')}"] = True
                    self.entity_index[entity.lower()].add(chunk_doc_id)
                
                for keyword in chunk_extraction.keywords + extraction.keywords:
                    combined_metadata[f"has_keyword_{keyword.lower()}"] = True
                    self.keyword_index[keyword.lower()].add(chunk_doc_id)
                
                for category in categories:
                    combined_metadata[f"has_category_{category.lower().replace(' ', '_')}"] = True
                    self.category_index[category.lower()].add(chunk_doc_id)
                
                all_chunks.append({
                    'id': chunk_doc_id,
                    'text': chunk_text,
                    'metadata': combined_metadata
                })
                
                # Create index entry for fast lookup - DISABLED
                # index_text = f"{' '.join(chunk_extraction.entities)} {' '.join(chunk_extraction.keywords)} {' '.join(categories)}"
                # all_index_entries.append({
                #     'id': f"idx_{chunk_doc_id}",
                #     'text': index_text,
                #     'metadata': {
                #         'chunk_id': chunk_doc_id,
                #         'categories': categories,
                #         'entity_count': len(chunk_extraction.entities),
                #         'keyword_count': len(chunk_extraction.keywords)
                #     }
                # })
        
        # Add to ChromaDB collections
        if all_chunks:
            self.chunks_collection.add(
                documents=[chunk['text'] for chunk in all_chunks],
                metadatas=[chunk['metadata'] for chunk in all_chunks],
                ids=[chunk['id'] for chunk in all_chunks]
            )
        
        # Add index entries - DISABLED
        # if all_index_entries:
        #     self.index_collection.add(
        #         documents=[entry['text'] for entry in all_index_entries],
        #         metadatas=[entry['metadata'] for entry in all_index_entries],
        #         ids=[entry['id'] for entry in all_index_entries]
        #     )
        
        # Save indexes - DISABLED
        # self._save_indexes()
        
        return len(all_chunks)
    
    def _create_overlapping_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Create overlapping chunks to maintain context"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) > overlap:  # Avoid tiny chunks
                chunks.append(' '.join(chunk_words))
        
        return chunks
    
    def fast_prefilter_search(self, query: str, categories: Optional[List[str]] = None, 
                            entities: Optional[List[str]] = None, keywords: Optional[List[str]] = None,
                            max_candidates: int = 100) -> Set[Any]:
        """
        Fast pre-filtering using indexes to reduce search space
        """
        candidate_chunks = set()
        
        # Filter by categories
        if categories:
            for category in categories:
                candidate_chunks.update(self.category_index.get(category.lower(), set()))
        
        # Filter by entities
        if entities:
            for entity in entities:
                candidate_chunks.update(self.entity_index.get(entity.lower(), set()))
        
        # Filter by keywords
        if keywords:
            for keyword in keywords:
                candidate_chunks.update(self.keyword_index.get(keyword.lower(), set()))
        
        # If no specific filters, use index collection for broad search - DISABLED
        # if not candidate_chunks:
        #     # Cast include parameter to Any to avoid type errors
        #     include_param: Any = ["metadatas"]
        #     index_results = self.index_collection.query(
        #         query_texts=[query],
        #         n_results=max_candidates,
        #         include=include_param
        #     )
        #     
        #     if index_results['metadatas'] and index_results['metadatas'][0]:
        #         candidate_chunks = {
        #             meta['chunk_id'] for meta in index_results['metadatas'][0] if meta and 'chunk_id' in meta
        #         }
        
        return candidate_chunks
    
    def realtime_search(self, query: str, categories: Optional[List[str]] = None,
                       conversation_id: Optional[str] = None, top_k: int = 20,
                       use_cache: bool = True) -> Dict:
        """
        Real-time search with caching and context awareness
        """
        # Create query hash for caching
        query_hash = self._create_query_hash(query, categories)
        
        # Check cache first - DISABLED
        # if use_cache and query_hash in self.query_cache:
        #     cached = self.query_cache[query_hash]
        #     if datetime.now() - cached.timestamp < timedelta(seconds=cached.ttl_seconds):
        #         return {'results': cached.results, 'from_cache': True, 'query_hash': query_hash}
        
        # Extract features from query
        query_extraction = self.extract_features(query, categories)
        
        # Fast pre-filtering
        candidate_chunks = self.fast_prefilter_search(
            query, categories, query_extraction.entities, query_extraction.keywords
        )
        
        # If we have conversation context, boost relevant chunks
        if conversation_id and conversation_id in self.conversation_cache:
            context_chunks = self.conversation_cache[conversation_id]
            # Boost chunks that are related to previous context
            candidate_chunks.update(context_chunks)
        
        # Semantic search on filtered candidates
        results = {}
        include_param: Any = ["documents", "metadatas", "distances"]
        
        if candidate_chunks:
            # Build where filter for candidate chunks
            # Using individual $eq conditions instead of $in for better compatibility
            where_filter: Any = {"$or": [{"chunk_id": {"$eq": chunk_id}} for chunk_id in list(candidate_chunks)[:1000]]}
            
            results = self.chunks_collection.query(
                query_texts=[query],
                n_results=top_k,
                where=cast(Where, where_filter),
                include=include_param
            )
        else:
            # Fallback to general search
            results = self.chunks_collection.query(
                query_texts=[query],
                n_results=top_k,
                include=include_param
            )
        
        # Process and rank results
        processed_results = self._process_and_rank_results(
            results, query_extraction, conversation_id
        )
        
        # Cache results - DISABLED
        # if use_cache:
        #     self.query_cache[query_hash] = CachedResult(
        #         query_hash=query_hash,
        #         results=processed_results,
        #         timestamp=datetime.now(),
        #         categories=categories or []
        #     )
        
        # Update conversation cache
        if conversation_id:
            relevant_chunks = {
                result['metadata']['chunk_id'] 
                for result in processed_results[:5]  # Top 5 for context
                if result['metadata'].get('chunk_id')
            }
            self.conversation_cache[conversation_id] = relevant_chunks
        
        return {
            'results': processed_results,
            'from_cache': False,
            'query_hash': query_hash,
            'candidates_filtered': len(candidate_chunks) if candidate_chunks else 0
        }
    
    def _process_and_rank_results(self, results: Any, query_extraction: ExtractionResult,
                                conversation_id: Optional[str] = None) -> List[Dict]:
        """
        Process and re-rank results based on multiple factors
        """
        processed = []
        
        if not results.get('documents') or not results['documents'][0]:
            return processed
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0], 
            results['distances'][0]
        )):
            # Calculate relevance score
            relevance_score = 1 - distance
            
            # Entity overlap bonus
            doc_entities = set(metadata.get('entities', []))
            query_entities = set(query_extraction.entities)
            entity_overlap = len(doc_entities.intersection(query_entities))
            
            # Keyword overlap bonus
            doc_keywords = set(metadata.get('keywords', []))
            query_keywords = set(query_extraction.keywords)
            keyword_overlap = len(doc_keywords.intersection(query_keywords))
            
            # Category relevance bonus
            doc_categories = set(metadata.get('categories', []))
            query_categories = set(query_extraction.categories)
            category_overlap = len(doc_categories.intersection(query_categories))
            
            # Conversation context bonus
            context_bonus = 0
            if conversation_id and conversation_id in self.conversation_cache:
                if metadata.get('chunk_id') in self.conversation_cache[conversation_id]:
                    context_bonus = 0.1
            
            # Calculate final score
            final_score = (
                relevance_score * 0.6 +
                entity_overlap * 0.1 +
                keyword_overlap * 0.1 +
                category_overlap * 0.15 +
                context_bonus * 0.05
            )
            
            processed.append({
                'document': doc,
                'metadata': metadata,
                'distance': distance,
                'relevance_score': relevance_score,
                'entity_overlap': entity_overlap,
                'keyword_overlap': keyword_overlap,
                'category_overlap': category_overlap,
                'final_score': final_score,
                'chunk_id': metadata.get('chunk_id')
            })
        
        # Sort by final score
        processed.sort(key=lambda x: x['final_score'], reverse=True)
        return processed
    
    def _create_query_hash(self, query: str, categories: Optional[List[str]] = None) -> str:
        """Create hash for query caching"""
        cache_key = f"{query}_{sorted(categories or [])}"
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _save_indexes(self):
        """Save in-memory indexes to disk"""
        indexes = {
            'entity_index': dict(self.entity_index),
            'keyword_index': dict(self.keyword_index),
            'category_index': dict(self.category_index)
        }
        
        try:
            # Use a standard filename for indexes
            with open('chroma_indexes.pkl', 'wb') as f:
                pickle.dump(indexes, f)
        except Exception as e:
            logger.warning(f"Failed to save indexes: {e}")
    
    def _load_indexes(self):
        """Load in-memory indexes from disk"""
        try:
            # Use standard index file
            with open('chroma_indexes.pkl', 'rb') as f:
                indexes = pickle.load(f)
                self.entity_index = defaultdict(set, indexes.get('entity_index', {}))
                self.keyword_index = defaultdict(set, indexes.get('keyword_index', {}))
                self.category_index = defaultdict(set, indexes.get('category_index', {}))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to load indexes: {e}")
    
    def clear_cache(self, conversation_id: Optional[str] = None):
        """Clear cache for specific conversation or all caches"""
        if conversation_id:
            self.conversation_cache.pop(conversation_id, None)
        else:
            self.query_cache.clear()
            self.conversation_cache.clear()
    
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        return {
            'total_chunks': self.chunks_collection.count(),
            # 'total_index_entries': self.index_collection.count(),
            'cached_queries': len(self.query_cache),
            'active_conversations': len(self.conversation_cache),
            'entity_index_size': len(self.entity_index),
            'keyword_index_size': len(self.keyword_index),
            'category_index_size': len(self.category_index),
            'chunks_collection': chroma_collections.chunks_collection,
            'cache_collection': chroma_collections.cache_collection
        }

    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about the current ChromaDB connection"""
        try:
            client_type = type(self.client).__name__
            connection_info = {
                "client_type": client_type,
                "collections": {
                    "chunks": self.chunks_collection.name,
                    # "index": self.index_collection.name,
                    "chunks_count": self.chunks_collection.count(),
                    # "index_count": self.index_collection.count()
                }
            }
            
            if hasattr(self.client, '_host'):
                connection_info["host"] = getattr(self.client, '_host', None)
                connection_info["port"] = getattr(self.client, '_port', None)
            
            return connection_info
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            return {"error": str(e)}

    def test_connection(self) -> Dict[str, Any]:
        """Test the ChromaDB connection and return status"""
        try:
            # Test heartbeat
            self.client.heartbeat()
            
            # Test collection access
            chunk_count = self.chunks_collection.count()
            # index_count = self.index_collection.count()
            
            return {
                "status": "connected",
                "chunk_collection_count": chunk_count,
                # "index_collection_count": index_count,
                "connection_info": self.get_connection_info()
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

class EnhancedExtractionRetriever:
    """
    A wrapper class for ExtractionBasedRetriever to make it easily usable with the app.agentic framework.
    Provides convenience methods for specialized retrievals and filters for different data sources.
    """
    
    def __init__(self, collection_name: Optional[str] = None, use_remote_chroma: bool = True):
        """
        Initialize the enhanced extraction retriever.
        
        Args:
            collection_name: Optional reference name for the retriever (not directly used for collections anymore)
            use_remote_chroma: Whether to use remote ChromaDB (True) or local (False)
        """
        # Store reference name (not used for actual collections anymore)
        self.collection_name = collection_name or "default"
        
        # Initialize the retriever (now uses standardized collection names from agent_config)
        self.retriever = ExtractionBasedRetriever(
            collection_name=self.collection_name,  # Just a reference name now
            use_remote_chroma=use_remote_chroma
        )
        logger.info(f"EnhancedExtractionRetriever initialized with reference name: {self.collection_name}")
        logger.info(f"Using collections from agent_config: chunks={chroma_collections.chunks_collection}, cache={chroma_collections.cache_collection}")
        
        # Test connection
        connection_status = self.retriever.test_connection()
        if connection_status["status"] == "connected":
            logger.info("Successfully connected to ChromaDB")
            logger.info(f"Connection details: {connection_status['connection_info']}")
        else:
            logger.error(f"Failed to connect to ChromaDB: {connection_status.get('error', 'Unknown error')}")
            raise ConnectionError(f"Failed to connect to ChromaDB: {connection_status.get('error', 'Unknown error')}")
    
    async def retrieve_documents(
        self, 
        query: str, 
        categories: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        source_type: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents using the ExtractionBasedRetriever with source filtering.
        
        Args:
            query: The search query
            categories: List of document categories to search in
            conversation_id: Optional conversation ID for context-aware search
            source_type: Optional source type filter ('salesforce', 'gong', etc.)
            document_ids: Optional list of document IDs to filter by
            topics: Optional list of topics to search for
            keywords: Optional list of keywords to search for
            top_k: Number of results to return
            
        Returns:
            List of retrieved documents with metadata and relevance scores
        """
        try:
            # Get agent config based on source type for proper limits
            config = get_agent_config(source_type=source_type)
            
            # Use config value if top_k is not provided
            if top_k is None:
                top_k = config.realtime_search_limit
            
            # Initialize categories as an empty list if None
            if categories is None:
                categories = []
                
            # If no categories provided but source_type is, create category from source_type
            if not categories and source_type:
                if source_type.lower() in ['salesforce', 'sfdc']:
                    categories = ['salesforce', 'sfdc', 'opportunity', 'deal', 'pipeline']
                elif source_type.lower() in ['gong', 'transcript']:
                    categories = ['gong', 'transcript', 'call']
            
            # If topics provided, add them to categories for better retrieval
            if topics:
                categories.extend(topics)
            
            # Add keywords to topics if provided
            if keywords:
                categories.extend(keywords)
            
            # Make sure categories is a list before passing to retriever
            if not isinstance(categories, list):
                categories = list(categories)
            
            # Create document type filter based on source_type
            where_filter = None
            if source_type:
                if source_type.lower() in ['salesforce', 'sfdc']:
                    # Filter for Salesforce documents (both insights and chunks)
                    where_filter = {"$or": [
                        {"document_type": {"$eq": "sfdc_opportunity_insights"}},
                        {"document_type": {"$eq": "sfdc_chunk"}},
                        {"metadata.document_type": {"$eq": "sfdc_opportunity_insights"}},
                        {"metadata.document_type": {"$eq": "sfdc_chunk"}}
                    ]}
                elif source_type.lower() in ['gong', 'transcript']:
                    # Filter for Gong documents
                    where_filter = {"$or": [
                        {"document_type": {"$eq": "gong_transcript"}},
                        {"document_type": {"$eq": "gong_chunk"}},
                        {"metadata.document_type": {"$eq": "gong_transcript"}},
                        {"metadata.document_type": {"$eq": "gong_chunk"}}
                    ]}
                elif source_type.lower() == 'parallel':
                    # Return both Salesforce and Gong documents
                    where_filter = {"$or": [
                        # Salesforce documents
                        {"document_type": {"$eq": "sfdc_opportunity_insights"}},
                        {"document_type": {"$eq": "sfdc_chunk"}},
                        {"metadata.document_type": {"$eq": "sfdc_opportunity_insights"}},
                        {"metadata.document_type": {"$eq": "sfdc_chunk"}},
                        # Gong documents
                        {"document_type": {"$eq": "gong_transcript"}},
                        {"document_type": {"$eq": "gong_chunk"}},
                        {"metadata.document_type": {"$eq": "gong_transcript"}},
                        {"metadata.document_type": {"$eq": "gong_chunk"}}
                    ]}
            
            # Call the realtime_search method
            logger.info(f"Performing retrieval for query: '{query}' with categories: {categories}")
            if where_filter:
                logger.info(f"Using document type filter: {where_filter}")
            start_time = time.time()
            
            try:
                # Pass the modified retriever.realtime_search method with a custom where_filter for document types
                search_results = self._search_with_filter(
                    query=query,
                    categories=categories,
                    conversation_id=conversation_id or f"temp_{int(time.time())}",
                    top_k=top_k,
                    where_filter=where_filter
                )
                
                # Get the search results
                results = search_results.get('results', [])
                logger.info(f"Retrieved {len(results)} documents in {time.time() - start_time:.2f} seconds")
                
                # Filter by document_ids if provided
                if document_ids:
                    # Extract document IDs from metadata
                    filtered_results = []
                    for result in results:
                        metadata = result.get('metadata', {})
                        result_doc_id = metadata.get('doc_id')
                        # Also check for document_id in metadata
                        if not result_doc_id:
                            result_doc_id = metadata.get('document_id')
                        # Check if the document ID is in the provided list
                        if result_doc_id and any(doc_id in str(result_doc_id) for doc_id in document_ids):
                            filtered_results.append(result)
                    results = filtered_results
                    logger.info(f"Filtered to {len(results)} documents matching document IDs")
                
                # Format the results for agent consumption
                formatted_results = []
                for result in results:
                    # Extract required fields from the retriever result
                    document = result.get('document', '')
                    metadata = result.get('metadata', {})
                    relevance_score = result.get('final_score', 0.0)
                    
                    # Format as expected by agentic
                    formatted_doc = {
                        "document_id": metadata.get('doc_id', metadata.get('document_id', '')),
                        "document_type": metadata.get('document_type', source_type or 'unknown'),
                        "content": document,
                        "relevance_score": relevance_score,
                        "metadata": metadata
                    }
                    formatted_results.append(formatted_doc)
                
                return formatted_results
            except Exception as e:
                logger.error(f"Error in retrieve_documents: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return []
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return []
    
    def _search_with_filter(self, query: str, categories: List[str], conversation_id: str, 
                           top_k: int, where_filter: Optional[Dict] = None) -> Dict:
        """
        Helper method to perform search with additional document type filtering.
        This method adapts the retriever.realtime_search to support document type filtering.
        
        Args:
            query: The search query
            categories: List of document categories to search in
            conversation_id: Conversation ID for context-aware search
            top_k: Number of results to return
            where_filter: Optional filter for document types
            
        Returns:
            Search result dictionary with results and metrics
        """
        try:
            # Get ChromaDB client with reduced logging
            chroma_db = self._get_chroma_client()
            
            # We'll adapt the retriever's logic but use ChromaDB directly with the where_filter
            # Extract features from the query for matching
            query_extraction = self.retriever.extract_features(query, categories)
            
            # Log extraction results
            logger.info(f"Query features - Entities: {query_extraction.entities[:5]}, "
                       f"Keywords: {query_extraction.keywords[:5]}, "
                       f"Topics: {query_extraction.topics[:5]}")
            
            # Build the retrieval query (combine query with extracted features)
            enhanced_query = f"{query} {' '.join(query_extraction.keywords[:5])} {' '.join(query_extraction.topics[:5])}"
            
            # Perform search
            search_start = time.time()
            
            # Query ChromaDB with the where_filter
            results = chroma_db.query_collection_with_relevance_scores(
                collection_name=chroma_collections.chunks_collection,
                query_texts=[enhanced_query],
                n_results=top_k,
                where=where_filter
            )
            
            search_time = time.time() - search_start
            logger.info(f"ChromaDB search completed in {search_time:.2f}s, retrieved {len(results)} results")
            
            # Process and rank results
            ranked_results = self.retriever._process_and_rank_results(
                results={"ids": [[r["document_id"] for r in results]],
                        "documents": [[r["content"] for r in results]],
                        "metadatas": [[r["metadata"] for r in results]],
                        "distances": [[r.get("distance", 0.5) for r in results]]},
                query_extraction=query_extraction,
                conversation_id=conversation_id
            )
            
            # Save query to conversation context
            if conversation_id:
                self.retriever.conversation_cache[conversation_id] = {
                    "last_query": query,
                    "last_results": ranked_results[:min(5, len(ranked_results))],
                    "timestamp": datetime.now()
                }
            
            # Return formatted results with metrics
            return {
                "results": ranked_results,
                "metrics": {
                    "search_time": search_time,
                    "total_candidates": len(results),
                    "final_results": len(ranked_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in _search_with_filter: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"results": [], "metrics": {"error": str(e)}}
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics from the retriever."""
        return self.retriever.get_statistics()
    
    def clear_cache(self, conversation_id: Optional[str] = None):
        """Clear cache for specific conversation or all caches."""
        self.retriever.clear_cache(conversation_id or "")
        logger.info(f"Cleared cache for conversation: {conversation_id if conversation_id else 'all'}")
    
    async def preprocess_documents(self, documents: List[Dict], chunk_size: int = 512, overlap: int = 50) -> int:
        """
        Preprocess and add documents to the retriever.
        
        Args:
            documents: List of documents to add
            chunk_size: Size of chunks to create
            overlap: Overlap between chunks
            
        Returns:
            Number of chunks created
        """
        start_time = time.time()
        logger.info(f"Preprocessing {len(documents)} documents")
        
        # Add documents to the retriever
        chunks_created = self.retriever.preprocess_and_chunk_documents(
            documents=documents,
            chunk_size=chunk_size,
            overlap=overlap
        )
        
        logger.info(f"Created {chunks_created} chunks in {time.time() - start_time:.2f} seconds")
        return chunks_created

    def _get_chroma_client(self) -> Any:
        """Initialize and return ChromaDB client with reduced logging level."""
        try:
            # Import ChromaDB here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            
            # Initialize with WARNING log level to reduce noise
            return ChromaDB(log_level="WARNING")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB client: {e}")
            raise
    
    async def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific document by its ID from any collection.
        
        Args:
            document_id: The document ID to retrieve
            
        Returns:
            The document if found, or None if not found
        """
        try:
            # Get ChromaDB client with reduced logging
            chroma_db = self._get_chroma_client()
            
            # Try each collection in turn
            for collection_name in [chroma_collections.documents_collection, 
                                   chroma_collections.insights_collection,
                                   chroma_collections.chunks_collection]:
                try:
                    result = chroma_db.get_record(collection_name, document_id)
                    if result and 'documents' in result and len(result['documents']) > 0:
                        # Create a formatted document object
                        doc = {
                            'document_id': document_id,
                            'content': result['documents'][0],
                            'metadata': result['metadatas'][0] if 'metadatas' in result and result['metadatas'] else {},
                            'collection': collection_name
                        }
                        return doc
                except Exception:
                    # Continue to the next collection if not found
                    pass
            
            logger.warning(f"Document not found in any collection: {document_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving document by ID: {e}")
            return None 