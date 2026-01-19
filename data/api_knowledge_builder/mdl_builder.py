"""
AsteraMDL Schema Builder - Converts OpenAPI schemas to AsteraMDL format
"""
from typing import Dict, List, Optional, Any
import json
from dataclasses import dataclass, asdict
from openapi_parser import SchemaDefinition, PropertySchema, EndpointDefinition


@dataclass
class MDLColumn:
    """Represents a column in MDL schema"""
    name: str
    type: str
    description: Optional[str] = None
    notNull: Optional[bool] = None
    isCalculated: Optional[bool] = None
    expression: Optional[str] = None
    relationship: Optional[str] = None
    properties: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        result = {}
        if self.name:
            result['name'] = self.name
        if self.type:
            result['type'] = self.type
        if self.description:
            if not self.properties:
                self.properties = {}
            self.properties['description'] = self.description
        if self.notNull is not None:
            result['notNull'] = self.notNull
        if self.isCalculated is not None:
            result['isCalculated'] = self.isCalculated
        if self.expression:
            result['expression'] = self.expression
        if self.relationship:
            result['relationship'] = self.relationship
        if self.properties:
            result['properties'] = self.properties
        return result


@dataclass
class MDLModel:
    """Represents a model in MDL schema"""
    name: str
    tableReference: Optional[Dict[str, str]] = None
    refSql: Optional[str] = None
    columns: List[MDLColumn] = None
    primaryKey: Optional[str] = None
    cached: Optional[bool] = None
    refreshTime: Optional[str] = None
    properties: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.columns is None:
            self.columns = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {'name': self.name}
        
        if self.tableReference:
            result['tableReference'] = self.tableReference
        if self.refSql:
            result['refSql'] = self.refSql
        if self.columns:
            result['columns'] = [col.to_dict() for col in self.columns]
        if self.primaryKey:
            result['primaryKey'] = self.primaryKey
        if self.cached is not None:
            result['cached'] = self.cached
        if self.refreshTime:
            result['refreshTime'] = self.refreshTime
        if self.properties:
            result['properties'] = self.properties
            
        return result


@dataclass
class MDLRelationship:
    """Represents a relationship in MDL schema"""
    name: str
    models: List[str]
    joinType: str  # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
    condition: str
    properties: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'name': self.name,
            'models': self.models,
            'joinType': self.joinType,
            'condition': self.condition
        }
        if self.properties:
            result['properties'] = self.properties
        return result


@dataclass
class MDLView:
    """Represents a view in MDL schema"""
    name: str
    statement: str
    properties: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'name': self.name,
            'statement': self.statement
        }
        if self.properties:
            result['properties'] = self.properties
        return result


