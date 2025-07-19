"""
Document processing utilities shared across different agent implementations.
"""

import json
import logging
from typing import Any, Dict, List, Optional

# Set up logging
logger = logging.getLogger("DocumentProcessor")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def format_documents_for_context(documents: List[Dict[str, Any]]) -> str:
    """
    Format documents for the context prompt.
    
    Args:
        documents: List of retrieved documents
        
    Returns:
        Formatted document text for LLM prompt
    """
    formatted_docs = []
    for i, doc in enumerate(documents):
        doc_id = doc.get("document_id", doc.get("id", f"doc_{i}"))
        title = doc.get("title", "Untitled Document")
        filename = doc.get("filename", "")
        metadata = doc.get("metadata", {})
        metadata_summary = doc.get("metadata_summary", "")
        
        # Extract text content from various possible fields
        content = doc.get("document", doc.get("text", doc.get("content", "")))
        if isinstance(content, dict) and "text" in content:
            content = content["text"]
        
        # Extract insights if available
        insights = doc.get("insights", {})
        
        # Format the document with metadata
        formatted_doc = f"DOCUMENT {i+1} (ID: {doc_id})\n"
        formatted_doc += f"TITLE: {title}\n"
        
        # Add filename if available
        if filename:
            formatted_doc += f"FILENAME: {filename}\n"
        
        # Add metadata summary if available
        if metadata_summary:
            formatted_doc += f"METADATA: {metadata_summary}\n"
        
        # Add insights if available
        if insights and isinstance(insights, dict) and insights:
            formatted_doc += "INSIGHTS:\n"
            for key, value in insights.items():
                if isinstance(value, (str, int, float, bool)):
                    formatted_doc += f"- {key}: {value}\n"
                elif isinstance(value, (list, dict)) and value:
                    formatted_doc += f"- {key}: {json.dumps(value, ensure_ascii=False)}\n"
            formatted_doc += "\n"
        
        # Add document content
        formatted_doc += f"CONTENT:\n{content}\n\n"
        formatted_docs.append(formatted_doc)
    
    return "\n".join(formatted_docs)

def extract_insights_from_metadata(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract useful insights from document metadata.
    
    Args:
        document: The raw document
        
    Returns:
        Document with processed metadata
    """
    try:
        # Check for json_metadata field specifically
        json_metadata = document.get("json_metadata", None)
        if json_metadata:
            if isinstance(json_metadata, str):
                try:
                    json_metadata = json.loads(json_metadata)
                    logger.info(f"Found json_metadata field and parsed successfully")
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse json_metadata JSON")
                    json_metadata = {}
            
            # If json_metadata was found, use it preferentially
            if isinstance(json_metadata, dict):
                logger.info(f"json_metadata keys: {list(json_metadata.keys())}")
                
                # Extract filename from json_metadata
                filename = json_metadata.get("filename", "")
                if filename:
                    logger.info(f"Found filename in json_metadata: {filename}")
        
        # Fall back to regular metadata field
        metadata = document.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
                logger.info(f"Parsed metadata field successfully")
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata JSON: {metadata}")
                metadata = {}
        
        # Use json_metadata if available, otherwise fallback to regular metadata
        if 'json_metadata' in document and isinstance(json_metadata, dict):
            metadata = json_metadata
        
        # Extract key metadata fields
        doc_type = metadata.get("document_type", document.get("document_type", "unknown"))
        title = metadata.get("title", document.get("title", "Untitled Document"))
        source = metadata.get("source", metadata.get("source_type", document.get("source_type", document.get("source", "unknown"))))
        created_date = metadata.get("created_date", document.get("created_date", "unknown"))
        file_type = metadata.get("file_type", document.get("file_type", "unknown"))
        
        # First check if filename exists at the document's top level
        filename = document.get("filename", "")
        if not filename and 'json_metadata' in document and isinstance(json_metadata, dict):
            # Then check in json_metadata
            filename = json_metadata.get("filename", "")
        
        if not filename:
            # Then check in metadata
            filename = metadata.get("filename", "")
            if not filename:
                # Try alternative field names that might contain the filename
                filename = metadata.get("file_name", metadata.get("file_path", metadata.get("path", "")))
                # If still not found, check for document_key which may contain filename
                if not filename:
                    document_key = document.get("document_key", metadata.get("document_key", ""))
                    if document_key:
                        filename = document_key
        
        # Create a summary of the document metadata
        metadata_summary = f"Document: {title}\nType: {doc_type}\nSource: {source}\nCreated Date: {created_date}\nFile Type: {file_type}"
        if filename:
            metadata_summary += f"\nFilename: {filename}"
        
        # Get document content
        content = document.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                # Content might be a plain text string
                content = {"text": content}
        
        # Extract text content
        text_content = ""
        if isinstance(content, dict):
            text_content = content.get("text", "")
        elif isinstance(content, str):
            text_content = content
        
        # Extract insights if available
        insights = document.get("insights", {})
        if isinstance(insights, str):
            try:
                insights = json.loads(insights)
            except json.JSONDecodeError:
                insights = {}
        
        # Create processed document
        processed_doc = {
            "id": document.get("document_id", ""),
            "document_id": document.get("document_id", ""),
            "document_type": doc_type,
            "metadata": metadata,
            "metadata_summary": metadata_summary,
            "document": text_content,
            "text": text_content,
            "title": title,
            "filename": filename,
            "content": content,
            "insights": insights,
            "file_type": file_type,
            "created_date": created_date,
            "source": source
        }
        
        return processed_doc
        
    except Exception as e:
        logger.error(f"Error processing document metadata: {e}")
        # Return the original document if processing fails
        return document

def process_retrieved_documents(documents: List[Dict[str, Any]], source_type: str) -> List[Dict[str, Any]]:
    """
    Process retrieved documents to standardize format and extract metadata.
    
    Args:
        documents: List of retrieved documents
        source_type: The type of source ("salesforce", "gong", etc.)
        
    Returns:
        List of processed documents
    """
    processed_docs = []
    
    for doc in documents:
        # Extract metadata
        metadata = doc.get('metadata', {})
        
        # Determine document type
        doc_type = metadata.get('document_type', '')
        collection = doc.get('collection', '')
        
        if not doc_type:
            if 'insight' in collection.lower():
                doc_type = f'{source_type}_insights'
            elif 'chunk' in collection.lower():
                doc_type = f'{source_type}_chunk'
            else:
                doc_type = f'{source_type}_document'
        
        # Extract content
        content = doc.get('content', doc.get('document', ''))
        
        # Create processed document
        processed_doc = {
            'document_id': doc.get('document_id', metadata.get('document_id', doc.get('id', 'unknown'))),
            'document_type': doc_type,
            'content': content,
            'collection': collection,
            'metadata': metadata,
            'relevance_score': doc.get('relevance_score', 0.0),
            'source_type': source_type
        }
        
        processed_docs.append(processed_doc)
    
    # Sort by relevance score
    processed_docs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return processed_docs 