# Enhanced Self-RAG Agent

This document describes the enhanced Self-RAG agent that integrates document planning, TF-IDF ranking, web search fallback, and advanced summarization capabilities.

## Overview

The Enhanced Self-RAG Agent provides a comprehensive question-answering system that:

- **Integrates with Document Planning**: Uses the enhanced document planner to create intelligent retrieval strategies
- **TF-IDF Ranking**: Implements TF-IDF scoring for better document chunk relevance
- **Web Search Fallback**: Uses Tavily search when documents are insufficient
- **Enhanced Summarization**: Provides formatted output with metadata and citations
- **Multi-Source Analysis**: Combines documents and web sources (database queries handled by dedicated SQL agents)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Enhanced Self-RAG Agent                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Document        │  │ TF-IDF          │  │ Tavily       │ │
│  │ Planning        │  │ Ranking         │  │ Web Search   │ │
│  │ Integration     │  │ System          │  │ Fallback     │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Enhanced        │  │ Metadata        │  │ Citation     │ │
│  │ Summarization   │  │ Extraction      │  │ Tracking     │ │
│  │                 │  │                 │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Document        │  │ ChromaDB        │  │ Web Search   │ │
│  │ Retrieval       │  │ Vector Store    │  │ Integration  │ │
│  │                 │  │                 │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Document Planning Integration

The agent uses the enhanced document planner to:
- Analyze questions and determine optimal retrieval strategies
- Grade retrieval quality and identify gaps
- Create execution plans based on question complexity
- Provide confidence scores and recommendations

**Planning Strategies:**
- Comprehensive Analysis
- Focused Extraction
- Comparative Analysis
- Timeline Analysis
- Metadata Analysis
- Content Summarization
- Structured Extraction

### 2. TF-IDF Ranking System

Enhanced document relevance scoring using:
- **Semantic Similarity**: Vector-based document matching
- **TF-IDF Scoring**: Keyword-based relevance scoring
- **Combined Scoring**: Weighted combination of both approaches
- **Chunk-Level Ranking**: Fine-grained relevance assessment

```python
# Example TF-IDF scoring
tfidf_scores = ranker.get_relevance_scores(query, documents)
combined_scores = (semantic_score * 0.6) + (tfidf_score * 0.4)
```

### 3. Tavily Web Search Integration

Fallback web search when documents are insufficient:
- **Automatic Triggering**: Based on document quality thresholds
- **Relevance Scoring**: Web results are scored for relevance
- **Content Extraction**: Structured extraction of web content
- **Source Integration**: Web sources integrated with document sources

### 4. Enhanced Summarization

Advanced answer generation with:
- **Structured Output**: JSON-formatted responses with metadata
- **Source Citations**: Detailed source tracking and citations
- **Confidence Scoring**: Confidence levels for answers
- **Metadata Analysis**: Rich metadata about sources and processing
- **Action Tracking**: Detailed logs of actions taken

## Usage Examples

### Basic Question Answering

```python
from app.agents.nodes.docs.enhanced_self_rag_agent import EnhancedSelfRAGAgent
from app.schemas.document_schemas import DocumentType

# Initialize agent
agent = EnhancedSelfRAGAgent()

# Ask a question
response = await agent.run_agent(
    messages=[],
    question="What are the key financial metrics in our quarterly reports?",
    source_type=DocumentType.GENERIC
)

print(f"Answer: {response['messages'][0]['message_content']}")
```

### With Specific Documents

```python
# Use specific document IDs
response = await agent.run_agent(
    messages=[],
    question="What are the main findings in these documents?",
    source_type=DocumentType.GENERIC,
    document_ids=["doc_123", "doc_456", "doc_789"]
)
```

### Multi-Turn Conversation

```python
# Maintain conversation context
chat_history = [
    {"message_type": "human", "message_content": "What are our revenue streams?"},
    {"message_type": "ai", "message_content": "Our main revenue streams include..."}
]

response = await agent.run_agent(
    messages=chat_history,
    question="How has SaaS revenue changed over time?",
    source_type=DocumentType.GENERIC
)
```

### API Usage

```bash
# Ask a question via API
curl -X POST "http://localhost:8000/enhanced-rag/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key financial metrics?",
    "source_type": "generic",
    "enable_web_search": true,
    "enable_tfidf": true
  }'

# Chat conversation
curl -X POST "http://localhost:8000/enhanced-rag/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are our main revenue streams?",
    "conversation_id": "chat_123",
    "source_type": "generic"
  }'
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key
CHROMA_STORE_PATH=/path/to/chroma/store

# Optional
TAVILY_API_KEY=your_tavily_api_key
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=5
```

### Dependencies

Install additional requirements:

```bash
pip install -r requirements_enhanced_rag.txt
```

Key dependencies:
- `scikit-learn>=1.3.0` - TF-IDF ranking
- `tavily-python>=0.3.0` - Web search
- `numpy>=1.24.0` - Numerical operations
- `nltk>=3.8.0` - Text processing

## API Endpoints

### `/enhanced-rag/ask`
Ask a single question with enhanced processing.

**Request:**
```json
{
  "question": "What are the key financial metrics?",
  "source_type": "generic",
  "document_ids": ["doc_123", "doc_456"],
  "enable_web_search": true,
  "enable_tfidf": true,
  "max_documents": 25
}
```

