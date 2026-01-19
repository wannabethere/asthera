"""
Test script for API to MDL Converter
Demonstrates various usage patterns
"""
import json
from api_to_mdl_converter import APIToMDLConverter, BatchConverter


# Example 1: Simple OpenAPI spec (minimal example)
SIMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Simple API",
        "version": "1.0.0"
    },
    "components": {
        "schemas": {
            "User": {
                "type": "object",
                "description": "A user in the system",
                "required": ["id", "email"],
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Unique user identifier"
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "User email address"
                    },
                    "name": {
                        "type": "string",
                        "description": "User full name"
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Account creation timestamp"
                    },
                    "org_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Organization identifier"
                    }
                }
            },
            "Organization": {
                "type": "object",
                "description": "An organization",
                "required": ["id", "name"],
                "properties": {
                    "id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Unique organization identifier"
                    },
                    "name": {
                        "type": "string",
                        "description": "Organization name"
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time"
                    }
                }
            }
        }
    },
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List all users",
                "tags": ["users"],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/User"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/organizations": {
            "get": {
                "operationId": "listOrganizations",
                "summary": "List all organizations",
                "tags": ["organizations"],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "properties": {
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/Organization"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def test_basic_conversion():
    """Test basic conversion of a simple OpenAPI spec"""
    print("\n" + "="*70)
    print("TEST 1: Basic Conversion")
    print("="*70)
    
    converter = APIToMDLConverter(
        SIMPLE_OPENAPI_SPEC,
        catalog="test_api",
        schema="v1"
    )
    
    mdl = converter.convert()
    
    # Print results
    print("\n" + "-"*70)
    print("Conversion Summary:")
    print("-"*70)
    summary = converter.get_conversion_summary()
    print(json.dumps(summary, indent=2))
    
    # Save to file
    converter.save("test_basic_mdl.json")
    
    return mdl


def test_filtered_conversion():
    """Test conversion with filters"""
    print("\n" + "="*70)
    print("TEST 2: Filtered Conversion (Organizations only)")
    print("="*70)
    
    converter = APIToMDLConverter(
        SIMPLE_OPENAPI_SPEC,
        catalog="test_api",
        schema="v1",
        create_endpoint_views=False,  # Disable endpoint views
        infer_relationships=False      # Disable relationship inference
    )
    
    mdl = converter.convert(
        filter_schemas=["Organization"]  # Only convert Organization schema
    )
    
    converter.save("test_filtered_mdl.json")
    
    return mdl


def test_endpoint_views():
    """Test endpoint view creation"""
    print("\n" + "="*70)
    print("TEST 3: Endpoint Views")
    print("="*70)
    
    converter = APIToMDLConverter(
        SIMPLE_OPENAPI_SPEC,
        catalog="test_api",
        schema="v1",
        create_endpoint_views=True
    )
    
    mdl = converter.convert()
    
    # Show views
    if 'views' in mdl:
        print(f"\nGenerated {len(mdl['views'])} views:")
        for view in mdl['views']:
            print(f"  - {view['name']}")
            if 'properties' in view:
                print(f"    Path: {view['properties'].get('endpoint_path')}")
                print(f"    Method: {view['properties'].get('http_method')}")
    
    converter.save("test_views_mdl.json")
    
    return mdl


def test_relationship_inference():
    """Test relationship inference"""
    print("\n" + "="*70)
    print("TEST 4: Relationship Inference")
    print("="*70)
    
    converter = APIToMDLConverter(
        SIMPLE_OPENAPI_SPEC,
        catalog="test_api",
        schema="v1",
        infer_relationships=True
    )
    
    mdl = converter.convert()
    
    # Show relationships
    if 'relationships' in mdl:
        print(f"\nInferred {len(mdl['relationships'])} relationships:")
        for rel in mdl['relationships']:
            print(f"  - {rel['name']}: {rel['models'][0]} -> {rel['models'][1]}")
            print(f"    Join Type: {rel['joinType']}")
            print(f"    Condition: {rel['condition']}")
    
    converter.save("test_relationships_mdl.json")
    
    return mdl


def test_from_file():
    """Test loading from a file (requires a JSON file)"""
    print("\n" + "="*70)
    print("TEST 5: Load from File")
    print("="*70)
    
    # First, save a test spec to a file
    test_file = "test_openapi_spec.json"
    with open(test_file, 'w') as f:
        json.dump(SIMPLE_OPENAPI_SPEC, f, indent=2)
    print(f"Saved test spec to: {test_file}")
    
    # Now load and convert
    converter = APIToMDLConverter.from_file(
        test_file,
        catalog="file_api",
        schema="v1"
    )
    
    mdl = converter.convert()
    converter.save("test_from_file_mdl.json")
    
    return mdl


def test_batch_conversion():
    """Test batch conversion of multiple specs"""
    print("\n" + "="*70)
    print("TEST 6: Batch Conversion")
    print("="*70)
    
    # Create another spec
    other_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Projects API",
            "version": "1.0.0"
        },
        "components": {
            "schemas": {
                "Project": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "format": "uuid"},
                        "name": {"type": "string"},
                        "org_id": {"type": "string", "format": "uuid"}
                    }
                }
            }
        },
        "paths": {}
    }
    
    batch = BatchConverter(catalog="multi_api")
    
    # Add multiple specs
    batch.add_spec("users_api", SIMPLE_OPENAPI_SPEC, schema="users")
    batch.add_spec("projects_api", other_spec, schema="projects")
    
    # Convert all
    results = batch.convert_all()
    
    # Save all
    batch.save_all(output_dir="batch_output")
    
    return results


