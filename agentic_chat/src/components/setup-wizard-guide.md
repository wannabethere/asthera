# Builder Setup Wizard - Complete Guide

## Overview

The **Builder Setup Wizard** is a 4-step configuration flow that users complete before accessing the main Feature Builder or Case Study Builder interface. It ensures users have properly configured their goal, data source, tables, and AI assistants before starting their work.

---

## User Flow

```
┌─────────────────────────────────────────────────────────────┐
│ User clicks [Transform] button                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Set Goal                                            │
│ • User describes what they want to achieve                  │
│ • Examples provided for guidance                            │
│ • Goal saved                                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Select Data Source                                  │
│ • Show connected data sources (Snowflake, PostgreSQL, etc.) │
│ • User selects one data source                              │
│ • Display connection status and table count                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Select Tables                                       │
│ • AI filters tables by relevance to goal                    │
│ • Show relevance score (95%, 88%, etc.)                     │
│ • User selects 1+ relevant tables                           │
│ • Search and filter capabilities                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Select AI Assistants                                │
│ • Show available assistants with capabilities               │
│ • Mark recommended assistants                               │
│ • User selects 1+ assistants                                │
│ • Explain how multiple assistants collaborate               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ [Launch Builder] button clicked                             │
│ → Transitions to Feature Builder or Case Study Builder     │
└─────────────────────────────────────────────────────────────┘
```

---

## 4-Step Wizard Design

### Visual Layout

