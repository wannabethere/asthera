# Agentic Chat

A React chat application that demonstrates SSE (Server-Sent Events) for real-time conversations with AI assistants from the Knowledge service.

## Features

- **Assistant Selection**: Choose from available assistants registered in the Knowledge service
- **Dataset Selection**: Select from available datasets (csod_risk_attrition, cornerstone_learning, etc.)
- **Split-Screen Layout**: Chat interface on the left, markdown outcomes panel on the right
- **Real-time Streaming**: Uses SSE to stream assistant responses as they're generated
- **Markdown Rendering**: Outcomes panel renders markdown content from SSE events in real-time
- **Chat Interface**: Clean, modern UI for conversations
- **Event Handling**: Processes various event types (graph_started, node_completed, result, etc.)

## Setup

1. Install dependencies:
```bash
npm install
```

2. Make sure the Knowledge service is running on port 8000 (default)

3. Start the development server:
```bash
npm run dev
```

The app will run on port 5174 (since 5173 is already in use).

## Configuration

The app is configured to proxy API requests to the Knowledge service:
- API Base: `http://localhost:8000/api/streams`
- The Vite dev server proxies `/api` requests to the backend

## Usage

1. **Select an Assistant**: Use the dropdown to choose an assistant
2. **Select a Dataset**: Choose a dataset from the list (e.g., csod_risk_attrition, cornerstone_learning)
3. **Send Messages**: Type your question in the left panel and click "Send" or press Enter
4. **View Responses**: 
   - Chat messages appear in the left panel
   - Markdown-formatted outcomes appear in the right panel in real-time
5. **Clear Chat**: Use the "Clear Chat" button to start a new conversation

**Note**: Both assistant and dataset must be selected before sending messages.

### Split-Screen Layout

The interface features a split-screen layout:
- **Left Panel**: Chat conversation with messages
- **Right Panel**: Outcomes panel that displays markdown-formatted results from SSE events

The outcomes panel automatically updates as the assistant processes your query, showing formatted markdown content including:
- Headers and text formatting
- Code blocks with syntax highlighting
- Tables
- Lists
- Links and other markdown elements

## API Integration

The app integrates with the Knowledge service's streaming API:

- `GET /api/streams/assistants` - List available assistants
- `POST /api/streams/invoke` - Invoke an assistant with SSE streaming

### Request Format

```json
{
  "assistant_id": "compliance_assistant",
  "query": "Your question here",
  "session_id": "optional_session_id",
  "input_data": {
    "query": "Your question here",
    "project_id": "csod_risk_attrition",
    "user_context": {
      "project_id": "csod_risk_attrition"
    }
  }
}
```

The `project_id` in `input_data` corresponds to the selected dataset and is used by the assistant to filter and retrieve relevant data.

### Event Types

The app handles various SSE event types:
- `graph_started` - Graph execution begins
- `node_started` - A node begins execution
- `node_completed` - A node completes execution
- `state_update` - Graph state is updated
- `result` - Final result data
- `graph_completed` - Graph execution completes
- `graph_error` - Graph execution fails

## Project Structure

```
src/
  ├── main.jsx              # Entry point
  ├── App.jsx               # Main app component
  ├── data/
  │   └── datasets.json     # Available datasets list
  ├── hooks/
  │   └── useSSE.js        # SSE streaming hook
  ├── services/
  │   └── api.js           # API service functions
  └── components/
      ├── AssistantSelector.jsx
      ├── DatasetSelector.jsx
      ├── SplitScreenLayout.jsx
      ├── ChatInterface.jsx
      ├── OutcomesPanel.jsx
      ├── MessageList.jsx
      └── MessageInput.jsx
```

## Development

- Uses Vite for fast development
- React 18 with hooks
- Modern CSS with flexbox/grid
- Responsive design

## Available Datasets

The app includes the following datasets (defined in `src/data/datasets.json`):

- **csod_risk_attrition**: Cornerstone Learning & Risk Management System
- **cornerstone_learning**: Cornerstone Learning Management System
- **cornerstone_talent**: Cornerstone Talent Management System
- **cornerstone**: Cornerstone Platform
- **csodworkday**: CSOD Workday Integration
- **cve_data**: CVE Security Data
- **employee_training**: Employee Training System
- **medrcm360**: MedRCM 360 Revenue Cycle
- **sumtotal_learn**: SumTotal Learning System

To add more datasets, edit `src/data/datasets.json` with the project_id and metadata.

## Notes

- The app expects the Knowledge service to be running on `localhost:8000`
- SSE events are parsed and displayed in real-time
- The final answer is extracted from the `result` event or `state_update` events
- The `project_id` from the selected dataset is passed in `input_data` to filter queries appropriately

