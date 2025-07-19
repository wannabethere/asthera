# Agent Utilities

This directory contains utility functions and helpers shared across different agent implementations, promoting code reuse and maintainability.

## Overview

- **document_processor.py**: Shared functions for processing documents from various data sources
- **prompt_builder.py**: Functions for building prompts with consistent templates
- **section_extractor.py**: Functions for extracting structured sections from documents
- **workflow_helpers.py**: Shared functions for workflow orchestration and document analysis
- **extraction_retriever.py**: Enhanced document retrieval with semantic search capabilities

## Module Details

#### document_processor.py

Provides shared functionality for processing retrieved documents:

- Document filtering and sorting
- Metadata extraction
- Content formatting for analysis

#### prompt_builder.py

Contains functions for building consistent prompts:

- System prompts with configurable components
- Message formatting helpers
- Prompt construction based on query types
- Common prompts for document analysis and workflow tasks

#### section_extractor.py

Functions for extracting structured data from documents:

- Pattern-based section extraction
- Structured data parsing
- Insight extraction from metadata

#### workflow_helpers.py

Utilities for workflow orchestration and document analysis:

- Data source determination based on query analysis
- Document relevance analysis
- Query refinement for better document retrieval
- Result aggregation across data sources
- Response formatting for chat interfaces

#### extraction_retriever.py

Advanced document retrieval with semantic search and filtering:

- Vector-based document retrieval using ChromaDB
- Source-specific filtering (Salesforce, Gong)
- Hierarchical search strategy for structured data
- Document chunking and preprocessing
- Relevance scoring with multiple factors
- Context-aware search with conversation history
- Document caching for performance optimization

## Usage

### In BaseAgent

The `BaseAgent` class now provides default implementations for common operations that can be overridden by child classes:

```python
def process_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return process_retrieved_documents(documents, self.source_type)

def format_documents_for_context(self, documents: List[Dict[str, Any]]) -> str:
    return format_documents_for_context(documents)

def build_system_prompt(self) -> str:
    return f"""You are an AI assistant specialized in {self.source_type} data analysis..."""

def build_human_prompt(self, question: str, context: str, ...) -> str:
    return build_human_prompt(question, context, ...)
```

### In Agent Implementations

Agent implementations should:

1. Import the utility functions they need
2. Override the default methods for agent-specific behavior
3. Use the utility functions to reduce code duplication

Example:

```python
from app.agentic.utils.document_processor import extract_insights_from_metadata
from app.agentic.utils.prompt_builder import build_gong_agent_system_prompt
from app.agentic.utils.section_extractor import extract_structured_sections


class GongAgent(BaseAgent):
    # Override build_system_prompt for Gong-specific prompt
    def build_system_prompt(self) -> str:
        return build_gong_agent_system_prompt()

    # Use utility functions in your implementation
    def _process_retrieved_documents(self, documents):
        # Process using shared code plus Gong-specific logic
        processed_docs = super().process_documents(documents)

        # Add Gong-specific processing
        for doc in processed_docs:
            if 'insight' in doc['document_type']:
                # Extract structured sections
                doc['structured_content'] = extract_structured_sections(doc['content'])

        return processed_docs
```

### Usage Examples

```python
# Using document processor
from app.agentic.utils.document_processor import process_retrieved_documents

processed_docs = await process_retrieved_documents(
    retrieved_documents=docs,
    query=query,
    document_ids=document_ids,
    source_filter=source_filter
)

# Using prompt builder
from app.agentic.utils.prompt_builder import build_system_prompt

system_prompt = build_system_prompt(source_type="gong", additional_context={})

# Using section extractor
from app.agentic.utils.section_extractor import extract_structured_sections

sections = extract_structured_sections(document)

# Using workflow helpers
from app.agentic.utils.workflow_helpers import determine_data_sources, analyze_document_relevance

source_type = await determine_data_sources(question, document_ids)
state = await analyze_document_relevance(state_data, llm=llm)

# Using extraction retriever
from app.agentic.utils.extraction_retriever import EnhancedExtractionRetriever

retriever = EnhancedExtractionRetriever(use_remote_chroma=True)
documents = await retriever.retrieve_documents(
    query="Tell me about our recent sales deals",
    source_type="salesforce",
    topics=["pipeline", "opportunity"],
    top_k=10
)
```

### Implementation Notes

- All utility functions should be stateless
- Each function should have clear documentation and type hints
- Error handling should be consistent across utilities
- Log relevant information for debugging and analysis 