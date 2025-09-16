# Document Router for DataServices

This document describes the new document router that provides document processing capabilities using the Document Persistence Service and Doc Insights, with the same interfaces as the original documents.py router.

## Overview

The document router (`/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/dataservices/app/routers/document_router.py`) provides a comprehensive API for:

- Document upload and processing
- Metadata extraction using advanced AI/ML techniques
- Document storage and retrieval
- Semantic search capabilities
- Insight extraction and analysis

## Features

### Document Processing
- **Multiple file formats**: PDF, TXT, JSON, DOCX, and more
- **Auto-detection**: Automatically detects document type based on file extension
- **Advanced extraction**: Uses business intelligence, entity extraction, and other AI-powered insights
- **Chunking**: Intelligent text chunking for better processing
- **Metadata extraction**: Comprehensive metadata extraction and storage

### Storage and Retrieval
- **PostgreSQL**: Document content and metadata storage
- **ChromaDB**: Vector embeddings for semantic search
- **Session management**: Proper database session handling
- **Multi-tenant support**: Domain-based document isolation

### Search Capabilities
- **Semantic search**: Vector-based similarity search
- **TF-IDF search**: Keyword-based search
- **Metadata filtering**: Filter by document type, source, date, etc.
- **Insight-based search**: Search by extracted insights and key phrases

## API Endpoints

### 1. Upload Document
```
POST /documents/
```

**Parameters:**
- `file`: Uploaded file (required)
- `document_type`: Document type enum (default: GENERIC)
- `test_mode`: Test mode (ENABLED/DISABLED, default: DISABLED)
- `user_context`: Optional user context for customization
- `questions`: Optional comma-separated questions for targeted extraction
- `domain_id`: Domain ID for multi-tenant support (default: "default_domain")
- `created_by`: User who created the document (default: "api_user")

**Response:**
```json
{
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "document_type": "generic",
  "text_length": 1234,
  "document_id": "uuid-string",
  "source_type": "upload",
  "event_type": "document_upload",
  "event_timestamp": "2024-01-01T00:00:00Z",
  "created_by": "api_user",
  "metadata": {
    "chromadb_ids": ["id1", "id2"],
    "extraction_types": ["business_intelligence", "entities"],
    "key_phrases": ["AI", "machine learning"],
    "insights_summary": {
      "has_business_intelligence": true,
      "has_entities": true,
      "has_financial_metrics": false,
      "has_compliance_terms": false
    }
  },
  "markdown_summary": "# Document Summary\n...",
  "test_mode": false,
  "success": true
}
```

### 2. Get All Documents
```
GET /documents/{document_type}/all?limit=10&domain_id=default_domain
```

**Parameters:**
- `document_type`: Document type enum
- `limit`: Maximum number of results (1-100, default: 10)
- `domain_id`: Domain ID for filtering

**Response:**
```json
[
  {
    "document_type": "generic",
    "document_id": "uuid-string",
    "document_name": "Document_12345678",
    "document_content": "Document content...",
    "metadata": {
      "chromadb_ids": ["id1", "id2"],
      "extraction_types": ["business_intelligence"],
      "key_phrases": ["AI", "ML"],
      "source_type": "upload",
      "event_type": "document_upload",
      "event_timestamp": "2024-01-01T00:00:00Z",
      "created_by": "api_user",
      "domain_id": "default_domain"
    },
    "source_type": "upload",
    "event_type": "document_upload",
    "event_timestamp": "2024-01-01T00:00:00Z",
    "created_by": "api_user",
    "success": true
  }
]
```

### 3. Get Document by ID
```
GET /documents/{document_type}/{document_id}?raw_metadata=false&domain_id=default_domain
```

**Parameters:**
- `document_type`: Document type enum
- `document_id`: Document UUID
- `raw_metadata`: Include raw metadata in response (default: false)
- `domain_id`: Domain ID for filtering

**Response:**
```json
{
  "document_type": "generic",
  "document_id": "uuid-string",
  "document_name": "Document_12345678",
  "document_content": "Full document content...",
  "markdown_summary": "# Document Summary\n...",
  "raw_metadata": {
    "chromadb_ids": ["id1", "id2"],
    "extraction_types": ["business_intelligence"],
    "key_phrases": ["AI", "ML"],
    "source_type": "upload",
    "event_type": "document_upload",
    "event_timestamp": "2024-01-01T00:00:00Z",
    "created_by": "api_user",
    "domain_id": "default_domain",
    "chunk_content_length": 1234,
    "extraction_date": "2024-01-01T00:00:00Z"
  }
}
```

### 4. Delete Document
```
DELETE /documents/{document_type}/{document_id}
```

**Parameters:**
- `document_type`: Document type enum
- `document_id`: Document UUID

**Response:**
```json
{
  "message": "Document deleted successfully"
}
```

### 5. Search Documents
```
POST /documents/search
```

**Parameters:**
- `query`: Search query text (required)
- `document_type`: Optional document type filter
- `source_type`: Optional source type filter
- `domain_id`: Domain ID for filtering (default: "default_domain")
- `limit`: Maximum number of results (1-100, default: 10)
- `use_tfidf`: Use TF-IDF search (default: true)

**Response:**
```json
{
  "query": "document processing",
  "results": [
    {
      "document_id": "uuid-string",
      "content": "Document content...",
      "metadata": {
        "source_type": "upload",
        "document_type": "generic",
        "created_by": "api_user",
        "created_at": "2024-01-01T00:00:00Z",
        "chromadb_ids": ["id1", "id2"],
        "key_phrases": ["AI", "ML"]
      },
      "score": 0.95
    }
  ],
  "total_results": 1,
  "search_type": "tfidf"
}
```

