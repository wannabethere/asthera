#!/usr/bin/env python3
"""
sf_sql_translator.py

A small CLI/tool that takes a natural-language Salesforce query on the
salesforce_opportunities table and returns a valid SQL SELECT statement.
"""

import os
import sys
import argparse
from typing import Optional, Dict, Any, List
from openai import OpenAI
from datetime import datetime

# Import the schema from sfdc_models
from app.models.sfdc_models import OPPORTUNITY_TABLE_SCHEMA_PROMPT
from app.utils.postgresdb import PostgresDB

def get_opportunity_metadata() -> Dict[str, List[str]]:
    """
    Fetch metadata about the salesforce_opportunities table,
    such as distinct values for categorical fields like 'type'.
    
    Returns:
        Dict with metadata about the table
    """
    try:
        db = PostgresDB()
        
        # Get distinct opportunity types
        type_query = "SELECT DISTINCT type FROM salesforce_opportunities WHERE type IS NOT NULL ORDER BY type;"
        types = db.execute_query(type_query)
        opportunity_types = [row['type'] for row in types]
        
        # You can add more metadata queries here (stages, lead sources, etc.)
        
        return {
            "opportunity_types": opportunity_types
        }
    except Exception as e:
        print(f"Warning: Could not fetch opportunity metadata: {e}", file=sys.stderr)
        return {"opportunity_types": []}

def build_system_prompt() -> str:
    """
    Build the system prompt with schema and metadata information
    """
    # Get metadata
    metadata = get_opportunity_metadata()
    
    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Build type information
    type_info = ""
    if metadata["opportunity_types"]:
        type_info = "Available opportunity types: " + ", ".join(f"'{t}'" for t in metadata["opportunity_types"])
    
    # Build the complete system prompt
    system_prompt = f"""
You are an expert assistant whose job is to turn user questions about Salesforce opportunities
into syntactically correct, efficient SQL SELECT statements operating on a PostgreSQL table.

– Respond with **only** the SQL query (no explanations, no commentary).
– Use the exact column names from the schema.
– Always wrap date/text values in single quotes.
– Omit any columns or clauses not requested.
- **Always include "name" column**
- **Always limit to top 15 results**
– Use PostgreSQL syntax.
- Today's date is {current_date}. Use this for any relative date calculations.

Schema:
{OPPORTUNITY_TABLE_SCHEMA_PROMPT}

Additional metadata:
{type_info}

Note: If a user asks about "upsell" opportunities, use type = 'Expansion' in the query as this is the equivalent in this Salesforce instance.
Note: If user is asking for a specific opportunity by name then you should find a close match using LIKE in the "name" column.
"""
    return system_prompt

def translate(nl_query: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("Please set your OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)
    
    # Get the dynamic system prompt with metadata
    system_prompt = build_system_prompt()
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nl_query}
        ],
        temperature=0.0,  # for deterministic / consistent results
        max_tokens=512,
    )
    
    if response.choices and response.choices[0].message and response.choices[0].message.content:
        sql = response.choices[0].message.content.strip()
        
        # Clean up any Markdown formatting
        sql = sql.replace("```sql", "").replace("```", "").strip()
        
        return sql
    return "Error: No response generated"

def execute_query(sql: str) -> None:
    """
    Execute the SQL query against the PostgreSQL database.
    This function requires psycopg to be installed.
    """
    try:
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv()
        
        # Use the PostgresDB utility class
        db = PostgresDB()
        
        print(f"Executing query: {sql}")
        
        # Execute the query
        results = db.execute_query(sql)
        
        if results:
            # Get column names (assuming all rows have the same structure)
            column_names = list(results[0].keys())
            
            # Print results in a tabular format
            print("\nResults:")
            print("-" * 100)
            print(" | ".join(column_names))
            print("-" * 100)
            
            for row in results:
                print(" | ".join(str(row[col]) for col in column_names))
            
            print(f"\nTotal rows: {len(results)}")
        else:
            print("Query executed successfully, but no results were returned.")
    
    except ImportError:
        print("To execute queries, please install required packages:")
        print("pip install psycopg python-dotenv")
        print("\nGenerated SQL query:")
        print(sql)
    except Exception as e:
        print(f"Error executing query: {e}")
        print("\nGenerated SQL query:")
        print(sql)

def execute_query_and_get_results(sql: str) -> List[Dict[str, Any]]:
    """
    Execute the SQL query against the PostgreSQL database and return results as a list of dictionaries.
    
    Args:
        sql: SQL query to execute
        
    Returns:
        List of dictionaries with query results
    """
    try:
        # Use the PostgresDB utility class
        db = PostgresDB()
        
        # Execute the query
        results = db.execute_query(sql)
        
        # Ensure "name" column is included
        if results and "name" not in results[0]:
            # If name is missing, modify the query to include it
            if "SELECT " in sql.upper() and " FROM " in sql.upper():
                # Insert name column into the SELECT clause
                select_part = sql.upper().split("SELECT ")[1].split(" FROM ")[0]
                if "*" not in select_part:
                    modified_sql = sql.replace(
                        "SELECT " + select_part, 
                        "SELECT name, " + select_part
                    )
                    # Re-run the query with name included
                    results = db.execute_query(modified_sql)
        
        return results
    except Exception as e:
        print(f"Error executing query: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description="Translate natural-language SFDC queries into SQL and optionally execute them."
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="Your natural-language SFDC query, e.g. \"List all closed-won opportunities over $100k.\""
    )
    parser.add_argument(
        "--execute", "-e",
        action="store_true",
        help="Execute the generated SQL query against the PostgreSQL database"
    )
    
    args = parser.parse_args()
    nl_query = " ".join(args.query)
    
    try:
        sql = translate(nl_query)
        
        if args.execute:
            execute_query(sql)
        else:
            print(sql)
            
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 