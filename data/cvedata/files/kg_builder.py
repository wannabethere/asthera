"""
Knowledge Graph Builder for Vulnerability Analytics
====================================================

This module reads JSON schema definitions and builds a comprehensive knowledge graph
in ChromaDB that encodes:
1. Entity schemas (Assets, Software, Vulnerabilities)
2. Attribute relationships and dependencies
3. Calculation paths (how to compute risk, exploitability, impact, etc.)
4. Function call planning (which functions need which attributes)
5. All possible query paths from entities to calculations

The graph enables automatic SQL function planning and query generation.

Author: Vulnerability Analytics Team
Date: 2024-11-29
"""

import json
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

@dataclass
class EntitySchema:
    """Represents the schema of an entity (Asset, Software, Vulnerability)"""
    entity_name: str
    entity_type: str
    description: str
    primary_key: List[str]
    attributes: List[Dict[str, Any]]
    attribute_groups: Dict[str, List[str]]
    
    def get_attribute_names(self) -> List[str]:
        """Get all attribute names"""
        return [attr["name"] for attr in self.attributes]
    
    def get_attributes_by_group(self, group_name: str) -> List[str]:
        """Get attributes in a specific group"""
        return self.attribute_groups.get(group_name, [])
    
    def to_document(self) -> str:
        """Convert to natural language document for embedding"""
        doc = f"""
Entity: {self.entity_name}
Type: {self.entity_type}
Description: {self.description}
Primary Key: {', '.join(self.primary_key)}

Attributes ({len(self.attributes)} total):
"""
        for attr in self.attributes[:20]:  # First 20 for embedding
            doc += f"- {attr['name']} ({attr.get('type', 'unknown')}): {attr.get('description', '')}\n"
        
        doc += f"\nAttribute Groups: {', '.join(self.attribute_groups.keys())}"
        return doc
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata"""
        return {
            "entity_type": "EntitySchema",
            "entity_name": self.entity_name,
            "schema_type": self.entity_type,
            "attribute_count": len(self.attributes),
            "primary_key": json.dumps(self.primary_key),
            "attribute_groups": json.dumps(list(self.attribute_groups.keys()))
        }


@dataclass
class CalculationPath:
    """Represents a path from entity attributes to a calculated value"""
    path_id: str
    path_name: str
    description: str
    calculation_type: str  # risk, exploitability, impact, likelihood, etc.
    
    # Source information
    source_entity: str
    source_attributes: List[str]
    
    # Intermediate steps
    intermediate_calculations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Target calculation
    target_function: str
    function_parameters: Dict[str, str]
    output_name: str
    output_type: str
    
    # Dependencies
    requires_entities: List[str] = field(default_factory=list)
    requires_attributes: List[str] = field(default_factory=list)
    requires_functions: List[str] = field(default_factory=list)
    
    # SQL information
    sql_pattern: str = ""
    joins_required: List[str] = field(default_factory=list)
    
    def to_document(self) -> str:
        """Convert to natural language document for embedding"""
        doc = f"""
Calculation Path: {self.path_name}
ID: {self.path_id}
Type: {self.calculation_type}
Description: {self.description}

Source: {self.source_entity}
Required Attributes: {', '.join(self.source_attributes)}

Calculation Flow:
"""
        for i, step in enumerate(self.intermediate_calculations, 1):
            doc += f"{i}. {step.get('description', step.get('function', 'Unknown step'))}\n"
        
        doc += f"\nFinal Calculation: {self.target_function}({', '.join(self.function_parameters.keys())})\n"
        doc += f"Output: {self.output_name} ({self.output_type})\n"
        doc += f"\nDependencies:\n"
        doc += f"- Entities: {', '.join(self.requires_entities)}\n"
        doc += f"- Functions: {', '.join(self.requires_functions)}\n"
        
        return doc
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata"""
        return {
            "entity_type": "CalculationPath",
            "path_id": self.path_id,
            "path_name": self.path_name,
            "calculation_type": self.calculation_type,
            "source_entity": self.source_entity,
            "target_function": self.target_function,
            "output_name": self.output_name,
            "requires_entities": json.dumps(self.requires_entities),
            "requires_functions": json.dumps(self.requires_functions),
            "source_attributes": json.dumps(self.source_attributes)
        }


