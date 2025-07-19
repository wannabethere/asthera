"""
Metadata extraction function using OpenAI function calling.
"""

import json
import time
import uuid
from typing import Any, Dict, Optional

from openai import OpenAI

from app.schemas.document_schemas import UNIFIED_DOCUMENT_SCHEMA, DocumentSource
from app.utils.chromadb import ChromaDB
from app.config.settings import get_settings
from app.utils.postgresdb import PostgresDB
from app.utils.time_checkpoint import checkpoint


async def run_unified_extraction(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the extraction process for a document using the unified schema

    Args:
        document: Document in unified schema format

    Returns:
        Updated document with extracted metadata
    """
    start_time = time.time()

    # Check if we're in test mode
    test_mode = document.get("test_mode", False)
    
    # Extract metadata
    metadata = extract_unified_metadata(document)
    document["metadata"] = metadata

    # In test mode, don't save to database
    if test_mode:
        print("TEST MODE: Extracting metadata without saving to database")
        # Generate a test document ID
        doc_id = "test-" + str(uuid.uuid4())
        document["document_id"] = doc_id
    else:
        # Save to database
        doc_id = save_unified_record(document)
        document["document_id"] = doc_id

    checkpoint("Completed unified metadata extraction", start_time)
    return document


def extract_unified_metadata(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from document using OpenAI function calling

    Args:
        document: Document in unified schema format

    Returns:
        Extracted metadata
    """
    start_time = time.time()
    checkpoint_time = checkpoint("Starting metadata extraction", start_time)

    # Store any existing metadata we want to preserve
    existing_metadata = document.get("metadata", {})
    document_date = existing_metadata.get("document_date")
    
    # Get user context if provided
    user_context = document.get("user_context")

    # Get API key from settings
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    checkpoint_time = checkpoint("Initialized OpenAI client", checkpoint_time)

    # Get schema definition for metadata part
    metadata_schema = UNIFIED_DOCUMENT_SCHEMA["properties"]["metadata"]

    # Create the prompt for the model
    source_type = document.get("source", "generic")
    raw_content = document.get("raw_content", "")

    # Include user context in the prompt if provided
    user_context_prompt = ""
    if user_context:
        user_context_prompt = f"""
        User Context:
        {user_context}
        
        Use this context to guide your extraction and focus on aspects that might be relevant to the user's needs.
        """
        print(f"Including user context in extraction prompt: {user_context}")

    prompt_text = f"""
    Extract metadata from the following {source_type} document according to this schema: 
    {json.dumps(metadata_schema, indent=2)}
    
    Document content: 
    {raw_content}
    
    {user_context_prompt}
    
    IMPORTANT: Look for any dates mentioned in the document that indicate when the document was created or when events took place, and include them as document_date.
    
    Return the extracted metadata as a JSON object matching the schema exactly.
    """
    
    # Print the full prompt to verify user context is included
    print("\n===== EXTRACTION PROMPT WITH USER CONTEXT =====")
    print(prompt_text)
    print("===== END OF EXTRACTION PROMPT =====\n")

    # Make the API call with function calling
    checkpoint_time = checkpoint("Making OpenAI API call", checkpoint_time)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_text}],
        tools=[{
            "type": "function",
            "function": {
                "name": "extract_document_metadata",
                "description": f"Extract structured metadata from {source_type} document content according to the provided schema.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metadata": {
                            "type": "object",
                            "properties": metadata_schema["properties"],
                            "additionalProperties": True,
                        }
                    },
                    "required": ["metadata"],
                    "additionalProperties": True,
                }
            }
        }],
        tool_choice={
            "type": "function",
            "function": {"name": "extract_document_metadata"},
        },
    )

    if completion.choices and completion.choices[0].message.tool_calls:
        try:
            tool_call = completion.choices[0].message.tool_calls[0]
            metadata_result = json.loads(tool_call.function.arguments)
            extracted_metadata = metadata_result["metadata"]
            
            # Preserve the document_date if it exists in our original metadata
            # and wasn't extracted by the LLM
            if document_date and not extracted_metadata.get("document_date"):
                extracted_metadata["document_date"] = document_date

            checkpoint(f"Extracted metadata: {json.dumps({'metadata': extracted_metadata}, indent=2)}", checkpoint_time)
            return extracted_metadata
        except json.JSONDecodeError as e:
            checkpoint(f"Failed to parse JSON from response: {e}", checkpoint_time)
            # Return original metadata with error if we have it
            if existing_metadata:
                existing_metadata["error"] = "Failed to parse metadata"
                return existing_metadata
            return {"error": "Failed to parse metadata"}

    # If we couldn't extract metadata, return existing metadata if available
    checkpoint("No metadata could be extracted", checkpoint_time)
    return existing_metadata if existing_metadata else {}


