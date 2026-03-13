# Automated Agent Conversation Script

This script automates multi-turn conversations with agents via the API, continuing until a final answer is received.

## Quick Start

### Basic Usage (Single Question)

```bash
python tests/automated_agent_conversation.py \
    --agent-id csod-planner \
    --query "I want to create a metrics dashboard for learning and development"
```

### Multi-Turn Conversation

```bash
python tests/automated_agent_conversation.py \
    --agent-id csod-planner \
    --query "I want to create a metrics dashboard" \
    --follow-ups "What metrics should I track?" "How do I visualize them?"
```

### Interactive Mode

```bash
python tests/automated_agent_conversation.py \
    --agent-id csod-planner \
    --query "I want to create a metrics dashboard" \
    --interactive
```

### With Live Server

```bash
# Terminal 1: Start server
python app/api/main.py

# Terminal 2: Run script
python tests/automated_agent_conversation.py \
    --agent-id csod-planner \
    --query "test query" \
    --server-url http://localhost:8002
```

### Auto-Respond to Checkpoints (for Testing)

```bash
python tests/automated_agent_conversation.py \
    --agent-id csod-planner \
    --query "test query" \
    --auto-respond-checkpoints
```

## Available Agents

- `csod-planner` - CSOD Planner
- `csod-workflow` - CSOD Metrics & KPIs Workflow
- `csod-metric-advisor` - CSOD Metric Advisor (with causal reasoning)
- `dt-workflow` - Detection & Triage Workflow
- `compliance-workflow` - Compliance Automation Workflow
- `dashboard-agent` - Dashboard Layout Advisor

## Features

- **Automatic Conversation Flow**: Continues until `FINAL` event is received
- **Question Detection**: Automatically detects when agent asks questions
- **Checkpoint Handling**: Can auto-respond to checkpoints or prompt for input
- **Streaming Support**: Handles SSE streaming responses
- **Conversation History**: Saves complete conversation to JSON file
- **Multiple Modes**: TestClient (no server) or live server support

## Output

Conversations are saved to:
```
tests/outputs/automated_conversations/{agent_id}_{timestamp}.json
```

Each file contains:
- Complete conversation history
- All events received
- Final answer
- Turn count
- Thread ID

## Examples

### Example 1: Simple Query

```bash
python tests/automated_agent_conversation.py \
    --agent-id compliance-workflow \
    --query "Analyze our compliance with SOC 2"
```

### Example 2: Multi-Step Conversation

```bash
python tests/automated_agent_conversation.py \
    --agent-id dt-workflow \
    --query "Create SIEM rules for SOC 2 CC6.1" \
    --follow-ups "What controls are needed?" "How do I implement them?"
```

### Example 3: Interactive Testing

```bash
python tests/automated_agent_conversation.py \
    --agent-id dashboard-agent \
    --query "Help me design a dashboard layout" \
    --interactive
```

## Command Line Options

- `--agent-id` (required): Agent identifier
- `--query` (required): Initial query
- `--follow-ups`: List of follow-up queries
- `--interactive`: Prompt for follow-ups interactively
- `--server-url`: Base URL for live server
- `--use-test-client`: Use TestClient (no server needed)
- `--auto-respond-checkpoints`: Auto-approve checkpoints
- `--max-turns`: Maximum conversation turns (default: 10)
- `--output-dir`: Custom output directory

## How It Works

1. **Sends Initial Query**: Connects to agent API and sends first query
2. **Streams Events**: Collects SSE events (tokens, tool calls, etc.)
3. **Detects Completion**: Looks for `FINAL` event or complete answer
4. **Handles Checkpoints**: Detects checkpoints and responds (auto or interactive)
5. **Continues Conversation**: Sends follow-up queries if provided
6. **Saves Results**: Writes complete conversation to JSON file

## Tips

- Use `--auto-respond-checkpoints` for fully automated testing
- Use `--interactive` when you want to manually respond to questions
- Check the output JSON files to see full event history
- Use `--max-turns` to prevent infinite loops
- The script automatically detects questions in responses and can continue