### 6. Get Document Insights
```
GET /documents/insights/{document_id}?insight_type=business_intelligence&domain_id=default_domain
```

**Parameters:**
- `document_id`: Document UUID
- `insight_type`: Optional specific insight type to retrieve
- `domain_id`: Domain ID for filtering (default: "default_domain")

**Response (all insights):**
```json
{
  "document_id": "uuid-string",
  "insights": {
    "business_intelligence": {
      "kpis": {...},
      "business_terms": {...},
      "data_definitions": {...},
      "operational_metrics": {...}
    },
    "entities": {
      "people": [...],
      "organizations": [...],
      "locations": [...],
      "concepts": [...]
    }
  },
  "extraction_config": {
    "extraction_types": ["business_intelligence", "entities"],
    "extraction_metadata": {...},
    "extraction_timestamp": "2024-01-01T00:00:00Z",
    "extraction_version": "5.0",
    "model_name": "gpt-4o",
    "temperature": 0.0,
    "chunk_count": 5
  },
  "key_phrases": ["AI", "machine learning", "document processing"],
  "chunk_content": "Consolidated chunk content...",
  "extraction_date": "2024-01-01T00:00:00Z",
  "chromadb_ids": ["id1", "id2"]
}
```

**Response (specific insight type):**
```json
{
  "document_id": "uuid-string",
  "insight_type": "business_intelligence",
  "data": {
    "kpis": {...},
    "business_terms": {...},
    "data_definitions": {...},
    "operational_metrics": {...}
  },
  "extraction_date": "2024-01-01T00:00:00Z"
}
```

### 7. Get Document Type Schema
```
GET /documents/{document_type}/schemas
```

**Parameters:**
- `document_type`: Document type enum

**Response:**
```json
{
  "document_type": "generic",
  "schema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "content": {"type": "string"},
      "tags": {"type": "array", "items": {"type": "string"}}
    }
  }
}
```

## Document Types

The router supports the following document types:

- `GONG_TRANSCRIPT`: Gong call transcripts
- `SLACK_CONVERSATION`: Slack conversation exports
- `CONTRACT`: Legal contracts and agreements
- `GENERIC`: Generic documents (default)
- `EXTENSIVE_CALL`: Extended call recordings
- `DOCS_DOCUMENTATION`: Documentation files
- `FINANCIAL_REPORT`: Financial reports and statements
- `BUSINESS_DOCUMENT`: Business documents
- `PDF_DOCUMENT`: PDF files
- `TEXT_DOCUMENT`: Plain text files
- `JSON_DOCUMENT`: JSON data files
- `WORD_DOCUMENT`: Microsoft Word documents
- `GOOGLE_DOCUMENT`: Google Docs documents
- `WIKI_DOCUMENT`: Wiki pages and markdown files

## Extraction Types

The system supports multiple extraction types:

- **Business Intelligence**: KPIs, business terms, data definitions, operational metrics
- **Entities**: People, organizations, locations, concepts, products
- **Financial Metrics**: Revenue, profit, growth metrics, financial ratios
- **Compliance Terms**: Regulations, requirements, compliance terminology

## Configuration

### Environment Variables
- `CHROMA_DB_PATH`: Path to ChromaDB storage (default: "./chroma_db")
- `DATABASE_URL`: PostgreSQL connection string
- `OPENAI_API_KEY`: OpenAI API key for LLM processing

### Service Configuration
The router uses the following services:
- `DocumentPersistenceService`: Handles database operations
- `DocumentIngestionService`: Handles document processing and extraction
- `SessionManager`: Manages database sessions
- `DomainManager`: Handles multi-tenant operations

## Testing

Run the test script to verify the router functionality:

```bash
cd /Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/dataservices
python test_document_router.py
```

## Error Handling

The router provides comprehensive error handling:

- **400 Bad Request**: Invalid file, empty file, or missing parameters
- **404 Not Found**: Document not found
- **500 Internal Server Error**: Processing errors with detailed error information

Error responses include:
- Error message and details
- Traceback (in test mode)
- Document ID and processing stage
- Suggested actions for resolution

## Security

- **File validation**: Validates file types and content
- **Size limits**: Configurable file size limits
- **Domain isolation**: Multi-tenant document isolation
- **Input sanitization**: Sanitizes user inputs and file content

## Performance

- **Async processing**: Non-blocking document processing
- **Caching**: Optional caching for repeated operations
- **Chunking**: Efficient text chunking for large documents
- **Vector indexing**: Optimized vector search with ChromaDB

## Monitoring

The router includes comprehensive logging:
- Document processing stages
- Error tracking and debugging
- Performance metrics
- User activity tracking

## Migration from Original Router

The new router maintains the same API interface as the original documents.py router, making migration straightforward:

1. **Same endpoints**: All original endpoints are preserved
2. **Same response formats**: Response schemas are identical
3. **Enhanced features**: Additional capabilities for advanced processing
4. **Better error handling**: Improved error messages and debugging
5. **Performance improvements**: Faster processing and better scalability

## Future Enhancements

Planned enhancements include:
- Real-time document processing
- Advanced analytics and reporting
- Custom extraction configurations
- Integration with external document sources
- Enhanced security features
- Performance optimizations
