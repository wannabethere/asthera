"""
TF-IDF Generator for Quick Reference Lookups

This module provides TF-IDF (Term Frequency-Inverse Document Frequency) generation
for documents to enable quick reference lookups and enhanced search capabilities.

Features:
- TF-IDF vector generation for documents
- Quick reference lookup by terms
- Similarity scoring between documents
- Efficient storage and retrieval of vectors
"""

import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import json

logger = logging.getLogger("genieml-agents")


class TFIDFGenerator:
    """
    TF-IDF generator for document vectors and quick reference lookups.
    
    This class provides:
    1. TF-IDF vector generation for documents
    2. Quick reference lookup by terms
    3. Similarity scoring between documents
    4. Efficient storage and retrieval of vectors
    """
    
    def __init__(
        self,
        max_features: int = 10000,
        ngram_range: Tuple[int, int] = (1, 2),
        min_df: int = 1,
        max_df: float = 0.95,
        stop_words: Optional[str] = "english"
    ):
        """
        Initialize TF-IDF generator.
        
        Args:
            max_features: Maximum number of features to consider
            ngram_range: Range of n-grams to consider
            min_df: Minimum document frequency for terms
            max_df: Maximum document frequency for terms
            stop_words: Stop words to remove (or None)
        """
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.max_df = max_df
        self.stop_words = stop_words
        
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=min_df,
            max_df=max_df,
            stop_words=stop_words,
            lowercase=True,
            strip_accents='unicode'
        )
        
        self.is_fitted = False
        self.feature_names = []
        self.document_vectors = []
        self.document_metadata = []
        
        logger.info("TF-IDF Generator initialized")
    
    async def generate_vectors(self, texts: List[str]) -> List[List[float]]:
        """
        Generate TF-IDF vectors for a list of texts.
        
        Args:
            texts: List of text documents
            
        Returns:
            List of TF-IDF vectors (one per document)
        """
        logger.info(f"Generating TF-IDF vectors for {len(texts)} documents")
        
        try:
            # Fit vectorizer and transform texts
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Convert to dense arrays for easier handling
            vectors = tfidf_matrix.toarray().tolist()
            
            # Store feature names and document vectors
            self.feature_names = self.vectorizer.get_feature_names_out().tolist()
            self.document_vectors = vectors
            self.is_fitted = True
            
            logger.info(f"Generated TF-IDF vectors with {len(self.feature_names)} features")
            return vectors
            
        except Exception as e:
            logger.error(f"Error generating TF-IDF vectors: {str(e)}")
            raise
    
    async def add_documents(
        self, 
        texts: List[str], 
        metadata: List[Dict[str, Any]]
    ) -> List[List[float]]:
        """
        Add new documents to the TF-IDF model.
        
        Args:
            texts: List of new text documents
            metadata: List of metadata for each document
            
        Returns:
            List of TF-IDF vectors for new documents
        """
        logger.info(f"Adding {len(texts)} new documents to TF-IDF model")
        
        try:
            if not self.is_fitted:
                # First time - fit and transform
                return await self.generate_vectors(texts)
            else:
                # Add to existing model
                new_vectors = self.vectorizer.transform(texts).toarray().tolist()
                self.document_vectors.extend(new_vectors)
                self.document_metadata.extend(metadata)
                
                logger.info(f"Added {len(new_vectors)} new vectors to model")
                return new_vectors
                
        except Exception as e:
            logger.error(f"Error adding documents to TF-IDF model: {str(e)}")
            raise
    
    async def find_similar_documents(
        self, 
        query_text: str, 
        top_k: int = 5,
        threshold: float = 0.1
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Find documents similar to the query text.
        
        Args:
            query_text: Query text to find similar documents for
            top_k: Number of top similar documents to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of tuples (document_index, similarity_score, metadata)
        """
        if not self.is_fitted:
            logger.warning("TF-IDF model not fitted, cannot find similar documents")
            return []
        
        try:
            # Transform query text
            query_vector = self.vectorizer.transform([query_text]).toarray()
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.document_vectors)[0]
            
            # Get top similar documents
            similar_indices = np.argsort(similarities)[::-1]
            similar_docs = []
            
            for idx in similar_indices[:top_k]:
                similarity = similarities[idx]
                if similarity >= threshold:
                    metadata = self.document_metadata[idx] if idx < len(self.document_metadata) else {}
                    similar_docs.append((int(idx), float(similarity), metadata))
            
            logger.info(f"Found {len(similar_docs)} similar documents for query")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Error finding similar documents: {str(e)}")
            return []
    
    async def get_term_importance(
        self, 
        document_index: int
    ) -> List[Tuple[str, float]]:
        """
        Get the most important terms for a specific document.
        
        Args:
            document_index: Index of the document
            
        Returns:
            List of tuples (term, importance_score)
        """
        if not self.is_fitted or document_index >= len(self.document_vectors):
            return []
        
        try:
            # Get document vector
            doc_vector = self.document_vectors[document_index]
            
            # Get term importance scores
            term_scores = list(zip(self.feature_names, doc_vector))
            
            # Sort by importance (descending)
            term_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Filter out zero scores
            important_terms = [(term, score) for term, score in term_scores if score > 0]
            
            logger.info(f"Found {len(important_terms)} important terms for document {document_index}")
            return important_terms
            
        except Exception as e:
            logger.error(f"Error getting term importance: {str(e)}")
            return []
    
    async def search_by_terms(
        self, 
        terms: List[str], 
        top_k: int = 10
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Search documents by specific terms.
        
        Args:
            terms: List of terms to search for
            top_k: Number of top documents to return
            
        Returns:
            List of tuples (document_index, relevance_score, metadata)
        """
        if not self.is_fitted:
            logger.warning("TF-IDF model not fitted, cannot search by terms")
            return []
        
        try:
            # Create query text from terms
            query_text = " ".join(terms)
            
            # Find similar documents
            similar_docs = await self.find_similar_documents(query_text, top_k=top_k)
            
            # Filter by terms (documents that actually contain the terms)
            term_filtered_docs = []
            for doc_idx, score, metadata in similar_docs:
                # Check if document contains any of the terms
                doc_text = self._get_document_text(doc_idx)
                if any(term.lower() in doc_text.lower() for term in terms):
                    term_filtered_docs.append((doc_idx, score, metadata))
            
            logger.info(f"Found {len(term_filtered_docs)} documents containing terms: {terms}")
            return term_filtered_docs
            
        except Exception as e:
            logger.error(f"Error searching by terms: {str(e)}")
            return []
    
    def _get_document_text(self, document_index: int) -> str:
        """Get the original text for a document index."""
        # This would need to be implemented based on how you store document texts
        # For now, return a placeholder
        return f"Document {document_index}"
    
    async def get_feature_names(self) -> List[str]:
        """Get the feature names (terms) from the TF-IDF model."""
        return self.feature_names.copy()
    
    async def get_document_count(self) -> int:
        """Get the number of documents in the model."""
        return len(self.document_vectors)
    
    async def save_model(self, filepath: str) -> None:
        """Save the TF-IDF model to disk."""
        try:
            model_data = {
                "vectorizer": self.vectorizer,
                "feature_names": self.feature_names,
                "document_vectors": self.document_vectors,
                "document_metadata": self.document_metadata,
                "is_fitted": self.is_fitted,
                "max_features": self.max_features,
                "ngram_range": self.ngram_range,
                "min_df": self.min_df,
                "max_df": self.max_df,
                "stop_words": self.stop_words
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"TF-IDF model saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving TF-IDF model: {str(e)}")
            raise
    
    async def load_model(self, filepath: str) -> None:
        """Load the TF-IDF model from disk."""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.vectorizer = model_data["vectorizer"]
            self.feature_names = model_data["feature_names"]
            self.document_vectors = model_data["document_vectors"]
            self.document_metadata = model_data["document_metadata"]
            self.is_fitted = model_data["is_fitted"]
            self.max_features = model_data["max_features"]
            self.ngram_range = model_data["ngram_range"]
            self.min_df = model_data["min_df"]
            self.max_df = model_data["max_df"]
            self.stop_words = model_data["stop_words"]
            
            logger.info(f"TF-IDF model loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Error loading TF-IDF model: {str(e)}")
            raise
    
    async def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about the TF-IDF model."""
        return {
            "is_fitted": self.is_fitted,
            "document_count": len(self.document_vectors),
            "feature_count": len(self.feature_names),
            "max_features": self.max_features,
            "ngram_range": self.ngram_range,
            "min_df": self.min_df,
            "max_df": self.max_df,
            "stop_words": self.stop_words
        }


class QuickReferenceLookup:
    """
    Quick reference lookup system using TF-IDF vectors.
    
    This class provides fast lookup capabilities for:
    - Table references
    - Column references
    - Relationship references
    - Business term references
    """
    
    def __init__(self, tfidf_generator: TFIDFGenerator):
        """Initialize quick reference lookup system."""
        self.tfidf_generator = tfidf_generator
        self.reference_index = {}  # term -> document_indices
        self.document_references = {}  # document_index -> reference_info
        
        logger.info("Quick Reference Lookup system initialized")
    
    async def build_reference_index(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build the reference index from documents.
        
        Args:
            documents: List of documents with metadata
        """
        logger.info("Building reference index")
        
        try:
            for doc_idx, doc in enumerate(documents):
                # Extract reference terms
                table_name = doc.get("metadata", {}).get("table_name", "")
                project_id = doc.get("metadata", {}).get("project_id", "")
                doc_type = doc.get("metadata", {}).get("type", "")
                
                # Create reference info
                reference_info = {
                    "document_index": doc_idx,
                    "table_name": table_name,
                    "project_id": project_id,
                    "document_type": doc_type,
                    "metadata": doc.get("metadata", {})
                }
                
                self.document_references[doc_idx] = reference_info
                
                # Index terms
                terms_to_index = [table_name, doc_type]
                if project_id:
                    terms_to_index.append(project_id)
                
                for term in terms_to_index:
                    if term:
                        term_lower = term.lower()
                        if term_lower not in self.reference_index:
                            self.reference_index[term_lower] = []
                        self.reference_index[term_lower].append(doc_idx)
            
            logger.info(f"Built reference index with {len(self.reference_index)} terms")
            
        except Exception as e:
            logger.error(f"Error building reference index: {str(e)}")
            raise
    
    async def lookup_by_table_name(
        self, 
        table_name: str, 
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lookup documents by table name.
        
        Args:
            table_name: Name of the table to lookup
            project_id: Optional project ID filter
            
        Returns:
            List of reference information
        """
        table_name_lower = table_name.lower()
        
        if table_name_lower not in self.reference_index:
            return []
        
        document_indices = self.reference_index[table_name_lower]
        references = []
        
        for doc_idx in document_indices:
            if doc_idx in self.document_references:
                ref_info = self.document_references[doc_idx]
                
                # Apply project filter if specified
                if project_id and ref_info.get("project_id") != project_id:
                    continue
                
                references.append(ref_info)
        
        logger.info(f"Found {len(references)} references for table: {table_name}")
        return references
    
    async def lookup_by_document_type(
        self, 
        doc_type: str, 
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lookup documents by document type.
        
        Args:
            doc_type: Type of document to lookup
            project_id: Optional project ID filter
            
        Returns:
            List of reference information
        """
        doc_type_lower = doc_type.lower()
        
        if doc_type_lower not in self.reference_index:
            return []
        
        document_indices = self.reference_index[doc_type_lower]
        references = []
        
        for doc_idx in document_indices:
            if doc_idx in self.document_references:
                ref_info = self.document_references[doc_idx]
                
                # Apply project filter if specified
                if project_id and ref_info.get("project_id") != project_id:
                    continue
                
                references.append(ref_info)
        
        logger.info(f"Found {len(references)} references for document type: {doc_type}")
        return references
    
    async def get_reference_stats(self) -> Dict[str, Any]:
        """Get statistics about the reference index."""
        return {
            "total_terms": len(self.reference_index),
            "total_documents": len(self.document_references),
            "terms": list(self.reference_index.keys())
        }