**Response:**
```json
{
  "question": "What are the key financial metrics?",
  "answer": "Based on our financial reports...",
  "sources": [
    {
      "type": "document",
      "id": "doc_123",
      "title": "Q3 Financial Report",
      "relevance_score": 0.85
    }
  ],
  "metadata": {
    "confidence": 0.85,
    "sources_used": 3,
    "action_taken": "Document planning + TF-IDF ranking"
  },
  "execution_time": 2.34,
  "sources_count": 3
}
```

### `/enhanced-rag/chat`
Multi-turn conversation with context.

**Request:**
```json
{
  "message": "How has our performance changed?",
  "conversation_id": "chat_123",
  "source_type": "generic"
}
```

### `/enhanced-rag/health`
Health check and service status.

### `/enhanced-rag/capabilities`
Get service capabilities and features.

### `/enhanced-rag/examples`
Get example requests and usage patterns.

## Advanced Features

### 1. Document Planning Strategies

The agent automatically selects the best strategy based on question analysis:

- **Comprehensive Analysis**: For complex questions requiring full document analysis
- **Focused Extraction**: For specific information extraction from limited documents
- **Comparative Analysis**: For comparing information across multiple documents
- **Timeline Analysis**: For time-based analysis of document content
- **Metadata Analysis**: For questions about document properties
- **Structured Extraction**: For extracting structured data (tables, lists)

### 2. TF-IDF Ranking

Enhanced relevance scoring:

```python
# TF-IDF vectorizer configuration
vectorizer = TfidfVectorizer(
    max_features=1000,
    stop_words='english',
    ngram_range=(1, 2)
)

# Combined scoring
combined_score = (semantic_score * 0.6) + (tfidf_score * 0.4)
```

### 3. Web Search Integration

Automatic web search when documents are insufficient:

```python
# Web search trigger conditions
if avg_document_score < 0.3:
    web_results = await tavily_search(query, max_results=5)
```

### 4. Enhanced Metadata

Rich metadata in responses:

```json
{
  "metadata": {
    "confidence": 0.85,
    "sources_used": 5,
    "document_sources": 3,
    "web_sources": 2,
    "action_taken": "Document planning + Web search",
    "limitations": ["Limited historical data"]
  }
}
```

## Performance Optimization

### 1. Caching
- Document retrieval results can be cached
- TF-IDF models can be persisted and reused
- Web search results can be cached for similar queries

### 2. Parallel Processing
- Multiple documents processed in parallel
- Web search and document retrieval can run concurrently
- TF-IDF scoring can be vectorized

### 3. Resource Management
- Configurable document limits
- Timeout settings for web search
- Memory management for large document sets

## Error Handling

### 1. Graceful Degradation
- Falls back to basic retrieval if planning fails
- Uses web search when documents are insufficient
- Provides partial results when some sources fail

### 2. Error Recovery
- Retries failed operations with exponential backoff
- Maintains state for error recovery
- Provides detailed error messages

### 3. Logging and Monitoring
- Comprehensive logging at all levels
- Performance metrics tracking
- Error rate monitoring

## Testing

### Unit Tests
```python
# Test document planning integration
async def test_document_planning():
    agent = EnhancedSelfRAGAgent()
    response = await agent.run_agent(
        messages=[],
        question="test question",
        source_type=DocumentType.GENERIC
    )
    assert 'messages' in response
```

### Integration Tests
```python
# Test full workflow
async def test_full_workflow():
    agent = EnhancedSelfRAGAgent()
    response = await agent.run_agent(
        messages=[],
        question="What are our key metrics?",
        source_type=DocumentType.GENERIC
    )
    assert response['messages'][0]['message_content']
```

### Performance Tests
```python
# Test performance with various question types
async def test_performance():
    questions = [
        "Simple question",
        "Complex analytical question",
        "Question requiring web search"
    ]
    
    for question in questions:
        start_time = time.time()
        response = await agent.run_agent(...)
        execution_time = time.time() - start_time
        assert execution_time < 30  # 30 second timeout
```

## Troubleshooting

### Common Issues

1. **No Documents Found**
   - Check document availability in ChromaDB
   - Verify search query specificity
   - Enable web search fallback

2. **Low Answer Quality**
   - Increase document retrieval limit
   - Enable TF-IDF ranking
   - Check document content quality

3. **Slow Performance**
   - Reduce max_documents parameter
   - Enable caching
   - Check network connectivity for web search

4. **Web Search Failures**
   - Verify Tavily API key
   - Check network connectivity
   - Review search query format

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("EnhancedSelfRAGAgent").setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Multi-Modal Analysis**: Support for images and other media
2. **Real-Time Updates**: Live document processing
3. **Advanced NLP**: More sophisticated text analysis
4. **Custom Models**: Support for custom language models
5. **Workflow Integration**: Integration with workflow systems

### Performance Improvements

1. **Distributed Processing**: Multi-node document processing
2. **Advanced Caching**: Intelligent result caching
3. **Streaming**: Real-time result streaming
4. **Optimization**: Query and execution optimization

## Contributing

### Development Setup

1. Install dependencies: `pip install -r requirements_enhanced_rag.txt`
2. Set up environment variables
3. Initialize database and vector stores
4. Run tests: `pytest tests/`

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add comprehensive docstrings
- Include error handling
- Write unit tests

## License

This enhanced Self-RAG agent is part of the ComplianceSpark platform and follows the same licensing terms.