```
┌──────────────────────────────────────────────────────────────┐
│ 🎯 Feature Builder Setup                                     │
│ Let's configure your builder in a few simple steps           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ Progress Indicator:                                          │
│                                                               │
│  [✓]────────[●]────────[ ]────────[ ]                       │
│ Set Goal  Data Source  Tables   Assistants                   │
│ ✓Complete  Current    Pending    Pending                     │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ [Step Content Area]                                          │
│                                                               │
│ Step-specific UI with:                                       │
│ • Icon and title                                             │
│ • Description                                                │
│ • Interactive selection interface                            │
│ • Tips and examples                                          │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ [← Back]           Step 2 of 4         [Continue →]         │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Step 1: Set Goal

### Purpose
Capture what the user wants to achieve with the builder.

### Visual Design
```
┌──────────────────────────────────────────────────────────┐
│              [🎯 Icon in gradient circle]                 │
│                                                           │
│                  What's your goal?                        │
│        Tell us what you want to achieve                   │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Describe your goal                                  │ │
│ │ ┌─────────────────────────────────────────────────┐ │ │
│ │ │ e.g., Build compliance features with risk       │ │ │
│ │ │ scoring for SOC2 audit readiness                │ │ │
│ │ │                                                  │ │ │
│ │ │                                                  │ │ │
│ │ └─────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 💡 Tips for writing a good goal:                    │ │
│ │ • Be specific about what you want to achieve        │ │
│ │ • Mention frameworks (SOC2, FAIR)                   │ │
│ │ • Include target audience if applicable             │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ [Example 1: Feature Engineering]  [Example 2: Case Study]│
└──────────────────────────────────────────────────────────┘
```

### Features
- Multi-line text input (4 rows)
- Placeholder with example
- Tips box with best practices
- Example cards for inspiration
- Character validation (must be non-empty)

### Validation
- Goal must be non-empty (trimmed)
- Minimum 10 characters recommended
- Continue button disabled until valid

---

## Step 2: Select Data Source

### Purpose
Choose which connected data source contains the relevant data.

### Visual Design
```
┌──────────────────────────────────────────────────────────┐
│              [💾 Database icon in gradient]               │
│                                                           │
│               Select Data Source                          │
│          Choose where your data is stored                 │
│                                                           │
│ ┌──────────────────────┐  ┌──────────────────────┐      │
│ │ ❄️ Snowflake    [✓]│  │ 🐘 PostgreSQL      │      │
│ │ Data Warehouse       │  │ Database            │      │
│ │ 🟢 Connected         │  │ 🟢 Connected        │      │
│ │ 45 tables            │  │ 23 tables           │      │
│ └──────────────────────┘  └──────────────────────┘      │
│                                                           │
│ ┌──────────────────────┐  ┌──────────────────────┐      │
│ │ 📊 BigQuery         │  │ ☁️ AWS S3           │      │
│ │ Data Warehouse       │  │ Object Storage      │      │
│ │ 🟢 Connected         │  │ 🟢 Connected        │      │
│ │ 67 tables            │  │ 12 tables           │      │
│ └──────────────────────┘  └──────────────────────┘      │
│                                                           │
│ ⚙️ Need to connect a new data source?                   │
│    Visit Settings → Data Sources                         │
└──────────────────────────────────────────────────────────┘
```

### Features
- Grid layout of data source cards
- Visual indicators (emoji icons)
- Connection status (green dot)
- Table count
- Single selection (radio behavior)
- Selected state: blue border, blue background, checkmark
- Link to settings for new connections

### Data Source Cards
```javascript
{
  id: 'snowflake',
  name: 'Snowflake',
  type: 'Data Warehouse',
  icon: '❄️',
  status: 'connected',
  tables: 45
}
```

### Validation
- Must select exactly one data source
- Continue button disabled until selected

---

## Step 3: Select Tables

### Purpose
Choose which tables from the selected data source are relevant to the goal.

### Visual Design
```
┌──────────────────────────────────────────────────────────┐
│              [📋 Table icon in gradient]                  │
│                                                           │
│                  Select Tables                            │
│         Choose tables relevant to your goal               │
│                                                           │
│ [🔍 Search tables...]                    [Filter ▼]      │
│                                                           │
│ 3 tables selected                       [Select all]     │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ compliance_controls                     [95% ✓]     │ │
│ │ Compliance control definitions with status...       │ │
│ │ 1,247 rows • 23 columns                             │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ risk_assessments                        [92% ✓]     │ │
│ │ Risk assessment results and scores                  │ │
│ │ 892 rows • 15 columns                               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ audit_findings                          [88% ✓]     │ │
│ │ Audit findings and remediation tracking             │ │
│ │ 456 rows • 18 columns                               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ 💡 Relevance Score: Tables are ranked by relevance to   │
│    your goal using AI analysis                           │
└──────────────────────────────────────────────────────────┘
```

### Features
- **Search bar**: Filter tables by name or description
- **Filter button**: Additional filtering options
- **Selection counter**: Shows "X tables selected"
- **Select all** button
- **Relevance badges**: Color-coded (green ≥90%, yellow ≥75%, gray <75%)
- **Multi-select**: Checkboxes with toggle behavior
- **Table metadata**: Row count, column count
- **Smart sorting**: By relevance score (highest first)

### Table Card Structure
```javascript
{
  id: 'compliance_controls',
  name: 'compliance_controls',
  rows: 1247,
  columns: 23,
  relevance: 95,  // AI-calculated relevance to goal
  description: 'Compliance control definitions...'
}
```

### Relevance Calculation
The AI analyzes:
1. **Goal keywords** vs. **table name**
2. **Goal keywords** vs. **column names**
3. **Goal keywords** vs. **table description**
4. **Historical usage patterns** for similar goals
5. **Data patterns** (e.g., audit columns for compliance goals)

### Validation
- Must select at least 1 table
- Continue button disabled until at least 1 selected

---

## Step 4: Select AI Assistants

### Purpose
Choose which AI assistants will help build the solution.

### Visual Design
```
┌──────────────────────────────────────────────────────────┐
│              [👥 Users icon in gradient]                  │
│                                                           │
│              Select AI Assistants                         │
│      Choose assistants that will help you build           │
│                                                           │
│ 2 assistants selected              [Select recommended]  │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [🛡️]  Compliance Expert           [Recommended] [✓]│ │
│ │                                                     │ │
│ │ Specializes in regulatory compliance, SOC2,         │ │
│ │ ISO27001, and audit readiness                       │ │
│ │                                                     │ │
│ │ [Framework alignment] [Control mapping] [Gap...]   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [📈]  Risk Analyst                 [Recommended] [✓]│ │
│ │                                                     │ │
│ │ Expert in risk quantification using FAIR            │ │
│ │ methodology and CVaR analysis                       │ │
│ │                                                     │ │
│ │ [Risk scoring] [Likelihood×Impact] [Monte Carlo]   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [💾]  Data Engineer                              [ ]│ │
│ │                                                     │ │
│ │ Builds optimized data pipelines and feature         │ │
│ │ transformations                                      │ │
│ │                                                     │ │
│ │ [Pipeline design] [SQL optimization] [Quality...]  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                           │
│ ⚡ Multiple assistants work together based on their      │
│    specialized expertise                                 │
└──────────────────────────────────────────────────────────┘
```

### Features
- **Multi-select cards** with checkboxes
- **Recommended badge** on suggested assistants
- **Select recommended** quick action
- **Color-coded icons** (blue, red, purple, green)
- **Capability tags** showing expertise areas
- **Detailed descriptions** of each assistant
- **Collaborative explanation** about how assistants work together

### Assistant Structure
```javascript
{
  id: 'compliance-expert',
  name: 'Compliance Expert',
  icon: Shield,
  color: 'blue',
  description: 'Specializes in regulatory compliance...',
  capabilities: [
    'Framework alignment',
    'Control mapping',
    'Gap analysis'
  ],
  recommended: true
}
```

### Recommendation Logic
Assistants are recommended based on:
1. **Goal analysis**: Keywords in goal (e.g., "SOC2" → Compliance Expert)
2. **Selected tables**: Table schemas (e.g., risk columns → Risk Analyst)
3. **Historical patterns**: What worked for similar goals
4. **Use case**: Feature Builder vs. Case Study Builder

### Validation
- Must select at least 1 assistant
- Continue button disabled until at least 1 selected

---

## Progress Indicator

### Visual Design
```
Step 1          Step 2          Step 3          Step 4
[✓]────────────[●]────────────[ ]────────────[ ]
Set Goal     Data Source    Tables      Assistants
✓ Complete    Current       Pending      Pending
```

### States

1. **Completed**: Green circle with checkmark, green text
2. **Current**: Blue circle with pulsing animation, blue text, bold
3. **Pending**: Gray circle, gray text

### Progress Line
- Green line between completed steps
- Gray line before current step

---

## Navigation

### Bottom Navigation Bar

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│ [← Back]           Step 2 of 4           [Continue →]    │
│  (gray)                                   (blue gradient)│
└──────────────────────────────────────────────────────────┘
```

