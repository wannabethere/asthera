# Alert Service Flow Diagrams

This document provides comprehensive flowcharts explaining how the SQL-to-Alert Service works, enabling business users to create intelligent alerts and monitoring configurations from SQL queries in minutes.

## Purpose & Business Value

**Transform SQL Queries into Intelligent Monitoring Alerts Instantly**

The Alert Service enables business professionals to convert their SQL queries and natural language alert requests into production-ready alert configurations for monitoring systems. This capability delivers significant organizational value:

- **💰 Cost Savings**: Eliminates dependency on DevOps or data engineering teams for alert setup and configuration
- **⚡ Speed to Value**: Business users can create sophisticated alert configurations in **minutes** instead of waiting days for engineering support
- **🔔 Intelligent Alert Generation**: Uses Self-RAG architecture to automatically determine optimal alert conditions and thresholds
- **📊 Pattern Detection**: Recognizes common alert patterns (training completion, anomaly detection, thresholds) and applies specialized configurations
- **🎯 Business Context Aware**: Understands business requirements and generates alerts aligned with operational needs
- **🔄 Feed Integration**: Directly integrates with monitoring systems (Tellius Feed) for immediate deployment
- **✅ Validation & Preview**: Built-in validation and preview capabilities ensure alerts work correctly before deployment

## Table of Contents