@dataclass
class FunctionDefinition:
    """Represents a SQL function that performs calculations"""
    function_name: str
    description: str
    purpose: str
    
    # Parameters
    parameters: List[Dict[str, Any]]
    return_type: str
    
    # Usage information
    use_cases: List[str]
    example_call: str
    
    # Attribute mapping
    required_attributes: Dict[str, List[str]]  # entity -> [attributes]
    
    def to_document(self) -> str:
        """Convert to natural language document for embedding"""
        doc = f"""
Function: {self.function_name}
Purpose: {self.purpose}
Description: {self.description}

Parameters ({len(self.parameters)}):
"""
        for param in self.parameters:
            doc += f"- {param['name']} ({param['type']}): {param.get('description', '')}\n"
        
        doc += f"\nReturns: {self.return_type}\n"
        doc += f"\nUse Cases:\n"
        for use_case in self.use_cases:
            doc += f"- {use_case}\n"
        
        doc += f"\nExample: {self.example_call}\n"
        
        doc += f"\nRequired Attributes:\n"
        for entity, attrs in self.required_attributes.items():
            doc += f"- {entity}: {', '.join(attrs)}\n"
        
        return doc
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata"""
        return {
            "entity_type": "FunctionDefinition",
            "function_name": self.function_name,
            "return_type": self.return_type,
            "parameter_count": len(self.parameters),
            "use_cases": json.dumps(self.use_cases),
            "required_entities": json.dumps(list(self.required_attributes.keys()))
        }


@dataclass
class AttributeDependency:
    """Represents dependency between attributes and calculations"""
    attribute_name: str
    entity_name: str
    attribute_type: str
    
    # What this attribute enables
    enables_functions: List[str] = field(default_factory=list)
    enables_calculations: List[str] = field(default_factory=list)
    
    # What this attribute requires
    depends_on_attributes: List[str] = field(default_factory=list)
    depends_on_entities: List[str] = field(default_factory=list)
    
    # Metadata enrichment
    enriched_by_metadata: Optional[str] = None
    
    def to_document(self) -> str:
        """Convert to natural language document for embedding"""
        doc = f"""
Attribute: {self.entity_name}.{self.attribute_name}
Type: {self.attribute_type}

This attribute enables:
- Functions: {', '.join(self.enables_functions) if self.enables_functions else 'None'}
- Calculations: {', '.join(self.enables_calculations) if self.enables_calculations else 'None'}

Dependencies:
- Requires attributes: {', '.join(self.depends_on_attributes) if self.depends_on_attributes else 'None'}
- Requires entities: {', '.join(self.depends_on_entities) if self.depends_on_entities else 'None'}

Metadata enrichment: {self.enriched_by_metadata or 'None'}
"""
        return doc
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB metadata"""
        return {
            "entity_type": "AttributeDependency",
            "attribute_name": self.attribute_name,
            "entity_name": self.entity_name,
            "attribute_type": self.attribute_type,
            "enables_functions": json.dumps(self.enables_functions),
            "enables_calculations": json.dumps(self.enables_calculations)
        }


# =============================================================================
# KNOWLEDGE GRAPH BUILDER
# =============================================================================

