from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class DocumentType(str, Enum):
    """Supported document types"""
    GONG_TRANSCRIPT = "gong_transcript"
    SLACK_CONVERSATION = "slack_conversation"
    CONTRACT = "contract"
    GENERIC = "generic"
    EXTENSIVE_CALL = "extensive_call"
    DOCS_DOCUMENTATION = "docs_documentation"
    FINANCIAL_REPORT = "financial_report"
    BUSINESS_DOCUMENT = "business_document"
    PDF_DOCUMENT = "pdf_document"
    TEXT_DOCUMENT = "text_document"
    JSON_DOCUMENT = "json_document"
    WORD_DOCUMENT = "word_document"
    GOOGLE_DOCUMENT = "google_document"
    WIKI_DOCUMENT = "wiki_document"

class DocumentSource(str, Enum):
    """Supported document sources for metadata extraction"""
    GONG = "gong"
    SALESFORCE = "salesforce"
    PDF = "pdf"
    SLACK = "slack"
    GENERIC = "generic"
    EXTENSIVE_CALL = "extensive_call"
    DOCS_DOCUMENTATION = "docs_documentation"
    UPLOAD = "upload"
    DIRECT_INPUT = "direct_input"
    STRUCTURED_DATA = "structured_data"
    FILE_UPLOAD = "file_upload"
    GOOGLE_DOCS = "google_docs"
    WIKI = "wiki"

class TestMode(str, Enum):
    """Test mode options"""
    ENABLED = "enabled"
    DISABLED = "disabled"

class Document(BaseModel):
    """Document response model"""
    document_type: DocumentType
    document_id: str
    document_name: str
    document_content: str
    metadata: Dict[str, Any]
    source_type: Optional[str] = None
    event_type: Optional[str] = None
    event_timestamp: Optional[str] = None
    created_by: Optional[str] = None
    success: bool = True

class MarkdownResponse(BaseModel):
    """Markdown response model"""
    document_type: DocumentType
    document_id: str
    document_name: str
    document_content: str
    markdown_summary: str
    raw_metadata: Optional[Dict[str, Any]] = None

class UploadedDocument(BaseModel):
    """Uploaded document response model"""
    filename: str
    content_type: str
    document_type: DocumentType
    text_length: int
    document_id: str
    source_type: str
    event_type: str
    event_timestamp: str
    created_by: str
    metadata: Dict[str, Any]
    markdown_summary: str
    test_mode: bool
    success: bool

# Document schemas for different types
DOCUMENT_SCHEMAS = {
    DocumentType.GONG_TRANSCRIPT: {
        "type": "object",
        "properties": {
            "call_id": {"type": "string"},
            "participants": {"type": "array", "items": {"type": "string"}},
            "duration": {"type": "integer"},
            "transcript": {"type": "string"}
        }
    },
    DocumentType.SLACK_CONVERSATION: {
        "type": "object",
        "properties": {
            "channel": {"type": "string"},
            "thread_ts": {"type": "string"},
            "messages": {"type": "array", "items": {"type": "object"}}
        }
    },
    DocumentType.CONTRACT: {
        "type": "object",
        "properties": {
            "contract_id": {"type": "string"},
            "parties": {"type": "array", "items": {"type": "string"}},
            "effective_date": {"type": "string"},
            "expiration_date": {"type": "string"}
        }
    },
    DocumentType.GENERIC: {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}}
        }
    },
    DocumentType.EXTENSIVE_CALL: {
        "type": "object",
        "properties": {
            "call_id": {"type": "string"},
            "duration": {"type": "integer"},
            "participants": {"type": "array", "items": {"type": "string"}},
            "topics": {"type": "array", "items": {"type": "string"}}
        }
    },
    DocumentType.DOCS_DOCUMENTATION: {
        "type": "object",
        "properties": {
            "doc_id": {"type": "string"},
            "title": {"type": "string"},
            "sections": {"type": "array", "items": {"type": "object"}}
        }
    },
    DocumentType.FINANCIAL_REPORT: {
        "type": "object",
        "properties": {
            "report_period": {"type": "string"},
            "company": {"type": "string"},
            "revenue": {"type": "number"},
            "profit": {"type": "number"}
        }
    },
    DocumentType.BUSINESS_DOCUMENT: {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "department": {"type": "string"},
            "priority": {"type": "string"},
            "status": {"type": "string"}
        }
    },
    DocumentType.PDF_DOCUMENT: {
        "type": "object",
        "properties": {
            "pages": {"type": "integer"},
            "file_size": {"type": "integer"},
            "title": {"type": "string"},
            "author": {"type": "string"}
        }
    },
    DocumentType.TEXT_DOCUMENT: {
        "type": "object",
        "properties": {
            "encoding": {"type": "string"},
            "line_count": {"type": "integer"},
            "word_count": {"type": "integer"}
        }
    },
    DocumentType.JSON_DOCUMENT: {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "data_type": {"type": "string"},
            "validation_status": {"type": "string"}
        }
    },
    DocumentType.WORD_DOCUMENT: {
        "type": "object",
        "properties": {
            "pages": {"type": "integer"},
            "word_count": {"type": "integer"},
            "author": {"type": "string"},
            "created_date": {"type": "string"}
        }
    },
    DocumentType.GOOGLE_DOCUMENT: {
        "type": "object",
        "properties": {
            "doc_id": {"type": "string"},
            "title": {"type": "string"},
            "collaborators": {"type": "array", "items": {"type": "string"}},
            "last_modified": {"type": "string"}
        }
    },
    DocumentType.WIKI_DOCUMENT: {
        "type": "object",
        "properties": {
            "wiki_page": {"type": "string"},
            "categories": {"type": "array", "items": {"type": "string"}},
            "last_edited": {"type": "string"},
            "editor": {"type": "string"}
        }
    }
}

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
