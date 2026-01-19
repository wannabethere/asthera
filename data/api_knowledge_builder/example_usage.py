#!/usr/bin/env python3
"""
Simple example: Convert an OpenAPI spec to AsteraMDL

Usage:
    python example_usage.py openapi_spec.json output_mdl.json
    python example_usage.py  # Use defaults
"""
import sys
import json
from api_to_mdl_converter import APIToMDLConverter


def convert_openapi_to_mdl(input_file: str, output_file: str):
    """
    Simple conversion function
    
    Args:
        input_file: Path to OpenAPI JSON file
        output_file: Path for output MDL JSON file
    """
    print(f"Converting {input_file} to {output_file}...")
    print("-" * 70)
    
    # Create converter
    converter = APIToMDLConverter.from_file(
        input_file,
        catalog="api_catalog",
        schema="public",
        create_endpoint_views=True,
        infer_relationships=True
    )
    
    # Perform conversion
    mdl = converter.convert()
    
    # Save result
    converter.save(output_file)
    
    # Print summary
    print("\n" + "=" * 70)
    print("Conversion Summary")
    print("=" * 70)
    summary = converter.get_conversion_summary()
    print(json.dumps(summary, indent=2))
    
    print(f"\n✅ Successfully converted!")
    print(f"   Input: {input_file}")
    print(f"   Output: {output_file}")
    
    return mdl


def main():
    """Main entry point"""
    
    # Parse command line arguments
    if len(sys.argv) >= 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    elif len(sys.argv) == 2:
        input_file = sys.argv[1]
        output_file = input_file.replace('.json', '_mdl.json')
    else:
        # Use defaults
        input_file = 'test_openapi_spec.json'
        output_file = 'test_mdl.json'
        
        # Create a sample OpenAPI spec if it doesn't exist
        try:
            with open(input_file, 'r') as f:
                pass
        except FileNotFoundError:
            print(f"Creating sample OpenAPI spec: {input_file}")
            sample_spec = {
                "openapi": "3.0.3",
                "info": {
                    "title": "Sample API",
                    "version": "1.0.0"
                },
                "components": {
                    "schemas": {
                        "User": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "email": {"type": "string", "format": "email"},
                                "name": {"type": "string"}
                            }
                        }
                    }
                },
                "paths": {
                    "/users": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "properties": {
                                                    "data": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/User"}
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
            with open(input_file, 'w') as f:
                json.dump(sample_spec, f, indent=2)
    
    try:
        convert_openapi_to_mdl(input_file, output_file)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {input_file}")
        print("\nUsage:")
        print(f"  python {sys.argv[0]} <input_openapi.json> <output_mdl.json>")
        print(f"  python {sys.argv[0]} <input_openapi.json>")
        print(f"  python {sys.argv[0]}  # Uses defaults")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
