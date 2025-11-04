# Report Service Flow Diagrams

This document provides comprehensive flowcharts explaining how the Report Service works, enabling business users to generate comprehensive, AI-written reports from SQL queries in minutes.

## Purpose & Business Value

**Transform Data into Comprehensive Business Reports Instantly**

The Report Service enables business professionals to transform their SQL queries and data insights into professionally written, comprehensive reports with executive summaries, analysis, and conclusions. This capability delivers significant organizational value:

- **💰 Cost Savings**: Eliminates dependency on data analysts or report writers for report generation
- **⚡ Speed to Value**: Business users can generate comprehensive, publication-ready reports in **minutes** instead of spending hours writing and formatting
- **📝 AI-Powered Writing**: Leverages self-correcting RAG architecture to generate high-quality, contextually relevant report content
- **🎯 Multiple Writer Personas**: Supports different writing styles (Executive, Analyst, Technical) tailored to target audiences
- **🔄 Workflow Integration**: Automatically generates reports from workflow question threads
- **📊 Comprehensive Structure**: Produces reports with executive summaries, detailed analysis, conclusions, and actionable recommendations
- **🎨 Customizable Templates**: Pre-built templates for different report types and business goals

## Table of Contents

1. [Report Generation Flow](#report-generation-flow)
2. [Self-Correcting RAG Report Writing](#self-correcting-rag-report-writing)
3. [Workflow-Based Report Generation](#workflow-based-report-generation)
4. [Report Components & Architecture](#report-components--architecture)
5. [API Endpoints Reference](#api-endpoints-reference)

---

## Report Generation Flow

The Report Service processes SQL queries and generates comprehensive reports using AI-powered writing agents with self-correcting capabilities.

### High-Level Report Generation Flow

```mermaid
flowchart TD
    A[Report Request] --> B{Request Type}
    
    B -->|Comprehensive| C[Report Orchestration Pipeline]
    B -->|Simple| D[Simple Report Generation]
    B -->|Workflow| E[Extract Workflow Components]
    
    C --> F[Process Report Queries]
    D --> G[Basic Report Processing]
    E --> H[Parse Thread Components]
    H --> F
    
    F --> I[Execute SQL Queries]
    I --> J[Retrieve Query Results]
    J --> K[Report Writing Agent]
    
    K --> L{Self-Correcting RAG}
    L --> M[Generate Initial Content]
    M --> N[Quality Evaluation]
    N --> O{Quality Acceptable?}
    
    O -->|No| P[Identify Issues]
    P --> Q[Refine Content]
    Q --> M
    O -->|Yes| R[Generate Sections]
    
    R --> S[Executive Summary]
    R --> T[Detailed Analysis]
    R --> U[Conclusions & Recommendations]
    
    S --> V[Assemble Report]
    T --> V
    U --> V
    
    V --> W[Apply Report Template]
    W --> X[Format & Style]
    X --> Y[Return Complete Report]
    
    G --> Z[Simple Report Output]
    
    style K fill:#e1f5ff
    style L fill:#fff4e1
    style V fill:#e1ffe1
    style Y fill:#ffe1e1
```

### Detailed Report Pipeline

```mermaid
flowchart TD
    R1[Report Service: Process Request] --> R2{Input Type}
    
    R2 -->|Report Queries| R3[Parse Report Queries]
    R2 -->|Workflow Data| R4[Extract Workflow Components]
    
    R3 --> R5[Validate Query Structure]
    R4 --> R6[Map Components to Queries]
    R6 --> R5
    
    R5 --> R7[Report Orchestrator Pipeline]
    
    subgraph "Query Processing"
        R7 --> R8[For Each Query]
        R8 --> R9[Execute SQL Query]
        R9 --> R10[Retrieve Results]
        R10 --> R11[Analyze Data Structure]
        R11 --> R12[Extract Key Metrics]
        R12 --> R13[Generate Data Summary]
    end
    
    R13 --> R14{All Queries Processed?}
    R14 -->|No| R8
    R14 -->|Yes| R15[Report Writing Agent]
    
    subgraph "Self-Correcting RAG Report Writing"
        R15 --> R16[Assemble Context]
        R16 --> R17[Select Writer Persona]
        R17 --> R18[Generate Initial Draft]
        R18 --> R19[Quality Evaluation]
        R19 --> R20{Quality Score}
        R20 -->|Low| R21[Identify Weaknesses]
        R21 --> R22[Generate Critique]
        R22 --> R23[Refine Content]
        R23 --> R18
        R20 -->|High| R24[Generate Report Sections]
    end
    
    subgraph "Report Assembly"
        R24 --> R25[Executive Summary Generation]
        R25 --> R26[Section-by-Section Writing]
        R26 --> R27[Analysis & Insights]
        R27 --> R28[Conclusions & Recommendations]
        R28 --> R29[Apply Report Template]
        R29 --> R30[Format Sections]
        R30 --> R31[Add Metadata & Citations]
    end
    
    R31 --> R32[Return Complete Report]
    
    style R7 fill:#e1f5ff
    style R15 fill:#fff4e1
    style R19 fill:#e1ffe1
    style R29 fill:#ffe1e1
```

---

## Self-Correcting RAG Report Writing

The Report Writing Agent uses a Self-Correcting RAG architecture to iteratively improve report quality through evaluation and refinement cycles.

### Self-Correcting RAG Report Flow

```mermaid
flowchart TD
    SR1[Report Writing Agent] --> SR2[Retrieval Phase]
    
    subgraph "Retrieval Phase"
        SR2 --> SR3[Gather Query Results]
        SR3 --> SR4[Extract Data Insights]
        SR4 --> SR5[Retrieve Domain Knowledge]
        SR5 --> SR6[Assemble Context]
    end
    
    SR6 --> SR7[Generation Phase]
    
    subgraph "Generation Phase"
        SR7 --> SR8[Select Writer Persona]
        SR8 --> SR9{Persona Type}
        SR9 -->|Executive| SR10[Executive Style]
        SR9 -->|Analyst| SR11[Analytical Style]
        SR9 -->|Technical| SR12[Technical Style]
        SR10 --> SR13[Generate Initial Content]
        SR11 --> SR13
        SR12 --> SR13
    end
    
    SR13 --> SR14[Evaluation Phase]
    
    subgraph "Evaluation Phase"
        SR14 --> SR15[Assess Content Quality]
        SR15 --> SR16[Check Relevance]
        SR16 --> SR17[Verify Clarity]
        SR17 --> SR18[Evaluate Actionability]
        SR18 --> SR19[Calculate Quality Score]
        SR19 --> SR20{Quality Acceptable?}
    end
    
    SR20 -->|No| SR21[Correction Phase]
    SR20 -->|Yes| SR22[Finalize Report]
    
    subgraph "Correction Phase"
        SR21 --> SR23[Identify Issues]
        SR23 --> SR24[Generate Improvement Suggestions]
        SR24 --> SR25[Refine Content]
        SR25 --> SR7
    end
    
    SR22 --> SR26[Return High-Quality Report]
    
    style SR2 fill:#e1f5ff
    style SR7 fill:#fff4e1
    style SR14 fill:#e1ffe1
    style SR21 fill:#ffe1e1
```

### Quality Evaluation Metrics

```mermaid
flowchart LR
    Q1[Quality Evaluation] --> Q2[Relevance Score]
    Q1 --> Q3[Clarity Score]
    Q1 --> Q4[Actionability Score]
    Q1 --> Q5[Completeness Score]
    
    Q2 --> Q6[Calculate Average]
    Q3 --> Q6
    Q4 --> Q6
    Q5 --> Q6
    
    Q6 --> Q7{Quality Threshold}
    Q7 -->|Above Threshold| Q8[Accept Report]
    Q7 -->|Below Threshold| Q9[Trigger Refinement]
    
    style Q1 fill:#e1f5ff
    style Q6 fill:#fff4e1
```

---

## Workflow-Based Report Generation

The Report Service can automatically generate reports from workflow data, extracting insights from question threads and creating comprehensive reports.

### Workflow Report Flow

```mermaid
flowchart TD
    WR1[Workflow Report Request] --> WR2[Extract Workflow ID]
    WR2 --> WR3[Retrieve Workflow Data]
    WR3 --> WR4[Parse Thread Components]
    
    WR4 --> WR5[Extract Component Data]
    
    subgraph "Component Analysis"
        WR5 --> WR6[For Each Component]
        WR6 --> WR7[Extract SQL Query]
        WR7 --> WR8[Extract Chart Config]
        WR8 --> WR9[Extract Data Overview]
        WR9 --> WR10[Extract Insights]
        WR10 --> WR11[Map to Report Section]
    end
    
    WR11 --> WR12{More Components?}
    WR12 -->|Yes| WR6
    WR12 -->|No| WR13[Apply Workflow Metadata]
    
    WR13 --> WR14[Select Report Template]
    WR14 --> WR15[Generate Report Context]
    WR15 --> WR16[Business Goal Alignment]
    WR16 --> WR17[Report Writing Pipeline]
    WR17 --> WR18[Return Comprehensive Report]
    
    style WR4 fill:#e1f5ff
    style WR17 fill:#fff4e1
```

### Report Orchestration Sequence

```mermaid
sequenceDiagram
    participant User
    participant API as Report API
    participant RS as Report Service
    participant RO as Report Orchestrator
    participant RW as Report Writing Agent
    participant DB as Database
    
    User->>API: POST /report/generate<br/>{queries, project_id, writer_actor}
    API->>RS: generate_comprehensive_report()
    RS->>RO: Orchestrate Report Generation
    
    par Parallel Query Processing
        RO->>DB: Execute SQL Queries
        DB-->>RO: Query Results
    end
    
    RO->>RO: Aggregate Data Insights
    RO->>RW: Generate Report Content
    
    loop Self-Correcting RAG Cycle
        RW->>RW: Generate Draft
        RW->>RW: Evaluate Quality
        RW->>RW: Refine if Needed
    end
    
    RW-->>RO: High-Quality Content
    RO->>RO: Assemble Report Sections
    RO->>RO: Apply Template
    RO-->>RS: Complete Report
    RS-->>API: ReportResponse
    API-->>User: Comprehensive Report
```

---

## Report Components & Architecture

### Component Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        C1[Business Users]
        C2[Report Consumers]
        C3[Workflow System]
    end
    
    subgraph "Report Service Layer"
        RS1[Report Service]
        RS2[Report Orchestrator]
        RS3[Template Engine]
    end
    
    subgraph "Agent Layer"
        AG1[Report Writing Agent<br/>Self-Correcting RAG]
        AG2[Quality Evaluator]
        AG3[Content Refiner]
        AG4[Section Generator]
    end
    
    subgraph "Data Layer"
        DB[(Database)]
        WF[(Workflow Data)]
        TEMPLATES[(Report Templates)]
    end
    
    C1 --> RS1
    C2 --> RS1
    C3 --> RS1
    
    RS1 --> RS2
    RS1 --> RS3
    
    RS2 --> AG1
    AG1 --> AG2
    AG1 --> AG3
    AG1 --> AG4
    
    RS2 --> DB
    RS3 --> TEMPLATES
    RS1 --> WF
    
    style RS1 fill:#e1f5ff
    style AG1 fill:#fff4e1
    style RS2 fill:#e1ffe1
```

---

## Key Components Summary

### Report Service Components

| Component | Purpose | Output |
|-----------|---------|--------|
| **Report Service** | Orchestrates report generation from queries or workflows | Complete report with all sections |
| **Report Orchestrator** | Coordinates query processing and report assembly | Aggregated data insights |
| **Report Writing Agent** | Self-correcting RAG agent that generates high-quality report content | Professionally written report sections |
| **Quality Evaluator** | Assesses content quality and relevance | Quality scores and improvement suggestions |
| **Content Refiner** | Iteratively improves report content based on evaluation | Refined, high-quality content |
| **Section Generator** | Creates structured report sections (executive summary, analysis, conclusions) | Formatted report sections |
| **Template Engine** | Applies report templates and formatting | Styled, publication-ready reports |

### Writer Personas

| Persona | Style | Use Case |
|---------|-------|----------|
| **Executive** | High-level, strategic, concise | C-suite reports, board presentations |
| **Analyst** | Detailed, data-driven, analytical | Deep-dive analysis, research reports |
| **Technical** | Precise, technical, comprehensive | Technical documentation, specifications |

### Report Templates

| Template | Sections | Target Audience |
|----------|----------|-----------------|
| **Executive Summary** | Overview, Key Findings, Recommendations | Executives, Decision Makers |
| **Comprehensive Analysis** | Full analysis with all sections | Analysts, Stakeholders |
| **Simple Report** | Basic overview and findings | General business users |

---

## API Endpoints Reference

### Report Generation

- `POST /report/generate` - Generate comprehensive report with AI writing
- `POST /report/generate-from-workflow` - Generate report from workflow data
- `POST /report/render-from-workflow` - Render report from workflow request
- `POST /report/generate-simple` - Generate simple report without comprehensive components

### Report Utilities

- `POST /report/conditional-formatting` - Generate conditional formatting for report data
- `POST /report/validate` - Validate report configuration
- `GET /report/templates` - Get available report templates
- `POST /report/templates/add` - Add custom report template
- `DELETE /report/templates/{template_name}` - Remove report template
- `GET /report/execution-history` - Get report execution history
- `GET /report/service-status` - Get service status
- `POST /report/clear-cache` - Clear report service cache

### Workflow Integration

- `GET /report/workflow/{workflow_id}/components` - Get workflow components
- `GET /report/workflow/{workflow_id}/status` - Get workflow status
- `POST /report/workflow/{workflow_id}/preview` - Preview workflow report

---

## Request/Response Examples

### Example 1: Comprehensive Report Generation

```mermaid
sequenceDiagram
    participant User
    participant API as Report API
    participant RS as Report Service
    participant RO as Report Orchestrator
    participant RW as Report Writing Agent
    participant DB as Database
    
    User->>API: POST /report/generate<br/>{queries, writer_actor, business_goal}
    API->>RS: generate_comprehensive_report()
    RS->>RO: Orchestrate Report
    
    par Query Processing
        RO->>DB: Execute SQL Queries
        DB-->>RO: Results
    end
    
    RO->>RW: Generate Report Content
    RW->>RW: Self-Correcting RAG Cycle
    RW-->>RO: High-Quality Content
    RO->>RO: Assemble Report
    RO-->>RS: Complete Report
    RS-->>API: ReportResponse
    API-->>User: Comprehensive Report
```

### Example 2: Workflow-Based Report

```mermaid
sequenceDiagram
    participant User
    participant API as Report API
    participant RS as Report Service
    participant WF as Workflow System
    participant RW as Report Writing Agent
    
    User->>API: POST /report/render-from-workflow<br/>{workflow_id, writer_actor}
    API->>RS: render_report_from_workflow_data()
    RS->>WF: Get Workflow Components
    WF-->>RS: Thread Components + Metadata
    
    RS->>RS: Extract Insights from Components
    RS->>RW: Generate Report
    RW->>RW: Self-Correcting RAG
    RW-->>RS: Report Content
    RS-->>API: Complete Report
    API-->>User: ReportResponse
```

---

## Notes

- **Business Impact**: Enables business users to generate publication-ready reports in minutes, eliminating hours of manual writing and formatting
- **AI-Powered Writing**: Leverages Self-Correcting RAG architecture for high-quality, contextually relevant content
- **Multiple Personas**: Supports different writing styles for different target audiences
- **Quality Assurance**: Iterative improvement ensures reports meet quality standards
- **Workflow Integration**: Automatically transforms question threads into comprehensive reports
- **Template System**: Pre-built templates for common report types
- **Customizable**: Supports custom templates and business goal alignment
- **Comprehensive Structure**: Includes executive summaries, detailed analysis, and actionable recommendations

---

*Last Updated: [Current Date]*
*Version: 1.0*

