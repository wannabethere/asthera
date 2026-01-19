"""
Graph Registry for managing multiple graphs per assistant/chat
"""
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class GraphConfig:
    """Configuration for a graph"""
    graph_id: str
    name: str
    description: Optional[str] = None
    graph: Any = None  # LangGraph compiled graph
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssistantConfig:
    """Configuration for an assistant with multiple graphs"""
    assistant_id: str
    name: str
    description: Optional[str] = None
    graphs: Dict[str, GraphConfig] = field(default_factory=dict)
    default_graph_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class GraphRegistry:
    """Registry for managing graphs and assistants"""
    
    def __init__(self):
        self._assistants: Dict[str, AssistantConfig] = {}
        self._graphs: Dict[str, GraphConfig] = {}  # Global graph lookup
    
    def register_assistant(
        self,
        assistant_id: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AssistantConfig:
        """Register a new assistant"""
        assistant = AssistantConfig(
            assistant_id=assistant_id,
            name=name,
            description=description,
            metadata=metadata or {}
        )
        self._assistants[assistant_id] = assistant
        logger.info(f"Registered assistant: {assistant_id}")
        return assistant
    
    def register_graph(
        self,
        assistant_id: str,
        graph_id: str,
        graph: Any,  # LangGraph compiled graph
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        set_as_default: bool = False
    ) -> GraphConfig:
        """Register a graph for an assistant"""
        if assistant_id not in self._assistants:
            raise ValueError(f"Assistant {assistant_id} not found. Register assistant first.")
        
        graph_config = GraphConfig(
            graph_id=graph_id,
            name=name or graph_id,
            description=description,
            graph=graph,
            metadata=metadata or {}
        )
        
        assistant = self._assistants[assistant_id]
        assistant.graphs[graph_id] = graph_config
        assistant.updated_at = datetime.now()
        
        # Also register in global lookup
        self._graphs[graph_id] = graph_config
        
        if set_as_default or assistant.default_graph_id is None:
            assistant.default_graph_id = graph_id
        
        logger.info(f"Registered graph {graph_id} for assistant {assistant_id}")
        return graph_config
    
    def get_assistant(self, assistant_id: str) -> Optional[AssistantConfig]:
        """Get assistant configuration"""
        return self._assistants.get(assistant_id)
    
    def get_graph(self, graph_id: str) -> Optional[GraphConfig]:
        """Get graph configuration by ID"""
        return self._graphs.get(graph_id)
    
    def get_assistant_graph(
        self,
        assistant_id: str,
        graph_id: Optional[str] = None
    ) -> Optional[GraphConfig]:
        """Get graph for an assistant (uses default if graph_id not provided)"""
        assistant = self.get_assistant(assistant_id)
        if not assistant:
            return None
        
        if graph_id is None:
            graph_id = assistant.default_graph_id
        
        if graph_id is None:
            return None
        
        return assistant.graphs.get(graph_id)
    
    def list_assistants(self) -> list[Dict[str, Any]]:
        """List all assistants"""
        return [
            {
                "assistant_id": a.assistant_id,
                "name": a.name,
                "description": a.description,
                "graph_count": len(a.graphs),
                "default_graph_id": a.default_graph_id,
                "metadata": a.metadata
            }
            for a in self._assistants.values()
        ]
    
    def list_assistant_graphs(self, assistant_id: str) -> list[Dict[str, Any]]:
        """List all graphs for an assistant"""
        assistant = self.get_assistant(assistant_id)
        if not assistant:
            return []
        
        return [
            {
                "graph_id": g.graph_id,
                "name": g.name,
                "description": g.description,
                "metadata": g.metadata,
                "is_default": g.graph_id == assistant.default_graph_id
            }
            for g in assistant.graphs.values()
        ]
    
    def unregister_graph(self, assistant_id: str, graph_id: str) -> bool:
        """Unregister a graph from an assistant"""
        assistant = self.get_assistant(assistant_id)
        if not assistant:
            return False
        
        if graph_id in assistant.graphs:
            del assistant.graphs[graph_id]
            assistant.updated_at = datetime.now()
            
            # Remove from global lookup
            if graph_id in self._graphs:
                del self._graphs[graph_id]
            
            # Update default if needed
            if assistant.default_graph_id == graph_id:
                assistant.default_graph_id = (
                    next(iter(assistant.graphs.keys()), None)
                    if assistant.graphs else None
                )
            
            logger.info(f"Unregistered graph {graph_id} from assistant {assistant_id}")
            return True
        
        return False
    
    def unregister_assistant(self, assistant_id: str) -> bool:
        """Unregister an assistant and all its graphs"""
        if assistant_id not in self._assistants:
            return False
        
        assistant = self._assistants[assistant_id]
        
        # Remove all graphs from global lookup
        for graph_id in assistant.graphs.keys():
            if graph_id in self._graphs:
                del self._graphs[graph_id]
        
        del self._assistants[assistant_id]
        logger.info(f"Unregistered assistant {assistant_id}")
        return True


# Global registry instance
_global_registry = GraphRegistry()


def get_registry() -> GraphRegistry:
    """Get the global graph registry"""
    return _global_registry

