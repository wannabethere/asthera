# Service Flow Diagrams

This document provides comprehensive flowcharts explaining how the Combined Ask Service and SQL Helper Service work, including the Safety Agent integrated into the SQL RAG Agent flow for governance.

## Purpose & Business Value

**Empower Business Users to Personalize Dashboards Independently**

Our platform enables business professionals to create, customize, and personalize dashboards using their own business intelligence tools—all through natural language queries. This self-service capability delivers significant value to organizations:

- **💰 Cost Savings**: Eliminates dependency on IT teams or expensive consultants for dashboard customization
- **⚡ Speed to Value**: Business users can create personalized dashboards in **minutes** instead of waiting days or weeks for IT requests
- **🎯 Self-Service Analytics**: Non-technical users can query data, generate visualizations, and build dashboards without SQL knowledge
- **🔒 Enterprise-Grade Governance**: Built-in safety controls ensure data access compliance and privacy protection
- **📊 Tool Agnostic**: Works seamlessly with any business intelligence tool, allowing organizations to leverage their existing investments

By combining natural language processing with Self-Correcting CRAG architecture, we transform complex SQL query generation into simple conversational interactions, putting the power of data analytics directly into the hands of business decision-makers.

## Table of Contents

1. [Combined Ask Service Flow](#combined-ask-service-flow)
2. [SQL Helper Service Flows](#sql-helper-service-flows)
3. [Integrated Service Architecture](#integrated-service-architecture)

---

## Combined Ask Service Flow

The Combined Ask Service processes user queries and provides both SQL results and intelligent question recommendations in a single request. This service combines the power of natural language to SQL conversion with proactive question suggestions.

**Business Impact**: Business users can ask questions in plain English like "Show me sales by region for Q4" and instantly receive SQL queries, visualizations, and dashboard configurations they can use in their own BI tools—all within minutes, eliminating the need for IT support.

### Self-Correcting CRAG Architecture

The **SQL RAG Agent** is built on a **Self-Correcting CRAG (Corrective Retrieval Augmented Generation)** architecture. This architecture enables the system to automatically detect, evaluate, and correct SQL queries through iterative improvement cycles.

**Key Principles of Self-Correcting CRAG:**

1. **Retrieval Phase**: Retrieves relevant database schema, table structures, and example queries from vector stores
2. **Generation Phase**: Generates SQL queries based on the retrieved context and user intent
3. **Evaluation Phase**: Validates the generated SQL for correctness, completeness, and performance
4. **Correction Phase**: Automatically corrects identified issues through iterative refinement
5. **Feedback Loop**: Learns from corrections to improve future query generation

This self-correcting capability ensures high-quality SQL generation by detecting errors early and continuously improving the output through multiple refinement cycles.

### Self-Correcting CRAG Flow Diagram

```mermaid
flowchart TD
    Start[User Query] --> R1[Retrieval Phase]
    
    subgraph "Retrieval Phase"
        R1 --> R2[Vector Search: Schema]
        R1 --> R3[Vector Search: Example Queries]
        R2 --> R4[Assemble Context]
        R3 --> R4
    end
    
    R4 --> G1[Generation Phase]
    
    subgraph "Generation Phase"
        G1 --> G2[Generate SQL Query]
        G2 --> G3[Apply Safety Governance]
    end
    
    G3 --> E1[Evaluation Phase]
    
    subgraph "Evaluation Phase"
        E1 --> E2[Validate SQL Syntax]
        E2 --> E3[Check Query Quality]
        E3 --> E4{Quality Acceptable?}
    end
    
    E4 -->|No| C1[Correction Phase]
    E4 -->|Yes| Execute[Execute SQL]
    
    subgraph "Correction Phase"
        C1 --> C2[Identify Issues]
        C2 --> C3[Generate Correction]
        C3 --> C4[Refine Query]
        C4 --> G1
    end
    
    Execute --> Results[Return Results]
    
    style R1 fill:#e1f5ff
    style G1 fill:#fff4e1
    style E1 fill:#e1ffe1
    style C1 fill:#ffe1e1
    style Execute fill:#e1ffe1
```

### High-Level Flow

```mermaid
flowchart TD
    A[User Query Received] --> B[Create AskRequest & RecommendationRequest]
    B --> C{Parallel Processing}
    
    C --> D[Ask Service Pipeline]
    C --> E[Question Recommendation Service]
    
    D --> D1[Check Historical Questions]
    D1 -->|Found| D2[Return Cached Result]
    D1 -->|Not Found| D3[Intent Classification]
    D3 -->|Non-SQL Intent| D4[Return Intent-Based Response]
    D3 -->|SQL Intent| D5[SQL RAG Agent]
    D5 --> D6[SQL Generation]
    D6 --> D7[SQL Validation & Correction]
    D7 --> D8[SQL Execution]
    D8 --> D9[Quality Scoring]
    D9 --> D10[SQL Result with Metadata]
    
    E --> E1[Analyze User Question]
    E1 --> E2[Generate Question Categories]
    E2 --> E3[Generate Recommended Questions]
    E3 --> E4[Parse & Structure Recommendations]
    
    D10 --> F[Combine Results]
    E4 --> F
    D2 --> F
    D4 --> F
    
    F --> G[Extract SQL Result Data]
    G --> H[Build Combined Response]
    H --> I{Response Type}
    I -->|Non-Streaming| J[Return CombinedAskResponse]
    I -->|Streaming| K[Stream Updates via SSE/WebSocket]
    I -->|WebSocket| L[Real-time WebSocket Updates]
    
    style D fill:#e1f5ff
    style E fill:#fff4e1
    style F fill:#e1ffe1
    style S1 fill:#ffe1e1
```

### Detailed Ask Service Pipeline with Self-Correcting CRAG

```mermaid
flowchart TD
    A1[Ask Service: Process Request] --> A2{Check History Cache}
    A2 -->|Match Found| A3[Return Historical Result]
    A2 -->|No Match| A4[Intent Classification Agent]
    
    A4 --> A5{Intent Type}
    A5 -->|CONVERSATIONAL| A6[Conversational Response]
    A5 -->|METADATA_QUERY| A7[Metadata Search]
    A5 -->|SQL_QUERY| A8[SQL Generation Pipeline]
    
    A8 --> A9[SQL RAG Agent<br/>Self-Correcting CRAG]
    
    subgraph "CRAG: Retrieval Phase"
        A9 --> A10[Retrieve Relevant Tables/Schema]
        A10 --> A11[Vector Search: Schema Examples]
        A11 --> A12[Context Assembly]
    end
    
    A12 --> SA1[Safety Agent: Governance Checks]
    SA1 --> SA2[Row Level Policies]
    SA2 --> SA3[Data Access Controls]
    SA3 --> SA4[PII Checker]
    SA4 --> SA5{Governance Pass?}
    SA5 -->|No| SA6[Block/Filter Access]
    
    subgraph "CRAG: Generation Phase"
        SA5 -->|Yes| A13[Generate SQL Query]
    end
    
    subgraph "CRAG: Evaluation & Correction Loop"
        A13 --> A14[SQL Validator]
        A14 --> A15[Quality Evaluation]
        A15 --> A16{Valid & High Quality?}
        A16 -->|No| A17[SQL Correction]
        A17 --> A18[Identify Issues]
        A18 --> A19[Refine Query]
        A19 --> A13
    end
    
    A16 -->|Yes| A20[Execute SQL with Row-Level Policies]
    A20 --> A21[Retrieve Results]
    
    A21 --> SA7[Safety Agent: Post-Processing]
    SA7 --> SA8[Apply Row Filters]
    SA8 --> SA9[Mask PII Data]
    SA9 --> A22[Quality Scoring]
    A22 --> A23[Generate Explanation]
    A23 --> A24[Format Response]
    
    SA6 --> A25[Return Error Response]
    A6 --> A24
    A7 --> A24
    A24 --> A26[Return AskResultResponse]
    
    style A8 fill:#e1f5ff
    style A9 fill:#ffe1e1
    style SA1 fill:#ffe1e1
    style A20 fill:#ffe1e1
    style A22 fill:#fff4e1
    style SA7 fill:#ffe1e1
    style A16 fill:#e1ffe1
```

### Question Recommendation Service Flow

```mermaid
flowchart TD
    R1[Question Recommendation Service] --> R2[Analyze User Question]
    R2 --> R3[Extract Context & Intent]
    R3 --> R4[Check Previous Questions]
    R4 --> R5[Generate Question Categories]
    R5 --> R6[Generate Questions per Category]
    R6 --> R7[Rank & Filter Questions]
    R7 --> R8[Parse Recommendations]
    R8 --> R9[Structure: Categories + Questions + Reasoning]
    R9 --> R10[Return Recommendation Response]
    
    style R5 fill:#e1f5ff
    style R6 fill:#fff4e1
```

---

## SQL Helper Service Flows

The SQL Helper Service provides comprehensive assistance for SQL queries, including summarization, visualization, analysis, and data generation capabilities.

**Business Impact**: Enables business users to generate ready-to-use visualizations, summaries, and dashboard components from SQL queries—reducing the time from query to insight from hours to minutes. Users can instantly understand their data and create personalized dashboard views without technical expertise.

### SQL Summary & Visualization Flow

```mermaid
flowchart TD
    S1[SQL Summary Request] --> S2[Validate SQL & Query]
    S2 --> S3[Data Summarization Pipeline]
    S3 --> S4[Execute SQL Query]
    S4 --> S5[Retrieve Query Results]
    S5 --> S6[Analyze Data Structure]
    S6 --> S7[Generate Data Summary]
    S7 --> S8{Include Visualization?}
    S8 -->|Yes| S9[Chart Generation Agent]
    S8 -->|No| S10[Return Summary Only]
    S9 --> S11[Determine Chart Type]
    S11 --> S12[Generate Vega-Lite Spec]
    S12 --> S13[Create Chart Metadata]
    S13 --> S14[Combine Summary + Chart]
    S14 --> S15[Return Complete Response]
    S10 --> S15
    
    style S7 fill:#e1f5ff
    style S9 fill:#fff4e1
    style S12 fill:#e1ffe1
```

### Query Requirements Analysis Flow

```mermaid
flowchart TD
    Q1[Query Requirements Analysis Request] --> Q2[Parse User Query]
    Q2 --> Q3[Extract Key Requirements]
    Q3 --> Q4[Identify Data Needs]
    Q4 --> Q5[SQL Expansion Pipeline]
    Q5 --> Q6[Generate Expanded Query Variations]
    Q6 --> Q7[SQL Correction Pipeline]
    Q7 --> Q8[Validate SQL Variations]
    Q8 --> Q9[Rank by Relevance]
    Q9 --> Q10[Return Requirements Analysis]
    
    style Q5 fill:#e1f5ff
    style Q7 fill:#fff4e1
```

### SQL Visualization Generation Flow

```mermaid
flowchart TD
    V1[Visualization Request] --> V2[Extract SQL Result Data]
    V2 --> V3[Analyze Data Characteristics]
    V3 --> V4{Chart Config Provided?}
    V4 -->|Yes| V5[Use Provided Config]
    V4 -->|No| V6[Auto-detect Chart Type]
    V6 --> V7[Generate Optimal Visualization]
    V5 --> V8[Generate Chart Specification]
    V7 --> V8
    V8 --> V9[Create Vega-Lite Chart]
    V9 --> V10[Include Data Summary]
    V10 --> V11[Return Visualization Response]
    
    style V6 fill:#e1f5ff
    style V9 fill:#fff4e1
```

### Data Assistance Flow

```mermaid
flowchart TD
    DA1[Data Assistance Request] --> DA2[Analyze Query Intent]
    DA2 --> DA3[Data Assistance Pipeline]
    DA3 --> DA4[Identify Data Gaps]
    DA4 --> DA5[Suggest Data Sources]
    DA5 --> DA6[Generate Data Recommendations]
    DA6 --> DA7[Provide Schema Context]
    DA7 --> DA8[Return Assistance Response]
    
    style DA3 fill:#e1f5ff
```

### SQL Expansion Flow

```mermaid
flowchart TD
    E1[SQL Expansion Request] --> E2[Parse Original Query & SQL]
    E2 --> E3[SQL Expansion Pipeline]
    E3 --> E4[Identify Expansion Opportunities]
    E4 --> E5[Generate Expanded Variations]
    E5 --> E6[Add Additional Filters]
    E6 --> E7[Include More Metrics]
    E7 --> E8[Add Grouping/Aggregations]
    E8 --> E9[Validate Expanded SQL]
    E9 --> E10[Return Expanded SQL Options]
    
    style E3 fill:#e1f5ff
```

### Data Generation Flow

```mermaid
flowchart TD
    DG1[Data Generation Request] --> DG2[Validate SQL Query]
    DG2 --> DG3[Execute SQL with Pagination]
    DG3 --> DG4[Retrieve Data Page]
    DG4 --> DG5[Format Data Response]
    DG5 --> DG6{More Pages?}
    DG6 -->|Yes| DG7[Generate Next Page]
    DG7 --> DG4
    DG6 -->|No| DG8[Return Complete Dataset]
    
    style DG3 fill:#e1f5ff
```

---

## Integrated Service Architecture

This diagram shows how the different services work together in the overall system architecture.

```mermaid
flowchart TB
    subgraph "Client Layer"
        C1[Web Application]
        C2[Mobile App]
        C3[API Clients]
    end
    
    subgraph "API Gateway"
        API1[/api/v1/combined]
        API2[/sql-helper/summary]
        API3[/sql-helper/visualization]
        API4[/sql-helper/analyze-requirements]
    end
    
    subgraph "Service Layer"
        SVC1[Ask Service]
        SVC2[Question Recommendation Service]
        SVC3[SQL Helper Service]
    end
    
    subgraph "Agent Layer"
        AG1[Intent Classification Agent]
        AG2[SQL RAG Agent<br/>Self-Correcting CRAG<br/>+ Safety Agent]
        AG3[SQL Generation Agent]
        AG4[Chart Generation Agent]
        AG5[Data Summarization Pipeline]
        AG6[SQL Expansion Pipeline]
        AG7[SQL Correction Pipeline]
    end
    
    subgraph "Data Layer"
        DB[(Database)]
        CACHE[(Cache Layer)]
        SCHEMA[(Schema Repository)]
    end
    
    C1 --> API1
    C2 --> API1
    C3 --> API1
    C1 --> API2
    C2 --> API3
    
    API1 --> SVC1
    API1 --> SVC2
    API2 --> SVC3
    API3 --> SVC3
    API4 --> SVC3
    
    SVC1 --> AG1
    SVC1 --> AG2
    SVC1 --> AG3
    SVC2 --> AG2
    SVC3 --> AG5
    SVC3 --> AG4
    SVC3 --> AG6
    SVC3 --> AG7
    
    AG1 --> CACHE
    AG2 --> SCHEMA
    AG2 --> CACHE
    AG3 --> DB
    AG5 --> DB
    AG6 --> SCHEMA
    AG7 --> DB
    
    style AG2 fill:#ffe1e1
    style API1 fill:#e1f5ff
    style SVC1 fill:#fff4e1
    style SVC2 fill:#fff4e1
    style SVC3 fill:#e1ffe1
```

---

## Request/Response Flow Examples

### Example 1: Complete Combined Ask Flow

```mermaid
sequenceDiagram
    participant User
    participant API as Combined API
    participant AS as Ask Service
    participant QR as Question Recommendation
    participant DB as Database
    
    User->>API: POST /api/v1/combined<br/>{query, project_id}
    API->>AS: Process AskRequest (async)
    API->>QR: Recommend Questions (async)
    
    par Parallel Processing
        AS->>AS: Check History
        AS->>AS: Intent Classification
        AS->>AS: CRAG Retrieval: Get Schema
        AS->>AS: CRAG Generation: Generate SQL
        AS->>AS: CRAG Evaluation: Validate SQL
        AS->>AS: CRAG Correction: Refine if needed
        AS->>AS: Safety Agent: Apply Governance
        AS->>DB: Execute SQL with Row-Level Policies
        DB-->>AS: Query Results
        AS->>AS: Safety Agent: Filter & Mask PII
        AS->>AS: Quality Scoring
    and
        QR->>QR: Analyze Query
        QR->>QR: Generate Recommendations
    end
    
    AS-->>API: AskResultResponse
    QR-->>API: RecommendationResponse
    API->>API: Combine Results
    API-->>User: CombinedAskResponse<br/>{sql_result, questions, metadata}
```

### Example 2: SQL Summary with Visualization

```mermaid
sequenceDiagram
    participant User
    participant API as SQL Helper API
    participant SH as SQL Helper Service
    participant DS as Data Summarization Pipeline
    participant CG as Chart Generation Agent
    participant DB as Database
    
    User->>API: POST /sql-helper/summary<br/>{sql, query, project_id}
    API->>SH: generate_sql_summary_and_visualization()
    SH->>DS: Run Pipeline
    DS->>DB: Execute SQL
    DB-->>DS: Query Results
    DS->>DS: Analyze Data Structure
    DS->>DS: Generate Summary
    
    alt Include Visualization
        DS->>CG: Generate Chart
        CG->>CG: Determine Chart Type
        CG->>CG: Create Vega-Lite Spec
        CG-->>DS: Chart Specification
    end
    
    DS-->>SH: Summary + Chart
    SH-->>API: Complete Response
    API-->>User: {summary, chart, metadata}
```

---

## Key Components Summary

### Combined Ask Service Components

| Component | Purpose | Output |
|-----------|---------|--------|
| **Ask Service** | Converts natural language to SQL and executes queries | SQL results, metadata, quality scores |
| **Question Recommendation** | Generates intelligent follow-up questions | Categorized question recommendations |
| **Intent Classification** | Determines query intent (SQL, conversational, metadata) | Intent type and appropriate response |
| **SQL RAG Agent** | Self-Correcting CRAG architecture: Retrieves relevant schema, generates SQL, evaluates, and auto-corrects queries iteratively | SQL query with reasoning, corrected and validated |
| **Safety Agent** | Enforces governance, row-level policies, data access controls, and PII checking | Governance-compliant SQL and filtered results |
| **Quality Scoring** | Evaluates SQL quality and correctness | Quality scores and metrics |

### SQL Helper Service Components

| Component | Purpose | Output |
|-----------|---------|--------|
| **Data Summarization Pipeline** | Analyzes SQL results and generates summaries | Data summaries with insights |
| **Chart Generation Agent** | Creates visualizations from SQL results | Vega-Lite chart specifications |
| **SQL Expansion Pipeline** | Generates expanded query variations | Multiple SQL query options |
| **SQL Correction Pipeline** | Validates and corrects SQL queries | Corrected and validated SQL |
| **Data Assistance Pipeline** | Provides guidance on data access and usage | Data recommendations and suggestions |

### Safety Agent Components (Integrated in SQL RAG Agent)

| Component | Purpose |
|-----------|---------|
| **Row Level Policies** | Enforces row-level security policies based on user context |
| **Data Access Controls** | Controls access to tables and columns based on user permissions |
| **PII Checker** | Detects and masks Personally Identifiable Information in queries and results |
| **Governance** | Ensures compliance with organizational policies and regulations |

---

## API Endpoints Reference

### Combined Ask Service

- `POST /api/v1/combined` - Process query and get recommendations (non-streaming)
- `POST /api/v1/combined/stream` - Process query with streaming updates (SSE)
- `WS /ws/combined?query_id={id}` - WebSocket endpoint for real-time updates

### SQL Helper Service

- `POST /sql-helper/summary` - Generate SQL summary and visualization
- `POST /sql-helper/summary/stream` - Stream SQL summary generation
- `POST /sql-helper/analyze-requirements` - Analyze query requirements
- `POST /sql-helper/visualization` - Generate visualization from SQL results
- `POST /sql-helper/data-assistance` - Get data access assistance
- `POST /sql-helper/sql-expansion` - Generate expanded SQL variations
- `POST /sql-helper/data-generation` - Generate paginated data results
- `GET /sql-helper/status/{query_id}` - Get query status
- `POST /sql-helper/stop/{query_id}` - Stop ongoing query

---

## Future Enhancements

1. **Enhanced Analytics**
   - Query performance optimization
   - Usage pattern analysis
   - Predictive query recommendations

3. **Advanced Visualizations**
   - Interactive chart generation
   - Multi-dimensional data visualization
   - Custom chart templates

4. **Collaboration Features**
   - Query sharing and collaboration
   - Saved query collections
   - Team-based access controls

---

## Notes

- All services support both synchronous and asynchronous (streaming) modes
- **SQL RAG Agent Architecture**: Built on Self-Correcting CRAG (Corrective Retrieval Augmented Generation), enabling automatic detection, evaluation, and correction of SQL queries through iterative refinement cycles
- **Safety Agent Integration**: The Safety Agent is integrated into the SQL RAG Agent flow, providing governance at the query and result level
- **Safety Agent Features**: Row Level Policies, Data Access Controls, PII Checker, and Governance
- **Self-Correcting Mechanism**: The CRAG architecture continuously improves SQL quality by:
  - Retrieving relevant schema and examples
  - Generating SQL queries
  - Evaluating correctness and quality
  - Automatically correcting identified issues
  - Iterating until high-quality SQL is produced
- Services are designed to be scalable and handle high concurrent loads
- All processing steps include comprehensive error handling and logging
- The system maintains audit trails for compliance and debugging purposes

---

*Last Updated: [Current Date]*
*Version: 1.0*

