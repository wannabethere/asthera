"""
Natural Language Search for TABLE_DOCUMENTs

This module provides natural language search capabilities for TABLE_DOCUMENTs,
enabling users to search for relevant tables and table names based on
natural language queries and project ID.

Features:
- Natural language query processing
- Semantic search across table descriptions
- Business context matching
- Project ID filtering
- Relevance scoring
- Search result ranking
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import json

from langchain_core.documents import Document as LangchainDocument
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger("genieml-agents")


@dataclass
class SearchResult:
    """Search result with relevance scoring."""
    table_name: str
    project_id: str
    display_name: str
    description: str
    business_purpose: str
    relevance_score: float
    match_type: str  # exact, semantic, business_context
    matched_terms: List[str]
    metadata: Dict[str, Any]


class NaturalLanguageSearch:
    """
    Natural language search for TABLE_DOCUMENTs.
    
    This class provides:
    1. Natural language query processing
    2. Semantic search across table descriptions
    3. Business context matching
    4. Project ID filtering
    5. Relevance scoring and ranking
    """
    
    def __init__(
        self,
        tfidf_vectorizer: Optional[TfidfVectorizer] = None,
        similarity_threshold: float = 0.1
    ):
        """
        Initialize natural language search.
        
        Args:
            tfidf_vectorizer: Optional pre-fitted TF-IDF vectorizer
            similarity_threshold: Minimum similarity threshold for results
        """
        self.tfidf_vectorizer = tfidf_vectorizer or TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            stop_words='english',
            lowercase=True,
            strip_accents='unicode'
        )
        self.similarity_threshold = similarity_threshold
        self.is_fitted = False
        self.table_documents = []
        self.searchable_texts = []
        
        logger.info("Natural Language Search initialized")
    
    async def index_table_documents(
        self,
        table_documents: List[LangchainDocument]
    ) -> None:
        """
        Index TABLE_DOCUMENTs for natural language search.
        
        Args:
            table_documents: List of TABLE_DOCUMENT LangchainDocuments
        """
        logger.info(f"Indexing {len(table_documents)} TABLE_DOCUMENTs for natural language search")
        
        try:
            self.table_documents = table_documents
            self.searchable_texts = []
            
            # Extract searchable text from each document
            for doc in table_documents:
                # Parse the document content
                content = json.loads(doc.page_content)
                
                # Create comprehensive searchable text
                searchable_text = self._create_comprehensive_searchable_text(content, doc.metadata)
                self.searchable_texts.append(searchable_text)
            
            # Fit TF-IDF vectorizer with adjusted parameters for small document sets
            if self.searchable_texts:
                num_docs = len(self.searchable_texts)
                
                # Adjust parameters if we have very few documents
                # to avoid the "max_df corresponds to < documents than min_df" error
                if num_docs < 3:
                    logger.info(f"Few documents ({num_docs}), adjusting TF-IDF parameters")
                    # For 1-2 documents, use min_df=1 and max_df=1.0 (accept all terms)
                    adjusted_vectorizer = TfidfVectorizer(
                        max_features=self.tfidf_vectorizer.max_features,
                        ngram_range=self.tfidf_vectorizer.ngram_range,
                        min_df=1,  # Accept terms appearing in at least 1 document
                        max_df=1.0,  # Accept terms appearing in all documents (all terms when < 3 docs)
                        stop_words=self.tfidf_vectorizer.stop_words,
                        lowercase=self.tfidf_vectorizer.lowercase,
                        strip_accents=self.tfidf_vectorizer.strip_accents
                    )
                    self.tfidf_vectorizer = adjusted_vectorizer
                
                self.tfidf_vectorizer.fit(self.searchable_texts)
                self.is_fitted = True
                logger.info("TF-IDF vectorizer fitted successfully")
            
        except Exception as e:
            logger.error(f"Error indexing table documents: {str(e)}")
            raise
    
    async def search_tables(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 10,
        match_types: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search for tables using natural language query.
        
        Args:
            query: Natural language search query
            project_id: Optional project ID filter
            top_k: Number of top results to return
            match_types: Optional list of match types to include
            
        Returns:
            List of SearchResult objects
        """
        if not self.is_fitted:
            logger.warning("Search index not fitted, cannot perform search")
            return []
        
        logger.info(f"Searching tables with query: '{query}'")
        
        try:
            # Process query
            processed_query = self._process_query(query)
            
            # Perform different types of searches
            all_results = []
            
            # Exact name matching
            exact_results = await self._search_exact_names(processed_query, project_id)
            all_results.extend(exact_results)
            
            # Semantic search
            semantic_results = await self._search_semantic(processed_query, project_id, top_k)
            all_results.extend(semantic_results)
            
            # Business context search
            business_results = await self._search_business_context(processed_query, project_id, top_k)
            all_results.extend(business_results)
            
            # Filter by match types if specified
            if match_types:
                all_results = [r for r in all_results if r.match_type in match_types]
            
            # Remove duplicates and rank results
            unique_results = self._deduplicate_and_rank(all_results, top_k)
            
            logger.info(f"Found {len(unique_results)} relevant tables")
            return unique_results
            
        except Exception as e:
            logger.error(f"Error searching tables: {str(e)}")
            return []
    
    async def search_by_business_domain(
        self,
        domain: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search for tables by business domain.
        
        Args:
            domain: Business domain to search for
            project_id: Optional project ID filter
            top_k: Number of top results to return
            
        Returns:
            List of SearchResult objects
        """
        logger.info(f"Searching tables by business domain: '{domain}'")
        
        results = []
        
        for i, doc in enumerate(self.table_documents):
            try:
                content = json.loads(doc.page_content)
                metadata = doc.metadata
                
                # Apply project filter
                if project_id and metadata.get("project_id") != project_id:
                    continue
                
                # Check domain match
                table_domain = content.get("domain", "")
                if domain.lower() in table_domain.lower():
                    result = SearchResult(
                        table_name=content.get("table_name", ""),
                        project_id=metadata.get("project_id", ""),
                        display_name=content.get("display_name", ""),
                        description=content.get("description", ""),
                        business_purpose=content.get("business_purpose", ""),
                        relevance_score=1.0,
                        match_type="domain",
                        matched_terms=[domain],
                        metadata=metadata
                    )
                    results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing document {i}: {str(e)}")
                continue
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(f"Found {len(results)} tables in domain: {domain}")
        return results[:top_k]
    
    async def search_by_usage_type(
        self,
        usage_type: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Search for tables by usage type.
        
        Args:
            usage_type: Usage type to search for (e.g., 'analytics', 'reporting', 'transactional')
            project_id: Optional project ID filter
            top_k: Number of top results to return
            
        Returns:
            List of SearchResult objects
        """
        logger.info(f"Searching tables by usage type: '{usage_type}'")
        
        results = []
        
        for i, doc in enumerate(self.table_documents):
            try:
                content = json.loads(doc.page_content)
                metadata = doc.metadata
                
                # Apply project filter
                if project_id and metadata.get("project_id") != project_id:
                    continue
                
                # Check usage type in columns
                columns = content.get("columns", [])
                for column in columns:
                    column_usage_type = column.get("usage_type", "")
                    if usage_type.lower() in column_usage_type.lower():
                        result = SearchResult(
                            table_name=content.get("table_name", ""),
                            project_id=metadata.get("project_id", ""),
                            display_name=content.get("display_name", ""),
                            description=content.get("description", ""),
                            business_purpose=content.get("business_purpose", ""),
                            relevance_score=0.8,
                            match_type="usage_type",
                            matched_terms=[usage_type],
                            metadata=metadata
                        )
                        results.append(result)
                        break  # Only add table once
                
            except Exception as e:
                logger.error(f"Error processing document {i}: {str(e)}")
                continue
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(f"Found {len(results)} tables with usage type: {usage_type}")
        return results[:top_k]
    
    def _process_query(self, query: str) -> str:
        """Process and normalize the search query."""
        # Convert to lowercase
        processed = query.lower()
        
        # Remove special characters but keep spaces
        processed = re.sub(r'[^\w\s]', ' ', processed)
        
        # Remove extra whitespace
        processed = ' '.join(processed.split())
        
        return processed
    
    def _create_comprehensive_searchable_text(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> str:
        """Create comprehensive searchable text for a table document."""
        searchable_parts = []
        
        # Table information
        searchable_parts.extend([
            content.get("table_name", ""),
            content.get("display_name", ""),
            content.get("description", ""),
            content.get("business_purpose", ""),
            content.get("domain", ""),
            content.get("classification", "")
        ])
        
        # Business rules and guidelines
        business_rules = content.get("business_rules", [])
        for rule in business_rules:
            searchable_parts.append(rule)
        
        usage_guidelines = content.get("usage_guidelines", [])
        for guideline in usage_guidelines:
            searchable_parts.append(guideline)
        
        # Tags
        tags = content.get("tags", [])
        searchable_parts.extend(tags)
        
        # Column information
        columns = content.get("columns", [])
        for column in columns:
            searchable_parts.extend([
                column.get("name", ""),
                column.get("display_name", ""),
                column.get("business_description", ""),
                column.get("business_purpose", ""),
                column.get("usage_type", ""),
                column.get("privacy_classification", "")
            ])
            
            # Column business rules
            column_rules = column.get("business_rules", [])
            for rule in column_rules:
                searchable_parts.append(rule)
            
            # Column usage guidelines
            column_guidelines = column.get("usage_guidelines", [])
            for guideline in column_guidelines:
                searchable_parts.append(guideline)
            
            # Related concepts
            related_concepts = column.get("related_concepts", [])
            searchable_parts.extend(related_concepts)
        
        # Relationship information
        relationships = content.get("relationships", [])
        for relationship in relationships:
            searchable_parts.extend([
                relationship.get("name", ""),
                relationship.get("description", ""),
                relationship.get("business_purpose", "")
            ])
        
        # Filter out empty strings and join
        return " ".join([part for part in searchable_parts if part])
    
    async def _search_exact_names(
        self,
        query: str,
        project_id: Optional[str] = None
    ) -> List[SearchResult]:
        """Search for exact table name matches."""
        results = []
        query_terms = query.split()
        
        for i, doc in enumerate(self.table_documents):
            try:
                content = json.loads(doc.page_content)
                metadata = doc.metadata
                
                # Apply project filter
                if project_id and metadata.get("project_id") != project_id:
                    continue
                
                table_name = content.get("table_name", "").lower()
                display_name = content.get("display_name", "").lower()
                
                # Check for exact matches
                matched_terms = []
                for term in query_terms:
                    if term in table_name or term in display_name:
                        matched_terms.append(term)
                
                if matched_terms:
                    result = SearchResult(
                        table_name=content.get("table_name", ""),
                        project_id=metadata.get("project_id", ""),
                        display_name=content.get("display_name", ""),
                        description=content.get("description", ""),
                        business_purpose=content.get("business_purpose", ""),
                        relevance_score=1.0,
                        match_type="exact",
                        matched_terms=matched_terms,
                        metadata=metadata
                    )
                    results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing document {i} for exact search: {str(e)}")
                continue
        
        return results
    
    async def _search_semantic(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Perform semantic search using TF-IDF."""
        if not self.is_fitted:
            return []
        
        try:
            # Transform query
            query_vector = self.tfidf_vectorizer.transform([query])
            
            # Transform all documents
            doc_vectors = self.tfidf_vectorizer.transform(self.searchable_texts)
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, doc_vectors)[0]
            
            # Get top similar documents
            similar_indices = np.argsort(similarities)[::-1]
            results = []
            
            for idx in similar_indices[:top_k]:
                similarity = similarities[idx]
                if similarity >= self.similarity_threshold:
                    doc = self.table_documents[idx]
                    content = json.loads(doc.page_content)
                    metadata = doc.metadata
                    
                    # Apply project filter
                    if project_id and metadata.get("project_id") != project_id:
                        continue
                    
                    result = SearchResult(
                        table_name=content.get("table_name", ""),
                        project_id=metadata.get("project_id", ""),
                        display_name=content.get("display_name", ""),
                        description=content.get("description", ""),
                        business_purpose=content.get("business_purpose", ""),
                        relevance_score=float(similarity),
                        match_type="semantic",
                        matched_terms=[],
                        metadata=metadata
                    )
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    async def _search_business_context(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Search based on business context and purpose."""
        results = []
        query_terms = query.split()
        
        for i, doc in enumerate(self.table_documents):
            try:
                content = json.loads(doc.page_content)
                metadata = doc.metadata
                
                # Apply project filter
                if project_id and metadata.get("project_id") != project_id:
                    continue
                
                # Check business context fields
                business_purpose = content.get("business_purpose", "").lower()
                description = content.get("description", "").lower()
                
                matched_terms = []
                for term in query_terms:
                    if term in business_purpose or term in description:
                        matched_terms.append(term)
                
                if matched_terms:
                    # Calculate relevance score based on number of matches
                    relevance_score = len(matched_terms) / len(query_terms)
                    
                    result = SearchResult(
                        table_name=content.get("table_name", ""),
                        project_id=metadata.get("project_id", ""),
                        display_name=content.get("display_name", ""),
                        description=content.get("description", ""),
                        business_purpose=content.get("business_purpose", ""),
                        relevance_score=relevance_score,
                        match_type="business_context",
                        matched_terms=matched_terms,
                        metadata=metadata
                    )
                    results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing document {i} for business context search: {str(e)}")
                continue
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return results[:top_k]
    
    def _deduplicate_and_rank(
        self,
        results: List[SearchResult],
        top_k: int
    ) -> List[SearchResult]:
        """Remove duplicates and rank results."""
        # Remove duplicates based on table_name and project_id
        seen = set()
        unique_results = []
        
        for result in results:
            key = (result.table_name, result.project_id)
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Sort by relevance score (exact matches first, then by score)
        def sort_key(result):
            if result.match_type == "exact":
                return (0, -result.relevance_score)
            elif result.match_type == "semantic":
                return (1, -result.relevance_score)
            else:
                return (2, -result.relevance_score)
        
        unique_results.sort(key=sort_key)
        
        return unique_results[:top_k]
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "indexed_documents": len(self.table_documents),
            "is_fitted": self.is_fitted,
            "similarity_threshold": self.similarity_threshold,
            "vectorizer_features": len(self.tfidf_vectorizer.get_feature_names_out()) if self.is_fitted else 0
        }