### Button States

**Back Button:**
- Disabled (Step 1): Gray background, gray text, cursor not-allowed
- Enabled: White background, gray text, border, hover effect

**Continue Button:**
- Disabled: Gray background, gray text, cursor not-allowed
- Enabled: Blue-purple gradient, white text, shadow, hover effect
- Step 4 text: "Launch Builder" with Play icon

### Validation Logic

```javascript
const canProceed = () => {
  switch (currentStep) {
    case 1: return goal.trim() !== '';
    case 2: return selectedDataSource !== null;
    case 3: return selectedTables.length > 0;
    case 4: return selectedAssistants.length > 0;
    default: return false;
  }
};
```

---

## State Management

```javascript
const [currentStep, setCurrentStep] = useState(1);
const [builderType, setBuilderType] = useState('feature'); // or 'case-study'

// Form state
const [goal, setGoal] = useState('');
const [selectedDataSource, setSelectedDataSource] = useState(null);
const [selectedTables, setSelectedTables] = useState([]);
const [selectedAssistants, setSelectedAssistants] = useState([]);
const [searchTables, setSearchTables] = useState('');
```

---

## Final Configuration Object

When user clicks "Launch Builder", pass this configuration:

```javascript
const configuration = {
  builderType: 'feature', // or 'case-study'
  goal: 'Build compliance features with risk scoring...',
  dataSource: {
    id: 'snowflake',
    name: 'Snowflake',
    type: 'Data Warehouse'
  },
  tables: [
    {
      id: 'compliance_controls',
      name: 'compliance_controls',
      rows: 1247,
      columns: 23,
      relevance: 95
    },
    {
      id: 'risk_assessments',
      name: 'risk_assessments',
      rows: 892,
      columns: 15,
      relevance: 92
    }
  ],
  assistants: [
    {
      id: 'compliance-expert',
      name: 'Compliance Expert',
      capabilities: ['Framework alignment', 'Control mapping', 'Gap analysis']
    },
    {
      id: 'risk-analyst',
      name: 'Risk Analyst',
      capabilities: ['Risk scoring', 'Likelihood × Impact', 'Monte Carlo']
    }
  ]
};
```

