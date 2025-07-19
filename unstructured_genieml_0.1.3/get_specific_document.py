#!/usr/bin/env python3
"""
Script to retrieve a specific document from the document_versions1 table.
"""

import json
import uuid
from app.utils.postgresdb import PostgresDB

# The specific document ID to retrieve
DOCUMENT_ID = "990fd182-6087-46d9-aebf-e91030fb012f"

def get_document():
    """
    Retrieves the document with the hardcoded document_id from the document_versions1 table.
    
    Returns:
        The document record or None if not found
    """
    try:
        # Initialize the PostgresDB connection
        db = PostgresDB()
        
        # Convert string document_id to UUID
        uuid_obj = uuid.UUID(DOCUMENT_ID)
        
        # Query to get the latest version of the document
        query = """
            SELECT * FROM document_versions1 
            WHERE document_id = %s 
            ORDER BY version DESC 
            LIMIT 1
        """
        
        results = db.execute_query(query, (uuid_obj,))
        
        if not results:
            print(f"No document found with document_id: {DOCUMENT_ID}")
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

if __name__ == "__main__":
    # Retrieve the document
    document = get_document()
    
    if document:
        # Pretty print the document
        print(json.dumps(document, indent=2))
    else:
        print(f"Failed to retrieve document with ID: {DOCUMENT_ID}") 