def test_custom_configuration():
    """Test with custom configuration"""
    print("\n" + "="*70)
    print("TEST 7: Custom Configuration")
    print("="*70)
    
    from mdl_builder import MDLSchemaBuilder, MDLColumn, MDLModel
    from openapi_parser import OpenAPIParser
    
    # Parse OpenAPI
    parser = OpenAPIParser(SIMPLE_OPENAPI_SPEC)
    parser.parse()
    
    # Create custom MDL builder
    builder = MDLSchemaBuilder(catalog="custom", schema="custom_v1")
    
    # Manually add a model with custom configuration
    for schema_name, schema_def in parser.schemas.items():
        model = builder.add_model_from_schema(
            schema_def,
            endpoint_info={
                'path': f'/custom/{schema_name.lower()}',
                'method': 'GET'
            }
        )
        
        # Add custom column
        custom_col = MDLColumn(
            name="_etl_timestamp",
            type="timestamp",
            description="ETL processing timestamp",
            properties={"etl": "true"}
        )
        model.columns.append(custom_col)
    
    # Build and save
    mdl = builder.build_mdl()
    builder.save_to_file("test_custom_mdl.json")
    
    return mdl


def demonstrate_llm_enrichment_pattern():
    """Demonstrate pattern for LLM enrichment"""
    print("\n" + "="*70)
    print("DEMO: LLM Enrichment Pattern")
    print("="*70)
    
    # Step 1: Convert API to MDL
    converter = APIToMDLConverter(
        SIMPLE_OPENAPI_SPEC,
        catalog="enrichment_demo",
        schema="v1"
    )
    mdl = converter.convert()
    
    # Step 2: Extract information for LLM enrichment
    enrichment_data = {
        'models': []
    }
    
    for model in mdl.get('models', []):
        model_info = {
            'name': model['name'],
            'columns': []
        }
        
        for col in model.get('columns', []):
            col_info = {
                'name': col['name'],
                'type': col['type'],
                'current_description': col.get('properties', {}).get('description', ''),
                # This is where you'd add context for LLM
                'needs_enrichment': not col.get('properties', {}).get('description')
            }
            model_info['columns'].append(col_info)
        
        enrichment_data['models'].append(model_info)
    
    # Step 3: Save enrichment template
    with open('enrichment_template.json', 'w') as f:
        json.dump(enrichment_data, indent=2, fp=f)
    
    print("\nEnrichment template saved to: enrichment_template.json")
    print("\nYou can now:")
    print("1. Load this file")
    print("2. Use an LLM to generate better descriptions for columns")
    print("3. Update the MDL schema with enriched descriptions")
    print("4. Add business context, metrics, and relationships")
    
    # Example enrichment structure
    print("\n" + "-"*70)
    print("Example LLM Enrichment Prompt:")
    print("-"*70)
    print("""
For each column in the following data model, provide:
1. A clear business-friendly description
2. Suggested data quality rules
3. Related metrics or KPIs
4. Privacy/security classification (if applicable)

Input:
{json_string}

Output format:
{{
  "model_name": "...",
  "column_name": "...",
  "enriched_description": "...",
  "data_quality_rules": [...],
  "related_metrics": [...],
  "privacy_level": "public|internal|confidential|restricted"
}}
""".format(json_string=json.dumps(enrichment_data, indent=2)))
    
    return enrichment_data


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("RUNNING ALL TESTS")
    print("="*70)
    
    tests = [
        ("Basic Conversion", test_basic_conversion),
        ("Filtered Conversion", test_filtered_conversion),
        ("Endpoint Views", test_endpoint_views),
        ("Relationship Inference", test_relationship_inference),
        ("Load from File", test_from_file),
        ("Batch Conversion", test_batch_conversion),
        ("Custom Configuration", test_custom_configuration),
        ("LLM Enrichment Pattern", demonstrate_llm_enrichment_pattern),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = {"status": "success", "result": result}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
            print(f"\n❌ Test failed: {name}")
            print(f"Error: {e}")
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, result in results.items():
        status = "✅" if result["status"] == "success" else "❌"
        print(f"{status} {name}: {result['status']}")
    
    return results


if __name__ == "__main__":
    # Run individual tests or all tests
    import sys
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        test_map = {
            "basic": test_basic_conversion,
            "filtered": test_filtered_conversion,
            "views": test_endpoint_views,
            "relationships": test_relationship_inference,
            "file": test_from_file,
            "batch": test_batch_conversion,
            "custom": test_custom_configuration,
            "enrichment": demonstrate_llm_enrichment_pattern,
        }
        
        if test_name in test_map:
            test_map[test_name]()
        else:
            print(f"Unknown test: {test_name}")
            print(f"Available tests: {', '.join(test_map.keys())}")
    else:
        # Run all tests
        run_all_tests()
