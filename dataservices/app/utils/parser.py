import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
from datetime import datetime

import openai
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from pydantic import BaseModel, Field
from app.service.models import SchemaInput, Table
# ============================================================================
# SCHEMA PARSING UTILITIES
# ============================================================================

class SchemaParser:
    """Parse various schema formats into standardized format"""
    
    @staticmethod
    def parse_ddl(ddl_statement: str) -> SchemaInput:
        """Parse DDL CREATE TABLE statement"""
        # Simple DDL parser - in production, use a proper SQL parser
        table_name_match = re.search(r'CREATE TABLE\s+(\w+)', ddl_statement, re.IGNORECASE)
        table_name = table_name_match.group(1) if table_name_match else "unknown_table"
        
        # Extract column definitions
        columns = []
        column_pattern = r'(\w+)\s+([A-Z]+(?:\(\d+(?:,\s*\d+)?\))?)[^,\n]*'
        
        for match in re.finditer(column_pattern, ddl_statement):
            column_name = match.group(1)
            data_type = match.group(2)
            
            # Skip common SQL keywords
            if column_name.upper() in ['PRIMARY', 'FOREIGN', 'KEY', 'CONSTRAINT', 'REFERENCES']:
                continue
                
            columns.append({
                "name": column_name,
                "data_type": data_type,
                "nullable": "NOT NULL" not in match.group(0).upper(),
                "primary_key": "PRIMARY KEY" in match.group(0).upper()
            })
        
        return SchemaInput(
            table_name=table_name,
            table_description=None,
            columns=columns
        )
    
    @staticmethod
    def parse_sqlalchemy_table(table: Table) -> SchemaInput:
        """Parse SQLAlchemy table model"""
        columns = []
        for column in table.columns:
            columns.append({
                "name": column.name,
                "data_type": str(column.data_type) if column.data_type else "VARCHAR",
                "nullable": column.is_nullable,
                "primary_key": column.is_primary_key,
                "description": column.description
            })
        
        return SchemaInput(
            table_name=table.name,
            table_description=table.description,
            columns=columns
        )
    
    @staticmethod
    def parse_json_schema(schema_json: Dict[str, Any]) -> SchemaInput:
        """Parse JSON schema definition"""
        table_name = schema_json.get("table_name", "unknown_table")
        columns = []
        
        for col_def in schema_json.get("columns", []):
            columns.append({
                "name": col_def.get("name"),
                "data_type": col_def.get("type", "VARCHAR"),
                "nullable": col_def.get("nullable", True),
                "primary_key": col_def.get("primary_key", False),
                "description": col_def.get("description")
            })
        
        return SchemaInput(
            table_name=table_name,
            table_description=schema_json.get("description"),
            columns=columns,
            sample_data=schema_json.get("sample_data"),
            constraints=schema_json.get("constraints")
        )