---

## Transition to Main Builder

### Animation Sequence

```
1. User clicks "Launch Builder"
2. Button shows loading state (spinner)
3. Configuration is saved
4. Fade out wizard
5. Show loading animation (1-2 seconds)
   "Setting up your workspace..."
   "Loading data sources..."
   "Initializing AI assistants..."
6. Fade in main builder interface
7. First message from AI in chat:
   "Hi! I've configured your workspace based on your goal..."
```

### Initial Chat Message

The first message in the builder should reference the setup:

```
🎯 Hi! I've configured your workspace for:
"Build compliance features with risk scoring for SOC2 audit readiness"

📊 Data Source: Snowflake
📋 Tables Loaded:
  • compliance_controls (1,247 rows)
  • risk_assessments (892 rows)

🤖 AI Assistants Ready:
  • Compliance Expert
  • Risk Analyst

I can help you:
• Build compliance story features
• Add risk scoring features  
• Create custom transformations

What would you like to do first?
```

---

## Design System

### Colors

**Step Icons:**
- Step 1 (Goal): Blue → Purple gradient
- Step 2 (Data Source): Purple → Pink gradient
- Step 3 (Tables): Green → Teal gradient
- Step 4 (Assistants): Orange → Red gradient

**Selection States:**
- Selected: Blue border (border-blue-500), Blue background (bg-blue-50)
- Hover: Blue border on hover (hover:border-blue-300)
- Default: Gray border (border-gray-200)

**Progress Indicator:**
- Completed: Green (bg-green-500, text-green-600)
- Current: Blue (bg-blue-500, text-blue-600)
- Pending: Gray (bg-gray-200, text-gray-400)

### Typography

- **Page Title**: text-3xl font-bold
- **Step Title**: text-2xl font-bold
- **Card Title**: text-base font-semibold
- **Description**: text-sm text-gray-600
- **Body Text**: text-sm

### Spacing

- Page padding: px-6 py-8
- Card padding: p-4 to p-8
- Gap between cards: gap-4
- Section margins: mb-6 to mb-8

---

## Responsive Design

### Desktop (>1024px)
- Full 4-step progress indicator with descriptions
- 2-column grid for data sources and assistants
- Full-width search and filters

### Tablet (768px - 1024px)
- 4-step progress indicator without descriptions
- 2-column grid maintained
- Slightly reduced padding

### Mobile (<768px)
- Simplified progress (1 of 4, 2 of 4, etc.)
- Single column for all cards
- Stacked navigation buttons
- Reduced padding

---

## Accessibility

### Keyboard Navigation
- Tab through all interactive elements
- Enter/Space to select cards
- Arrow keys in progress indicator
- Escape to go back

### Screen Readers
- Proper ARIA labels on all interactive elements
- Progress indicator announces step completion
- Selection state announced
- Validation errors announced

