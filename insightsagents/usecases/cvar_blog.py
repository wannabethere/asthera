# Conversational Pipeline Configuration Generator with Self-RAG
# Based on Scott Haines' "Hitchhiker's Guide to Delta Lake Streaming"

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Core Configuration Models
@dataclass
class DeltaSourceConfig:
    """Configuration for Delta Lake streaming source"""
    catalog_name: str
    schema_name: str
    table_name: str
    max_files_per_trigger: Optional[int] = None
    max_bytes_per_trigger: Optional[str] = None
    starting_version: Optional[int] = None
    starting_timestamp: Optional[str] = None
    ignore_deletes: bool = False
    ignore_changes: bool = False
    with_event_time_order: bool = False
    schema_tracking_location: Optional[str] = None

@dataclass
class DeltaSinkConfig:
    """Configuration for Delta Lake streaming sink"""
    catalog_name: str
    schema_name: str
    table_name: str
    output_mode: str = "append"
    checkpoint_location: str = ""
    trigger_mode: str = "ProcessingTime"
    trigger_interval: str = "10 seconds"
    partition_columns: List[str] = None

@dataclass
class PipelineConfig:
    """Complete pipeline configuration"""
    name: str
    source: DeltaSourceConfig
    sink: DeltaSinkConfig
    transformations: List[str] = None

# Self-RAG Agent Components
class MetadataRetriever:
    """Retrieves metadata from Unity Catalog for context"""
    
    def __init__(self, workspace_client):
        self.workspace_client = workspace_client
    
    def get_table_schema(self, catalog: str, schema: str, table: str) -> Dict[str, Any]:
        """Retrieve table schema and metadata"""
        try:
            table_info = self.workspace_client.tables.get(
                full_name=f"{catalog}.{schema}.{table}"
            )
            return {
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type_text,
                        "nullable": col.nullable
                    } for col in table_info.columns
                ],
                "table_type": table_info.table_type,
                "data_source_format": table_info.data_source_format,
                "properties": table_info.properties
            }
        except Exception as e:
            return {"error": f"Failed to retrieve schema: {str(e)}"}
    
    def get_table_stats(self, catalog: str, schema: str, table: str) -> Dict[str, Any]:
        """Get table statistics for optimization"""
        try:
            # This would integrate with actual table stats
            return {
                "row_count": "estimated_from_metadata",
                "size_bytes": "estimated_from_metadata", 
                "partition_columns": [],
                "last_modified": "timestamp"
            }
        except Exception as e:
            return {"error": f"Failed to retrieve stats: {str(e)}"}

class ConfigurationGenerator:
    """Generates optimized configurations based on metadata"""
    
    def __init__(self, metadata_retriever: MetadataRetriever):
        self.metadata_retriever = metadata_retriever
    
    def suggest_source_config(self, table_path: str, requirements: Dict[str, Any]) -> DeltaSourceConfig:
        """Generate source configuration with optimization suggestions"""
        catalog, schema, table = table_path.split('.')
        
        # Retrieve metadata for context
        table_info = self.metadata_retriever.get_table_schema(catalog, schema, table)
        table_stats = self.metadata_retriever.get_table_stats(catalog, schema, table)
        
        # Apply self-reflection and optimization
        config = DeltaSourceConfig(
            catalog_name=catalog,
            schema_name=schema,
            table_name=table
        )
        
        # Optimize based on table size and requirements
        if requirements.get("throughput") == "high":
            config.max_files_per_trigger = 1000
            config.max_bytes_per_trigger = "1g"
        elif requirements.get("throughput") == "low":
            config.max_files_per_trigger = 10
            config.max_bytes_per_trigger = "128m"
        
        # Handle schema evolution
        if requirements.get("schema_evolution", False):
            config.schema_tracking_location = f"/tmp/schema_tracking/{catalog}_{schema}_{table}"
        
        return config
    
    def suggest_sink_config(self, table_path: str, requirements: Dict[str, Any]) -> DeltaSinkConfig:
        """Generate sink configuration with optimization"""
        catalog, schema, table = table_path.split('.')
        
        config = DeltaSinkConfig(
            catalog_name=catalog,
            schema_name=schema,
            table_name=table,
            checkpoint_location=f"/tmp/checkpoints/{catalog}_{schema}_{table}"
        )
        
        # Optimize trigger based on latency requirements
        if requirements.get("latency") == "low":
            config.trigger_mode = "Continuous"
            config.trigger_interval = "1 second"
        elif requirements.get("latency") == "high":
            config.trigger_mode = "ProcessingTime"
            config.trigger_interval = "5 minutes"
        
        return config

