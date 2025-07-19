"""
Ingestion Pipeline orchestrator.

This module provides the main orchestration logic for running ingestion pipelines
using components created by the abstract factories.
"""
import json
import logging
from typing import Dict, List, Any, Optional, cast

from .factories import IngestFactory
from .storage.base import IStorage
from .storage.postgres import PostgresStorage
from .storage.chroma import ChromaDBStorage

# Configure logging
logger = logging.getLogger(__name__)

class IngestPipeline:
    """
    Main orchestrator for running an ingestion pipeline.
    
    This class coordinates the extraction, vectorization, stats generation,
    and storage steps of the ingestion process.
    """
    
    def __init__(self, factory: IngestFactory):
        """
        Initialize the pipeline with components from the provided factory.
        
        Args:
            factory: Factory to create pipeline components
        """
        self.factory = factory
        self.extractor = factory.create_extractor()
        self.stats_generator = factory.create_stats_generator()
        self.vectorizer = factory.create_vectorizer()
    
    def run(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the complete ingestion pipeline.
        
        Args:
            config: Configuration for the ingestion process
            
        Returns:
            Dictionary containing results and statistics about the ingestion process
        """
        debug_mode = config.get("debug", False)
        
        logger.info("Starting ingestion pipeline")
        if debug_mode:
            logger.debug(f"Pipeline config: {json.dumps(config, default=str)}")
        
        # Track metrics for the pipeline run
        metrics = {
            "documents_extracted": 0,
            "stats_generated": 0,
            "vectors_created": 0,
            "storage_results": {
                "documents": 0,
                "vectors": 0,
                "stats": 0,
                "insights": 0
            },
            "success": False,
            "errors": []
        }
        
        # Create storage backends based on config
        postgres_storage = None
        chroma_storage = None
        
        # Only initialize storage if not in test mode
        if not config.get("test_mode", False):
            # Create PostgreSQL storage if enabled
            if config.get("use_postgres", True):
                storage = self.factory.create_storage("postgres")
                if isinstance(storage, PostgresStorage):
                    postgres_storage = storage
            
            # Create ChromaDB storage if enabled
            if config.get("use_chroma", True):
                storage = self.factory.create_storage("chroma")
                if isinstance(storage, ChromaDBStorage):
                    chroma_storage = storage
        
        try:
            # Step 1: Extract documents from source
            logger.info("Step 1: Extracting documents")
            documents = self.extractor.extract(config)
            metrics["documents_extracted"] = len(documents)
            
            if debug_mode:
                logger.debug(f"Extracted {len(documents)} documents")
                if documents:
                    logger.debug(f"PIPELINE EXTRACTION OUTPUT SAMPLE: {json.dumps(documents[0], indent=2, default=str)}")
            
            if not documents:
                metrics["errors"].append("No documents extracted")
                return metrics
            
            # Add debug flag to all document metadata so components can detect it
            for doc in documents:
                if "metadata" not in doc:
                    doc["metadata"] = {}
                doc["metadata"]["debug"] = debug_mode
            
            # Step 2: Generate stats if available
            logger.info("Step 2: Generating stats")
            stats = []
            if self.stats_generator:
                # Pass debug config to stats generator
                stats_config = config.copy()
                stats_config["debug"] = debug_mode
                stats = self.stats_generator.generate_stats(documents)
                metrics["stats_generated"] = len(stats)
                
                if debug_mode:
                    logger.debug(f"Generated {len(stats)} stats records")
                    if stats:
                        logger.debug(f"PIPELINE STATS OUTPUT SAMPLE: {json.dumps(stats[0], indent=2, default=str)}")
            
            # Step 3: Vectorize documents to create chunks and insights
            logger.info("Step 3: Vectorizing documents")
            vectors = []
            if self.vectorizer and not config.get("skip_insights", False):
                # Pass debug config to vectorizer
                vectorizer_config = config.copy()
                vectorizer_config["debug"] = debug_mode
                vectors = self.vectorizer.vectorize(documents)
                metrics["vectors_created"] = len(vectors)
                
                if debug_mode:
                    logger.debug(f"Generated {len(vectors)} vector chunks")
                    if vectors:
                        logger.debug(f"PIPELINE VECTORIZATION OUTPUT SAMPLE: {json.dumps(vectors[0], indent=2, default=str)}")
            
            # Step 4: Store everything in storage backends
            logger.info("Step 4: Storing data")
            # Only proceed with storage if not in test mode
            if not config.get("test_mode", False):
                # Step 4.1: Store stats in PostgreSQL if available
                if stats and postgres_storage:
                    logger.info("Step 4.1: Storing stats in PostgreSQL")
                    # Use the appropriate method based on source type
                    source_type = config.get("source_type", "").lower()
                    if source_type == "gong":
                        result = postgres_storage.store_gong_stats({"calls": stats})
                    else:
                        result = postgres_storage.store_metrics({"stats": stats})
                    
                    if result.get("success", False):
                        metrics["storage_results"]["stats"] = result.get("metrics_count", len(stats))
                        if debug_mode:
                            logger.debug(f"Successfully stored {metrics['storage_results']['stats']} stats records in PostgreSQL")
                
                # Step 4.2: Store vectors (chunks and insights) in ChromaDB if available
                if vectors and chroma_storage:
                    logger.info("Step 4.2: Storing vectors in ChromaDB")
                    
                    # Determine the source type to use the appropriate storage method
                    source_type = config.get("source_type", "").lower()
                    
                    if source_type == "gong":
                        # Use Gong-specific storage methods
                        # Separate vectors into chunks and insights
                        chunks = [v for v in vectors if not v.get("insights")]
                        insights = [v for v in vectors if v.get("insights")]
                        
                        if debug_mode:
                            logger.debug(f"Separated vectors into {len(chunks)} chunks and {len(insights)} insights")
                        
                        # Store chunks
                        if chunks:
                            chunk_results = []
                            for doc in chunks:
                                result = chroma_storage.store_gong_chunks(doc)
                                chunk_results.extend(result)
                            
                            # Count successful storage operations
                            successful_chunks = sum(1 for r in chunk_results if r.get("success", False))
                            metrics["storage_results"]["vectors"] = successful_chunks
                            if debug_mode:
                                logger.debug(f"Successfully stored {successful_chunks} chunks in ChromaDB")
                        
                        # Store insights
                        if insights:
                            insight_results = chroma_storage.store_insights(insights)
                            successful_insights = sum(1 for r in insight_results if r.get("success", False))
                            metrics["storage_results"]["insights"] = successful_insights
                            if debug_mode:
                                logger.debug(f"Successfully stored {successful_insights} insights in ChromaDB")
                    
                    elif source_type in ["pdf", "gdrive"]:
                        # Use document-specific storage methods for PDF/GDrive documents
                        logger.info("Using document-specific storage for PDF/GDrive documents")
                        
                        # Store each vector using the document_chunks method
                        vector_results = []
                        for vector in vectors:
                            result = chroma_storage.store_document_chunks(vector)
                            vector_results.extend(result)
                        
                        # Count successful storage operations
                        successful_vectors = sum(1 for r in vector_results if r.get("success", False))
                        metrics["storage_results"]["vectors"] = successful_vectors
                        if debug_mode:
                            logger.debug(f"Successfully stored {successful_vectors} document vectors in ChromaDB")
                    
                    else:
                        # Default storage method for other source types
                        # Separate vectors into chunks and insights
                        chunks = [v for v in vectors if not v.get("insights")]
                        insights = [v for v in vectors if v.get("insights")]
                        
                        if debug_mode:
                            logger.debug(f"Separated vectors into {len(chunks)} chunks and {len(insights)} insights")
                        
                        # Store chunks
                        if chunks:
                            chunk_results = chroma_storage.store_chunks(chunks)
                            
                            # Count successful storage operations
                            successful_chunks = sum(1 for r in chunk_results if r.get("success", False))
                            metrics["storage_results"]["vectors"] = successful_chunks
                            if debug_mode:
                                logger.debug(f"Successfully stored {successful_chunks} chunks in ChromaDB")
                        
                        # Store insights
                        if insights:
                            insight_results = chroma_storage.store_insights(insights)
                            successful_insights = sum(1 for r in insight_results if r.get("success", False))
                            metrics["storage_results"]["insights"] = successful_insights
                            if debug_mode:
                                logger.debug(f"Successfully stored {successful_insights} insights in ChromaDB")
                
                # Step 4.3: Store original documents in all enabled storage backends
                # Only after all processing is complete
                logger.info("Step 4.3: Storing original documents")
                doc_storage_count = 0
                if postgres_storage:
                    for doc in documents:
                        result = postgres_storage.store_document(doc)
                        if result.get("success", False):
                            doc_storage_count += 1
                
                if chroma_storage:
                    for doc in documents:
                        result = chroma_storage.store_document(doc)
                        if result.get("success", False):
                            doc_storage_count += 1
                
                metrics["storage_results"]["documents"] = doc_storage_count
                if debug_mode:
                    logger.debug(f"Successfully stored {doc_storage_count} original documents")
            else:
                if debug_mode:
                    logger.debug("Test mode enabled - skipping storage steps")
            
            # Mark as successful if we got this far
            metrics["success"] = True
            logger.info("Pipeline execution completed successfully")
            
        except Exception as e:
            metrics["success"] = False
            error_msg = str(e)
            metrics["errors"].append(error_msg)
            logger.error(f"Pipeline execution failed: {error_msg}")
            if debug_mode:
                logger.exception("Detailed pipeline error")
            # Re-raise the exception for the caller to handle
            raise
        
        if debug_mode:
            logger.debug(f"Pipeline metrics: {json.dumps(metrics, indent=2, default=str)}")
        
        return metrics

def run_pipeline(source_type: str, config: Dict[str, Any], storage_type: str = "default") -> Dict[str, Any]:
    """
    Convenience function to run a pipeline for a specific source type.
    
    Args:
        source_type: Type of source ("gong", "pdf", "gdrive", "sfdc")
        config: Configuration for the ingestion process
        storage_type: Type of storage to use (ignored, as we now use multiple storage backends)
        
    Returns:
        Dictionary containing results and statistics about the ingestion process
    """
    from .factories import get_factory
    
    # Add source type to config
    config["source_type"] = source_type
    
    # Get the appropriate factory for this source type
    factory = get_factory(source_type)
    
    # Create and run the pipeline
    pipeline = IngestPipeline(factory)
    return pipeline.run(config) 