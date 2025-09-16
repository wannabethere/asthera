# Agent Capabilities Documentation

This document provides a comprehensive overview of all agent capabilities available in the GenieML platform. The agents are organized into different categories based on their functionality and use cases.

## Table of Contents

1. [Overview](#overview)
2. [Agent Architecture](#agent-architecture)
3. [Core Agent Categories](#core-agent-categories)
4. [SQL & Data Analysis Agents](#sql--data-analysis-agents)
5. [Document Processing Agents](#document-processing-agents)
6. [Writing & Content Generation Agents](#writing--content-generation-agents)
7. [Dashboard & Visualization Agents](#dashboard--visualization-agents)
8. [Retrieval & Search Agents](#retrieval--search-agents)
9. [Pipeline Orchestration](#pipeline-orchestration)
10. [Graph-Based Workflows](#graph-based-workflows)
11. [API Endpoints](#api-endpoints)
12. [Configuration & Settings](#configuration--settings)

## Overview

The GenieML platform includes a sophisticated multi-agent system designed to handle various data analysis, document processing, and content generation tasks. The agents are built using LangChain and LangGraph frameworks, providing robust orchestration and self-correcting capabilities.

### Key Features

- **Self-Correcting RAG (Retrieval-Augmented Generation)**: Agents can self-evaluate and correct their outputs
- **Multi-Modal Processing**: Support for text, SQL, charts, and document analysis
- **Pipeline Orchestration**: Complex workflows can be chained together
- **Real-time Streaming**: Support for streaming responses and real-time updates
- **Caching & Performance**: Built-in caching mechanisms for improved performance
- **Extensible Architecture**: Easy to add new agents and capabilities

## Agent Architecture

### Core Components

1. **Agent Nodes**: Individual processing units that perform specific tasks
2. **Pipelines**: Orchestrated sequences of agent operations
3. **Graphs**: Complex workflows using LangGraph for state management
4. **Retrieval Systems**: Document and knowledge retrieval mechanisms
5. **Storage Layer**: Document and vector storage using ChromaDB

### State Management

Agents use Pydantic models for state management, ensuring type safety and validation throughout the processing pipeline.

## Core Agent Categories

### 1. SQL & Data Analysis Agents

#### SQL RAG Agent
**Purpose**: Comprehensive SQL query generation, analysis, and optimization

**Key Capabilities**:
- Natural language to SQL conversion
- SQL query breakdown and explanation
- Query correction and optimization
- Follow-up question generation
- Intent classification for SQL queries
- Misleading query detection and assistance
- Relationship recommendation between database entities
- Semantic description generation

**Supported Operations**:
- `GENERATION`: Convert natural language to SQL
- `BREAKDOWN`: Explain complex SQL queries
- `EXPANSION`: Expand simple queries with additional context
- `CORRECTION`: Fix SQL syntax and logic errors
- `REASONING`: Provide step-by-step SQL reasoning
- `ANSWER`: Generate natural language answers from SQL results

**Tools Available**:
- SQL generation and breakdown processors
- Chart adjustment tools
- Follow-up SQL generation
- Intent classification
- Misleading assistance detection
- Relationship recommendation
- Semantics description

#### Enhanced SQL Pipeline
**Purpose**: Orchestrated SQL processing with multiple specialized agents

**Pipeline Types**:
- `SQL_GENERATION`: Generate SQL from natural language
- `SQL_BREAKDOWN`: Break down complex SQL queries
- `SQL_REASONING`: Provide reasoning for SQL logic
- `SQL_CORRECTION`: Correct SQL errors
- `SQL_EXPANSION`: Expand SQL with additional context
- `CHART_ADJUSTMENT`: Adjust charts based on SQL results
- `INTENT_CLASSIFICATION`: Classify user intent
- `MISLEADING_ASSISTANCE`: Detect and help with misleading queries

#### Data Analysis Agent
**Purpose**: Comprehensive dataframe analysis and KPI recommendation

**Key Capabilities**:
- Schema analysis and data type detection
- Statistical summary generation
- Time series detection
- Groupby column suggestions
- Aggregation function recommendations
- Correlation analysis
- Missing data analysis
- Function suggestions for data analysis
- Context generation for datasets

**Analysis Features**:
- Automatic data type detection
- Categorical vs continuous data identification
- Outlier detection using IQR method
- Correlation matrix calculation
- Missing data pattern analysis
- Time series column detection
- Groupby column recommendations
- Custom function suggestions based on data characteristics

### 2. Document Processing Agents

#### Enhanced Self-RAG Agent
**Purpose**: Advanced document retrieval and question answering with self-correction

**Key Capabilities**:
- Document planning and strategy selection
- TF-IDF based chunk ranking
- Web search integration (Tavily API)
- Document grading and quality assessment
- Self-correction and iterative improvement
- Multi-source retrieval (documents + web)
- Performance optimization modes (fast/balanced/quality)

**Retrieval Strategies**:
- `CHUNKS_ONLY`: Use TF-IDF chunks for specific queries
- `FULL_DOCS`: Use full documents for summary queries
- `HYBRID`: Combine both approaches

**Performance Modes**:
- `fast`: Maximum speed, minimal LLM calls
- `balanced`: Good speed with reasonable quality
- `quality`: Maximum quality, more LLM calls

#### Document Planning Agent
**Purpose**: Intelligent document retrieval planning and strategy selection

**Key Capabilities**:
- Document retrieval strategy planning
- Retrieval quality assessment
- Document relevance grading
- Strategy confidence scoring
- Multi-document analysis planning

#### Document Plan Executor
**Purpose**: Execute document retrieval plans with quality control

**Key Capabilities**:
- Plan execution with quality monitoring
- Document retrieval result processing
- Quality threshold enforcement
- Fallback strategy implementation

### 3. Writing & Content Generation Agents

#### Report Writing Agent
**Purpose**: Generate comprehensive reports with self-correcting capabilities

**Key Capabilities**:
- Multi-actor report generation (Executive, Analyst, Technical, etc.)
- Self-correcting RAG architecture
- Content quality evaluation
- Business goal alignment
- Thread component integration
- Iterative content improvement

**Writer Actor Types**:
- `EXECUTIVE`: High-level strategic reports
- `ANALYST`: Detailed analytical reports
- `TECHNICAL`: Technical documentation
- `BUSINESS_USER`: Business-focused content
- `DATA_SCIENTIST`: Data science reports
- `CONSULTANT`: Consulting-style reports

**Report Components**:
- Executive summary generation
- Section-based content organization
- Key insights extraction
- Data source attribution
- Confidence scoring
- Recommendations generation

#### Dashboard Agent
**Purpose**: Generate and manage dashboard configurations

**Key Capabilities**:
- Dashboard configuration generation
- Conditional formatting setup
- Control filter management
- Chart configuration
- Time filter handling
- SQL expansion for filters

#### Alerts Agent
**Purpose**: Convert SQL queries and natural language to alert configurations

**Key Capabilities**:
- SQL to alert conversion
- Natural language alert configuration
- Alert condition validation
- Threshold operator management
- Schedule type configuration
- Self-correcting alert generation

### 4. Dashboard & Visualization Agents

#### Conditional Formatting Agent
**Purpose**: Translate natural language to dashboard conditional formatting

**Key Capabilities**:
- Natural language to configuration translation
- Historical configuration retrieval
- Filter type examples
- Configuration validation
- Chart adjustment integration

**Filter Types**:
- `column_filter`: Column-based filtering
- `time_filter`: Time-based filtering
- `conditional_format`: Conditional formatting
- `aggregation_filter`: Aggregation-based filtering
- `custom_filter`: Custom filter definitions

**Filter Operators**:
- `equals`, `not_equals`, `greater_than`, `less_than`
- `greater_equal`, `less_equal`, `contains`, `not_contains`
- `starts_with`, `ends_with`, `in`, `not_in`
- `between`, `is_null`, `is_not_null`, `regex`

#### Chart Generation Agents
**Purpose**: Generate various types of charts and visualizations

**Supported Chart Types**:
- Plotly charts
- PowerBI charts
- Tableau charts
- Enhanced charts

**Key Capabilities**:
- Chart type selection based on data
- Chart configuration generation
- Chart adjustment and optimization
- Multi-platform chart support
- Interactive chart features

### 5. Retrieval & Search Agents

#### Retrieval Helper
**Purpose**: Unified retrieval interface for various data sources

**Key Capabilities**:
- Historical question retrieval
- Instruction retrieval
- SQL pairs retrieval
- Database schema retrieval
- Document retrieval
- Vector similarity search
- Caching and performance optimization

#### Historical Question Retrieval
**Purpose**: Retrieve similar historical questions for context

**Key Capabilities**:
- Semantic similarity search
- Question pattern matching
- Context-aware retrieval
- Performance optimization

#### SQL Pairs Retrieval
**Purpose**: Retrieve relevant SQL query pairs for learning

**Key Capabilities**:
- SQL pattern matching
- Query similarity search
- Example retrieval
- Learning context provision

### 6. Pipeline Orchestration

#### Pipeline Container
**Purpose**: Centralized pipeline management and orchestration

**Key Capabilities**:
- Pipeline registration and discovery
- Pipeline execution management
- Configuration management
- Metrics collection
- Error handling and recovery

#### Base Pipeline
**Purpose**: Foundation class for all agent pipelines

**Key Features**:
- Standardized pipeline interface
- Configuration management
- Metrics tracking
- Error handling
- Lifecycle management

### 7. Graph-Based Workflows

#### DataFrame Analyzer Graph
**Purpose**: Comprehensive dataframe analysis using LangGraph

**Workflow Steps**:
1. Schema analysis
2. Statistics calculation
3. Time series detection
4. Groupby suggestions
5. Aggregation recommendations
6. Correlation analysis
7. Missing data analysis
8. Function suggestions
9. Context generation

#### KPI Recommender Graph
**Purpose**: KPI recommendation system using strategic maps

**Workflow Steps**:
1. Goal context finding
2. Dataset metrics analysis
3. Objectives retrieval
4. KPIs retrieval
5. Strategic path analysis
6. Related KPIs finding
7. Insights retrieval
8. Query correction
9. KPI recommendation
10. Relevance scoring
11. Response generation

## API Endpoints

### Core Endpoints

#### Ask Endpoint
- **Purpose**: Main question answering interface
- **Methods**: POST
- **Features**: Multi-agent orchestration, streaming responses

#### Combined Ask
- **Purpose**: Enhanced question answering with multiple agent types
- **Methods**: POST
- **Features**: Agent selection, parallel processing

#### SQL Helper
- **Purpose**: SQL-specific operations
- **Methods**: POST
- **Features**: SQL generation, validation, execution

#### Chart Operations
- **Purpose**: Chart generation and modification
- **Methods**: POST
- **Features**: Chart creation, adjustment, optimization

#### Dashboard Management
- **Purpose**: Dashboard configuration and management
- **Methods**: POST, GET, PUT, DELETE
- **Features**: Dashboard CRUD, conditional formatting

#### Report Generation
- **Purpose**: Report creation and management
- **Methods**: POST, GET
- **Features**: Report generation, retrieval

#### Alert Management
- **Purpose**: Alert configuration and management
- **Methods**: POST, GET, PUT, DELETE
- **Features**: Alert CRUD, validation

#### Data Analysis
- **Purpose**: Data analysis operations
- **Methods**: POST
- **Features**: DataFrame analysis, KPI recommendations

#### Question Recommendation
- **Purpose**: Suggest relevant questions
- **Methods**: POST
- **Features**: Question similarity, recommendation

#### Instructions
- **Purpose**: Instruction retrieval and management
- **Methods**: GET, POST
- **Features**: Instruction search, retrieval

### Document Processing Endpoints

#### Document Persistence
- **Purpose**: Document storage and retrieval
- **Methods**: POST, GET, PUT, DELETE
- **Features**: Document CRUD, metadata management

#### Document Planning
- **Purpose**: Document retrieval planning
- **Methods**: POST
- **Features**: Plan generation, strategy selection

#### Enhanced RAG
- **Purpose**: Advanced document retrieval and Q&A
- **Methods**: POST
- **Features**: Self-correcting RAG, multi-source retrieval

## Configuration & Settings

### Environment Variables

#### Required Settings
- `OPENAI_API_KEY`: OpenAI API key for LLM access
- `TAVILY_API_KEY`: Tavily API key for web search
- `CHROMA_PERSIST_DIRECTORY`: ChromaDB persistence directory
- `REDIS_URL`: Redis URL for caching

#### Optional Settings
- `LLM_TEMPERATURE`: Default temperature for LLM calls
- `LLM_MODEL`: Default LLM model to use
- `CACHE_TTL`: Cache time-to-live in seconds
- `MAX_RETRIEVAL_SIZE`: Maximum number of documents to retrieve
- `SIMILARITY_THRESHOLD`: Minimum similarity threshold for retrieval

### Agent Configuration

#### Performance Modes
- **Fast Mode**: Optimized for speed, minimal LLM calls
- **Balanced Mode**: Good balance of speed and quality
- **Quality Mode**: Optimized for maximum quality

#### Retrieval Configuration
- **Similarity Threshold**: Minimum similarity for document retrieval
- **Top K**: Number of top documents to retrieve
- **Max Retrieval Size**: Maximum documents per retrieval
- **Cache TTL**: Cache expiration time

#### Pipeline Configuration
- **Max Iterations**: Maximum iterations for self-correction
- **Early Stopping**: Enable early stopping for convergence
- **Verbose Mode**: Enable detailed logging
- **Streaming**: Enable real-time response streaming

## Usage Examples

### Basic Question Answering
Initialize the SQL RAG Agent and ask questions about your data:

```python
# Initialize agent
llm = get_llm()
agent = SQLRAGAgent(llm=llm, engine=engine)

# Ask a question
result = await agent.process_query(
    query="What are the top 10 customers by revenue?",
    project_id="my_project"
)
```

### Document Analysis
Use the Enhanced Self-RAG Agent for document analysis:

```python
# Initialize agent
agent = EnhancedSelfRAGAgent(performance_mode="balanced")

# Analyze documents
result = await agent.run_agent(
    messages=chat_history,
    question="What are the key insights from the quarterly report?",
    source_type="gong_transcript"
)
```

### Report Generation
Generate comprehensive reports with the Report Writing Agent:

```python
# Initialize agent
agent = ReportWritingAgent()

# Generate report
result = agent.generate_report(
    workflow_data=workflow_data,
    thread_components=components,
    writer_actor=WriterActorType.EXECUTIVE,
    business_goal=business_goal
)
```

### Data Analysis
Perform comprehensive data analysis with the DataFrame Analyzer:

```python
# Initialize analyzer
analyzer = DataFrameAnalyzer(dataframe)

# Perform comprehensive analysis
result = analyzer.analyze_with_langgraph()
```

## Best Practices

### Performance Optimization
1. Use appropriate performance modes based on requirements
2. Enable caching for frequently accessed data
3. Use streaming for real-time responses
4. Optimize retrieval parameters based on data size

### Error Handling
1. Implement proper error handling in custom agents
2. Use fallback strategies for critical operations
3. Monitor agent performance and adjust configurations
4. Implement retry mechanisms for transient failures

### Security Considerations
1. Validate all inputs before processing
2. Implement proper access controls
3. Sanitize outputs before returning to users
4. Monitor for potential security vulnerabilities

### Monitoring and Logging
1. Enable comprehensive logging for debugging
2. Monitor agent performance metrics
3. Track error rates and success rates
4. Implement alerting for critical failures

## Future Enhancements

### Planned Features
1. **Multi-Modal Support**: Support for images, audio, and video processing
2. **Advanced Caching**: More sophisticated caching strategies
3. **Agent Learning**: Agents that learn from user interactions
4. **Distributed Processing**: Support for distributed agent execution
5. **Custom Agent Builder**: GUI for building custom agents

### Integration Opportunities
1. **External APIs**: Integration with external data sources
2. **Cloud Services**: Integration with cloud-based AI services
3. **Real-time Data**: Support for real-time data streams
4. **Mobile Support**: Mobile-optimized agent interfaces

---

This documentation provides a comprehensive overview of all agent capabilities in the GenieML platform. For specific implementation details, refer to the individual agent components and their associated documentation.
