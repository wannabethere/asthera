import os
import tempfile
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any
import uuid
from .template_manager import template_manager


class QueryExecutor:
    """
    A Python executor that generates executable code from query templates.
    Now supports dynamic template discovery and is easily extensible for new data sources.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the QueryExecutor.
        
        Args:
            template_dir: Directory containing template files. 
                         Defaults to the templates subdirectory.
        """
        self.template_manager = template_manager
        if template_dir:
            # Create a custom template manager if custom directory is specified
            from .template_manager import TemplateManager
            self.template_manager = TemplateManager(Path(template_dir))
    
    @property
    def supported_databases(self) -> List[str]:
        """Get list of supported database types."""
        return self.template_manager.list_templates()
    
    def list_available_templates(self) -> List[str]:
        """List all available template names."""
        return self.template_manager.list_templates()
    
    def get_template_info(self, database_type: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific template.
        
        Args:
            database_type: Type of database/template
            
        Returns:
            Template information dictionary or None if not found
        """
        return self.template_manager.get_template_info(database_type)
    
    def validate_template(self, database_type: str) -> bool:
        """
        Validate that a template is properly implemented.
        
        Args:
            database_type: Type of database/template
            
        Returns:
            True if template is valid, False otherwise
        """
        return self.template_manager.validate_template(database_type)
    
    def generate_executable_code(
        self, 
        query: str, 
        database_type: str,
        output_file: Optional[str] = None,
        connection_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate executable Python code from a template with the provided query.
        
        Args:
            query: SQL query to execute
            database_type: Type of database (e.g., 'postgres', 'trino', 'mysql')
            output_file: Optional output file path. If None, generates a temporary file.
            connection_config: Optional connection configuration to override template defaults
            
        Returns:
            Path to the generated executable file
        """
        # Check if template exists
        if database_type not in self.supported_databases:
            raise ValueError(f"Unsupported database type: {database_type}. "
                           f"Supported types: {self.supported_databases}")
        
        # Validate template
        if not self.validate_template(database_type):
            raise ValueError(f"Template {database_type} is not properly implemented")
        
        # Generate executable code using template manager
        executable_content = self.template_manager.create_template(
            database_type, query, connection_config
        )
        
        if not executable_content:
            raise RuntimeError(f"Failed to generate executable code for {database_type}")
        
        # Generate output file path
        if output_file is None:
            timestamp = uuid.uuid4().hex[:8]
            output_file = f"generated_{database_type}_executor_{timestamp}.py"
        
        # Write the generated code
        with open(output_file, 'w') as f:
            f.write(executable_content)
        
        return output_file, executable_content
    
    def generate_deployment_package(
        self, 
        query: str, 
        database_type: str,
        connection_config: Optional[Dict[str, Any]] = None,
        include_requirements: bool = True,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Generate a complete deployment package with requirements and executable.
        
        Args:
            query: SQL query to execute
            database_type: Type of database
            connection_config: Optional connection configuration
            include_requirements: Whether to include requirements.txt
            output_dir: Output directory for the package
            
        Returns:
            Path to the deployment package directory
        """
        if output_dir is None:
            output_dir = f"deployment_package_{database_type}_{uuid.uuid4().hex[:8]}"
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Generate the main executable
        executable_file = self.generate_executable_code(
            query, database_type, 
            output_file=output_path / f"main.py",
            connection_config=connection_config
        )
        
        # Generate requirements.txt if requested
        if include_requirements:
            requirements_file = output_path / "requirements.txt"
            self._generate_requirements(requirements_file, database_type)
        
        # Generate README
        readme_file = output_path / "README.md"
        self._generate_readme(readme_file, database_type, query)
        
        # Generate deployment script
        deploy_script = output_path / "deploy.sh"
        self._generate_deploy_script(deploy_script, database_type)
        
        # Generate template info
        info_file = output_path / "template_info.json"
        self._generate_template_info(info_file, database_type)
        
        return str(output_path)
    
    def _generate_requirements(self, requirements_file: Path, database_type: str):
        """Generate requirements.txt file using template information."""
        requirements = self.template_manager.get_requirements(database_type)
        
        with open(requirements_file, 'w') as f:
            f.write('\n'.join(requirements))
    
    def _generate_readme(self, readme_file: Path, database_type: str, query: str):
        """Generate README.md file."""
        template_info = self.template_manager.get_template_info(database_type)
        
        readme_content = f"""# {database_type.title()} Query Executor

This is an auto-generated Python executor for running SQL queries against a {database_type} database.

## Query
```sql
{query}
```

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure your database connection in `main.py`
3. Run the executor: `python main.py`

## Configuration
Edit the connection parameters in `main.py` to match your database setup.

## Connection Parameters
"""
        
        if template_info and "connection_parameters" in template_info:
            for param, meta in template_info["connection_parameters"].items():
                required = "Required" if meta.get("required", False) else "Optional"
                default = meta.get("default", "None")
                description = meta.get("description", "")
                readme_content += f"- **{param}** ({required}): {description} (Default: {default})\n"
        
        readme_content += f"""
## Deployment
Use the provided `deploy.sh` script for automated deployment on remote servers.

## Template Information
This executor was generated using the {database_type} template.
Check `template_info.json` for detailed template information.
"""
        
        with open(readme_file, 'w') as f:
            f.write(readme_content)
    
    def _generate_deploy_script(self, deploy_script: Path, database_type: str):
        """Generate deployment script."""
        script_content = f"""#!/bin/bash
# Deployment script for {database_type} query executor

echo "Deploying {database_type} query executor..."

# Install Python if not present
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Make executable
chmod +x main.py

echo "Deployment complete! Run with: python3 main.py"
"""
        
        with open(deploy_script, 'w') as f:
            f.write(script_content)
        
        # Make the script executable
        os.chmod(deploy_script, 0o755)
    
    def _generate_template_info(self, info_file: Path, database_type: str):
        """Generate template information file."""
        template_info = self.template_manager.get_template_info(database_type)
        
        if template_info:
            import json
            with open(info_file, 'w') as f:
                json.dump(template_info, f, indent=2)
    
    def add_custom_template(self, name: str, template_class):
        """
        Add a custom template to the executor.
        
        Args:
            name: Template name
            template_class: Template class that inherits from BaseTemplate
        """
        self.template_manager.register_template(name, template_class)
    
    def get_config_schema(self, database_type: str) -> Optional[Dict[str, Any]]:
        """
        Get JSON schema for template configuration.
        
        Args:
            database_type: Type of database
            
        Returns:
            JSON schema dictionary or None if template not found
        """
        return self.template_manager.get_config_schema(database_type)


def main():
    """Example usage of the QueryExecutor."""
    executor = QueryExecutor()
    
    print("🚀 QueryExecutor with Template System")
    print("=" * 50)
    
    # List available templates
    print(f"Available templates: {executor.list_available_templates()}")
    print()
    
    # Example query
    sample_query = """
    SELECT 
        customer_id,
        customer_name,
        total_orders,
        total_spent
    FROM customers 
    WHERE total_spent > 1000
    ORDER BY total_spent DESC
    LIMIT 10
    """
    
    # Example connection configuration
    postgres_config = {
        "host": "prod-db.company.com",
        "port": 5432,
        "database": "analytics",
        "user": "analytics_user",
        "password": "secure_password_123"
    }
    
    # Generate PostgreSQL executor
    print("Generating PostgreSQL executor...")
    postgres_file = executor.generate_executable_code(
        sample_query, "postgres", connection_config=postgres_config
    )
    print(f"Generated: {postgres_file}")
    
    # Generate Trino executor
    print("\nGenerating Trino executor...")
    trino_file = executor.generate_executable_code(
        sample_query, "trino"
    )
    print(f"Generated: {trino_file}")
    
    # Generate deployment package
    print("\nGenerating deployment package...")
    package_dir = executor.generate_deployment_package(
        sample_query, "postgres", connection_config=postgres_config
    )
    print(f"Deployment package created at: {package_dir}")
    
    # Show template information
    print("\nTemplate Information:")
    for template_name in executor.list_available_templates():
        info = executor.get_template_info(template_name)
        if info:
            print(f"\n{template_name.upper()}:")
            print(f"  Dependencies: {', '.join(info['dependencies'])}")
            print(f"  Connection Parameters: {list(info['connection_parameters'].keys())}")


if __name__ == "__main__":
    main()