class ConversationalAgent:
    """Self-RAG conversational agent for pipeline configuration"""
    
    def __init__(self, config_generator: ConfigurationGenerator):
        self.config_generator = config_generator
        self.conversation_state = {}
    
    def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """Process natural language input and generate responses"""
        
        # Simple intent recognition (would use LLM in practice)
        if "create pipeline" in user_input.lower():
            return self._handle_pipeline_creation(user_input)
        elif "optimize" in user_input.lower():
            return self._handle_optimization_request(user_input)
        elif "explain" in user_input.lower():
            return self._handle_explanation_request(user_input)
        else:
            return {"response": "I can help you create, optimize, or explain Delta Lake streaming pipelines. What would you like to do?"}
    
    def _handle_pipeline_creation(self, user_input: str) -> Dict[str, Any]:
        """Handle pipeline creation requests"""
        # Extract requirements from natural language (simplified)
        requirements = self._extract_requirements(user_input)
        
        if not requirements.get("source_table"):
            return {
                "response": "I need to know the source table. Please specify it as catalog.schema.table",
                "needs_input": "source_table"
            }
        
        if not requirements.get("sink_table"):
            return {
                "response": "I need to know the destination table. Please specify it as catalog.schema.table",
                "needs_input": "sink_table"
            }
        
        # Generate configuration using self-RAG
        source_config = self.config_generator.suggest_source_config(
            requirements["source_table"], 
            requirements
        )
        
        sink_config = self.config_generator.suggest_sink_config(
            requirements["sink_table"],
            requirements
        )
        
        pipeline_config = PipelineConfig(
            name=requirements.get("name", "auto_generated_pipeline"),
            source=source_config,
            sink=sink_config
        )
        
        return {
            "response": "I've generated an optimized pipeline configuration based on your requirements.",
            "config": pipeline_config,
            "explanation": self._explain_configuration(pipeline_config)
        }
    
    def _extract_requirements(self, user_input: str) -> Dict[str, Any]:
        """Extract requirements from natural language input"""
        # Simplified extraction - would use LLM parsing in practice
        requirements = {}
        
        if "high throughput" in user_input.lower():
            requirements["throughput"] = "high"
        elif "low throughput" in user_input.lower():
            requirements["throughput"] = "low"
        
        if "low latency" in user_input.lower():
            requirements["latency"] = "low"
        elif "high latency" in user_input.lower():
            requirements["latency"] = "high"
        
        if "schema evolution" in user_input.lower():
            requirements["schema_evolution"] = True
        
        # Extract table names (simplified regex)
        import re
        table_pattern = r'(\w+\.\w+\.\w+)'
        tables = re.findall(table_pattern, user_input)
        if len(tables) >= 1:
            requirements["source_table"] = tables[0]
        if len(tables) >= 2:
            requirements["sink_table"] = tables[1]
        
        return requirements
    
    def _explain_configuration(self, config: PipelineConfig) -> str:
        """Generate explanation for the configuration choices"""
        explanation = f"Configuration for pipeline '{config.name}':\n\n"
        
        # Source explanation
        explanation += f"**Source Configuration:**\n"
        explanation += f"- Reading from: {config.source.catalog_name}.{config.source.schema_name}.{config.source.table_name}\n"
        
        if config.source.max_files_per_trigger:
            explanation += f"- Rate limited to {config.source.max_files_per_trigger} files per trigger for optimal throughput\n"
        
        if config.source.schema_tracking_location:
            explanation += f"- Schema evolution tracking enabled at {config.source.schema_tracking_location}\n"
        
        # Sink explanation  
        explanation += f"\n**Sink Configuration:**\n"
        explanation += f"- Writing to: {config.sink.catalog_name}.{config.sink.schema_name}.{config.sink.table_name}\n"
        explanation += f"- Trigger mode: {config.sink.trigger_mode} with {config.sink.trigger_interval} interval\n"
        explanation += f"- Checkpoint location: {config.sink.checkpoint_location}\n"
        
        return explanation
    
    def _handle_optimization_request(self, user_input: str) -> Dict[str, Any]:
        """Handle requests to optimize existing configurations"""
        return {
            "response": "I can help optimize your pipeline. Please share your current configuration or describe the performance issues you're experiencing."
        }
    
    def _handle_explanation_request(self, user_input: str) -> Dict[str, Any]:
        """Handle requests to explain configurations or concepts"""
        return {
            "response": "I can explain Delta Lake streaming concepts, configuration options, or help you understand why certain settings were chosen. What would you like me to explain?"
        }