class KnowledgeGraphBuilder:
    """Builds knowledge graph from JSON schema definitions"""
    
    def __init__(self, persist_directory: str = "./chromadb_kg_builder"):
        """Initialize ChromaDB client and collections"""
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory
        ))
        
        # Create collections
        self.collections = {
            "entity_schemas": self._get_or_create_collection("kg_entity_schemas"),
            "calculation_paths": self._get_or_create_collection("kg_calculation_paths"),
            "function_definitions": self._get_or_create_collection("kg_function_definitions"),
            "attribute_dependencies": self._get_or_create_collection("kg_attribute_dependencies"),
            "query_patterns": self._get_or_create_collection("kg_query_patterns")
        }
        
        # Storage for loaded data
        self.entity_schemas: Dict[str, EntitySchema] = {}
        self.function_definitions: Dict[str, FunctionDefinition] = {}
        self.calculation_paths: List[CalculationPath] = []
        self.attribute_dependencies: List[AttributeDependency] = []
        
        logger.info("KnowledgeGraphBuilder initialized")
    
    def _get_or_create_collection(self, name: str):
        """Get existing collection or create new one"""
        try:
            return self.client.get_collection(name)
        except:
            return self.client.create_collection(name)
    
    # =========================================================================
    # LOAD SCHEMAS FROM JSON
    # =========================================================================
    
    def load_entity_schema(self, json_path: str) -> EntitySchema:
        """Load entity schema from JSON file"""
        with open(json_path, 'r') as f:
            schema_data = json.load(f)
        
        # Parse schema
        entity_name = schema_data.get("entity_name", Path(json_path).stem)
        entity_type = schema_data.get("type", "unknown")
        description = schema_data.get("description", "")
        primary_key = schema_data.get("primary_key", [])
        
        # Parse attributes
        attributes = []
        if "properties" in schema_data:
            for attr_name, attr_def in schema_data["properties"].items():
                attributes.append({
                    "name": attr_name,
                    "type": attr_def.get("type", "unknown"),
                    "description": attr_def.get("description", ""),
                    "format": attr_def.get("format"),
                    "enum": attr_def.get("enum"),
                    "items": attr_def.get("items")
                })
        
        # Group attributes by category
        attribute_groups = self._categorize_attributes(attributes)
        
        schema = EntitySchema(
            entity_name=entity_name,
            entity_type=entity_type,
            description=description,
            primary_key=primary_key,
            attributes=attributes,
            attribute_groups=attribute_groups
        )
        
        self.entity_schemas[entity_name] = schema
        logger.info(f"Loaded entity schema: {entity_name} with {len(attributes)} attributes")
        
        return schema
    
    def _categorize_attributes(self, attributes: List[Dict]) -> Dict[str, List[str]]:
        """Categorize attributes into logical groups"""
        groups = {
            "identifiers": [],
            "scores": [],
            "temporal": [],
            "network": [],
            "risk": [],
            "likelihood": [],
            "impact": [],
            "cvss_components": [],
            "configuration": [],
            "location": [],
            "classification": [],
            "metadata": []
        }
        
        for attr in attributes:
            name = attr["name"].lower()
            
            # Categorize based on name patterns
            if any(x in name for x in ["id", "key", "nuid", "dev_id", "pk"]):
                groups["identifiers"].append(attr["name"])
            
            elif any(x in name for x in ["score", "basescore", "gtm"]):
                groups["scores"].append(attr["name"])
            
            elif any(x in name for x in ["time", "date", "days", "dwell", "age"]):
                groups["temporal"].append(attr["name"])
            
            elif any(x in name for x in ["ip", "mac", "port", "network", "zone", "bastion", "propagation"]):
                groups["network"].append(attr["name"])
            
            elif "risk" in name and "likelihood" not in name:
                groups["risk"].append(attr["name"])
            
            elif "likelihood" in name:
                groups["likelihood"].append(attr["name"])
            
            elif "impact" in name:
                groups["impact"].append(attr["name"])
            
            elif any(x in name for x in ["attack_vector", "attack_complexity", "privileges", "user_interaction", 
                                          "scope", "confidentiality", "integrity", "availability"]):
                groups["cvss_components"].append(attr["name"])
            
            elif any(x in name for x in ["config", "smb", "secure_boot", "power_shell", "policy"]):
                groups["configuration"].append(attr["name"])
            
            elif any(x in name for x in ["location", "region", "country", "city", "site"]):
                groups["location"].append(attr["name"])
            
            elif any(x in name for x in ["class", "type", "category", "platform", "os_", "device_type"]):
                groups["classification"].append(attr["name"])
            
            else:
                groups["metadata"].append(attr["name"])
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    def load_function_definitions(self, json_path: str):
        """Load function definitions from JSON file"""
        with open(json_path, 'r') as f:
            functions_data = json.load(f)
        
        for func_name, func_def in functions_data.get("functions", {}).items():
            function = FunctionDefinition(
                function_name=func_name,
                description=func_def.get("description", ""),
                purpose=func_def.get("purpose", ""),
                parameters=func_def.get("parameters", []),
                return_type=func_def.get("return_type", "DECIMAL"),
                use_cases=func_def.get("use_cases", []),
                example_call=func_def.get("example_call", ""),
                required_attributes=func_def.get("required_attributes", {})
            )
            
            self.function_definitions[func_name] = function
            logger.info(f"Loaded function definition: {func_name}")
    
    # =========================================================================
    # BUILD CALCULATION PATHS
    # =========================================================================
    
    def build_calculation_paths(self):
        """Automatically discover and build all calculation paths"""
        logger.info("Building calculation paths...")
        
        # Build paths for each function
        for func_name, func_def in self.function_definitions.items():
            paths = self._build_paths_for_function(func_def)
            self.calculation_paths.extend(paths)
        
        # Build composite paths (multi-function calculations)
        composite_paths = self._build_composite_paths()
        self.calculation_paths.extend(composite_paths)
        
        logger.info(f"Built {len(self.calculation_paths)} calculation paths")
    
    def _build_paths_for_function(self, func_def: FunctionDefinition) -> List[CalculationPath]:
        """Build calculation paths for a specific function"""
        paths = []
        
        # For each entity that has required attributes
        for entity_name, required_attrs in func_def.required_attributes.items():
            if entity_name not in self.entity_schemas:
                continue
            
            entity_schema = self.entity_schemas[entity_name]
            
            # Check if entity has all required attributes
            entity_attrs = set(entity_schema.get_attribute_names())
            if not all(attr in entity_attrs for attr in required_attrs):
                continue
            
            # Determine calculation type
            calc_type = self._determine_calculation_type(func_def.function_name)
            
            # Build parameter mapping
            param_mapping = {}
            for param in func_def.parameters:
                param_name = param["name"]
                # Map parameter to entity attribute
                matching_attr = self._find_matching_attribute(param_name, required_attrs)
                if matching_attr:
                    param_mapping[param_name] = f"{entity_name}.{matching_attr}"
            
            # Create path
            path = CalculationPath(
                path_id=f"{entity_name}_to_{func_def.function_name}",
                path_name=f"{entity_name} → {func_def.function_name.replace('calculate_', '').replace('_', ' ').title()}",
                description=f"Calculate {func_def.function_name} from {entity_name} attributes",
                calculation_type=calc_type,
                source_entity=entity_name,
                source_attributes=required_attrs,
                target_function=func_def.function_name,
                function_parameters=param_mapping,
                output_name=func_def.function_name.replace("calculate_", "") + "_score",
                output_type=func_def.return_type,
                requires_entities=[entity_name],
                requires_attributes=required_attrs,
                requires_functions=[func_def.function_name]
            )
            
            paths.append(path)
        
        return paths
    
    def _build_composite_paths(self) -> List[CalculationPath]:
        """Build composite calculation paths that use multiple functions"""
        composite_paths = []
        
        # Example: Comprehensive Risk Score
        # Requires: exploitability_score + impact_score + time_weighted_stats
        
        if "calculate_exploitability_score" in self.function_definitions and \
           "calculate_impact_score" in self.function_definitions:
            
            # Find entity that has both CVSS attack and impact attributes
            for entity_name, entity_schema in self.entity_schemas.items():
                attrs = set(entity_schema.get_attribute_names())
                
                has_attack_attrs = any(attr in attrs for attr in 
                    ["attack_vector", "attack_complexity", "privileges_required", "user_interaction"])
                has_impact_attrs = any(attr in attrs for attr in 
                    ["confidentiality_impact", "integrity_impact", "availability_impact"])
                
                if has_attack_attrs and has_impact_attrs:
                    path = CalculationPath(
                        path_id=f"{entity_name}_to_comprehensive_risk",
                        path_name=f"{entity_name} → Comprehensive Risk Score",
                        description=f"Calculate comprehensive risk combining exploitability, impact, and time factors",
                        calculation_type="comprehensive_risk",
                        source_entity=entity_name,
                        source_attributes=list(entity_schema.get_attributes_by_group("cvss_components")),
                        intermediate_calculations=[
                            {
                                "step": 1,
                                "function": "calculate_exploitability_score",
                                "description": "Calculate exploitability from CVSS attack metrics"
                            },
                            {
                                "step": 2,
                                "function": "calculate_impact_score",
                                "description": "Calculate impact from CVSS impact metrics"
                            },
                            {
                                "step": 3,
                                "function": "calculate_time_weighted_stats",
                                "description": "Apply time-weighted decay to risk scores"
                            }
                        ],
                        target_function="comprehensive_risk_calculation",
                        function_parameters={},
                        output_name="comprehensive_risk_score",
                        output_type="DECIMAL",
                        requires_entities=[entity_name],
                        requires_attributes=list(entity_schema.get_attributes_by_group("cvss_components")),
                        requires_functions=["calculate_exploitability_score", "calculate_impact_score", "calculate_time_weighted_stats"],
                        sql_pattern="SELECT *, calculate_exploitability_score(...) as exploit, calculate_impact_score(...) as impact FROM ..."
                    )
                    composite_paths.append(path)
        
        return composite_paths
    
    def _determine_calculation_type(self, function_name: str) -> str:
        """Determine calculation type from function name"""
        if "exploitability" in function_name:
            return "exploitability"
        elif "impact" in function_name:
            return "impact"
        elif "breach" in function_name or "likelihood" in function_name:
            return "breach_likelihood"
        elif "time_weighted" in function_name:
            return "time_series"
        elif "risk" in function_name:
            return "risk"
        else:
            return "calculation"
    
    def _find_matching_attribute(self, param_name: str, available_attrs: List[str]) -> Optional[str]:
        """Find attribute that matches parameter name"""
        param_lower = param_name.lower().replace("p_", "").replace("_weight", "")
        
        for attr in available_attrs:
            attr_lower = attr.lower()
            if param_lower in attr_lower or attr_lower in param_lower:
                return attr
        
        return None
    
    # =========================================================================
    # BUILD ATTRIBUTE DEPENDENCIES
    # =========================================================================
    
    def build_attribute_dependencies(self):
        """Build attribute dependency graph"""
        logger.info("Building attribute dependencies...")
        
        for entity_name, entity_schema in self.entity_schemas.items():
            for attr in entity_schema.attributes:
                attr_name = attr["name"]
                
                # Find which functions this attribute enables
                enables_functions = []
                enables_calculations = []
                
                for func_name, func_def in self.function_definitions.items():
                    if entity_name in func_def.required_attributes:
                        if attr_name in func_def.required_attributes[entity_name]:
                            enables_functions.append(func_name)
                
                # Find which calculation paths use this attribute
                for path in self.calculation_paths:
                    if entity_name == path.source_entity and attr_name in path.source_attributes:
                        enables_calculations.append(path.path_id)
                
                # Create dependency
                if enables_functions or enables_calculations:
                    dependency = AttributeDependency(
                        attribute_name=attr_name,
                        entity_name=entity_name,
                        attribute_type=attr.get("type", "unknown"),
                        enables_functions=enables_functions,
                        enables_calculations=enables_calculations
                    )
                    self.attribute_dependencies.append(dependency)
        
        logger.info(f"Built {len(self.attribute_dependencies)} attribute dependencies")
    
    # =========================================================================
    # STORE IN CHROMADB
    # =========================================================================
    
    def store_knowledge_graph(self):
        """Store all knowledge graph components in ChromaDB"""
        logger.info("Storing knowledge graph in ChromaDB...")
        
        # Store entity schemas
        for entity_name, schema in self.entity_schemas.items():
            self.collections["entity_schemas"].add(
                documents=[schema.to_document()],
                metadatas=[schema.to_metadata()],
                ids=[f"schema_{entity_name}"]
            )
        
        # Store function definitions
        for func_name, func_def in self.function_definitions.items():
            self.collections["function_definitions"].add(
                documents=[func_def.to_document()],
                metadatas=[func_def.to_metadata()],
                ids=[f"function_{func_name}"]
            )
        
        # Store calculation paths
        for path in self.calculation_paths:
            self.collections["calculation_paths"].add(
                documents=[path.to_document()],
                metadatas=[path.to_metadata()],
                ids=[path.path_id]
            )
        
        # Store attribute dependencies
        for i, dep in enumerate(self.attribute_dependencies):
            self.collections["attribute_dependencies"].add(
                documents=[dep.to_document()],
                metadatas=[dep.to_metadata()],
                ids=[f"attr_dep_{dep.entity_name}_{dep.attribute_name}_{i}"]
            )
        
        logger.info("Knowledge graph stored successfully")
    
    # =========================================================================
    # QUERY KNOWLEDGE GRAPH
    # =========================================================================
    
    def find_calculation_paths(self, query: str, n_results: int = 5) -> Dict:
        """Find calculation paths relevant to query"""
        return self.collections["calculation_paths"].query(
            query_texts=[query],
            n_results=n_results
        )
    
    def find_required_attributes(self, calculation_type: str) -> List[str]:
        """Find attributes required for a calculation type"""
        results = self.collections["calculation_paths"].query(
            query_texts=[calculation_type],
            n_results=10,
            where={"calculation_type": calculation_type}
        )
        
        required_attrs = set()
        for metadata in results.get("metadatas", []):
            attrs = json.loads(metadata.get("source_attributes", "[]"))
            required_attrs.update(attrs)
        
        return list(required_attrs)
    
    def find_functions_for_entity(self, entity_name: str) -> List[str]:
        """Find all functions that can be calculated from an entity"""
        results = self.collections["calculation_paths"].query(
            query_texts=[f"{entity_name} calculations"],
            n_results=20,
            where={"source_entity": entity_name}
        )
        
        functions = set()
        for metadata in results.get("metadatas", []):
            func = metadata.get("target_function")
            if func:
                functions.add(func)
        
        return list(functions)
    
    # =========================================================================
    # EXPORT KNOWLEDGE GRAPH
    # =========================================================================
    
    def export_graph_summary(self, output_path: str):
        """Export knowledge graph summary to JSON"""
        summary = {
            "entities": {
                name: {
                    "type": schema.entity_type,
                    "attribute_count": len(schema.attributes),
                    "attribute_groups": list(schema.attribute_groups.keys())
                }
                for name, schema in self.entity_schemas.items()
            },
            "functions": {
                name: {
                    "purpose": func.purpose,
                    "parameter_count": len(func.parameters),
                    "return_type": func.return_type
                }
                for name, func in self.function_definitions.items()
            },
            "calculation_paths": [
                {
                    "path_id": path.path_id,
                    "path_name": path.path_name,
                    "calculation_type": path.calculation_type,
                    "source_entity": path.source_entity,
                    "target_function": path.target_function,
                    "requires_functions": path.requires_functions
                }
                for path in self.calculation_paths
            ],
            "statistics": {
                "total_entities": len(self.entity_schemas),
                "total_functions": len(self.function_definitions),
                "total_paths": len(self.calculation_paths),
                "total_dependencies": len(self.attribute_dependencies)
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Exported graph summary to {output_path}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function"""
    
    # Initialize builder
    builder = KnowledgeGraphBuilder(persist_directory="./chromadb_kg_builder")
    
    # Load entity schemas from uploaded JSON files
    # (Assuming JSON schema files are available)
    entity_schemas = [
        "assets_schema.json",
        "vulnerability_instances_schema.json",
        "software_instances_schema.json",
        "misconfig_schema.json",
        "fix_instances_schema.json"
    ]
    
    print("=" * 80)
    print("VULNERABILITY ANALYTICS KNOWLEDGE GRAPH BUILDER")
    print("=" * 80)
    
    # Example: Load from sample data structure
    # In production, load from actual JSON files
    print("\n1. Loading entity schemas...")
    
    # Example: Create sample schemas programmatically
    # (In production, use builder.load_entity_schema(json_path))
    
    # Asset schema
    asset_schema = EntitySchema(
        entity_name="Asset",
        entity_type="entity",
        description="Physical or virtual computing resources",
        primary_key=["nuid", "dev_id"],
        attributes=[
            {"name": "nuid", "type": "integer", "description": "Network unique identifier"},
            {"name": "dev_id", "type": "integer", "description": "Device identifier"},
            {"name": "host_name", "type": "string", "description": "Asset hostname"},
            {"name": "ip", "type": "string", "description": "IP address"},
            {"name": "device_type", "type": "string", "description": "Device type"},
            {"name": "platform", "type": "string", "description": "Operating system platform"},
            {"name": "impact_class", "type": "string", "description": "Impact classification"},
            {"name": "propagation_class", "type": "string", "description": "Network propagation class"},
            {"name": "effective_risk", "type": "number", "description": "Effective risk score"},
            {"name": "unpatched_vulnerability_likelihood", "type": "number", "description": "Likelihood of unpatched vulnerabilities"},
            {"name": "weak_credentials_likelihood", "type": "number", "description": "Likelihood of weak credentials"},
            {"name": "misconfiguration_likelihood", "type": "number", "description": "Likelihood of misconfigurations"}
        ],
        attribute_groups={
            "identifiers": ["nuid", "dev_id", "host_name", "ip"],
            "classification": ["device_type", "platform", "impact_class", "propagation_class"],
            "risk": ["effective_risk"],
            "likelihood": ["unpatched_vulnerability_likelihood", "weak_credentials_likelihood", "misconfiguration_likelihood"]
        }
    )
    builder.entity_schemas["Asset"] = asset_schema
    
    # Vulnerability schema
    vuln_schema = EntitySchema(
        entity_name="Vulnerability",
        entity_type="entity",
        description="Security vulnerabilities (CVEs)",
        primary_key=["cve_id", "nuid", "dev_id", "instance_id"],
        attributes=[
            {"name": "cve_id", "type": "string", "description": "CVE identifier"},
            {"name": "nuid", "type": "integer", "description": "Asset network unique identifier"},
            {"name": "dev_id", "type": "integer", "description": "Asset device identifier"},
            {"name": "instance_id", "type": "string", "description": "Vulnerability instance ID"},
            {"name": "severity", "type": "string", "description": "Severity level"},
            {"name": "cvssv3_basescore", "type": "number", "description": "CVSS v3 base score"},
            {"name": "attack_vector", "type": "string", "description": "CVSS attack vector"},
            {"name": "attack_complexity", "type": "string", "description": "CVSS attack complexity"},
            {"name": "privileges_required", "type": "string", "description": "CVSS privileges required"},
            {"name": "user_interaction", "type": "string", "description": "CVSS user interaction"},
            {"name": "confidentiality_impact", "type": "string", "description": "CVSS confidentiality impact"},
            {"name": "integrity_impact", "type": "string", "description": "CVSS integrity impact"},
            {"name": "availability_impact", "type": "string", "description": "CVSS availability impact"},
            {"name": "scope", "type": "string", "description": "CVSS scope"},
            {"name": "dwell_time_days", "type": "integer", "description": "Days since detection"},
            {"name": "has_patch_available", "type": "boolean", "description": "Patch availability flag"}
        ],
        attribute_groups={
            "identifiers": ["cve_id", "nuid", "dev_id", "instance_id"],
            "scores": ["cvssv3_basescore"],
            "cvss_components": ["attack_vector", "attack_complexity", "privileges_required", "user_interaction",
                               "confidentiality_impact", "integrity_impact", "availability_impact", "scope"],
            "temporal": ["dwell_time_days"]
        }
    )
    builder.entity_schemas["Vulnerability"] = vuln_schema
    
    print(f"   Loaded {len(builder.entity_schemas)} entity schemas")
    
    # Load function definitions
    print("\n2. Loading function definitions...")
    
    # Example function definitions
    builder.function_definitions["calculate_exploitability_score"] = FunctionDefinition(
        function_name="calculate_exploitability_score",
        description="Calculate exploitability score from CVSS v3 attack metrics",
        purpose="Determine how easily a vulnerability can be exploited",
        parameters=[
            {"name": "p_attack_vector_weight", "type": "DECIMAL", "description": "Attack vector weight"},
            {"name": "p_attack_complexity_weight", "type": "DECIMAL", "description": "Attack complexity weight"},
            {"name": "p_privileges_required_weight", "type": "DECIMAL", "description": "Privileges required weight"},
            {"name": "p_user_interaction_weight", "type": "DECIMAL", "description": "User interaction weight"}
        ],
        return_type="DECIMAL",
        use_cases=["Vulnerability prioritization", "Exploit difficulty assessment", "Attack surface analysis"],
        example_call="calculate_exploitability_score(0.85, 0.77, 0.85, 0.85)",
        required_attributes={
            "Vulnerability": ["attack_vector", "attack_complexity", "privileges_required", "user_interaction"]
        }
    )
    
    builder.function_definitions["calculate_impact_score"] = FunctionDefinition(
        function_name="calculate_impact_score",
        description="Calculate impact score from CVSS v3 impact metrics",
        purpose="Determine potential damage from successful exploitation",
        parameters=[
            {"name": "p_confidentiality_weight", "type": "DECIMAL", "description": "Confidentiality impact weight"},
            {"name": "p_integrity_weight", "type": "DECIMAL", "description": "Integrity impact weight"},
            {"name": "p_availability_weight", "type": "DECIMAL", "description": "Availability impact weight"},
            {"name": "p_scope_weight", "type": "DECIMAL", "description": "Scope weight"}
        ],
        return_type="DECIMAL",
        use_cases=["Impact assessment", "Business risk evaluation", "Damage potential analysis"],
        example_call="calculate_impact_score(0.56, 0.56, 0.56, 1.0)",
        required_attributes={
            "Vulnerability": ["confidentiality_impact", "integrity_impact", "availability_impact", "scope"]
        }
    )
    
    builder.function_definitions["calculate_breach_method_likelihood"] = FunctionDefinition(
        function_name="calculate_breach_method_likelihood",
        description="Calculate likelihood scores for each breach method",
        purpose="Identify most likely attack vectors",
        parameters=[
            {"name": "p_cve_id", "type": "TEXT", "description": "CVE identifier"},
            {"name": "p_exploitability_score", "type": "DECIMAL", "description": "Exploitability score"},
            {"name": "p_impact_score", "type": "DECIMAL", "description": "Impact score"},
            {"name": "p_has_known_exploit", "type": "BOOLEAN", "description": "Known exploit flag"},
            {"name": "p_has_patch_available", "type": "BOOLEAN", "description": "Patch available flag"},
            {"name": "p_dwell_time_days", "type": "INTEGER", "description": "Days since detection"},
            {"name": "p_asset_exposure_score", "type": "DECIMAL", "description": "Asset exposure score"}
        ],
        return_type="TABLE",
        use_cases=["Attack vector identification", "Threat modeling", "Security control prioritization"],
        example_call="calculate_breach_method_likelihood('CVE-2024-12345', 85.5, 92.3, TRUE, TRUE, 45, 78.0)",
        required_attributes={
            "Vulnerability": ["cve_id", "dwell_time_days", "has_patch_available"],
            "Asset": ["asset_exposure_score"]
        }
    )
    
    builder.function_definitions["calculate_time_weighted_stats"] = FunctionDefinition(
        function_name="calculate_time_weighted_stats",
        description="Calculate time-weighted statistics with exponential decay",
        purpose="Apply temporal weighting to risk metrics",
        parameters=[
            {"name": "p_value", "type": "DECIMAL", "description": "Value to weight"},
            {"name": "p_time_delta_days", "type": "INTEGER", "description": "Time difference in days"},
            {"name": "p_tau_zero", "type": "DECIMAL", "description": "Decay constant"}
        ],
        return_type="TABLE",
        use_cases=["Time series analysis", "Trend forecasting", "Historical risk weighting"],
        example_call="calculate_time_weighted_stats(85.5, 30, 30.0)",
        required_attributes={
            "Vulnerability": ["dwell_time_days"]
        }
    )
    
    print(f"   Loaded {len(builder.function_definitions)} function definitions")
    
    # Build calculation paths
    print("\n3. Building calculation paths...")
    builder.build_calculation_paths()
    print(f"   Built {len(builder.calculation_paths)} calculation paths")
    
    # Build attribute dependencies
    print("\n4. Building attribute dependencies...")
    builder.build_attribute_dependencies()
    print(f"   Built {len(builder.attribute_dependencies)} attribute dependencies")
    
    # Store in ChromaDB
    print("\n5. Storing knowledge graph in ChromaDB...")
    builder.store_knowledge_graph()
    print("   ✓ Knowledge graph stored successfully")
    
    # Export summary
    print("\n6. Exporting graph summary...")
    builder.export_graph_summary("knowledge_graph_summary.json")
    print("   ✓ Summary exported to knowledge_graph_summary.json")
    
    # Display statistics
    print("\n" + "=" * 80)
    print("KNOWLEDGE GRAPH STATISTICS")
    print("=" * 80)
    print(f"Total Entities:              {len(builder.entity_schemas)}")
    print(f"Total Functions:             {len(builder.function_definitions)}")
    print(f"Total Calculation Paths:     {len(builder.calculation_paths)}")
    print(f"Total Attribute Dependencies: {len(builder.attribute_dependencies)}")
    
    # Show sample paths
    print("\n" + "=" * 80)
    print("SAMPLE CALCULATION PATHS")
    print("=" * 80)
    for i, path in enumerate(builder.calculation_paths[:5], 1):
        print(f"\n{i}. {path.path_name}")
        print(f"   Path ID: {path.path_id}")
        print(f"   Type: {path.calculation_type}")
        print(f"   Source: {path.source_entity}")
        print(f"   Function: {path.target_function}")
        print(f"   Required Attributes: {', '.join(path.source_attributes[:5])}...")
    
    print("\n" + "=" * 80)
    print("✓ Knowledge graph built successfully!")
    print("=" * 80)
    
    return builder


if __name__ == "__main__":
    builder = main()
