"""
API to MDL Converter - Main orchestrator for converting OpenAPI specs to AsteraMDL
"""
from typing import Dict, List, Optional, Any
from openapi_parser import OpenAPIParser, SchemaDefinition, EndpointDefinition
from mdl_builder import MDLSchemaBuilder


class APIToMDLConverter:
    """
    Convert OpenAPI specifications to AsteraMDL schema format
    
    This converter:
    1. Parses OpenAPI specs to extract schemas and endpoints
    2. Converts schemas to MDL models
    3. Optionally creates views for endpoints
    4. Infers relationships between models
    """
    
    def __init__(self, 
                 openapi_spec: Dict[str, Any],
                 catalog: str = "api",
                 schema: str = "public",
                 create_endpoint_views: bool = True,
                 infer_relationships: bool = True):
        """
        Initialize converter
        
        Args:
            openapi_spec: OpenAPI specification as dictionary
            catalog: MDL catalog name
            schema: MDL schema name
            create_endpoint_views: Whether to create views for API endpoints
            infer_relationships: Whether to automatically infer relationships
        """
        self.parser = OpenAPIParser(openapi_spec)
        self.builder = MDLSchemaBuilder(catalog=catalog, schema=schema)
        self.create_endpoint_views = create_endpoint_views
        self.infer_relationships = infer_relationships
        
        # Tracking
        self.schema_to_model: Dict[str, str] = {}  # OpenAPI schema -> MDL model name
        self.endpoint_to_schema: Dict[str, str] = {}  # Endpoint -> Response schema
        
    @classmethod
    def from_file(cls, 
                  filepath: str, 
                  catalog: str = "api",
                  schema: str = "public",
                  **kwargs) -> 'APIToMDLConverter':
        """Load from OpenAPI JSON file"""
        parser = OpenAPIParser.from_file(filepath)
        return cls(parser.spec, catalog, schema, **kwargs)
    
    @classmethod
    def from_url(cls,
                 url: str,
                 catalog: str = "api", 
                 schema: str = "public",
                 **kwargs) -> 'APIToMDLConverter':
        """Load from OpenAPI URL"""
        parser = OpenAPIParser.from_url(url)
        return cls(parser.spec, catalog, schema, **kwargs)
    
    def convert(self, 
                filter_schemas: Optional[List[str]] = None,
                filter_tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform the conversion
        
        Args:
            filter_schemas: Optional list of schema names to include (None = all)
            filter_tags: Optional list of endpoint tags to filter by (None = all)
            
        Returns:
            MDL schema as dictionary
        """
        # Parse OpenAPI spec
        print("Parsing OpenAPI specification...")
        self.parser.parse()
        self.parser.print_summary()
        
        # Convert schemas to models
        print("\nConverting schemas to MDL models...")
        self._convert_schemas(filter_schemas)
        
        # Create endpoint views
        if self.create_endpoint_views:
            print("\nCreating views for API endpoints...")
            self._create_endpoint_views(filter_tags)
        
        # Infer relationships
        if self.infer_relationships:
            print("\nInferring relationships between models...")
            self._infer_relationships()
        
        # Build and return MDL
        print("\nBuilding MDL schema...")
        self.builder.print_summary()
        
        return self.builder.build_mdl()
    
    def _convert_schemas(self, filter_schemas: Optional[List[str]] = None):
        """Convert OpenAPI schemas to MDL models"""
        schemas = self.parser.get_all_schemas()
        
        for schema in schemas:
            # Apply filter if specified
            if filter_schemas and schema.name not in filter_schemas:
                continue
            
            print(f"  Converting schema: {schema.name}")
            model = self.builder.add_model_from_schema(schema)
            self.schema_to_model[schema.name] = model.name
    
    def _create_endpoint_views(self, filter_tags: Optional[List[str]] = None):
        """Create views for API endpoints"""
        endpoints = self.parser.endpoints
        
        # Apply tag filter if specified
        if filter_tags:
            endpoints = [ep for ep in endpoints 
                        if any(tag in ep.tags for tag in filter_tags)]
        
        for endpoint in endpoints:
            # Get response schema for 200 response
            response_schema = self.parser.get_response_schema(endpoint)
            
            if response_schema and response_schema in self.schema_to_model:
                model_name = self.schema_to_model[response_schema]
                view_name = f"{endpoint.method}_{self._sanitize_path(endpoint.path)}"
                print(f"  Creating view: {view_name} -> {model_name}")
                
                self.builder.add_view_for_endpoint(endpoint, model_name)
                self.endpoint_to_schema[f"{endpoint.method} {endpoint.path}"] = response_schema
    
    def _infer_relationships(self):
        """Infer relationships between models based on naming patterns"""
        models = self.builder.models
        
        for model in models:
            for column in model.columns:
                # Look for foreign key patterns (e.g., org_id, project_id)
                if column.name.endswith('_id') and column.name != 'id':
                    # Extract referenced model name
                    ref_model_base = column.name[:-3]  # Remove '_id'
                    
                    # Try to find matching model
                    for target_model in models:
                        target_name_lower = target_model.name.lower()
                        
                        # Check if target model name matches the reference
                        if (target_name_lower == ref_model_base or
                            target_name_lower == ref_model_base + 's' or
                            target_name_lower == ref_model_base + 'es'):
                            
                            print(f"  Inferring relationship: {model.name}.{column.name} -> {target_model.name}.id")
                            
                            self.builder.infer_relationship(
                                from_model=model.name,
                                to_model=target_model.name,
                                foreign_key=column.name,
                                join_type="MANY_TO_ONE"
                            )
                            break
    
    def _sanitize_path(self, path: str) -> str:
        """Sanitize API path for use in names"""
        # Remove leading slash and replace special chars
        sanitized = path.lstrip('/')
        sanitized = sanitized.replace('/', '_').replace('{', '').replace('}', '')
        sanitized = sanitized.replace('-', '_')
        return sanitized
    
    def save(self, filepath: str, indent: int = 2):
        """Save MDL schema to file"""
        self.builder.save_to_file(filepath, indent)
    
    def get_mdl_json(self, indent: int = 2) -> str:
        """Get MDL schema as JSON string"""
        return self.builder.to_json(indent)
    
    def get_conversion_summary(self) -> Dict[str, Any]:
        """Get summary of conversion results"""
        return {
            'api_info': {
                'title': self.parser.spec.get('info', {}).get('title', 'Unknown'),
                'version': self.parser.spec.get('info', {}).get('version', 'Unknown'),
                'openapi_version': self.parser.spec.get('openapi', 'Unknown'),
            },
            'parsed': {
                'schemas': len(self.parser.schemas),
                'endpoints': len(self.parser.endpoints),
            },
            'converted': {
                'models': len(self.builder.models),
                'relationships': len(self.builder.relationships),
                'views': len(self.builder.views),
            },
            'mapping': {
                'schema_to_model': self.schema_to_model,
                'endpoint_to_schema': self.endpoint_to_schema,
            }
        }


class BatchConverter:
    """
    Batch converter for processing multiple OpenAPI specs
    """
    
    def __init__(self, catalog: str = "api"):
        """
        Initialize batch converter
        
        Args:
            catalog: Catalog name for all schemas
        """
        self.catalog = catalog
        self.converters: Dict[str, APIToMDLConverter] = {}
        
    def add_spec(self, 
                 name: str,
                 spec: Dict[str, Any],
                 schema: Optional[str] = None,
                 **kwargs):
        """
        Add an OpenAPI spec to the batch
        
        Args:
            name: Identifier for this spec
            spec: OpenAPI specification
            schema: Optional schema name (defaults to name)
            **kwargs: Additional arguments for converter
        """
        schema = schema or name
        converter = APIToMDLConverter(
            spec, 
            catalog=self.catalog,
            schema=schema,
            **kwargs
        )
        self.converters[name] = converter
        
    def add_from_file(self, name: str, filepath: str, **kwargs):
        """Add spec from file"""
        parser = OpenAPIParser.from_file(filepath)
        self.add_spec(name, parser.spec, **kwargs)
        
    def add_from_url(self, name: str, url: str, **kwargs):
        """Add spec from URL"""
        parser = OpenAPIParser.from_url(url)
        self.add_spec(name, parser.spec, **kwargs)
    
    def convert_all(self) -> Dict[str, Dict[str, Any]]:
        """Convert all specs"""
        results = {}
        
        for name, converter in self.converters.items():
            print(f"\n{'='*60}")
            print(f"Converting: {name}")
            print(f"{'='*60}")
            
            mdl = converter.convert()
            results[name] = {
                'mdl': mdl,
                'summary': converter.get_conversion_summary()
            }
            
        return results
    
    def save_all(self, output_dir: str = "."):
        """Save all converted schemas to separate files"""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        for name, converter in self.converters.items():
            filepath = os.path.join(output_dir, f"{name}_mdl.json")
            converter.save(filepath)
