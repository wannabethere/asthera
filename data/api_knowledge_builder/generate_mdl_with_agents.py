#!/usr/bin/env python3
"""
Standalone script to generate enhanced MDL schemas from OpenAPI specifications
using the agent-based enhancement pipeline.

This script:
1. Parses OpenAPI specifications
2. Filters for GET endpoints only
3. Converts to MDL format
4. Enhances with agents:
   - Semantic descriptions
   - Schema documentation
   - Relationship recommendations
   - Business context

Usage:
    python generate_mdl_with_agents.py --input <openapi_file_or_url> --output <output_file.json> [options]
"""

import asyncio
import json
import argparse
import sys
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add current directory to path for local imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Add dataservices to path for agent imports
dataservices_path = Path(__file__).parent.parent.parent / "dataservices"
sys.path.insert(0, str(dataservices_path))

# Local imports (from same directory)
from api_to_mdl_converter import APIToMDLConverter
from openapi_parser import OpenAPIParser, EndpointDefinition
from real_api_converter import RealAPIConverter

# Standalone settings and dependencies (local copies)
from standalone_settings import get_settings, init_environment
from standalone_dependencies import get_llm, get_embeddings

# Import agents (from dataservices)
from app.agents.semantics_description import SemanticsDescription
from app.agents.relationship_recommendation import RelationshipRecommendation
from app.agents.schema_manager import LLMSchemaDocumentationGenerator, SchemaDocumentationUtils
from app.agents.project_manager import MDLSchemaGenerator
from app.service.models import DomainContext, SchemaInput


