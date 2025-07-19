from enum import Enum

class DocumentType(str, Enum):
    """Supported document types"""
    GONG_TRANSCRIPT = "gong_transcript"
    SLACK_CONVERSATION = "slack_conversation"
    CONTRACT = "contract"
    GENERIC = "generic"
    EXTENSIVE_CALL = "extensive_call"
    DOCS_DOCUMENTATION = "docs_documentation"
    CSOD_DATA = "csod_data"

class DocumentSource(str, Enum):
    """Supported document sources for metadata extraction"""
    GONG = "gong"
    SALESFORCE = "salesforce"
    PDF = "pdf"
    SLACK = "slack"
    GENERIC = "generic"
    EXTENSIVE_CALL = "extensive_call"
    DOCS_DOCUMENTATION = "docs_documentation"
    CSOD = "csod"



# Unified document schema for all document types
UNIFIED_DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_id": {"type": "string", "example": "550e8400-e29b-41d4-a716-446655440000"},
        "source": {"type": "string", "example": "gong", "description": "e.g. gong, salesforce, pdf, slack"},
        "source_doc_id": {"type": "string", "example": "8119903977292895368", "description": "the native ID from the source system"},
        "ingest_timestamp": {"type": "string", "example": "2024-06-03T10:30:43-04:00", "description": "ISO8601 timestamp when document was ingested"},
        "raw_content": {"type": "string", "example": "<full document content>", "description": "the full text to chunk/embed"},
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string", "example": "550e8400-e29b-41d4-a716-446655440001"},
                    "chunk_index": {"type": "integer", "example": 0, "description": "order within the document"},
                    "text": {"type": "string", "example": "<chunk text>", "description": "the actual chunk text"},
                    "context": {
                        "type": "object",
                        "description": "any extra filterable info",
                        "example": {"start_time": "00:00", "end_time": "00:10"}
                    }
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "example": "Discussion focused on Q2 sales targets and strategies."},
                "entities": {"type": "array", "items": {"type": "string"}, "example": ["Acme Corp", "John Smith"]},
                "topics": {"type": "array", "items": {"type": "string"}, "example": ["Sales Strategy", "Customer Feedback"]},
                "sentiment": {"type": "string", "example": "positive", "description": "positive | neutral | negative"},
                "custom_tags": {"type": "array", "items": {"type": "string"}, "example": ["important", "follow-up"]}
            }
        }
    },
    "required": ["document_id", "source", "raw_content"]
}

# Add to the end of your file
DOCUMENT_SCHEMAS = {
    DocumentType.GONG_TRANSCRIPT: {},
    DocumentType.SLACK_CONVERSATION: {},
    DocumentType.CONTRACT: {},
    DocumentType.GENERIC: {},
    DocumentType.EXTENSIVE_CALL: {},
    DocumentType.DOCS_DOCUMENTATION: {},
    DocumentType.CSOD_DATA: {},
}