# Usage Example
def create_pipeline_conversation():
    """Example conversation flow"""
    
    # Initialize components (would connect to actual Databricks workspace)
    from unittest.mock import Mock
    mock_workspace = Mock()
    
    metadata_retriever = MetadataRetriever(mock_workspace)
    config_generator = ConfigurationGenerator(metadata_retriever)
    agent = ConversationalAgent(config_generator)
    
    # Simulate conversation
    user_input = "Create a high throughput pipeline from sales.bronze.transactions to sales.silver.processed_transactions with schema evolution support"
    
    response = agent.process_user_input(user_input)
    
    print("Agent Response:", response["response"])
    if "config" in response:
        print("\nGenerated Configuration:")
        print(json.dumps(response["config"].__dict__, indent=2, default=str))
        print("\nExplanation:")
        print(response["explanation"])

# Spark Configuration Generator
class SparkConfigGenerator:
    """Generates Spark configuration based on pipeline requirements"""
    
    def generate_spark_config(self, pipeline_config: PipelineConfig) -> Dict[str, str]:
        """Generate optimized Spark configuration"""
        config = {}
        
        # Source configuration
        source_prefix = "spark.app.source.delta"
        config[f"{source_prefix}.table.catalog"] = pipeline_config.source.catalog_name
        config[f"{source_prefix}.table.schema"] = pipeline_config.source.schema_name  
        config[f"{source_prefix}.table.name"] = pipeline_config.source.table_name
        
        if pipeline_config.source.max_files_per_trigger:
            config[f"{source_prefix}.maxFilesPerTrigger"] = str(pipeline_config.source.max_files_per_trigger)
        
        if pipeline_config.source.max_bytes_per_trigger:
            config[f"{source_prefix}.maxBytesPerTrigger"] = pipeline_config.source.max_bytes_per_trigger
        
        # Sink configuration
        sink_prefix = "spark.app.sink.delta"
        config[f"{sink_prefix}.table.catalog"] = pipeline_config.sink.catalog_name
        config[f"{sink_prefix}.table.schema"] = pipeline_config.sink.schema_name
        config[f"{sink_prefix}.table.name"] = pipeline_config.sink.table_name
        config[f"{sink_prefix}.outputMode"] = pipeline_config.sink.output_mode
        
        # Checkpoint configuration
        config["spark.app.checkpoints.path"] = pipeline_config.sink.checkpoint_location
        config["spark.app.checkpoints.version"] = "canary"
        
        return config

if __name__ == "__main__":
    create_pipeline_conversation()