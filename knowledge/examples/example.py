"""
Example usage of the graph streaming module

This example shows how to:
1. Create an assistant
2. Register a graph
3. Stream graph execution
4. Handle events
"""
import asyncio
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from app.streams import (
    get_registry,
    GraphStreamingService,
    GraphStartedEvent,
    NodeStartedEvent,
    ResultEvent
)


# Example state model
class SimpleState(BaseModel):
    query: str = ""
    answer: str = ""
    step: str = ""


# Example node functions
def node_1(state: SimpleState) -> SimpleState:
    """First node"""
    state.step = "processing"
    state.answer = f"Processing: {state.query}"
    return state


def node_2(state: SimpleState) -> SimpleState:
    """Second node"""
    state.step = "completed"
    state.answer = f"Answer to: {state.query}"
    return state


def build_example_graph():
    """Build a simple example graph"""
    graph = StateGraph(SimpleState)
    graph.add_node("node_1", node_1)
    graph.add_node("node_2", node_2)
    graph.add_edge("node_1", "node_2")
    graph.set_entry_point("node_1")
    
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


async def example_basic_usage():
    """Basic usage example"""
    print("=== Basic Usage Example ===\n")
    
    # Get registry
    registry = get_registry()
    
    # Register assistant
    assistant = registry.register_assistant(
        assistant_id="example_assistant",
        name="Example Assistant",
        description="A simple example assistant"
    )
    print(f"Registered assistant: {assistant.assistant_id}")
    
    # Build and register graph
    graph = build_example_graph()
    graph_config = registry.register_graph(
        assistant_id="example_assistant",
        graph_id="example_graph",
        graph=graph,
        name="Example Graph",
        set_as_default=True
    )
    print(f"Registered graph: {graph_config.graph_id}\n")
    
    # Create streaming service
    service = GraphStreamingService(registry=registry)
    
    # Stream execution
    print("Streaming graph execution...\n")
    event_count = 0
    
    async for event_str in service.stream_graph_execution(
        assistant_id="example_assistant",
        graph_id="example_graph",
        input_data={"query": "What is LangGraph?"},
        session_id="example-session-1"
    ):
        event_count += 1
        # Parse and display event
        import json
        if event_str.startswith("event: "):
            lines = event_str.strip().split("\n")
            event_type = None
            data = None
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
            
            if event_type and data:
                print(f"[{event_type}] {data.get('node_name', data.get('event_type', ''))}")
                
                if event_type == "result":
                    print(f"  Result: {data.get('result', {})}")
                elif event_type == "graph_completed":
                    print(f"  Duration: {data.get('duration_ms', 0):.2f}ms")
    
    print(f"\nTotal events: {event_count}")


async def example_with_result_extractor():
    """Example with custom result extraction"""
    print("\n=== Result Extractor Example ===\n")
    
    registry = get_registry()
    service = GraphStreamingService(registry=registry)
    
    def extract_result(state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the answer from state"""
        return {
            "answer": state.get("answer", ""),
            "step": state.get("step", "")
        }
    
    print("Streaming with custom result extractor...\n")
    
    async for event_str in service.stream_graph_execution(
        assistant_id="example_assistant",
        graph_id="example_graph",
        input_data={"query": "How does streaming work?"},
        session_id="example-session-2",
        result_extractor=extract_result
    ):
        import json
        if "data: " in event_str:
            data_line = [l for l in event_str.split("\n") if l.startswith("data: ")][0]
            data = json.loads(data_line[6:])
            
            if data.get("event_type") == "result":
                print(f"Extracted result: {data.get('result')}")


async def example_multiple_graphs():
    """Example with multiple graphs per assistant"""
    print("\n=== Multiple Graphs Example ===\n")
    
    registry = get_registry()
    
    # Create a second graph
    def node_alt(state: SimpleState) -> SimpleState:
        state.answer = f"Alternative answer: {state.query}"
        return state
    
    graph2 = StateGraph(SimpleState)
    graph2.add_node("alt_node", node_alt)
    graph2.set_entry_point("alt_node")
    
    checkpointer = MemorySaver()
    compiled_graph2 = graph2.compile(checkpointer=checkpointer)
    
    # Register second graph
    registry.register_graph(
        assistant_id="example_assistant",
        graph_id="alternative_graph",
        graph=compiled_graph2,
        name="Alternative Graph"
    )
    
    # List graphs
    graphs = registry.list_assistant_graphs("example_assistant")
    print(f"Graphs for assistant:")
    for g in graphs:
        print(f"  - {g['graph_id']}: {g['name']} (default: {g['is_default']})")
    
    # Stream with specific graph
    service = GraphStreamingService(registry=registry)
    print("\nStreaming alternative graph...\n")
    
    async for event_str in service.stream_graph_execution(
        assistant_id="example_assistant",
        graph_id="alternative_graph",  # Use specific graph
        input_data={"query": "Test query"},
        session_id="example-session-3"
    ):
        import json
        if "data: " in event_str:
            data_line = [l for l in event_str.split("\n") if l.startswith("data: ")][0]
            data = json.loads(data_line[6:])
            if data.get("event_type") == "result":
                print(f"Result from alternative graph: {data.get('result', {}).get('answer')}")


async def main():
    """Run all examples"""
    await example_basic_usage()
    await example_with_result_extractor()
    await example_multiple_graphs()
    
    print("\n=== Examples Complete ===")


if __name__ == "__main__":
    asyncio.run(main())