### Visual Indicators
- Color is not the only indicator (icons, text, borders)
- High contrast mode support
- Focus indicators on all interactive elements

---

## Error Handling

### Validation Errors

```javascript
const validationErrors = {
  goal: goal.trim() === '' ? 'Please describe your goal' : null,
  dataSource: !selectedDataSource ? 'Please select a data source' : null,
  tables: selectedTables.length === 0 ? 'Please select at least one table' : null,
  assistants: selectedAssistants.length === 0 ? 'Please select at least one assistant' : null
};
```

### Network Errors

If data sources or tables fail to load:
```
┌──────────────────────────────────────────────────────────┐
│ ⚠️ Unable to load data sources                           │
│                                                           │
│ Please check your connection and try again.               │
│                                                           │
│ [Retry]                                                   │
└──────────────────────────────────────────────────────────┘
```

---

## Analytics Events

```javascript
// Wizard started
analytics.track('wizard_started', {
  builder_type: 'feature',
  timestamp: Date.now()
});

// Step completed
analytics.track('wizard_step_completed', {
  step: 1,
  step_name: 'set_goal',
  goal_length: goal.length,
  time_spent_seconds: 45
});

// Data source selected
analytics.track('data_source_selected', {
  source_id: 'snowflake',
  source_type: 'Data Warehouse',
  available_tables: 45
});

// Tables selected
analytics.track('tables_selected', {
  table_count: 3,
  avg_relevance: 91.7,
  total_rows: 2595
});

// Assistants selected
analytics.track('assistants_selected', {
  assistant_ids: ['compliance-expert', 'risk-analyst'],
  recommended_count: 2,
  custom_count: 0
});

// Wizard completed
analytics.track('wizard_completed', {
  builder_type: 'feature',
  total_time_seconds: 180,
  data_source: 'snowflake',
  table_count: 3,
  assistant_count: 2
});
```

---

## Best Practices

### DO:
✅ Show progress clearly at each step
✅ Provide examples and guidance
✅ Enable quick selection (Select All, Select Recommended)
✅ Show relevance scores for AI-filtered content
✅ Allow back navigation to change selections
✅ Save state if user navigates away
✅ Validate each step before proceeding
✅ Provide contextual help and tips

### DON'T:
❌ Allow skipping required steps
❌ Hide validation errors
❌ Make users re-enter information
❌ Show too many options at once
❌ Use unclear or technical language
❌ Forget to show connection status
❌ Allow incomplete configuration

---

## Future Enhancements

### Phase 1: Current Implementation
- 4-step wizard with manual selection
- AI relevance scoring for tables
- Recommended assistants
- Basic validation

### Phase 2: Smart Defaults
- Auto-select highly relevant tables (>90%)
- Auto-select all recommended assistants
- Pre-fill goal based on recent activity
- Remember previous selections

### Phase 3: Advanced Features
- "Quick Start" mode: Skip wizard with smart defaults
- Save configurations as templates
- Share configurations with team
- Import/export configurations

### Phase 4: AI-Powered
- AI suggests goal based on data source analysis
- AI explains why tables are relevant
- AI optimizes assistant selection
- Real-time goal refinement suggestions

---

## Summary

The **Builder Setup Wizard** provides a guided, 4-step configuration experience that:

1. **Captures user intent** through goal definition
2. **Connects to data** via data source selection
3. **Filters relevant data** with AI-powered table selection
4. **Assembles AI team** through assistant selection

This ensures users have a properly configured environment before starting their work, leading to better outcomes and reduced friction in the main builder interface.

**Key Benefits:**
- Reduces setup errors
- Improves data relevance
- Optimizes assistant selection
- Creates clear user expectations
- Enables context-aware AI assistance
- Provides smooth onboarding experience

The wizard is designed to work identically for both Feature Builder and Case Study Builder, with only minor differences in examples and assistant recommendations based on the use case.
