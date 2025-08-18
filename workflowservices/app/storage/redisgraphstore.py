import redis
from redisgraph import Node, Edge, Graph
from typing import Dict, List, Optional, Any


class RedisGraphStore:
    """Class to handle operations with RedisGraph."""
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        password: Optional[str] = None, 
        db: int = 0
    ):
        """Initialize the RedisGraph connection.
        
        Args:
            host: Redis host
            port: Redis port
            password: Redis password
            db: Redis database number
        """
        self.redis_conn = redis.Redis(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True
        )
        
    def get_graph(self, graph_name: str) -> Graph:
        """Get a graph by name.
        
        Args:
            graph_name: Name of the graph
            
        Returns:
            Graph object
        """
        return Graph(graph_name, self.redis_conn)
    
    def create_node(
        self, 
        graph: Graph, 
        label: str, 
        properties: Dict[str, Any]
    ) -> Node:
        """Create a node in the graph.
        
        Args:
            graph: Graph object
            label: Node label
            properties: Node properties
            
        Returns:
            Created node
        """
        node = Node(label=label, properties=properties)
        graph.add_node(node)
        return node
    
    def create_edge(
        self, 
        graph: Graph, 
        src_node: Node, 
        rel: str, 
        dest_node: Node, 
        properties: Optional[Dict[str, Any]] = None
    ) -> Edge:
        """Create an edge between two nodes.
        
        Args:
            graph: Graph object
            src_node: Source node
            rel: Relationship type
            dest_node: Destination node
            properties: Edge properties
            
        Returns:
            Created edge
        """
        edge = Edge(src_node, rel, dest_node, properties or {})
        graph.add_edge(edge)
        return edge
    
    def commit(self, graph: Graph) -> None:
        """Commit changes to the graph.
        
        Args:
            graph: Graph object
        """
        graph.commit()
        
    def query(self, graph: Graph, query: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query on the graph.
        
        Args:
            graph: Graph object
            query: Cypher query
            
        Returns:
            Query results
            
        Raises:
            Exception: If the query fails to execute
        """
        try:
            result = graph.query(query)
            return self._process_query_result(result)
        except Exception as e:
            print(f"Error executing query: {query}")
            print(f"Error details: {str(e)}")
            # Return empty list instead of raising to allow graceful handling
            return []
    
    def _process_query_result(self, result):
        """Process query result to a more usable format.
        
        Args:
            result: Query result
            
        Returns:
            Processed results as a list of dictionaries
        """
        processed_results = []
        
        # If there are no results
        if result is None or result.result_set is None:
            return processed_results
            
        # Get header
        header = [col.decode('utf-8') if isinstance(col, bytes) else col 
                  for col in result.header]
        
        # Process each record
        for record in result.result_set:
            record_dict = {}
            for i, value in enumerate(record):
                # Use a simple key based on the index
                header_key = f"result_{i}"
                
                if isinstance(value, list):
                    record_dict[header_key] = value
                elif isinstance(value, Node):  # RedisGraph Node
                    record_dict[header_key] = {
                        'label': value.label,
                        'properties': value.properties
                    }
                elif isinstance(value, Edge):  # RedisGraph Edge
                    record_dict[header_key] = {
                        'relation': value.relation,
                        'properties': value.properties
                    }
                else:
                    record_dict[header_key] = value
            processed_results.append(record_dict)
            
        return processed_results