1. [Alert Generation Flow](#alert-generation-flow)
2. [Self-RAG Alert Pipeline](#self-rag-alert-pipeline)
3. [Pattern Detection & Specialization](#pattern-detection--specialization)
4. [Alert Validation & Preview](#alert-validation--preview)
5. [Alert Components & Architecture](#alert-components--architecture)
6. [API Endpoints Reference](#api-endpoints-reference)

---

## Alert Generation Flow

The Alert Service processes SQL queries and natural language alert requests to generate comprehensive alert configurations for monitoring systems.

### High-Level Alert Generation Flow

```mermaid
flowchart TD
    A[Alert Request] --> B[SQL Analysis]
    B --> C[Extract Metrics & Dimensions]
    C --> D[Natural Language Processing]
    D --> E[Self-RAG Pipeline]
    
    E --> F[Retrieval Phase]
    F --> G[Generate Initial Alert Config]
    G --> H[Critique & Evaluation]
    H --> I{Quality Acceptable?}
    
    I -->|No| J[Refine Alert Config]
    J --> G
    I -->|Yes| K[Pattern Detection]
    
    K --> L{Pattern Match?}
    L -->|Yes| M[Apply Specialized Handler]
    L -->|No| N[Standard Alert Config]
    
    M --> O[Generate Feed Configuration]
    N --> O
    
    O --> P[Create API Payload]
    P --> Q[Validate Configuration]
    Q --> R{Valid?}
    
    R -->|No| S[Fix Issues]
    S --> O
    R -->|Yes| T[Return Alert Configuration]
    
    style E fill:#e1f5ff
    style K fill:#fff4e1
    style O fill:#e1ffe1
    style T fill:#ffe1e1
```

### Detailed Alert Pipeline

```mermaid
flowchart TD
    AL1[SQL-to-Alert Agent] --> AL2[SQL Analysis]
    
    subgraph "SQL Analysis Phase"
        AL2 --> AL3[Parse SQL Structure]
        AL3 --> AL4[Extract Metrics]
        AL4 --> AL5[Extract Dimensions]
        AL5 --> AL6[Identify Time Dimensions]
        AL6 --> AL7[Determine Data Patterns]
    end
    
    AL7 --> AL8[Self-RAG Pipeline]
    
    subgraph "Self-RAG: Retrieval Phase"
        AL8 --> AL9[Analyze Alert Request]
        AL9 --> AL10[Retrieve Domain Knowledge]
        AL10 --> AL11[Match Alert Patterns]
        AL11 --> AL12[Assemble Context]
    end
    
    AL12 --> AL13[Self-RAG: Generation Phase]
    
    subgraph "Self-RAG: Generation Phase"
        AL13 --> AL14[Generate Initial Feed Config]
        AL14 --> AL15[Determine Alert Conditions]
        AL15 --> AL16[Select Condition Type]
        AL16 --> AL17[Configure Thresholds]
        AL17 --> AL18[Set Drilldown Dimensions]
        AL18 --> AL19[Configure Schedule]
    end
    
    AL19 --> AL20[Self-RAG: Critique Phase]
    
    subgraph "Self-RAG: Critique Phase"
        AL20 --> AL21[Evaluate Configuration]
        AL21 --> AL22[Check Metric Alignment]
        AL22 --> AL23[Validate Conditions]
        AL23 --> AL24[Assess Completeness]
        AL24 --> AL25{Quality Acceptable?}
    end
    
    AL25 -->|No| AL26[Self-RAG: Refine Phase]
    AL25 -->|Yes| AL27[Pattern Detection]
    
    subgraph "Self-RAG: Refine Phase"
        AL26 --> AL28[Identify Issues]
        AL28 --> AL29[Generate Improvements]
        AL29 --> AL13
    end
    
    AL27 --> AL30{Pattern Match?}
    
    subgraph "Pattern Specialization"
        AL30 -->|Training Completion| AL31[Apply Training Handler]
        AL30 -->|Percentage Anomaly| AL32[Apply Anomaly Handler]
        AL30 -->|Operational Threshold| AL33[Apply Threshold Handler]
        AL30 -->|Trend Analysis| AL34[Apply Trend Handler]
        AL30 -->|No Match| AL35[Standard Configuration]
    end
    
    AL31 --> AL36[Generate Feed Configuration]
    AL32 --> AL36
    AL33 --> AL36
    AL34 --> AL36
    AL35 --> AL36
    
    AL36 --> AL37[Create API Payload]
    AL37 --> AL38[Return Alert Configuration]
    
    style AL8 fill:#e1f5ff
    style AL13 fill:#fff4e1
    style AL20 fill:#e1ffe1
    style AL27 fill:#ffe1e1
```

---

## Self-RAG Alert Pipeline

The Alert Service uses a Self-Reflective RAG (Self-RAG) architecture that retrieves, generates, critiques, and refines alert configurations iteratively.

### Self-RAG Flow Diagram

```mermaid
flowchart TD
    SR1[Self-RAG Alert Pipeline] --> SR2[RETRIEVE]
    
    subgraph "RETRIEVE Phase"
        SR2 --> SR3[SQL Analysis Results]
        SR3 --> SR4[Domain Knowledge Base]
        SR4 --> SR5[Alert Pattern Examples]
        SR5 --> SR6[Best Practices]
        SR6 --> SR7[Assemble Context]
    end
    
    SR7 --> SR8[GENERATE]
    
    subgraph "GENERATE Phase"
        SR8 --> SR9[Initial Feed Configuration]
        SR9 --> SR10[Metric Configuration]
        SR10 --> SR11[Condition Selection]
        SR11 --> SR12[Threshold Configuration]
        SR12 --> SR13[Drilldown Setup]
        SR13 --> SR14[Schedule Configuration]
    end
    
    SR14 --> SR15[CRITIQUE]
    
    subgraph "CRITIQUE Phase"
        SR15 --> SR16[Validate Metric Selection]
        SR16 --> SR17[Check Condition Appropriateness]
        SR17 --> SR18[Verify Threshold Logic]
        SR18 --> SR19[Assess Completeness]
        SR19 --> SR20[Quality Evaluation]
        SR20 --> SR21{Quality Score}
    end
    
    SR21 -->|Low| SR22[REFINE]
    SR21 -->|High| SR23[Final Configuration]
    
    subgraph "REFINE Phase"
        SR22 --> SR24[Identify Weaknesses]
        SR24 --> SR25[Generate Improvements]
        SR25 --> SR8
    end
    
    SR23 --> SR26[Pattern Application]
    SR26 --> SR27[Feed Integration Ready]
    
    style SR2 fill:#e1f5ff
    style SR8 fill:#fff4e1
    style SR15 fill:#e1ffe1
    style SR22 fill:#ffe1e1
```

---

## Pattern Detection & Specialization

The Alert Service automatically detects common alert patterns and applies specialized handlers for optimal configuration.

### Pattern Detection Flow

```mermaid
flowchart TD
    PD1[Alert Configuration] --> PD2[Pattern Analysis]
    
    PD2 --> PD3{Pattern Detection}
    
    PD3 -->|Training Keywords| PD4[Training Completion Pattern]
    PD3 -->|Percentage Metrics| PD5[Percentage Anomaly Pattern]
    PD3 -->|Threshold Terms| PD6[Operational Threshold Pattern]
    PD3 -->|Trend Terms| PD7[Trend Analysis Pattern]
    PD3 -->|No Match| PD8[Standard Pattern]
    
    PD4 --> PD9[Apply Training Handler]
    PD5 --> PD10[Apply Anomaly Handler]
    PD6 --> PD11[Apply Threshold Handler]
    PD7 --> PD12[Apply Trend Handler]
    PD8 --> PD13[Apply Standard Handler]
    
    subgraph "Specialized Handlers"
        PD9 --> PD14[Configure Completion Thresholds]
        PD14 --> PD15[Set Expiry Alerts]
        PD15 --> PD16[Add Assignment Backlog]
        
        PD10 --> PD17[Configure ARIMA Detection]
        PD17 --> PD18[Set Seasonal Patterns]
        PD18 --> PD19[Add Variance Thresholds]
        
        PD11 --> PD20[Configure Value Thresholds]
        PD20 --> PD21[Set Change Alerts]
        PD21 --> PD22[Add Schedule with Refresh]
        
        PD12 --> PD23[Configure Percent Change]
        PD12 --> PD24[Set Trend Direction]
        PD24 --> PD25[Add Custom Schedule]
    end
    
    PD16 --> PD26[Enhanced Configuration]
    PD19 --> PD26
    PD22 --> PD26
    PD25 --> PD26
    PD13 --> PD26
    
    PD26 --> PD27[Return Specialized Alert]
    
    style PD2 fill:#e1f5ff
    style PD9 fill:#fff4e1
    style PD10 fill:#fff4e1
    style PD11 fill:#fff4e1
    style PD12 fill:#fff4e1
```

### Common Alert Patterns

| Pattern | Description | Typical Metrics | Condition Types |
|---------|-------------|----------------|-----------------|
| **Training Completion** | Alerts for training completion rates, backlogs, expiry | completion_percentage, assigned_count, expired_percentage | threshold_value, threshold_percent_change |
| **Percentage Anomaly** | Anomaly detection for percentage-based metrics | conversion_rate, completion_rate, satisfaction_score | intelligent_arima |
| **Operational Threshold** | Simple threshold alerts for operational metrics | count, sum, average | threshold_value, threshold_change |
| **Trend Analysis** | Trend-based alerts for strategic metrics | revenue, user_growth, performance_score | threshold_percent_change, intelligent_arima |

---

## Alert Validation & Preview

The Alert Service provides validation and preview capabilities to ensure alerts work correctly before deployment.

### Validation Flow

```mermaid
flowchart TD
    V1[Alert Validation Request] --> V2[SQL Analysis]
    V2 --> V3[Extract Available Metrics]
    V3 --> V4[Extract Available Dimensions]
    
    V4 --> V5[Validate Proposed Alert]
    
    subgraph "Validation Checks"
        V5 --> V6[Metric Availability Check]
        V6 --> V7[Dimension Compatibility Check]
        V7 --> V8[Condition Appropriateness Check]
        V8 --> V9[Threshold Logic Check]
        V9 --> V10[Feed Compatibility Check]
    end
    
    V10 --> V11{All Checks Pass?}
    V11 -->|No| V12[Generate Issues List]
    V11 -->|Yes| V13[Calculate Validation Score]
    
    V12 --> V14[Generate Suggestions]
    V14 --> V15[Return Validation Result]
    
    V13 --> V16[Return Valid Configuration]
    
    style V5 fill:#e1f5ff
    style V11 fill:#fff4e1
```

### Preview Flow

```mermaid
flowchart TD
    PR1[Alert Preview Request] --> PR2[Load Alert Configuration]
    PR2 --> PR3[Simulate with Historical Data]
    
    PR3 --> PR4[Execute SQL with Sample Data]
    PR4 --> PR5[Apply Alert Conditions]
    PR5 --> PR6[Simulate Trigger Events]
    
    PR6 --> PR7[Generate Preview Results]
    
    subgraph "Preview Analysis"
        PR7 --> PR8[Would Trigger?]
        PR8 --> PR9[Trigger Frequency]
        PR9 --> PR10[Sample Alert Events]
        PR10 --> PR11[Metric Trends]
        PR11 --> PR12[Recommendations]
    end
    
    PR12 --> PR13[Return Preview Response]
    
    style PR3 fill:#e1f5ff
    style PR7 fill:#fff4e1
```

---

## Alert Components & Architecture

### Component Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        C1[Business Users]
        C2[Monitoring Systems]
        C3[Feed API]
    end
    
    subgraph "Alert Service Layer"
        AS1[SQL-to-Alert Agent]
        AS2[Self-RAG Pipeline]
        AS3[Pattern Detector]
        AS4[Validation Engine]
    end
    
    subgraph "Handler Layer"
        H1[Training Completion Handler]
        H2[Anomaly Detection Handler]
        H3[Threshold Handler]
        H4[Trend Handler]
        H5[Standard Handler]
    end
    
    subgraph "Data Layer"
        DB[(Database)]
        KB[(Knowledge Base)]
        PATTERNS[(Pattern Library)]
    end
    
    C1 --> AS1
    C2 --> AS1
    C3 --> AS1
    
    AS1 --> AS2
    AS1 --> AS3
    AS1 --> AS4
    
    AS2 --> KB
    AS3 --> PATTERNS
    
    AS3 --> H1
    AS3 --> H2
    AS3 --> H3
    AS3 --> H4
    AS3 --> H5
    
    AS1 --> DB
    
    style AS1 fill:#e1f5ff
    style AS2 fill:#fff4e1
    style AS3 fill:#e1ffe1
```

---

## Key Components Summary

### Alert Service Components

| Component | Purpose | Output |
|-----------|---------|--------|
| **SQL-to-Alert Agent** | Main agent that converts SQL to alert configurations | Complete Feed alert configuration |
| **SQL Analyzer** | Analyzes SQL queries to extract metrics and dimensions | SQL analysis with metrics and dimensions |
| **Self-RAG Pipeline** | Self-reflective pipeline for generating and refining alerts | High-quality alert configurations |
| **Pattern Detector** | Detects common alert patterns and applies specialized handlers | Pattern-matched alert configuration |
| **Feed Configuration Generator** | Creates Tellius Feed-compatible configurations | Feed configuration JSON |
| **Validation Engine** | Validates alert configurations before deployment | Validation results with suggestions |
| **Preview Simulator** | Simulates alert behavior with historical data | Preview results and recommendations |

### Alert Condition Types

| Condition Type | Description | Use Cases |
|----------------|-------------|-----------|
| **intelligent_arima** | Automatic time-series anomaly detection using ARIMA | Seasonal data, trend detection, pattern anomalies |
| **threshold_value** | Simple value-based threshold alerts | SLA monitoring, capacity limits, business rules |
| **threshold_change** | Absolute change from previous period | Growth tracking, decline detection |
| **threshold_percent_change** | Percentage change from previous period | Relative performance, percentage tracking |

---

## API Endpoints Reference

### Alert Generation

- `POST /api/sql-alerts/generate` - Generate Feed alert configuration from SQL and natural language
- `POST /api/sql-alerts/batch` - Generate multiple alerts in batch with parallel processing

### Alert Specialization

- `POST /api/sql-alerts/training-completion` - Specialized endpoint for training completion alerts
- `POST /api/sql-alerts/percentage-anomaly` - Specialized endpoint for percentage-based anomaly detection

### Alert Utilities

- `POST /api/sql-alerts/validate` - Validate alert configuration
- `POST /api/sql-alerts/preview` - Preview alert behavior with historical data
- `POST /api/sql-alerts/feed-integration` - Directly integrate with Feed API
- `GET /api/sql-alerts/patterns` - Get supported alert patterns
- `GET /api/sql-alerts/feed-conditions` - Get available Feed condition types
- `DELETE /api/sql-alerts/sessions/{session_id}` - Clear alert generation session

---

## Request/Response Examples

### Example 1: Standard Alert Generation

```mermaid
sequenceDiagram
    participant User
    participant API as Alert API
    participant Agent as SQL-to-Alert Agent
    participant SRAG as Self-RAG Pipeline
    participant PD as Pattern Detector
    
    User->>API: POST /api/sql-alerts/generate<br/>{sql, alert_request}
    API->>Agent: generate_alert()
    Agent->>Agent: Analyze SQL
    
    Agent->>SRAG: Generate Alert Config
    SRAG->>SRAG: RETRIEVE Phase
    SRAG->>SRAG: GENERATE Phase
    SRAG->>SRAG: CRITIQUE Phase
    SRAG->>SRAG: REFINE if needed
    SRAG-->>Agent: High-Quality Config
    
    Agent->>PD: Detect Patterns
    PD-->>Agent: Pattern Match
    Agent->>Agent: Apply Specialized Handler
    Agent->>Agent: Generate Feed Config
    Agent-->>API: Alert Configuration
    API-->>User: SQLAlertAPIResponse
```

### Example 2: Training Completion Alert

```mermaid
sequenceDiagram
    participant User
    participant API as Alert API
    participant Agent as SQL-to-Alert Agent
    participant TH as Training Handler
    
    User->>API: POST /api/sql-alerts/training-completion<br/>{sql, completion_threshold}
    API->>Agent: generate_alert()
    Agent->>Agent: Analyze SQL
    Agent->>TH: Apply Training Pattern
    TH->>TH: Configure Completion Thresholds
    TH->>TH: Set Expiry Alerts
    TH-->>Agent: Specialized Config
    Agent-->>API: Training Completion Alert
    API-->>User: Alert Configuration
```

---

## Notes

- **Business Impact**: Enables business users to create sophisticated alert configurations in minutes, eliminating days of waiting for DevOps support
- **Self-RAG Architecture**: Uses self-reflective RAG for iterative improvement of alert configurations
- **Pattern Recognition**: Automatically detects common patterns and applies specialized configurations
- **Validation & Preview**: Built-in validation and preview capabilities ensure alerts work correctly
- **Feed Integration**: Direct integration with Tellius Feed for immediate deployment
- **Batch Processing**: Supports parallel processing for generating multiple alerts
- **Session Management**: Maintains context across multiple requests for iterative refinement
- **Pattern Library**: Extensive library of common alert patterns for various business scenarios

---

*Last Updated: [Current Date]*
*Version: 1.0*

