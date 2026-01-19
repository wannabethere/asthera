"""
File Storage Utility
Saves indexed documents to files for testing and preview before storing in vector databases.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class FileStorage:
    """Stores documents in files for testing and preview."""
    
    def __init__(self, output_dir: str = "indexing_preview"):
        """
        Initialize file storage.
        
        Args:
            output_dir: Directory to store preview files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileStorage initialized with output directory: {self.output_dir}")
    
    def save_documents(
        self,
        documents: List[Document],
        content_type: str,
        domain: Optional[str] = None,
        product_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Save documents to files.
        
        Args:
            documents: List of Document objects
            content_type: Type of content (e.g., "soc2_controls", "policy_documents")
            domain: Domain filter
            product_name: Product name
            metadata: Additional metadata
            
        Returns:
            Dictionary with file paths and summary
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Create subdirectory for this content type
        content_dir = self.output_dir / content_type
        content_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename
        filename_parts = [content_type, timestamp]
        if domain:
            filename_parts.append(domain)
        if product_name:
            filename_parts.append(product_name.replace(" ", "_"))
        
        filename = "_".join(filename_parts) + ".json"
        file_path = content_dir / filename
        
        # Prepare document data
        document_data = {
            "metadata": {
                "content_type": content_type,
                "domain": domain,
                "product_name": product_name,
                "document_count": len(documents),
                "timestamp": timestamp,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            },
            "documents": []
        }
        
        # Convert documents to serializable format
        for i, doc in enumerate(documents):
            doc_data = {
                "index": i,
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "content_length": len(doc.page_content),
                "metadata_keys": list(doc.metadata.keys())
            }
            document_data["documents"].append(doc_data)
        
        # Save to file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(document_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Saved {len(documents)} documents to {file_path}")
            
            # Create summary file
            summary_path = content_dir / f"{content_type}_summary_{timestamp}.txt"
            self._create_summary(summary_path, document_data)
            
            return {
                "success": True,
                "file_path": str(file_path),
                "summary_path": str(summary_path),
                "document_count": len(documents),
                "total_content_length": sum(len(doc.page_content) for doc in documents)
            }
        except Exception as e:
            logger.error(f"Error saving documents to file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_summary(self, summary_path: Path, document_data: Dict[str, Any]):
        """Create a human-readable summary file."""
        lines = [
            "=" * 80,
            f"Indexing Preview Summary",
            "=" * 80,
            "",
            f"Content Type: {document_data['metadata']['content_type']}",
            f"Domain: {document_data['metadata'].get('domain', 'N/A')}",
            f"Product Name: {document_data['metadata'].get('product_name', 'N/A')}",
            f"Document Count: {document_data['metadata']['document_count']}",
            f"Timestamp: {document_data['metadata']['timestamp']}",
            "",
            "=" * 80,
            "Documents:",
            "=" * 80,
            ""
        ]
        
        for i, doc in enumerate(document_data["documents"], 1):
            lines.extend([
                f"Document {i}:",
                f"  Content Length: {doc['content_length']} characters",
                f"  Metadata Keys: {', '.join(doc['metadata_keys'])}",
                f"  Content Preview: {doc['page_content'][:200]}...",
                ""
            ])
        
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            logger.warning(f"Error creating summary file: {e}")
    
    def list_preview_files(self, content_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all preview files.
        
        Args:
            content_type: Optional filter by content type
            
        Returns:
            List of file information dictionaries
        """
        files = []
        
        if content_type:
            content_dir = self.output_dir / content_type
            if content_dir.exists():
                for file_path in content_dir.glob("*.json"):
                    files.append({
                        "path": str(file_path),
                        "content_type": content_type,
                        "size": file_path.stat().st_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
        else:
            for content_dir in self.output_dir.iterdir():
                if content_dir.is_dir():
                    for file_path in content_dir.glob("*.json"):
                        files.append({
                            "path": str(file_path),
                            "content_type": content_dir.name,
                            "size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })
        
        return files
    
    def load_preview_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load a preview file.
        
        Args:
            file_path: Path to preview file
            
        Returns:
            Document data dictionary
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Preview file not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