class MDLSchemaBuilder:
    """Build AsteraMDL schemas from OpenAPI definitions"""
    
    def __init__(self, catalog: str = "api", schema: str = "public"):
        """
        Initialize MDL schema builder
        
        Args:
            catalog: Catalog name for MDL
            schema: Schema name for MDL
        """
        self.catalog = catalog
        self.schema = schema
        self.models: List[MDLModel] = []
        self.relationships: List[MDLRelationship] = []
        self.views: List[MDLView] = []
        
    def add_model_from_schema(self, 
                            schema_def: SchemaDefinition,
                            table_name: Optional[str] = None,
                            endpoint_info: Optional[Dict[str, Any]] = None) -> MDLModel:
        """
        Convert an OpenAPI schema definition to an MDL model
        
        Args:
            schema_def: OpenAPI schema definition
            table_name: Optional table name override
            endpoint_info: Optional endpoint metadata
        """
        model_name = self._sanitize_name(schema_def.name)
        
        # Convert properties to columns
        columns = []
        for prop in schema_def.properties:
            column = self._property_to_column(prop)
            columns.append(column)
        
        # Determine primary key
        pk_candidates = schema_def.get_primary_key_candidates()
        primary_key = pk_candidates[0] if pk_candidates else None
        
        # Build properties
        properties = {}
        if schema_def.description:
            properties['description'] = schema_def.description
        if endpoint_info:
            properties['source_endpoint'] = endpoint_info.get('path', '')
            properties['http_method'] = endpoint_info.get('method', '')
        
        # Create table reference or refSql
        table_ref = None
        ref_sql = None
        
        if table_name:
            table_ref = {
                'catalog': self.catalog,
                'schema': self.schema,
                'table': table_name
            }
        else:
            # Use refSql for API endpoint simulation
            ref_sql = f"SELECT * FROM {self.schema}.{model_name}"
        
        model = MDLModel(
            name=model_name,
            tableReference=table_ref,
            refSql=ref_sql,
            columns=columns,
            primaryKey=primary_key,
            properties=properties if properties else None
        )
        
        self.models.append(model)
        return model
    
    def add_view_for_endpoint(self, 
                            endpoint: EndpointDefinition,
                            response_model: str) -> MDLView:
        """
        Create a view that represents an API endpoint
        
        Args:
            endpoint: API endpoint definition
            response_model: Name of the response model
        """
        view_name = self._sanitize_name(
            endpoint.operation_id or f"{endpoint.method}_{endpoint.path}"
        )
        
        # Build SQL statement that simulates the endpoint
        statement = f"""
-- API Endpoint: {endpoint.method} {endpoint.path}
-- Response Model: {response_model}
SELECT * FROM {self.schema}.{self._sanitize_name(response_model)}
        """.strip()
        
        properties = {
            'endpoint_path': endpoint.path,
            'http_method': endpoint.method,
            'operation_id': endpoint.operation_id or '',
        }
        
        if endpoint.summary:
            properties['summary'] = endpoint.summary
        if endpoint.description:
            properties['description'] = endpoint.description
        
        view = MDLView(
            name=view_name,
            statement=statement,
            properties=properties
        )
        
        self.views.append(view)
        return view
    
    def infer_relationship(self,
                          from_model: str,
                          to_model: str,
                          foreign_key: str,
                          join_type: str = "MANY_TO_ONE") -> MDLRelationship:
        """
        Create a relationship between two models
        
        Args:
            from_model: Source model name
            to_model: Target model name
            foreign_key: Foreign key column name
            join_type: Type of join (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY)
        """
        rel_name = f"{from_model}_{to_model}"
        
        # Assume primary key is 'id' if not specified
        condition = f"{from_model}.{foreign_key} = {to_model}.id"
        
        relationship = MDLRelationship(
            name=rel_name,
            models=[from_model, to_model],
            joinType=join_type,
            condition=condition,
            properties={
                'foreign_key': foreign_key,
                'inferred': 'true'
            }
        )
        
        self.relationships.append(relationship)
        return relationship
    
    def _property_to_column(self, prop: PropertySchema) -> MDLColumn:
        """Convert a PropertySchema to an MDL Column"""
        mdl_type = prop.to_mdl_type()
        
        properties = {}
        if prop.format:
            properties['format'] = prop.format
        if prop.enum:
            properties['enum'] = ','.join(str(e) for e in prop.enum)
        
        # Handle array types
        if prop.type == 'array' and prop.items:
            properties['items_type'] = prop.items.get('type', 'string')
            if '$ref' in prop.items:
                properties['items_ref'] = prop.items['$ref'].split('/')[-1]
        
        # Handle object types
        if prop.type == 'object':
            if prop.properties:
                properties['nested_properties'] = 'true'
        
        return MDLColumn(
            name=prop.name,
            type=mdl_type,
            description=prop.description,
            notNull=prop.required,
            properties=properties if properties else None
        )
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize names for MDL compatibility"""
        # Replace special characters with underscores
        sanitized = name.replace('-', '_').replace('/', '_').replace('{', '').replace('}', '')
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return sanitized
    
    def build_mdl(self) -> Dict[str, Any]:
        """Build the complete MDL schema"""
        mdl = {
            'catalog': self.catalog,
            'schema': self.schema,
        }
        
        if self.models:
            mdl['models'] = [model.to_dict() for model in self.models]
        
        if self.relationships:
            mdl['relationships'] = [rel.to_dict() for rel in self.relationships]
        
        if self.views:
            mdl['views'] = [view.to_dict() for view in self.views]
        
        return mdl
    
    def to_json(self, indent: int = 2) -> str:
        """Convert MDL schema to JSON string"""
        return json.dumps(self.build_mdl(), indent=indent)
    
    def save_to_file(self, filepath: str, indent: int = 2):
        """Save MDL schema to a JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.build_mdl(), f, indent=indent)
        print(f"MDL schema saved to: {filepath}")
    
    def print_summary(self):
        """Print a summary of the MDL schema"""
        print(f"MDL Schema Summary")
        print(f"Catalog: {self.catalog}")
        print(f"Schema: {self.schema}")
        print(f"Models: {len(self.models)}")
        for model in self.models:
            print(f"  - {model.name}: {len(model.columns)} columns")
        print(f"Relationships: {len(self.relationships)}")
        for rel in self.relationships:
            print(f"  - {rel.name}: {rel.models[0]} -> {rel.models[1]} ({rel.joinType})")
        print(f"Views: {len(self.views)}")
        for view in self.views:
            print(f"  - {view.name}")