def save_unified_record(document: Dict[str, Any]) -> str:
    """
    Writes a unified document to postgres and chroma

    Args:
        document: The document in unified schema format

    Returns:
        The uuid from postgres
    """
    start_time = time.time()
    checkpoint_time = checkpoint("Writing record to postgres", start_time)

    # Check if we're in test mode (should never happen, but just in case)
    if document.get("test_mode", False):
        print("TEST MODE: Skipping database writes")
        return "test-" + str(uuid.uuid4())

    settings = get_settings()
    postgres_db = PostgresDB(
        connection_params={
            "host": settings.DB_HOST,
            "port": settings.DB_PORT,
            "dbname": settings.DB_NAME,
            "user": settings.DB_USER,
            "password": settings.DB_PASSWORD,
        }
    )

    # Convert document to format suitable for PostgreSQL
    db_record = {
        "source": document.get("source", "unknown"),
        "source_doc_id": document.get("source_doc_id", ""),
        "ingest_timestamp": document.get("ingest_timestamp", ""),
        "raw_content": document.get("raw_content", ""),
        "chunks": json.dumps(document.get("chunks", [])),
        "metadata": json.dumps(document.get("metadata", {}))
    }

    # Insert into unified_documents table
    doc_id = postgres_db.insert_record("unified_documents", db_record)
    if not doc_id:
        doc_id = str(uuid.uuid4())  # Fallback if insert fails

    checkpoint_time = checkpoint(f"Record successfully written to postgres with id {doc_id}", checkpoint_time)

    # Add each chunk to ChromaDB
    chroma_db = ChromaDB(
        connection_params={
            "host": settings.CHROMA_HOST,
            "port": settings.CHROMA_PORT,
        }
    )

    # Create a collection based on source if it doesn't exist
    collection_name = f"unified_{document.get('source', 'documents')}"

    # Get chunks to add to vector store
    chunks = document.get("chunks", [])

    if chunks:
        documents = []
        ids = []
        metadatas = []

        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            chunk_id = chunk.get("chunk_id", str(uuid.uuid4()))

            # Create metadata for this chunk
            chunk_metadata = {
                "document_id": doc_id,
                "source": document.get("source", "unknown"),
                "source_doc_id": document.get("source_doc_id", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "context": chunk.get("context", {}),
                "document_metadata": document.get("metadata", {})
            }

            documents.append(chunk_text)
            ids.append(chunk_id)
            metadatas.append(chunk_metadata)

        # Add chunks to ChromaDB
        chroma_db.add_documents(
            collection_name=collection_name,
            documents=documents,
            ids=ids,
            metadata=metadatas
        )

    checkpoint_time = checkpoint("Chunks successfully written to chroma", checkpoint_time)

    return doc_id


async def run_extraction(
    document_name: str,
    document_content: str,
    document_type: str,
    test_mode: bool = False,
    user_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run extraction on document content

    Args:
        document_name: The name of the document
        document_content: The content of the document
        document_type: The type of document
        test_mode: If True, no data will be written to the database
        user_context: Optional user-provided context to guide extraction
    """
    print(f"{'TEST MODE' if test_mode else 'NORMAL MODE'} - Running extraction on {document_name} with type {document_type}")
    if user_context:
        print(f"User context provided: {user_context[:100]}{'...' if len(user_context) > 100 else ''}")
    
    # Run the metadata extraction process...
    # Format document in unified schema
    document = {
        "raw_content": document_content,
        "source": document_type,
        "source_doc_id": document_name,
        "ingest_timestamp": time.time(),
        "test_mode": test_mode,
        "user_context": user_context,
    }

    try:
        # Extract metadata using OpenAI function calling
        result = await run_unified_extraction(document)
        
        # Get the extracted metadata
        metadata = result.get("metadata", {})
        doc_id = result.get("document_id", "")
        
        # Create a standardized response with full metadata and document details
        response = {
            "success": True,
            "document_id": doc_id,
            "source_type": document_type,
            "event_type": "upload",
            "event_timestamp": result.get("ingest_timestamp", time.time()),
            "created_by": "api_upload",
            "insight": metadata,
            "phrases": metadata.get("key_points", []),
            "extracted_entities": {
                "organizations": metadata.get("organizations", []),
                "people": metadata.get("people", []),
                "locations": metadata.get("locations", []),
                "dates": [metadata.get("document_date", "")]
            },
            "ner_text": metadata.get("summary", ""),
            "chromadb_ids": [],
            "test_mode": test_mode
        }
        
        # Add enhanced insights if available
        if "summary" in metadata:
            response["enhanced_insights"] = {
                "question_based_insights": {
                    "What is this document about?": metadata.get("summary", ""),
                    "What are the key points?": metadata.get("key_points", []),
                    "Who are the key people mentioned?": metadata.get("people", []),
                    "What organizations are mentioned?": metadata.get("organizations", []),
                    "When was this document created?": metadata.get("document_date", "")
                }
            }
        
        print(f"{'TEST MODE' if test_mode else 'NORMAL MODE'} - Completed extraction for {document_name}")
        return response
    except Exception as e:
        print(f"ERROR in extraction: {str(e)}")
        # Return basic response for failed extraction
        return {
            "success": False,
            "document_id": f"error-{str(uuid.uuid4())[:8]}",
            "source_type": document_type,
            "event_type": "upload_failed",
            "event_timestamp": time.time(),
            "created_by": "api_upload",
            "error": str(e),
            "test_mode": test_mode
        }