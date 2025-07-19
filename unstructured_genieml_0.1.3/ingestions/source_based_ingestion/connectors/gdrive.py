"""
Google Drive connector for document ingestion.
"""
import os
import glob
import logging
from typing import Dict, List, Any
from pathlib import Path

from langchain_community.document_loaders import UnstructuredPDFLoader, DirectoryLoader
from langchain_core.documents import Document as LangchainDocument

from .base import IExtractor

# Configure logging
logger = logging.getLogger(__name__)

class GDriveExtractor(IExtractor):
    """Extractor for loading PDF documents from Google Drive or local directory."""
    
    def extract(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract documents from a directory path based on the provided configuration.
        
        Args:
            config: Configuration parameters including:
                - directory_path: Path to directory containing PDFs
                - input_path: Alternative name for directory_path
                - limit: Optional limit on number of files to process
        
        Returns:
            List of document dictionaries with content and metadata
        """
        # Check for directory_path or input_path
        directory_path = config.get("directory_path") or config.get("input_path")
        if not directory_path:
            raise ValueError("directory_path not provided in configuration")
        
        # Check if directory exists
        if not os.path.exists(directory_path):
            raise ValueError(f"Directory {directory_path} does not exist")
        
        logger.info(f"Loading PDFs from {directory_path}...")
        
        # Load all PDFs from directory
        loader = DirectoryLoader(
            directory_path, 
            glob="**/*.pdf",
            loader_cls=UnstructuredPDFLoader
        )
        
        try:
            langchain_docs = loader.load()
            logger.info(f"Loaded {len(langchain_docs)} documents")
            
            # Apply limit if specified
            limit = config.get("limit")
            if limit and isinstance(limit, int) and limit > 0:
                langchain_docs = langchain_docs[:limit]
                logger.info(f"Limited to {len(langchain_docs)} documents")
            
            # Convert Langchain Documents to our internal document format
            documents = []
            for doc in langchain_docs:
                # Extract filename from path
                source_path = doc.metadata.get('source', 'unknown')
                filename = os.path.basename(source_path)
                
                # Create document dictionary
                document = {
                    "content": doc.page_content,
                    "metadata": {
                        "source": filename,
                        "source_path": source_path,
                        "source_type": "pdf",
                        "document_type": "unknown",  # Will be determined by vectorizer
                        "page": doc.metadata.get('page', 0) if hasattr(doc.metadata, 'get') else 0
                    }
                }
                documents.append(document)
            
            return documents
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")
            raise 