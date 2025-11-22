"""
OpenMetadata MCP Client for fetching table metadata from OpenMetadata server.

This module provides a client for interacting with OpenMetadata's MCP (Model Context Protocol) server
to fetch table metadata, column descriptions, relationships, and usage information.
"""

from typing import Dict, Any, List, Optional
import httpx


class OpenMetadataMCPClient:
    """Client for fetching metadata from OpenMetadata MCP Server"""
    
    def __init__(self, mcp_server_url: str = "http://localhost:8585", api_token: Optional[str] = None):
        """
        Initialize the OpenMetadata MCP client.
        
        Args:
            mcp_server_url: Base URL of the OpenMetadata server (default: http://localhost:8585)
            api_token: Optional API token for authentication
        """
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.api_token = api_token
        self.base_url = f"{self.mcp_server_url}/api/v1"
    
    async def get_table_metadata(self, table_fqn: str) -> Dict[str, Any]:
        """
        Fetch table metadata from OpenMetadata MCP server.
        
        Args:
            table_fqn: Fully Qualified Name in format: databaseServiceName.databaseName.schemaName.tableName
        
        Returns:
            Dictionary containing table metadata, or empty dict if not found/error
        """
        try:
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            
            # Fetch table entity
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try to get table by FQN
                response = await client.get(
                    f"{self.base_url}/tables/name/{table_fqn}",
                    headers=headers,
                    params={"fields": "columns,description,usageSummary,joins,tableConstraints"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    # Return empty structure if not found
                    return {}
        except Exception as e:
            # Return empty structure on error (graceful degradation)
            return {}
    
    async def get_column_descriptions(self, table_fqn: str) -> Dict[str, str]:
        """
        Get column descriptions from OpenMetadata.
        
        Args:
            table_fqn: Fully Qualified Name of the table
        
        Returns:
            Dictionary mapping column names to their descriptions
        """
        metadata = await self.get_table_metadata(table_fqn)
        column_descriptions = {}
        
        if "columns" in metadata:
            for col in metadata.get("columns", []):
                col_name = col.get("name", "")
                col_desc = col.get("description", "") or col.get("dataTypeDisplay", "")
                column_descriptions[col_name] = col_desc
        
        return column_descriptions
    
    async def get_table_usage(self, table_fqn: str) -> Dict[str, List[str]]:
        """
        Get table usage information (SQLs, Joins, Cubes, Dashboards).
        
        Args:
            table_fqn: Fully Qualified Name of the table
        
        Returns:
            Dictionary with usage information categorized by type
        """
        metadata = await self.get_table_metadata(table_fqn)
        usage = {
            "SQLs": [],
            "Joins": [],
            "Cubes": [],
            "Dashboards": []
        }
        
        # Extract usage summary
        usage_summary = metadata.get("usageSummary", {})
        if usage_summary:
            # This is a placeholder - actual implementation would parse usageSummary
            usage["SQLs"] = usage_summary.get("queries", [])
        
        # Extract joins
        joins = metadata.get("joins", [])
        for join_info in joins:
            usage["Joins"].append({
                "joined_with": join_info.get("joinedWith", {}).get("fullyQualifiedName", ""),
                "join_type": join_info.get("joinType", ""),
                "join_count": join_info.get("joinCount", 0)
            })
        
        return usage
    
    async def get_table_relationships(self, table_fqn: str) -> List[Dict[str, Any]]:
        """
        Get table relationships from OpenMetadata (foreign keys, etc.).
        
        Args:
            table_fqn: Fully Qualified Name of the table
        
        Returns:
            List of relationship dictionaries
        """
        metadata = await self.get_table_metadata(table_fqn)
        relationships = []
        
        # Extract foreign key constraints
        constraints = metadata.get("tableConstraints", [])
        for constraint in constraints:
            if constraint.get("constraintType") == "FOREIGN_KEY":
                relationships.append({
                    "type": "FOREIGN_KEY",
                    "columns": constraint.get("columns", []),
                    "referred_columns": constraint.get("referredColumns", []),
                    "referred_table": constraint.get("referredTable", "")
                })
        
        return relationships