class EnhancedAPIToMDLGenerator:
    """
    Enhanced API to MDL generator that uses agents to enrich the MDL schema
    """
    
    def __init__(self, 
                 domain_id: str = "api",
                 domain_name: str = "API Data",
                 business_domain: str = "api_integration",
                 catalog: str = "api",
                 schema: str = "public"):
        """
        Initialize the enhanced generator
        
        Args:
            domain_id: Domain identifier
            domain_name: Domain display name
            business_domain: Business domain name
            catalog: MDL catalog name
            schema: MDL schema name
        """
        # Initialize environment FIRST (before any agents)
        # This sets up environment variables that agents will use
        init_environment()
        
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.business_domain = business_domain
        self.catalog = catalog
        self.schema = schema
        
        # Initialize agents
        # Note: Agents use get_llm() from dataservices, which will pick up
        # environment variables set by init_environment()
        self.semantics_agent = SemanticsDescription()
        self.relationship_agent = RelationshipRecommendation()
        
        # Schema manager can take explicit LLM or use default
        # Using standalone get_llm() for consistency
        llm = get_llm()
        self.schema_manager = LLMSchemaDocumentationGenerator(llm=llm)
        
        # Create domain context
        self.domain_context = DomainContext(
            domain_id=domain_id,
            project_name=domain_name,
            business_domain=business_domain,
            purpose=f"API data integration and analysis for {domain_name}",
            target_users=["API Developers", "Data Analysts", "Business Analysts"],
            key_business_concepts=["api_integration", "data_access", "endpoint_analysis"],
            data_sources=["REST API"],
            compliance_requirements=[]
        )
    
    async def generate_enhanced_mdl(self, 
                                    openapi_spec: Optional[Dict[str, Any]] = None,
                                    openapi_url: Optional[str] = None,
                                    openapi_file: Optional[str] = None,
                                    filter_get_only: bool = True,
                                    api_token: Optional[str] = None,
                                    version: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate enhanced MDL schema from OpenAPI spec
        
        Args:
            openapi_spec: OpenAPI specification dictionary
            filter_get_only: Whether to only process GET endpoints
            
        Returns:
            Enhanced MDL schema dictionary
        """
        print("=" * 80)
        print("🚀 Starting Enhanced MDL Generation from OpenAPI")
        print("=" * 80)
        
        # Step 0: Load OpenAPI spec if not provided
        if openapi_spec is None:
            print("\n📋 Step 0: Loading OpenAPI specification...")
            if openapi_url:
                print(f"   Loading from URL: {openapi_url}")
                real_converter = RealAPIConverter(api_token=api_token)
                openapi_spec = real_converter.fetch_spec(openapi_url, version=version)
            elif openapi_file:
                print(f"   Loading from file: {openapi_file}")
                parser = OpenAPIParser.from_file(openapi_file)
                openapi_spec = parser.spec
            else:
                raise ValueError("Must provide openapi_spec, openapi_url, or openapi_file")
        
        # Step 1: Parse OpenAPI spec first to get endpoints
        print("\n📋 Step 1: Parsing OpenAPI specification...")
        parser = OpenAPIParser(openapi_spec)
        parser.parse()
        
        # Filter for GET endpoints only if requested
        get_tags = None
        if filter_get_only:
            print("\n🔍 Filtering for GET endpoints only...")
            # Filter endpoints in parser
            original_endpoints = parser.endpoints
            parser.endpoints = [
                ep for ep in original_endpoints 
                if ep.method.upper() == 'GET'
            ]
            print(f"   Found {len(parser.endpoints)} GET endpoints (out of {len(original_endpoints)} total)")
            
            # Filter tags to only those used by GET endpoints
            get_tags = set()
            for ep in parser.endpoints:
                get_tags.update(ep.tags)
            
            print(f"   GET endpoints use tags: {', '.join(get_tags) if get_tags else 'none'}")
        
        # Step 2: Convert OpenAPI to MDL
        print("\n📋 Step 2: Converting OpenAPI to MDL...")
        converter = APIToMDLConverter(
            openapi_spec,
            catalog=self.catalog,
            schema=self.schema,
            create_endpoint_views=True,
            infer_relationships=True
        )
        
        # Replace parser with filtered one (only GET endpoints)
        converter.parser = parser
        
        # Convert with filtered tags if needed
        if filter_get_only and get_tags:
            mdl = converter.convert(filter_tags=list(get_tags))
        else:
            mdl = converter.convert()
        
        print(f"✅ Initial MDL generated: {len(mdl.get('models', []))} models, {len(mdl.get('views', []))} views")
        
        # Step 3: Enhance models with semantic descriptions
        print("\n📋 Step 3: Enhancing models with semantic descriptions...")
        mdl = await self._enhance_models_with_semantics(mdl)
        
        # Step 4: Enhance with schema documentation
        print("\n📋 Step 4: Enhancing with schema documentation...")
        mdl = await self._enhance_with_schema_documentation(mdl)
        
        # Step 5: Recommend relationships
        print("\n📋 Step 5: Recommending relationships...")
        mdl = await self._enhance_with_relationships(mdl)
        
        # Step 6: Validate and finalize
        print("\n📋 Step 6: Validating MDL schema...")
        is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(mdl)
        
        if not is_valid:
            print(f"⚠️  MDL validation found {len(errors)} issues:")
            for error in errors[:10]:  # Show first 10 errors
                print(f"   - {error}")
        else:
            print("✅ MDL schema validation passed")
        
        print("\n" + "=" * 80)
        print("✅ Enhanced MDL Generation Complete!")
        print("=" * 80)
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        print(f"   Metrics: {len(mdl.get('metrics', []))}")
        
        return mdl
    
    async def _enhance_models_with_semantics(self, mdl: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance models with semantic descriptions"""
        models = mdl.get('models', [])
        
        for i, model in enumerate(models):
            try:
                print(f"   Processing model {i+1}/{len(models)}: {model.get('name', 'Unknown')}")
                
                # Convert model to table_data format for semantics agent
                table_data = {
                    'name': model.get('name', ''),
                    'description': model.get('description', '') or model.get('properties', {}).get('description', ''),
                    'columns': []
                }
                
                # Convert columns
                for col in model.get('columns', []):
                    col_data = {
                        'name': col.get('name', ''),
                        'display_name': col.get('properties', {}).get('displayName', col.get('name', '')),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', ''),
                        'data_type': col.get('type', 'VARCHAR'),
                        'is_primary_key': col.get('name') == model.get('primaryKey'),
                        'is_nullable': not col.get('notNull', False)
                    }
                    table_data['columns'].append(col_data)
                
                # Get semantic description
                result = await self.semantics_agent.describe(
                    SemanticsDescription.Input(
                        id=f"semantics_{model.get('name', '')}",
                        table_data=table_data,
                        domain_id=self.domain_id
                    )
                )
                
                if result.status == "finished" and result.response:
                    semantic_data = result.response
                    
                    # Update model description
                    if semantic_data.get('description'):
                        if 'properties' not in model:
                            model['properties'] = {}
                        model['properties']['semantic_description'] = semantic_data['description']
                        model['properties']['table_purpose'] = semantic_data.get('table_purpose', '')
                        model['properties']['business_context'] = semantic_data.get('business_context', '')
                        
                        if not model.get('description'):
                            model['description'] = semantic_data['description']
                    
                    # Update column descriptions
                    key_columns = semantic_data.get('key_columns', [])
                    for key_col in key_columns:
                        col_name = key_col.get('name')
                        for col in model.get('columns', []):
                            if col.get('name') == col_name:
                                if 'properties' not in col:
                                    col['properties'] = {}
                                col['properties']['business_significance'] = key_col.get('business_significance', '')
                                if not col.get('description'):
                                    col['description'] = key_col.get('description', '')
                                break
                
            except Exception as e:
                print(f"   ⚠️  Error enhancing model {model.get('name', 'Unknown')}: {str(e)}")
                continue
        
        return mdl
    
    async def _enhance_with_schema_documentation(self, mdl: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance models with schema documentation"""
        models = mdl.get('models', [])
        
        for i, model in enumerate(models):
            try:
                print(f"   Processing model {i+1}/{len(models)}: {model.get('name', 'Unknown')}")
                
                # Convert model to SchemaInput format
                columns = []
                for col in model.get('columns', []):
                    col_dict = {
                        'name': col.get('name', ''),
                        'type': col.get('type', 'VARCHAR'),
                        'data_type': col.get('type', 'VARCHAR'),
                        'nullable': not col.get('notNull', False),
                        'primary_key': col.get('name') == model.get('primaryKey'),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', '')
                    }
                    columns.append(col_dict)
                
                schema_input = SchemaInput(
                    table_name=model.get('name', ''),
                    table_description=model.get('description', '') or model.get('properties', {}).get('description', ''),
                    columns=columns,
                    sample_data=None
                )
                
                # Generate documentation
                documented_table = await self.schema_manager.document_table_schema(
                    schema_input,
                    self.domain_context
                )
                
                # Update model with documentation
                if 'properties' not in model:
                    model['properties'] = {}
                
                model['properties']['display_name'] = documented_table.display_name
                model['properties']['business_purpose'] = documented_table.business_purpose
                model['properties']['primary_use_cases'] = ','.join(documented_table.primary_use_cases)
                model['properties']['key_relationships'] = ','.join(documented_table.key_relationships)
                model['properties']['update_frequency'] = documented_table.update_frequency
                
                if not model.get('description'):
                    model['description'] = documented_table.description
                
                # Update columns with enhanced documentation
                for doc_col in documented_table.columns:
                    for mdl_col in model.get('columns', []):
                        if mdl_col.get('name') == doc_col.column_name:
                            if 'properties' not in mdl_col:
                                mdl_col['properties'] = {}
                            
                            mdl_col['properties']['displayName'] = doc_col.display_name
                            mdl_col['properties']['businessDescription'] = doc_col.business_description
                            mdl_col['properties']['usageType'] = doc_col.usage_type.value
                            
                            if doc_col.example_values:
                                mdl_col['properties']['exampleValues'] = ','.join(doc_col.example_values[:5])
                            
                            if not mdl_col.get('description'):
                                mdl_col['description'] = doc_col.description
                            break
                
            except Exception as e:
                print(f"   ⚠️  Error documenting model {model.get('name', 'Unknown')}: {str(e)}")
                continue
        
        return mdl
    
    async def _enhance_with_relationships(self, mdl: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance MDL with relationship recommendations"""
        models = mdl.get('models', [])
        
        if len(models) < 2:
            print("   ⚠️  Need at least 2 models for relationship recommendations")
            return mdl
        
        try:
            # Convert models to table_data format
            tables_data = []
            for model in models:
                table_data = {
                    'name': model.get('name', ''),
                    'display_name': model.get('properties', {}).get('display_name', model.get('name', '')),
                    'description': model.get('description', '') or model.get('properties', {}).get('description', ''),
                    'columns': []
                }
                
                for col in model.get('columns', []):
                    col_data = {
                        'name': col.get('name', ''),
                        'display_name': col.get('properties', {}).get('displayName', col.get('name', '')),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', ''),
                        'data_type': col.get('type', 'VARCHAR'),
                        'is_primary_key': col.get('name') == model.get('primaryKey'),
                        'is_nullable': not col.get('notNull', False),
                        'is_foreign_key': False  # Could be enhanced
                    }
                    table_data['columns'].append(col_data)
                
                tables_data.append(table_data)
            
            # Get relationship recommendations
            result = await self.relationship_agent.recommend(
                RelationshipRecommendation.Input(
                    id="relationship_recommendations",
                    tables_data=tables_data,
                    domain_id=self.domain_id
                )
            )
            
            if result.status == "finished" and result.response:
                recommendations = result.response.get('relationships', [])
                
                # Add recommended relationships to MDL
                existing_relationships = {rel.get('name'): rel for rel in mdl.get('relationships', [])}
                
                for rec in recommendations:
                    rel_name = f"{rec['source_table']}_{rec['target_table']}"
                    
                    if rel_name not in existing_relationships:
                        relationship = {
                            'name': rel_name,
                            'models': [rec['source_table'], rec['target_table']],
                            'joinType': rec['relationship_type'].upper().replace('-', '_'),
                            'condition': f"{rec['source_table']}.{rec['source_column']} = {rec['target_table']}.{rec['target_column']}",
                            'properties': {
                                'explanation': rec.get('explanation', ''),
                                'business_value': rec.get('business_value', ''),
                                'confidence_score': str(rec.get('confidence_score', 0.0))
                            }
                        }
                        
                        if 'relationships' not in mdl:
                            mdl['relationships'] = []
                        mdl['relationships'].append(relationship)
                
                print(f"   ✅ Added {len(recommendations)} relationship recommendations")
        
        except Exception as e:
            print(f"   ⚠️  Error recommending relationships: {str(e)}")
        
        return mdl


async def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Generate enhanced MDL schemas from OpenAPI specifications using agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From local file
  python generate_mdl_with_agents.py --input openapi.json --output mdl.json
  
  # From URL
  python generate_mdl_with_agents.py --input https://api.example.com/openapi.json --output mdl.json
  
  # From known API (Snyk)
  python generate_mdl_with_agents.py --api snyk --version 2024-10-15 --output snyk_mdl.json
  
  # With API token
  python generate_mdl_with_agents.py --input https://api.example.com/openapi.json --api-token YOUR_TOKEN --output mdl.json
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--input',
        type=str,
        help='Input OpenAPI specification (file path or URL)'
    )
    input_group.add_argument(
        '--api',
        type=str,
        choices=['snyk'],
        help='Use a known API specification (e.g., snyk)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output MDL JSON file path'
    )
    
    parser.add_argument(
        '--domain-id',
        type=str,
        default='api',
        help='Domain identifier (default: api)'
    )
    
    parser.add_argument(
        '--domain-name',
        type=str,
        default='API Data',
        help='Domain display name (default: API Data)'
    )
    
    parser.add_argument(
        '--catalog',
        type=str,
        default='api',
        help='MDL catalog name (default: api)'
    )
    
    parser.add_argument(
        '--schema',
        type=str,
        default='public',
        help='MDL schema name (default: public)'
    )
    
    parser.add_argument(
        '--all-methods',
        action='store_true',
        help='Process all HTTP methods, not just GET (default: GET only)'
    )
    
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='JSON indentation (default: 2)'
    )
    
    parser.add_argument(
        '--api-token',
        type=str,
        help='API token for authenticated endpoints'
    )
    
    parser.add_argument(
        '--version',
        type=str,
        help='API version (for APIs that support versioning, e.g., Snyk)'
    )
    
    args = parser.parse_args()
    
    # Determine input source
    openapi_spec = None
    openapi_url = None
    openapi_file = None
    
    if args.api:
        # Use known API
        real_converter = RealAPIConverter(api_token=args.api_token)
        
        if args.api == 'snyk':
            version = args.version or "2024-10-15"
            print(f"📥 Loading Snyk API specification (version: {version})")
            openapi_url = real_converter.KNOWN_SPECS['snyk_rest']
        else:
            print(f"❌ Unknown API: {args.api}")
            sys.exit(1)
    elif args.input:
        if args.input.startswith('http://') or args.input.startswith('https://'):
            openapi_url = args.input
            print(f"📥 Loading OpenAPI specification from URL: {openapi_url}")
        else:
            if not os.path.exists(args.input):
                print(f"❌ Error: File not found: {args.input}")
                sys.exit(1)
            openapi_file = args.input
            print(f"📥 Loading OpenAPI specification from file: {openapi_file}")
    
    # Generate enhanced MDL
    generator = EnhancedAPIToMDLGenerator(
        domain_id=args.domain_id,
        domain_name=args.domain_name,
        catalog=args.catalog,
        schema=args.schema
    )
    
    try:
        mdl = await generator.generate_enhanced_mdl(
            openapi_spec=openapi_spec,
            openapi_url=openapi_url,
            openapi_file=openapi_file,
            filter_get_only=not args.all_methods,
            api_token=args.api_token,
            version=args.version
        )
        
        # Save to file
        print(f"\n💾 Saving MDL to: {args.output}")
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(mdl, f, indent=args.indent)
        
        print(f"✅ Successfully saved MDL schema to {args.output}")
        print(f"\n📊 Summary:")
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        print(f"   Metrics: {len(mdl.get('metrics', []))}")
        
    except Exception as e:
        print(f"❌ Error generating MDL: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

