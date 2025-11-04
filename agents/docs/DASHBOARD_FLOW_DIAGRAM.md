# Dashboard Service Flow Diagrams

This document provides comprehensive flowcharts explaining how the Dashboard Service works, enabling business users to create personalized, interactive dashboards in minutes.

## Purpose & Business Value

**Transform Data Queries into Personalized Dashboards Instantly**

The Dashboard Service enables business professionals to transform their SQL queries and natural language questions into fully functional, personalized dashboards for their BI tools. This capability delivers significant organizational value:

- **💰 Cost Savings**: Eliminates dependency on IT teams or dashboard developers for dashboard creation and customization
- **⚡ Speed to Value**: Business users can generate complete, production-ready dashboards in **minutes** instead of waiting days or weeks
- **🎯 Self-Service Dashboard Creation**: Non-technical users can create interactive dashboards with multiple charts, conditional formatting, and real-time updates
- **🔄 Workflow Integration**: Seamlessly integrates with existing workflows to automatically generate dashboards from question threads
- **📊 BI Tool Compatibility**: Generates dashboard configurations compatible with any business intelligence tool
- **🎨 Intelligent Layouts**: Automatically determines optimal dashboard layouts and chart arrangements based on data characteristics

## Table of Contents

1. [Dashboard Generation Flow](#dashboard-generation-flow)
2. [Workflow-Based Dashboard Generation](#workflow-based-dashboard-generation)
3. [Dashboard Components & Architecture](#dashboard-components--architecture)
4. [Conditional Formatting Flow](#conditional-formatting-flow)
5. [API Endpoints Reference](#api-endpoints-reference)

---

## Dashboard Generation Flow

The Dashboard Service processes SQL queries and natural language requests to generate comprehensive dashboard configurations with charts, layouts, and conditional formatting.

### High-Level Dashboard Generation Flow

```mermaid
flowchart TD
    A[Dashboard Request] --> B{Request Type}
    
    B -->|Standard| C[Process Dashboard Queries]
    B -->|Workflow| D[Extract Workflow Components]
    B -->|Execute Only| E[Execute Queries Only]
    
    C --> F[Validate Dashboard Queries]
    D --> G[Parse Thread Components]
    G --> F
    
    F --> H[Dashboard Agent Pipeline]
    H --> I[Execute SQL Queries]
    I --> J[Retrieve Query Results]
    J --> K[Chart Generation Agent]
    K --> L[Generate Chart Configurations]
    L --> M{Conditional Formatting?}
    
    M -->|Yes| N[Natural Language Processing]
    M -->|No| O[Assemble Dashboard]
    N --> P[Generate Conditional Formatting Rules]
    P --> O
    
    O --> Q[Apply Dashboard Template]
    Q --> R[Generate Layout Configuration]
    R --> S[Create Interactive Features]
    S --> T[Return Dashboard Configuration]
    
    E --> U[Execute Queries]
    U --> V[Return Raw Data]
    
    style H fill:#e1f5ff
    style K fill:#fff4e1
    style P fill:#e1ffe1
    style T fill:#ffe1e1
```

### Detailed Dashboard Pipeline

```mermaid
flowchart TD
    D1[Dashboard Service: Process Request] --> D2{Input Type}
    
    D2 -->|Dashboard Queries| D3[Parse Dashboard Queries]
    D2 -->|Workflow Data| D4[Extract Workflow Components]
    
    D3 --> D5[Validate Query Structure]
    D4 --> D6[Map Components to Queries]
    D6 --> D5
    
    D5 --> D7[Dashboard Agent Pipeline]
    
    subgraph "Dashboard Agent Processing"
        D7 --> D8[For Each Query]
        D8 --> D9[Execute SQL Query]
        D9 --> D10[Retrieve Results]
        D10 --> D11[Analyze Data Structure]
        D11 --> D12[Chart Generation Agent]
        D12 --> D13[Determine Chart Type]
        D13 --> D14[Generate Vega-Lite Spec]
        D14 --> D15[Create Chart Metadata]
        D15 --> D16[Apply Chart Config]
    end
    
    D16 --> D17{All Queries Processed?}
    D17 -->|No| D8
    D17 -->|Yes| D18[Conditional Formatting Agent]
    
    subgraph "Conditional Formatting"
        D18 --> D19{Natural Language Query?}
        D19 -->|Yes| D20[Parse Formatting Requirements]
        D20 --> D21[Generate Formatting Rules]
        D21 --> D22[Apply Color Schemes]
        D22 --> D23[Create Threshold Rules]
        D23 --> D24[Link Rules to Charts]
        D19 -->|No| D25[Use Default Formatting]
        D25 --> D24
    end
    
    D24 --> D26[Enhanced Dashboard Pipeline]
    
    subgraph "Dashboard Assembly"
        D26 --> D27[Select Dashboard Template]
        D27 --> D28[Generate Layout Grid]
        D28 --> D29[Arrange Charts]
        D29 --> D30[Add Interactive Features]
        D30 --> D31[Configure Refresh Settings]
        D31 --> D32[Apply Theme & Styling]
        D32 --> D33[Generate Export Options]
    end
    
    D33 --> D34[Return Complete Dashboard]
    
    style D7 fill:#e1f5ff
    style D12 fill:#fff4e1
    style D18 fill:#e1ffe1
    style D26 fill:#ffe1e1
```

---

## Workflow-Based Dashboard Generation

The Dashboard Service can automatically generate dashboards from workflow data, extracting components from question threads and assembling them into cohesive dashboard configurations.

### Workflow Dashboard Flow

```mermaid
flowchart TD
    W1[Workflow Dashboard Request] --> W2[Extract Workflow ID]
    W2 --> W3[Retrieve Workflow Data]
    W3 --> W4[Parse Thread Components]
    
    W4 --> W5[For Each Thread Component]
    W5 --> W6[Extract Component Data]
    
    subgraph "Component Processing"
        W6 --> W7{Component Type}
        W7 -->|Chart| W8[Use Chart Schema]
        W7 -->|Table| W9[Use Table Config]
        W7 -->|SQL Query| W10[Use SQL Query]
        W8 --> W11[Extract SQL & Metadata]
        W9 --> W11
        W10 --> W11
    end
    
    W11 --> W12[Map to Dashboard Query]
    W12 --> W13{More Components?}
    W13 -->|Yes| W5
    W13 -->|No| W14[Apply Workflow Metadata]
    
    W14 --> W15[Dashboard Template Selection]
    W15 --> W16[Generate Dashboard Context]
    W16 --> W17[Standard Dashboard Pipeline]
    W17 --> W18[Return Workflow Dashboard]
    
    style W4 fill:#e1f5ff
    style W17 fill:#fff4e1
```

### Workflow Integration Sequence

```mermaid
sequenceDiagram
    participant User
    participant API as Dashboard API
    participant DS as Dashboard Service
    participant WF as Workflow Integration
    participant DA as Dashboard Agent
    participant CG as Chart Generation Agent
    
    User->>API: POST /dashboard/render-from-workflow
    API->>DS: render_dashboard_from_workflow_data()
    DS->>WF: Get Workflow Components
    WF-->>DS: Thread Components + Metadata
    
    par Parallel Processing
        DS->>DA: Process Each Component
        DA->>DA: Execute SQL Queries
        DA->>CG: Generate Chart Configs
        CG-->>DA: Chart Specifications
    end
    
    DA-->>DS: Dashboard Queries
    DS->>DS: Apply Conditional Formatting
    DS->>DS: Generate Dashboard Layout
    DS->>DS: Assemble Complete Dashboard
    DS-->>API: Dashboard Configuration
    API-->>User: DashboardResponse
```

---

## Dashboard Components & Architecture

### Component Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        C1[Business Users]
        C2[BI Tools]
        C3[Workflow System]
    end
    
    subgraph "Dashboard Service Layer"
        DS1[Dashboard Service]
        DS2[Workflow Integration]
        DS3[Template Engine]
    end
    
    subgraph "Agent Layer"
        AG1[Dashboard Agent]
        AG2[Chart Generation Agent]
        AG3[Conditional Formatting Agent]
        AG4[Enhanced Dashboard Pipeline]
    end
    
    subgraph "Data Layer"
        DB[(Database)]
        WF[(Workflow Data)]
        CACHE[(Dashboard Templates)]
    end
    
    C1 --> DS1
    C2 --> DS1
    C3 --> DS2
    DS2 --> DS1
    
    DS1 --> AG1
    DS1 --> AG3
    DS1 --> DS3
    
    AG1 --> AG2
    AG1 --> AG4
    AG1 --> DB
    AG3 --> AG4
    
    DS3 --> CACHE
    DS2 --> WF
    
    style DS1 fill:#e1f5ff
    style AG1 fill:#fff4e1
    style AG4 fill:#e1ffe1
```

---

## Conditional Formatting Flow

The Conditional Formatting Agent processes natural language queries to automatically generate visual formatting rules for dashboard charts.

### Conditional Formatting Pipeline

```mermaid
flowchart TD
    CF1[Natural Language Query] --> CF2[Parse Formatting Intent]
    CF2 --> CF3[Extract Key Terms]
    
    CF3 --> CF4{Formatting Type}
    
    CF4 -->|Thresholds| CF5[Extract Threshold Values]
    CF4 -->|Colors| CF6[Extract Color Preferences]
    CF4 -->|Comparisons| CF7[Extract Comparison Logic]
    CF4 -->|Trends| CF8[Extract Trend Indicators]
    
    CF5 --> CF9[Generate Threshold Rules]
    CF6 --> CF10[Generate Color Rules]
    CF7 --> CF11[Generate Comparison Rules]
    CF8 --> CF12[Generate Trend Rules]
    
    CF9 --> CF13[Apply to Charts]
    CF10 --> CF13
    CF11 --> CF13
    CF12 --> CF13
    
    CF13 --> CF14[Validate Formatting Rules]
    CF14 --> CF15[Return Formatting Configuration]
    
    style CF2 fill:#e1f5ff
    style CF13 fill:#fff4e1
```

---

## Key Components Summary

### Dashboard Service Components

| Component | Purpose | Output |
|-----------|---------|--------|
| **Dashboard Service** | Orchestrates dashboard generation from queries or workflows | Complete dashboard configuration |
| **Dashboard Agent** | Processes queries and coordinates chart generation | Dashboard queries with chart schemas |
| **Chart Generation Agent** | Creates visualization configurations for each query | Vega-Lite chart specifications |
| **Conditional Formatting Agent** | Generates visual formatting rules from natural language | Conditional formatting rules |
| **Enhanced Dashboard Pipeline** | Assembles final dashboard with layout, styling, and features | Complete dashboard configuration |
| **Workflow Integration** | Extracts components from workflows for dashboard generation | Mapped dashboard queries from workflow |

### Dashboard Templates

| Template | Use Case | Layout |
|----------|----------|--------|
| **Operational Dashboard** | Real-time operational metrics | Grid layout with refresh |
| **Analytical Dashboard** | Deep-dive analysis | Multi-section layout |
| **Executive Dashboard** | High-level KPIs | Summary-focused layout |
| **Custom Dashboard** | User-defined structure | Flexible layout |

---

## API Endpoints Reference

### Dashboard Generation

- `POST /dashboard/generate` - Generate comprehensive dashboard with conditional formatting
- `POST /dashboard/generate-from-workflow` - Generate dashboard from workflow data
- `POST /dashboard/render-from-workflow` - Render dashboard from workflow request
- `POST /dashboard/execute-only` - Execute dashboard queries without formatting

### Dashboard Utilities

- `POST /dashboard/conditional-formatting` - Generate only conditional formatting
- `POST /dashboard/validate` - Validate dashboard configuration
- `GET /dashboard/templates` - Get available dashboard templates
- `GET /dashboard/execution-history` - Get dashboard execution history
- `GET /dashboard/service-status` - Get service status
- `POST /dashboard/clear-cache` - Clear dashboard service cache

### Workflow Integration

- `GET /dashboard/workflow/{workflow_id}/components` - Get workflow components
- `GET /dashboard/workflow/{workflow_id}/status` - Get workflow status
- `POST /dashboard/workflow/{workflow_id}/preview` - Preview workflow dashboard

---

## Request/Response Examples

### Example 1: Standard Dashboard Generation

```mermaid
sequenceDiagram
    participant User
    participant API as Dashboard API
    participant DS as Dashboard Service
    participant DA as Dashboard Agent
    participant DB as Database
    
    User->>API: POST /dashboard/generate<br/>{queries, project_id}
    API->>DS: process_dashboard_with_conditional_formatting()
    DS->>DA: Process Dashboard Queries
    
    loop For Each Query
        DA->>DB: Execute SQL
        DB-->>DA: Query Results
        DA->>DA: Generate Chart Config
    end
    
    DA-->>DS: Dashboard Queries with Charts
    DS->>DS: Apply Conditional Formatting
    DS->>DS: Generate Layout
    DS-->>API: Complete Dashboard Config
    API-->>User: DashboardResponse
```

### Example 2: Workflow-Based Dashboard

```mermaid
sequenceDiagram
    participant User
    participant API as Dashboard API
    participant DS as Dashboard Service
    participant WF as Workflow System
    participant DA as Dashboard Agent
    
    User->>API: POST /dashboard/render-from-workflow<br/>{workflow_id, project_id}
    API->>DS: render_dashboard_from_workflow_data()
    DS->>WF: Get Workflow Components
    WF-->>DS: Thread Components
    
    DS->>DS: Map Components to Queries
    DS->>DA: Process Dashboard
    DA-->>DS: Dashboard Configuration
    DS-->>API: Complete Dashboard
    API-->>User: DashboardResponse
```

---

## Notes

- **Business Impact**: Enables business users to generate production-ready dashboards in minutes, eliminating weeks of waiting for IT support
- **Self-Service Capability**: Non-technical users can create complex, multi-chart dashboards through natural language queries
- **Workflow Integration**: Automatically transforms question threads into cohesive dashboard configurations
- **Conditional Formatting**: Intelligent visual formatting based on natural language requirements
- **BI Tool Agnostic**: Generates configurations compatible with any business intelligence platform
- **Template System**: Pre-built templates for common dashboard types (operational, analytical, executive)
- **Real-time Updates**: Supports auto-refresh and real-time data updates
- **Export Options**: Built-in support for exporting dashboards to PDF, PNG, CSV formats

---

*Last Updated: [Current Date]*
*Version: 1.0*

