#!/usr/bin/env python3
"""
Script to retrieve a document from the document_versions1 table using its document_id.
"""

import json
import sys
import uuid
from app.utils.postgresdb import PostgresDB
from app.config.settings import get_settings, print_settings_summary

def get_document_by_id(document_id: str):
    """
    Retrieves a document from the document_versions1 table by its document_id.
    
    Args:
        document_id: The UUID of the document to retrieve
    
    Returns:
        The document record or None if not found
    """
    try:
        # Validate the document_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(document_id)
        except ValueError:
            print(f"Error: Invalid document_id format. Must be a valid UUID.")
            return None
        
        # Initialize the PostgresDB connection
        db = PostgresDB()
        
        # Query to get the latest version of the document
        query = """
            SELECT * FROM document_versions1 
            WHERE document_id = %s 
            ORDER BY version DESC 
            LIMIT 1
        """
        
        results = db.execute_query(query, (uuid_obj,))
        
        if not results:
            print(f"No document found with document_id: {document_id}")
            return None
        
        document = results[0]
        
        # Format the document for better readability
        formatted_document = {
            "id": str(document["id"]),
            "document_id": str(document["document_id"]),
            "version": document["version"],
            "content": document["content"],
            "source_type": document["source_type"],
            "document_type": document["document_type"],
            "created_at": document["created_at"].isoformat() if document["created_at"] else None,
            "created_by": document["created_by"]
        }
        
        # Format the JSON metadata if available
        if document.get("json_metadata"):
            if isinstance(document["json_metadata"], str):
                try:
                    formatted_document["json_metadata"] = json.loads(document["json_metadata"])
                except json.JSONDecodeError:
                    formatted_document["json_metadata"] = document["json_metadata"]
            else:
                formatted_document["json_metadata"] = document["json_metadata"]
        else:
            formatted_document["json_metadata"] = None
        
        return formatted_document
        
    except Exception as e:
        print(f"Error retrieving document: {str(e)}")
        return None

def main():
    """Main function to run the script."""
    # Check if document_id is provided as a command-line argument
    if len(sys.argv) != 2:
        print("Usage: python get_document_by_id.py <document_id>")
        return
    
    document_id = sys.argv[1]
    
    # Retrieve the document
    document = get_document_by_id(document_id)
    
    if document:
        # Pretty print the document
        print(json.dumps(document, indent=2))

if __name__ == "__main__":
    main() 