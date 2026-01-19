#!/usr/bin/env python3
"""
Example script demonstrating how to use the enhanced MDL generator programmatically
"""

import asyncio
import json
from pathlib import Path
import sys

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "dataservices"))

from generate_mdl_with_agents import EnhancedAPIToMDLGenerator
from openapi_parser import OpenAPIParser


async def example_basic_usage():
    """Example: Basic usage with a local OpenAPI file"""
    
    print("=" * 80)
    print("Example 1: Basic Usage")
    print("=" * 80)
    
    # Create a sample OpenAPI spec (or load from file)
    sample_openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Example API",
            "version": "1.0.0"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get all users",
                    "operationId": "getUsers",
                    "tags": ["users"],
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user by ID",
                    "operationId": "getUserById",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "User details",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "description": "User account information",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique user identifier"
                        },
                        "name": {
                            "type": "string",
                            "description": "User's full name"
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "description": "User's email address"
                        },
                        "created_at": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Account creation timestamp"
                        }
                    },
                    "required": ["id", "name", "email"]
                }
            }
        }
    }
    
    # Initialize generator
    generator = EnhancedAPIToMDLGenerator(
        domain_id="example_api",
        domain_name="Example API Integration",
        catalog="example",
        schema="public"
    )
    
    # Generate enhanced MDL
    try:
        mdl = await generator.generate_enhanced_mdl(
            sample_openapi,
            filter_get_only=True
        )
        
        # Save to file
        output_file = "example_enhanced_mdl.json"
        with open(output_file, 'w') as f:
            json.dump(mdl, f, indent=2)
        
        print(f"\n✅ Successfully generated enhanced MDL: {output_file}")
        print(f"\n📊 Summary:")
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        
        return mdl
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def example_from_file():
    """Example: Load from OpenAPI file"""
    
    print("\n" + "=" * 80)
    print("Example 2: Load from File")
    print("=" * 80)
    
    # Check if file exists
    openapi_file = "sample_openapi.json"
    if not Path(openapi_file).exists():
        print(f"⚠️  File not found: {openapi_file}")
        print("   Skipping this example")
        return None
    
    # Load OpenAPI spec
    parser = OpenAPIParser.from_file(openapi_file)
    openapi_spec = parser.spec
    
    # Initialize generator
    generator = EnhancedAPIToMDLGenerator(
        domain_id="file_api",
        domain_name="File-based API",
        catalog="file_api",
        schema="public"
    )
    
    # Generate enhanced MDL
    try:
        mdl = await generator.generate_enhanced_mdl(
            openapi_spec,
            filter_get_only=True
        )
        
        output_file = "file_enhanced_mdl.json"
        with open(output_file, 'w') as f:
            json.dump(mdl, f, indent=2)
        
        print(f"\n✅ Successfully generated enhanced MDL: {output_file}")
        return mdl
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def example_all_methods():
    """Example: Process all HTTP methods, not just GET"""
    
    print("\n" + "=" * 80)
    print("Example 3: All HTTP Methods")
    print("=" * 80)
    
    # Use the same sample OpenAPI but add POST endpoint
    sample_openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Example API with All Methods",
            "version": "1.0.0"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get all users",
                    "operationId": "getUsers",
                    "tags": ["users"],
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create user",
                    "operationId": "createUser",
                    "tags": ["users"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created user",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    }
                }
            }
        }
    }
    
    generator = EnhancedAPIToMDLGenerator(
        domain_id="all_methods_api",
        domain_name="All Methods API",
        catalog="all_methods",
        schema="public"
    )
    
    try:
        # Process all methods (not just GET)
        mdl = await generator.generate_enhanced_mdl(
            sample_openapi,
            filter_get_only=False  # Process all methods
        )
        
        output_file = "all_methods_enhanced_mdl.json"
        with open(output_file, 'w') as f:
            json.dump(mdl, f, indent=2)
        
        print(f"\n✅ Successfully generated enhanced MDL: {output_file}")
        print(f"   Note: This includes all HTTP methods, not just GET")
        return mdl
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run all examples"""
    print("🚀 Enhanced MDL Generation Examples")
    print("=" * 80)
    
    # Example 1: Basic usage
    await example_basic_usage()
    
    # Example 2: From file (if file exists)
    await example_from_file()
    
    # Example 3: All methods
    await example_all_methods()
    
    print("\n" + "=" * 80)
    print("✅ All examples completed!")
    print("=" * 80)
    print("\nTo use the command-line interface:")
    print("  python generate_mdl_with_agents.py --input <openapi_file> --output <mdl_file>")


if __name__ == "__main__":
    asyncio.run(main())

