"""
MySQL template implementation.
This template handles MySQL database connections and query execution.
This is an example of how to add new data sources to the system.
"""

from typing import Dict, Any
from pathlib import Path
from ..base_template import BaseTemplate


class MySQLTemplate(BaseTemplate):
    """MySQL database template implementation."""
    
    @property
    def data_source_name(self) -> str:
        return "mysql"
    
    @property
    def required_dependencies(self) -> list:
        return [
            "pandas>=1.5.0",
            "sqlalchemy>=1.4.0",
            "pymysql>=1.0.0"
        ]
    
    @property
    def connection_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            "host": {
                "default": "your_mysql_host",
                "type": "string",
                "required": True,
                "description": "MySQL server hostname or IP address"
            },
            "port": {
                "default": 3306,
                "type": "integer",
                "required": False,
                "description": "MySQL server port"
            },
            "database": {
                "default": "your_database",
                "type": "string",
                "required": True,
                "description": "Database name to connect to"
            },
            "user": {
                "default": "your_username",
                "type": "string",
                "required": True,
                "description": "Database username"
            },
            "password": {
                "default": "your_password",
                "type": "string",
                "required": True,
                "description": "Database password"
            },
            "charset": {
                "default": "utf8mb4",
                "type": "string",
                "required": False,
                "description": "Character set for the connection"
            }
        }
    
    @property
    def query_placeholder(self) -> str:
        return 'query = "DUMMY_QUERY PLACE HOLDER"'
    
    def apply_connection_config(self, content: str, config: Dict[str, Any]) -> str:
        """
        Apply MySQL connection configuration to the template content.
        
        Args:
            content: Template content
            config: Connection configuration dictionary
            
        Returns:
            Modified content with connection configuration applied
        """
        # Replace host
        if "host" in config:
            content = content.replace(
                'MYSQL_HOST = "your_mysql_host"',
                f'MYSQL_HOST = "{config["host"]}"'
            )
        
        # Replace port
        if "port" in config:
            content = content.replace(
                'MYSQL_PORT = 3306',
                f'MYSQL_PORT = {config["port"]}'
            )
        
        # Replace database name
        if "database" in config:
            content = content.replace(
                'MYSQL_DATABASE = "your_database"',
                f'MYSQL_DATABASE = "{config["database"]}"'
            )
        
        # Replace user
        if "user" in config:
            content = content.replace(
                'MYSQL_USER = "your_username"',
                f'MYSQL_USER = "{config["user"]}"'
            )
        
        # Replace password
        if "password" in config:
            content = content.replace(
                'MYSQL_PASSWORD = "your_password"',
                f'MYSQL_PASSWORD = "{config["password"]}"'
            )
        
        # Replace charset
        if "charset" in config:
            content = content.replace(
                'MYSQL_CHARSET = "utf8mb4"',
                f'MYSQL_CHARSET = "{config["charset"]}"'
            )
        
        return content
