"""
Storage Manager for Unified ChromaDB System

This module provides a high-level storage manager that orchestrates the unified
storage system, TF-IDF generation, and document building. It serves as the
main interface for the new indexing system.

Features:
- Unified storage orchestration
- TF-IDF integration
- Document building coordination
- Backward compatibility
- Enhanced search capabilities
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Union
import json
import os

from langchain_core.documents import Document as LangchainDocument
from app.storage.documents import AsyncDocumentWriter, DocumentChromaStore, DuplicatePolicy

from app.indexing2.unified_storage import UnifiedStorage
from app.indexing2.tfidf_generator import TFIDFGenerator, QuickReferenceLookup
from app.indexing2.document_builder import DocumentBuilder
from app.indexing2.ddl_chunker import DDLChunker
from app.indexing2.natural_language_search import NaturalLanguageSearch
from app.indexing2.query_builder import QueryBuilder
from app.indexing2.llm_field_classifier import LLMFieldClassifier
from app.indexing2.llm_query_optimizer import LLMQueryOptimizer
from app.settings import get_settings
from app.core.dependencies import get_llm   
logger = logging.getLogger("genieml-agents")

settings = get_settings()
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
llm = get_llm()

class StorageManager:
    """
    High-level storage manager for the unified ChromaDB system.
    
    This class orchestrates:
    1. Unified storage operations
    2. TF-IDF generation and management
    3. Document building and enhancement
    4. Quick reference lookups
    5. Backward compatibility with existing systems
    """
    
    def __init__(
        self,
        document_store: DocumentChromaStore,
        embedder: Any,
        column_batch_size: int = 200,
        enable_tfidf: bool = True,
        tfidf_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the storage manager.
        
        Args:
            document_store: ChromaDB document store
            embedder: Embedding model
            column_batch_size: Batch size for column processing
            enable_tfidf: Whether to enable TF-IDF generation
            tfidf_config: Configuration for TF-IDF generator
        """
        logger.info("Initializing Storage Manager")
        
        self._document_store = document_store
        self._embedder = embedder
        self._column_batch_size = column_batch_size
        self._enable_tfidf = enable_tfidf
        
        # Initialize components
        self._unified_storage = UnifiedStorage(
            document_store=document_store,
            embedder=embedder,
            column_batch_size=column_batch_size
        )
        
        self._document_builder = DocumentBuilder()
        self._ddl_chunker = DDLChunker(column_batch_size=column_batch_size)
        self._natural_language_search = NaturalLanguageSearch()
        self._query_builder = QueryBuilder()
        self._llm_field_classifier = LLMFieldClassifier(llm_client=llm)
        self._llm_query_optimizer = LLMQueryOptimizer(llm_client=llm)
        
        # Initialize TF-IDF if enabled
        self._tfidf_generator = None
        self._quick_lookup = None
        if enable_tfidf:
            tfidf_config = tfidf_config or {}
            self._tfidf_generator = TFIDFGenerator(**tfidf_config)
            self._quick_lookup = QuickReferenceLookup(self._tfidf_generator)
        
        logger.info("Storage Manager initialized successfully")
    
    async def process_mdl(
        self, 
        mdl_str: str, 
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process MDL string and create unified documents with TF-IDF.
        
        Args:
            mdl_str: MDL string containing models, relationships, views, metrics
            project_id: Project identifier
            
        Returns:
            Dict containing processing results
        """
        logger.info(f"Starting unified MDL processing for project: {project_id}")
        
        try:
            # Parse MDL
            mdl = json.loads(mdl_str)
            logger.info("MDL parsed successfully")
            
            # Create unified documents
            unified_docs = await self._create_unified_documents(mdl, project_id)
            logger.info(f"Created {len(unified_docs)} unified documents")
            
            # Create individual documents
            individual_docs = await self._create_individual_documents(mdl, project_id)
            logger.info(f"Created {len(individual_docs)} individual documents")
            
            # Create TABLE_DOCUMENTs for natural language search
            table_docs = await self._ddl_chunker.create_table_documents(mdl, project_id)
            logger.info(f"Created {len(table_docs)} TABLE_DOCUMENTs")
            
            # Create TABLE_COLUMN documents using helper.py functionality
            table_column_docs = await self._ddl_chunker.create_table_column_documents(mdl, project_id)
            logger.info(f"Created {len(table_column_docs)} TABLE_COLUMN documents")
            
            # Index TABLE_DOCUMENTs for natural language search
            await self._natural_language_search.index_table_documents(table_docs)
            logger.info("TABLE_DOCUMENTs indexed for natural language search")
            
            # Generate TF-IDF vectors if enabled
            if self._enable_tfidf and self._tfidf_generator:
                await self._generate_tfidf_vectors(unified_docs + individual_docs)
                logger.info("TF-IDF vectors generated successfully")
                
                # Build quick reference index
                if self._quick_lookup:
                    await self._build_quick_reference_index(unified_docs + individual_docs)
                    logger.info("Quick reference index built successfully")
            
            # Store documents
            all_documents = unified_docs + individual_docs + table_docs + table_column_docs
            write_result = await self._unified_storage._writer.run(documents=all_documents)
            logger.info(f"Successfully stored {write_result['documents_written']} documents")
            
            return {
                "documents_written": write_result["documents_written"],
                "unified_documents": len(unified_docs),
                "individual_documents": len(individual_docs),
                "table_documents": len(table_docs),
                "table_column_documents": len(table_column_docs),
                "tfidf_enabled": self._enable_tfidf,
                "natural_language_search_enabled": True,
                "project_id": project_id
            }
            
        except Exception as e:
            error_msg = f"Error in unified MDL processing: {str(e)}"
            logger.error(error_msg)
            raise
    
    async def _create_unified_documents(
        self, 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create unified TABLE_SCHEMA documents."""
        logger.info("Creating unified TABLE_SCHEMA documents")
        
        documents = []
        models = mdl.get("models", [])
        
        for model in models:
            try:
                table_name = model.get("name", "")
                if not table_name:
                    continue
                
                # Extract relationships for this table
                relationships = self._extract_table_relationships(table_name, mdl.get("relationships", []))
                
                # Enhance columns with business context
                enhanced_columns = await self._enhance_columns(model.get("columns", []), model)
                
                # Build unified document
                doc = self._document_builder.build_unified_document(
                    table_name=table_name,
                    project_id=project_id,
                    model=model,
                    mdl=mdl,
                    enhanced_columns=enhanced_columns,
                    relationships=relationships
                )
                
                documents.append(doc)
                logger.info(f"Created unified document for table: {table_name}")
                
            except Exception as e:
                logger.error(f"Error creating unified document for {model.get('name', 'unknown')}: {str(e)}")
                continue
        
        return documents
    
    async def _create_individual_documents(
        self, 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create individual documents for each type."""
        logger.info("Creating individual documents")
        
        documents = []
        
        # Process models for TABLE_COLUMNS documents
        for model in mdl.get("models", []):
            table_name = model.get("name", "")
            if not table_name:
                continue
            
            # Create TABLE_COLUMNS documents
            column_docs = await self._create_table_columns_documents(model, project_id)
            documents.extend(column_docs)
            
            # Create RELATIONSHIPS documents
            relationship_docs = await self._create_relationships_documents(model, mdl, project_id)
            documents.extend(relationship_docs)
        
        # Process views
        for view in mdl.get("views", []):
            view_doc = await self._create_view_document(view, project_id)
            if view_doc:
                documents.append(view_doc)
        
        # Process metrics
        for metric in mdl.get("metrics", []):
            metric_doc = await self._create_metric_document(metric, project_id)
            if metric_doc:
                documents.append(metric_doc)
        
        return documents
    
    async def _create_table_columns_documents(
        self, 
        model: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create TABLE_COLUMNS documents."""
        documents = []
        table_name = model.get("name", "")
        columns = model.get("columns", [])
        
        # Batch columns
        for i in range(0, len(columns), self._column_batch_size):
            batch_columns = columns[i:i + self._column_batch_size]
            
            # Enhance columns in this batch
            enhanced_batch = []
            for column in batch_columns:
                if column.get("isHidden", False):
                    continue
                
                enhanced_column = self._document_builder.enhance_column_with_business_context(
                    column, model
                )
                enhanced_batch.append(enhanced_column)
            
            if enhanced_batch:
                # Create TABLE_COLUMNS document
                doc = self._document_builder.build_table_columns_document(
                    table_name=table_name,
                    project_id=project_id,
                    columns=enhanced_batch,
                    batch_index=i // self._column_batch_size
                )
                documents.append(doc)
        
        return documents
    
    async def _create_relationships_documents(
        self, 
        model: Dict[str, Any], 
        mdl: Dict[str, Any], 
        project_id: str
    ) -> List[LangchainDocument]:
        """Create RELATIONSHIPS documents."""
        documents = []
        table_name = model.get("name", "")
        relationships = mdl.get("relationships", [])
        
        # Create primary keys map
        primary_keys_map = {m["name"]: m.get("primaryKey", "") for m in mdl.get("models", [])}
        
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            if table_name not in models_in_relationship:
                continue
            
            # Build foreign key constraint
            condition = relationship.get("condition", "")
            join_type = relationship.get("joinType", "")
            
            if len(models_in_relationship) == 2 and condition and "=" in condition:
                is_source = table_name == models_in_relationship[0]
                related_table = models_in_relationship[1] if is_source else models_in_relationship[0]
                
                condition_parts = condition.split(" = ")
                fk_column = condition_parts[0 if is_source else 1].split(".")[1]
                
                fk_constraint = f"FOREIGN KEY ({fk_column}) REFERENCES {related_table}({primary_keys_map.get(related_table, '')})"
                
                # Create RELATIONSHIPS document
                doc = self._document_builder.build_relationships_document(
                    table_name=table_name,
                    project_id=project_id,
                    relationship=relationship,
                    constraint=fk_constraint
                )
                documents.append(doc)
        
        return documents
    
    async def _create_view_document(
        self, 
        view: Dict[str, Any], 
        project_id: str
    ) -> Optional[LangchainDocument]:
        """Create VIEW document."""
        view_name = view.get("name", "")
        if not view_name:
            return None
        
        return self._document_builder.build_view_document(
            view_name=view_name,
            project_id=project_id,
            view=view
        )
    
    async def _create_metric_document(
        self, 
        metric: Dict[str, Any], 
        project_id: str
    ) -> Optional[LangchainDocument]:
        """Create METRIC document."""
        metric_name = metric.get("name", "")
        if not metric_name:
            return None
        
        # Create dimension and measure columns
        dimensions = []
        measures = []
        
        for dim in metric.get("dimension", []):
            dimensions.append({
                "type": "COLUMN",
                "name": dim.get("name", ""),
                "data_type": dim.get("type", ""),
                "comment": "-- This column is a dimension\n  "
            })
        
        for measure in metric.get("measure", []):
            measures.append({
                "type": "COLUMN", 
                "name": measure.get("name", ""),
                "data_type": measure.get("type", ""),
                "comment": "-- This column is a measure\n  "
            })
        
        return self._document_builder.build_metric_document(
            metric_name=metric_name,
            project_id=project_id,
            metric=metric,
            dimensions=dimensions,
            measures=measures
        )
    
    async def _enhance_columns(
        self, 
        columns: List[Dict[str, Any]], 
        model: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhance columns with business context."""
        enhanced_columns = []
        
        for column in columns:
            if column.get("isHidden", False):
                continue
            
            enhanced_column = self._document_builder.enhance_column_with_business_context(
                column, model
            )
            enhanced_columns.append(enhanced_column)
        
        return enhanced_columns
    
    def _extract_table_relationships(
        self, 
        table_name: str, 
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relationships for a specific table."""
        table_relationships = []
        
        for relationship in relationships:
            models_in_relationship = relationship.get("models", [])
            if table_name in models_in_relationship:
                table_relationships.append({
                    "name": relationship.get("name", ""),
                    "models": models_in_relationship,
                    "joinType": relationship.get("joinType", ""),
                    "condition": relationship.get("condition", ""),
                    "properties": relationship.get("properties", {})
                })
        
        return table_relationships
    
    async def _generate_tfidf_vectors(
        self, 
        documents: List[LangchainDocument]
    ) -> None:
        """Generate TF-IDF vectors for documents."""
        if not self._tfidf_generator:
            logger.warning("TF-IDF generator not available, skipping vector generation")
            return
        
        logger.info("Generating TF-IDF vectors for documents")
        
        try:
            # Extract text content from documents
            texts = []
            metadata_list = []
            
            for doc in documents:
                # Combine page_content and metadata for TF-IDF
                text_content = f"{doc.page_content} {json.dumps(doc.metadata)}"
                texts.append(text_content)
                metadata_list.append(doc.metadata)
            
            # Generate TF-IDF vectors
            tfidf_vectors = await self._tfidf_generator.generate_vectors(texts)
            
            # Add vectors to document metadata
            for i, doc in enumerate(documents):
                if i < len(tfidf_vectors):
                    doc.metadata["tfidf_vector"] = tfidf_vectors[i]
            
            logger.info(f"Generated TF-IDF vectors for {len(documents)} documents")
            
        except Exception as e:
            logger.error(f"Error generating TF-IDF vectors: {str(e)}")
    
    async def _build_quick_reference_index(
        self, 
        documents: List[LangchainDocument]
    ) -> None:
        """Build quick reference index for fast lookups."""
        if not self._quick_lookup:
            logger.warning("Quick lookup not available, skipping index building")
            return
        
        logger.info("Building quick reference index")
        
        try:
            # Prepare documents for indexing
            doc_data = []
            for doc in documents:
                doc_data.append({
                    "metadata": doc.metadata,
                    "content": doc.page_content
                })
            
            # Build reference index
            await self._quick_lookup.build_reference_index(doc_data)
            
            logger.info("Quick reference index built successfully")
            
        except Exception as e:
            logger.error(f"Error building quick reference index: {str(e)}")
    
    async def search_by_table_name(
        self, 
        table_name: str, 
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents by table name using quick reference lookup.
        
        Args:
            table_name: Name of the table to search for
            project_id: Optional project ID filter
            
        Returns:
            List of document references
        """
        if not self._quick_lookup:
            logger.warning("Quick lookup not available")
            return []
        
        try:
            references = await self._quick_lookup.lookup_by_table_name(table_name, project_id)
            logger.info(f"Found {len(references)} references for table: {table_name}")
            return references
            
        except Exception as e:
            logger.error(f"Error searching by table name: {str(e)}")
            return []
    
    async def search_by_document_type(
        self, 
        doc_type: str, 
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents by document type using quick reference lookup.
        
        Args:
            doc_type: Type of document to search for
            project_id: Optional project ID filter
            
        Returns:
            List of document references
        """
        if not self._quick_lookup:
            logger.warning("Quick lookup not available")
            return []
        
        try:
            references = await self._quick_lookup.lookup_by_document_type(doc_type, project_id)
            logger.info(f"Found {len(references)} references for document type: {doc_type}")
            return references
            
        except Exception as e:
            logger.error(f"Error searching by document type: {str(e)}")
            return []
    
    async def find_similar_documents(
        self, 
        query_text: str, 
        top_k: int = 5,
        threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Find documents similar to the query text using TF-IDF.
        
        Args:
            query_text: Query text to find similar documents for
            top_k: Number of top similar documents to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar document references
        """
        if not self._tfidf_generator:
            logger.warning("TF-IDF generator not available")
            return []
        
        try:
            similar_docs = await self._tfidf_generator.find_similar_documents(
                query_text, top_k, threshold
            )
            
            # Convert to reference format
            references = []
            for doc_idx, score, metadata in similar_docs:
                references.append({
                    "document_index": doc_idx,
                    "similarity_score": score,
                    "metadata": metadata
                })
            
            logger.info(f"Found {len(references)} similar documents for query")
            return references
            
        except Exception as e:
            logger.error(f"Error finding similar documents: {str(e)}")
            return []
    
    async def get_tfidf_stats(self) -> Dict[str, Any]:
        """Get TF-IDF generator statistics."""
        if not self._tfidf_generator:
            return {"enabled": False}
        
        try:
            stats = await self._tfidf_generator.get_model_stats()
            stats["enabled"] = True
            return stats
            
        except Exception as e:
            logger.error(f"Error getting TF-IDF stats: {str(e)}")
            return {"enabled": False, "error": str(e)}
    
    async def get_quick_lookup_stats(self) -> Dict[str, Any]:
        """Get quick reference lookup statistics."""
        if not self._quick_lookup:
            return {"enabled": False}
        
        try:
            stats = await self._quick_lookup.get_reference_stats()
            stats["enabled"] = True
            return stats
            
        except Exception as e:
            logger.error(f"Error getting quick lookup stats: {str(e)}")
            return {"enabled": False, "error": str(e)}
    
    async def search_tables_by_natural_language(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 10,
        match_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for tables using natural language query.
        
        Args:
            query: Natural language search query
            project_id: Optional project ID filter
            top_k: Number of top results to return
            match_types: Optional list of match types to include
            
        Returns:
            List of search results with relevance scoring
        """
        logger.info(f"Searching tables with natural language query: '{query}'")
        
        try:
            results = await self._natural_language_search.search_tables(
                query=query,
                project_id=project_id,
                top_k=top_k,
                match_types=match_types
            )
            
            # Convert SearchResult objects to dictionaries
            search_results = []
            for result in results:
                search_results.append({
                    "table_name": result.table_name,
                    "project_id": result.project_id,
                    "display_name": result.display_name,
                    "description": result.description,
                    "business_purpose": result.business_purpose,
                    "relevance_score": result.relevance_score,
                    "match_type": result.match_type,
                    "matched_terms": result.matched_terms,
                    "metadata": result.metadata
                })
            
            logger.info(f"Found {len(search_results)} relevant tables")
            return search_results
            
        except Exception as e:
            logger.error(f"Error in natural language search: {str(e)}")
            return []
    
    async def search_tables_by_domain(
        self,
        domain: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for tables by business domain.
        
        Args:
            domain: Business domain to search for
            project_id: Optional project ID filter
            top_k: Number of top results to return
            
        Returns:
            List of search results
        """
        logger.info(f"Searching tables by domain: '{domain}'")
        
        try:
            results = await self._natural_language_search.search_by_business_domain(
                domain=domain,
                project_id=project_id,
                top_k=top_k
            )
            
            # Convert SearchResult objects to dictionaries
            search_results = []
            for result in results:
                search_results.append({
                    "table_name": result.table_name,
                    "project_id": result.project_id,
                    "display_name": result.display_name,
                    "description": result.description,
                    "business_purpose": result.business_purpose,
                    "relevance_score": result.relevance_score,
                    "match_type": result.match_type,
                    "matched_terms": result.matched_terms,
                    "metadata": result.metadata
                })
            
            logger.info(f"Found {len(search_results)} tables in domain: {domain}")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching by domain: {str(e)}")
            return []
    
    async def search_tables_by_usage_type(
        self,
        usage_type: str,
        project_id: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for tables by usage type.
        
        Args:
            usage_type: Usage type to search for
            project_id: Optional project ID filter
            top_k: Number of top results to return
            
        Returns:
            List of search results
        """
        logger.info(f"Searching tables by usage type: '{usage_type}'")
        
        try:
            results = await self._natural_language_search.search_by_usage_type(
                usage_type=usage_type,
                project_id=project_id,
                top_k=top_k
            )
            
            # Convert SearchResult objects to dictionaries
            search_results = []
            for result in results:
                search_results.append({
                    "table_name": result.table_name,
                    "project_id": result.project_id,
                    "display_name": result.display_name,
                    "description": result.description,
                    "business_purpose": result.business_purpose,
                    "relevance_score": result.relevance_score,
                    "match_type": result.match_type,
                    "matched_terms": result.matched_terms,
                    "metadata": result.metadata
                })
            
            logger.info(f"Found {len(search_results)} tables with usage type: {usage_type}")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching by usage type: {str(e)}")
            return []
    
    async def get_natural_language_search_stats(self) -> Dict[str, Any]:
        """Get natural language search statistics."""
        try:
            stats = await self._natural_language_search.get_search_stats()
            stats["enabled"] = True
            return stats
            
        except Exception as e:
            logger.error(f"Error getting natural language search stats: {str(e)}")
            return {"enabled": False, "error": str(e)}
    
    async def build_query_for_table(
        self,
        table_name: str,
        project_id: str,
        query_type: str = "analytical",
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[List[str]] = None,
        group_by: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build an optimized query for a specific table using field type classification.
        
        Args:
            table_name: Name of the table to build query for
            project_id: Project ID to filter by
            query_type: Type of query (analytical, transactional, reporting)
            filters: Optional filters to apply
            aggregations: Optional aggregation functions
            group_by: Optional GROUP BY columns
            order_by: Optional ORDER BY columns
            limit: Optional LIMIT clause
            
        Returns:
            Dictionary containing the generated query and metadata
        """
        logger.info(f"Building {query_type} query for table: {table_name}")
        
        try:
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            
            # Build query using the query builder
            query_result = self._query_builder.build_query_from_table_document(
                table_document=table_document,
                query_type=query_type,
                filters=filters,
                aggregations=aggregations,
                group_by=group_by,
                order_by=order_by,
                limit=limit
            )
            
            logger.info(f"Successfully built {query_type} query for table: {table_name}")
            return query_result
            
        except Exception as e:
            logger.error(f"Error building query for table {table_name}: {str(e)}")
            raise
    
    async def get_query_suggestions(
        self,
        table_name: str,
        project_id: str,
        field_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get query suggestions for a table based on field types.
        
        Args:
            table_name: Name of the table
            project_id: Project ID to filter by
            field_type: Optional field type to filter suggestions by
            
        Returns:
            Dictionary containing query suggestions
        """
        logger.info(f"Getting query suggestions for table: {table_name}")
        
        try:
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            columns = table_document.get("columns", [])
            
            # Classify columns by field type
            classified_columns = self._query_builder._classify_columns_by_field_type(columns)
            
            # Generate suggestions based on field types
            suggestions = {
                "analytical_queries": self._get_analytical_suggestions(classified_columns),
                "transactional_queries": self._get_transactional_suggestions(classified_columns),
                "reporting_queries": self._get_reporting_suggestions(classified_columns),
                "performance_optimizations": self._get_performance_suggestions(classified_columns),
                "indexing_recommendations": self._get_indexing_recommendations(classified_columns)
            }
            
            # Filter by field type if specified
            if field_type:
                suggestions = self._filter_suggestions_by_field_type(suggestions, field_type)
            
            logger.info(f"Generated query suggestions for table: {table_name}")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting query suggestions for table {table_name}: {str(e)}")
            raise
    
    def _get_analytical_suggestions(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get analytical query suggestions."""
        # Not needed - using SQL pairs and instructions
        return []
    
    def _get_transactional_suggestions(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get transactional query suggestions."""
        # Not needed - using SQL pairs and instructions
        return []
    
    def _get_reporting_suggestions(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get reporting query suggestions."""
        # Not needed - using SQL pairs and instructions
        return []
    
    def _get_performance_suggestions(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get performance optimization suggestions."""
        suggestions = []
        
        if classified_columns["facts"]:
            suggestions.append("Consider using columnar storage for analytical workloads")
            suggestions.append("Use appropriate aggregation functions for better performance")
        
        if classified_columns["dimensions"]:
            suggestions.append("Consider bitmap indexes for low-cardinality dimensions")
            suggestions.append("Use appropriate data types to minimize storage")
        
        if classified_columns["identifiers"]:
            suggestions.append("Ensure proper indexing on identifier columns")
            suggestions.append("Use integer types for better join performance")
        
        if classified_columns["timestamps"]:
            suggestions.append("Consider partitioning by date ranges")
            suggestions.append("Use appropriate timestamp data types")
        
        return suggestions
    
    def _get_indexing_recommendations(self, classified_columns: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Get indexing recommendations."""
        recommendations = []
        
        for field_type, columns in classified_columns.items():
            for column in columns:
                column_name = column.get("name", "")
                
                if field_type == "identifier":
                    recommendations.append(f"Create primary key or unique index on {column_name}")
                elif field_type == "dimension":
                    recommendations.append(f"Consider index on {column_name} for frequent filtering")
                elif field_type == "timestamp":
                    recommendations.append(f"Create index on {column_name} for date range queries")
                elif field_type == "fact":
                    recommendations.append(f"Consider composite indexes with dimension columns for {column_name}")
        
        return recommendations
    
    def _filter_suggestions_by_field_type(self, suggestions: Dict[str, Any], field_type: str) -> Dict[str, Any]:
        """Filter suggestions by field type."""
        filtered_suggestions = {}
        
        for category, suggestion_list in suggestions.items():
            if isinstance(suggestion_list, list):
                filtered_suggestions[category] = [
                    suggestion for suggestion in suggestion_list
                    if field_type.lower() in suggestion.lower()
                ]
            else:
                filtered_suggestions[category] = suggestion_list
        
        return filtered_suggestions
    
    async def classify_columns_with_llm(
        self,
        table_name: str,
        project_id: str,
        llm_client=None
    ) -> Dict[str, Any]:
        """
        Use LLM to classify table columns for better query building.
        
        Args:
            table_name: Name of the table to classify
            project_id: Project ID to filter by
            llm_client: Optional LLM client for classification
            
        Returns:
            Dictionary with LLM classification results
        """
        logger.info(f"Classifying columns with LLM for table: {table_name}")
        
        try:
            # Set LLM client if provided
            if llm_client:
                self._llm_field_classifier.llm_client = llm_client
            
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            
            # Classify columns with LLM
            classification_results = await self._llm_field_classifier.classify_table_columns_with_llm(
                table_document=table_document,
                project_context={"project_id": project_id}
            )
            
            # Get classification statistics
            stats = await self._llm_field_classifier.get_classification_stats()
            
            logger.info(f"Successfully classified {len(classification_results)} columns with LLM")
            return {
                "table_name": table_name,
                "project_id": project_id,
                "classification_results": classification_results,
                "classification_stats": stats,
                "llm_enabled": llm_client is not None
            }
            
        except Exception as e:
            logger.error(f"Error classifying columns with LLM: {str(e)}")
            raise
    
    async def optimize_query_with_llm(
        self,
        query: str,
        table_name: str,
        project_id: str,
        optimization_level: str = "intermediate",
        llm_client=None
    ) -> Dict[str, Any]:
        """
        Use LLM to optimize a SQL query.
        
        Args:
            query: SQL query to optimize
            table_name: Name of the table
            project_id: Project ID to filter by
            optimization_level: Level of optimization (basic, intermediate, advanced, expert)
            llm_client: Optional LLM client for optimization
            
        Returns:
            Dictionary with optimized query and recommendations
        """
        logger.info(f"Optimizing query with LLM for table: {table_name}")
        
        try:
            # Set LLM client if provided
            if llm_client:
                self._llm_query_optimizer.llm_client = llm_client
            
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            
            # Optimize query with LLM
            from .llm_query_optimizer import OptimizationLevel
            opt_level = OptimizationLevel(optimization_level)
            
            optimization_result = await self._llm_query_optimizer.optimize_query_with_llm(
                original_query=query,
                table_document=table_document,
                query_context={"table_name": table_name, "project_id": project_id},
                optimization_level=opt_level
            )
            
            # Get optimization statistics
            stats = await self._llm_query_optimizer.get_optimization_stats()
            
            logger.info(f"Successfully optimized query with LLM")
            return {
                "original_query": query,
                "optimized_query": optimization_result.optimized_query,
                "optimization_level": optimization_result.optimization_level,
                "performance_improvements": optimization_result.performance_improvements,
                "indexing_suggestions": optimization_result.indexing_suggestions,
                "business_impact": optimization_result.business_impact,
                "confidence": optimization_result.confidence,
                "reasoning": optimization_result.reasoning,
                "optimization_stats": stats,
                "llm_enabled": llm_client is not None
            }
            
        except Exception as e:
            logger.error(f"Error optimizing query with LLM: {str(e)}")
            raise
    
    async def analyze_query_performance_with_llm(
        self,
        query: str,
        table_name: str,
        project_id: str,
        performance_metrics: Optional[Dict[str, Any]] = None,
        llm_client=None
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze query performance.
        
        Args:
            query: SQL query to analyze
            table_name: Name of the table
            project_id: Project ID to filter by
            performance_metrics: Optional performance metrics
            llm_client: Optional LLM client for analysis
            
        Returns:
            Dictionary with performance analysis and recommendations
        """
        logger.info(f"Analyzing query performance with LLM for table: {table_name}")
        
        try:
            # Set LLM client if provided
            if llm_client:
                self._llm_query_optimizer.llm_client = llm_client
            
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            
            # Analyze performance with LLM
            performance_analysis = await self._llm_query_optimizer.analyze_query_performance_with_llm(
                query=query,
                table_document=table_document,
                performance_metrics=performance_metrics
            )
            
            logger.info(f"Successfully analyzed query performance with LLM")
            return {
                "query": query,
                "table_name": table_name,
                "project_id": project_id,
                "performance_analysis": performance_analysis,
                "llm_enabled": llm_client is not None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing query performance with LLM: {str(e)}")
            raise
    
    async def suggest_indexing_strategy_with_llm(
        self,
        table_name: str,
        project_id: str,
        query_patterns: List[str],
        performance_requirements: Optional[Dict[str, Any]] = None,
        llm_client=None
    ) -> Dict[str, Any]:
        """
        Use LLM to suggest indexing strategies.
        
        Args:
            table_name: Name of the table
            project_id: Project ID to filter by
            query_patterns: List of common query patterns
            performance_requirements: Optional performance requirements
            llm_client: Optional LLM client for strategy generation
            
        Returns:
            Dictionary with indexing strategy recommendations
        """
        logger.info(f"Suggesting indexing strategy with LLM for table: {table_name}")
        
        try:
            # Set LLM client if provided
            if llm_client:
                self._llm_query_optimizer.llm_client = llm_client
            
            # Search for the table document
            table_results = await self.search_tables_by_natural_language(
                table_name,
                project_id=project_id,
                top_k=1
            )
            
            if not table_results:
                raise ValueError(f"Table '{table_name}' not found in project '{project_id}'")
            
            table_document = table_results[0]
            
            # Suggest indexing strategy with LLM
            indexing_strategy = await self._llm_query_optimizer.suggest_indexing_strategy_with_llm(
                table_document=table_document,
                query_patterns=query_patterns,
                performance_requirements=performance_requirements
            )
            
            logger.info(f"Successfully suggested indexing strategy with LLM")
            return {
                "table_name": table_name,
                "project_id": project_id,
                "indexing_strategy": indexing_strategy,
                "llm_enabled": llm_client is not None
            }
            
        except Exception as e:
            logger.error(f"Error suggesting indexing strategy with LLM: {str(e)}")
            raise
    
    async def get_llm_capabilities(self) -> Dict[str, Any]:
        """Get LLM capabilities and status."""
        try:
            classification_stats = await self._llm_field_classifier.get_classification_stats()
            optimization_stats = await self._llm_query_optimizer.get_optimization_stats()
            
            return {
                "field_classification": {
                    "enabled": classification_stats.get("llm_available", False),
                    "method": classification_stats.get("classification_method", "Rule-based"),
                    "cache_size": classification_stats.get("cache_size", 0)
                },
                "query_optimization": {
                    "enabled": optimization_stats.get("llm_available", False),
                    "method": optimization_stats.get("optimization_method", "Rule-based"),
                    "cache_size": optimization_stats.get("cache_size", 0)
                },
                "overall_llm_enabled": (
                    classification_stats.get("llm_available", False) or
                    optimization_stats.get("llm_available", False)
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting LLM capabilities: {str(e)}")
            return {
                "field_classification": {"enabled": False, "error": str(e)},
                "query_optimization": {"enabled": False, "error": str(e)},
                "overall_llm_enabled": False
            }
    
    async def clean(self, project_id: Optional[str] = None) -> None:
        """Clean documents for the specified project."""
        logger.info(f"Starting cleanup for project: {project_id}")
        
        try:
            await self._unified_storage.clean(project_id)
            logger.info(f"Successfully cleaned documents for project: {project_id}")
            
        except Exception as e:
            error_msg = f"Error cleaning documents: {str(e)}"
            logger.error(error_msg)
            raise
