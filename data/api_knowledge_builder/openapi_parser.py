"""
OpenAPI Parser for extracting schema information from OpenAPI 3.x specifications.
"""
from typing import Dict, List, Optional, Any
import json
from dataclasses import dataclass, field
from enum import Enum


class SchemaType(Enum):
    """Schema types for mapping OpenAPI types to MDL types"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


@dataclass
class PropertySchema:
    """Represents a property in an OpenAPI schema"""
    name: str
    type: str
    description: Optional[str] = None
    format: Optional[str] = None
    required: bool = False
    nullable: bool = False
    enum: Optional[List[str]] = None
    items: Optional[Dict[str, Any]] = None  # For array types
    ref: Optional[str] = None  # For $ref references
    properties: Optional[Dict[str, Any]] = None  # For nested objects
    additional_properties: Optional[Dict[str, Any]] = None
    
    def to_mdl_type(self) -> str:
        """Convert OpenAPI type to MDL type"""
        type_mapping = {
            "string": "varchar",
            "integer": "integer",
            "number": "double",
            "boolean": "boolean",
            "array": "array",
            "object": "json",
        }
        
        # Handle format-specific types
        if self.format:
            format_mapping = {
                "date": "date",
                "date-time": "timestamp",
                "uuid": "varchar",
                "email": "varchar",
                "uri": "varchar",
                "int32": "integer",
                "int64": "bigint",
                "float": "float",
                "double": "double",
            }
            return format_mapping.get(self.format, type_mapping.get(self.type, "varchar"))
        
        return type_mapping.get(self.type, "varchar")


@dataclass
class SchemaDefinition:
    """Represents a schema definition (model) from OpenAPI"""
    name: str
    description: Optional[str] = None
    properties: List[PropertySchema] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    type: str = "object"
    
    def get_primary_key_candidates(self) -> List[str]:
        """Identify potential primary key fields"""
        pk_candidates = []
        for prop in self.properties:
            # Common primary key patterns
            if prop.name.lower() in ['id', 'uuid', 'key']:
                pk_candidates.append(prop.name)
            elif prop.name.lower().endswith('_id'):
                pk_candidates.append(prop.name)
        return pk_candidates


@dataclass
class EndpointDefinition:
    """Represents an API endpoint"""
    path: str
    method: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class OpenAPIParser:
    """Parse OpenAPI 3.x specifications and extract schema information"""
    
    def __init__(self, spec: Dict[str, Any]):
        """
        Initialize parser with OpenAPI spec
        
        Args:
            spec: OpenAPI specification as dictionary
        """
        self.spec = spec
        self.schemas: Dict[str, SchemaDefinition] = {}
        self.endpoints: List[EndpointDefinition] = []
        self.components = spec.get('components', {})
        self.schemas_raw = self.components.get('schemas', {})
        
    @classmethod
    def from_file(cls, filepath: str) -> 'OpenAPIParser':
        """Load OpenAPI spec from JSON file"""
        with open(filepath, 'r') as f:
            spec = json.load(f)
        return cls(spec)
    
    @classmethod
    def from_url(cls, url: str) -> 'OpenAPIParser':
        """Load OpenAPI spec from URL"""
        import requests
        response = requests.get(url)
        response.raise_for_status()
        spec = response.json()
        return cls(spec)
    
    def parse(self):
        """Parse the OpenAPI spec and extract schemas and endpoints"""
        self._parse_schemas()
        self._parse_endpoints()
        
    def _resolve_ref(self, ref: str) -> Optional[Dict[str, Any]]:
        """Resolve a $ref reference"""
        if not ref.startswith('#/'):
            return None
        
        parts = ref[2:].split('/')
        current = self.spec
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
                
        return current
    
    def _parse_property(self, name: str, prop_schema: Dict[str, Any], 
                       required: bool = False) -> PropertySchema:
        """Parse a property schema"""
        # Handle $ref
        if '$ref' in prop_schema:
            ref_schema = self._resolve_ref(prop_schema['$ref'])
            if ref_schema:
                prop_schema = {**ref_schema, **prop_schema}
        
        # Handle allOf, oneOf, anyOf (simplified - take first)
        if 'allOf' in prop_schema:
            base_schema = {}
            for schema in prop_schema['allOf']:
                if '$ref' in schema:
                    resolved = self._resolve_ref(schema['$ref'])
                    if resolved:
                        base_schema.update(resolved)
                else:
                    base_schema.update(schema)
            prop_schema = {**base_schema, **prop_schema}
        
        prop_type = prop_schema.get('type', 'string')
        
        # Handle array items
        items = None
        if prop_type == 'array' and 'items' in prop_schema:
            items = prop_schema['items']
        
        # Handle nested properties
        properties = None
        if prop_type == 'object' and 'properties' in prop_schema:
            properties = prop_schema['properties']
        
        return PropertySchema(
            name=name,
            type=prop_type,
            description=prop_schema.get('description'),
            format=prop_schema.get('format'),
            required=required,
            nullable=prop_schema.get('nullable', False),
            enum=prop_schema.get('enum'),
            items=items,
            ref=prop_schema.get('$ref'),
            properties=properties,
            additional_properties=prop_schema.get('additionalProperties')
        )
    
    def _parse_schemas(self):
        """Parse component schemas into SchemaDefinitions"""
        for schema_name, schema_def in self.schemas_raw.items():
            if schema_def.get('type') != 'object':
                continue
            
            properties = []
            required_fields = schema_def.get('required', [])
            
            for prop_name, prop_schema in schema_def.get('properties', {}).items():
                prop = self._parse_property(
                    prop_name, 
                    prop_schema,
                    required=prop_name in required_fields
                )
                properties.append(prop)
            
            schema = SchemaDefinition(
                name=schema_name,
                description=schema_def.get('description'),
                properties=properties,
                required_fields=required_fields,
                type=schema_def.get('type', 'object')
            )
            
            self.schemas[schema_name] = schema
    
    def _parse_endpoints(self):
        """Parse API endpoints/paths"""
        paths = self.spec.get('paths', {})
        
        for path, path_item in paths.items():
            for method in ['get', 'post', 'put', 'patch', 'delete']:
                if method not in path_item:
                    continue
                
                operation = path_item[method]
                
                endpoint = EndpointDefinition(
                    path=path,
                    method=method.upper(),
                    operation_id=operation.get('operationId'),
                    summary=operation.get('summary'),
                    description=operation.get('description'),
                    parameters=operation.get('parameters', []),
                    request_body=operation.get('requestBody'),
                    responses=operation.get('responses', {}),
                    tags=operation.get('tags', [])
                )
                
                self.endpoints.append(endpoint)
    
    def get_schema(self, name: str) -> Optional[SchemaDefinition]:
        """Get a specific schema by name"""
        return self.schemas.get(name)
    
    def get_all_schemas(self) -> List[SchemaDefinition]:
        """Get all parsed schemas"""
        return list(self.schemas.values())
    
    def get_endpoints_by_tag(self, tag: str) -> List[EndpointDefinition]:
        """Get endpoints filtered by tag"""
        return [ep for ep in self.endpoints if tag in ep.tags]
    
    def get_response_schema(self, endpoint: EndpointDefinition, 
                          status_code: str = '200') -> Optional[str]:
        """Extract the schema reference from an endpoint response"""
        response = endpoint.responses.get(status_code)
        if not response:
            return None
        
        content = response.get('content', {})
        json_content = content.get('application/json', {})
        schema = json_content.get('schema', {})
        
        # Handle direct $ref
        if '$ref' in schema:
            ref = schema['$ref']
            return ref.split('/')[-1]
        
        # Handle data.items pattern (common in JSON:API)
        if 'properties' in schema:
            data_prop = schema.get('properties', {}).get('data', {})
            if 'items' in data_prop:
                ref = data_prop['items'].get('$ref', '')
                if ref:
                    return ref.split('/')[-1]
            elif '$ref' in data_prop:
                ref = data_prop['$ref']
                return ref.split('/')[-1]
        
        return None
    
    def print_summary(self):
        """Print a summary of parsed schemas and endpoints"""
        print(f"OpenAPI Version: {self.spec.get('openapi', 'Unknown')}")
        print(f"API Title: {self.spec.get('info', {}).get('title', 'Unknown')}")
        print(f"API Version: {self.spec.get('info', {}).get('version', 'Unknown')}")
        print(f"\nSchemas found: {len(self.schemas)}")
        for name, schema in self.schemas.items():
            print(f"  - {name}: {len(schema.properties)} properties")
        print(f"\nEndpoints found: {len(self.endpoints)}")
        for endpoint in self.endpoints[:5]:  # Show first 5
            print(f"  - {endpoint.method} {endpoint.path}")
        if len(self.endpoints) > 5:
            print(f"  ... and {len(self.endpoints) - 5} more")
