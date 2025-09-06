#!/usr/bin/env python3
"""
Command-line interface for the QueryExecutor.
Usage: python cli.py --query "SELECT * FROM table" --database postgres --output my_executor.py
"""

import argparse
import sys
from pathlib import Path
from query_executor import QueryExecutor


def main():
    parser = argparse.ArgumentParser(
        description="Generate executable Python code from SQL query templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate PostgreSQL executor with custom query
  python cli.py --query "SELECT * FROM users WHERE active = true" --database postgres
  
  # Generate Trino executor with custom output file
  python cli.py --query "SELECT * FROM sales" --database trino --output sales_query.py
  
  # Generate deployment package with connection config
  python cli.py --query "SELECT * FROM analytics" --database postgres --deploy-package --connection-config config.json
  
  # Generate executor with inline connection parameters
  python cli.py --query "SELECT * FROM data" --database postgres --host localhost --port 5432 --user myuser --password mypass
        """
    )
    
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="SQL query to execute"
    )
    
    parser.add_argument(
        "--database", "-d",
        choices=["postgres", "trino"],
        required=True,
        help="Database type"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: auto-generated name)"
    )
    
    parser.add_argument(
        "--deploy-package",
        action="store_true",
        help="Generate complete deployment package instead of single file"
    )
    
    parser.add_argument(
        "--connection-config",
        help="Path to JSON file with connection configuration"
    )
    
    # Inline connection parameters for PostgreSQL
    parser.add_argument("--host", help="Database host")
    parser.add_argument("--port", type=int, help="Database port")
    parser.add_argument("--user", help="Database user")
    parser.add_argument("--password", help="Database password")
    parser.add_argument("--database-name", help="Database name (for PostgreSQL)")
    
    # Inline connection parameters for Trino
    parser.add_argument("--catalog", help="Trino catalog")
    parser.add_argument("--schema", help="Trino schema")
    
    parser.add_argument(
        "--no-requirements",
        action="store_true",
        help="Skip generating requirements.txt in deployment package"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Output directory for deployment package"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize executor
        executor = QueryExecutor()
        
        # Build connection configuration
        connection_config = {}
        
        if args.connection_config:
            # Load from JSON file
            import json
            with open(args.connection_config, 'r') as f:
                connection_config = json.load(f)
        else:
            # Build from inline arguments
            if args.database == "postgres":
                if args.host:
                    connection_config["host"] = args.host
                if args.port:
                    connection_config["port"] = args.port
                if args.user:
                    connection_config["user"] = args.user
                if args.password:
                    connection_config["password"] = args.password
                if args.database_name:
                    connection_config["database"] = args.database_name
            elif args.database == "trino":
                if args.host:
                    connection_config["host"] = args.host
                if args.port:
                    connection_config["port"] = args.port
                if args.user:
                    connection_config["user"] = args.user
                if args.catalog:
                    connection_config["catalog"] = args.catalog
                if args.schema:
                    connection_config["schema"] = args.schema
        
        if args.deploy_package:
            # Generate deployment package
            package_dir = executor.generate_deployment_package(
                query=args.query,
                database_type=args.database,
                connection_config=connection_config if connection_config else None,
                include_requirements=not args.no_requirements,
                output_dir=args.output_dir
            )
            print(f"✅ Deployment package generated successfully!")
            print(f"📁 Location: {package_dir}")
            print(f"🚀 To deploy, run: cd {package_dir} && ./deploy.sh")
            
        else:
            # Generate single executable file
            output_file = executor.generate_executable_code(
                query=args.query,
                database_type=args.database,
                output_file=args.output,
                connection_config=connection_config if connection_config else None
            )
            print(f"✅ Executable code generated successfully!")
            print(f"📁 File: {output_file}")
            print(f"🐍 Run with: python {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
