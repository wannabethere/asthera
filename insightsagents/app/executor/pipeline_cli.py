#!/usr/bin/env python3
"""
Command-line interface for the Pipeline Code Generator.
Usage: python pipeline_cli.py --input pipeline_code.py --output executable.py
"""

import argparse
import sys
from pathlib import Path
from pipeline_code_generator import PipelineCodeGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate executable code from ML pipeline code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate executable from pipeline code file
  python pipeline_cli.py --input my_pipeline.py --output executable.py
  
  # Generate executable from inline pipeline code
  python pipeline_cli.py --code "MetricsPipe.from_dataframe('data').to_df()" --output result.py
  
  # Generate with custom data loading
  python pipeline_cli.py --input pipeline.py --output exec.py --data-sources "orders.csv,users.csv"
  
  # Preview generated code without saving
  python pipeline_cli.py --input pipeline.py --preview
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input", "-i",
        help="Input file containing pipeline code"
    )
    input_group.add_argument(
        "--code", "-c",
        help="Inline pipeline code string"
    )
    
    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output file for generated executable (optional)"
    )
    
    # Data source options
    parser.add_argument(
        "--data-sources",
        help="Comma-separated list of data source files or names"
    )
    
    # Preview option
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview generated code without saving to file"
    )
    
    # Verbose option
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with detailed information"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize generator
        generator = PipelineCodeGenerator()
        
        # Get pipeline code
        if args.input:
            pipeline_code = _read_pipeline_file(args.input)
            source_name = f"file: {args.input}"
        else:
            pipeline_code = args.code
            source_name = "inline code"
        
        if args.verbose:
            print(f"🔍 Processing pipeline code from: {source_name}")
            print(f"📏 Code length: {len(pipeline_code)} characters")
            print(f"📝 Pipeline code preview:")
            print("-" * 50)
            print(pipeline_code[:200] + "..." if len(pipeline_code) > 200 else pipeline_code)
            print("-" * 50)
        
        # Generate executable code
        print("🚀 Generating executable code...")
        executable_code = generator.generate_executable(pipeline_code)
        
        if args.verbose:
            print(f"✅ Generated {len(executable_code)} characters of executable code")
        
        # Handle output
        if args.preview:
            print("\n🔍 Generated Code Preview:")
            print("=" * 60)
            print(executable_code)
            print("=" * 60)
        elif args.output:
            # Save to file
            with open(args.output, 'w') as f:
                f.write(executable_code)
            print(f"✅ Executable code saved to: {args.output}")
            
            # Make executable
            output_path = Path(args.output)
            output_path.chmod(0o755)
            print(f"🔒 Made file executable: {output_path.stat().st_mode & 0o777:o}")
            
            # Show usage instructions
            print(f"\n🚀 To run the generated executable:")
            print(f"   python {args.output}")
            print(f"   # or")
            print(f"   ./{args.output}")
        else:
            # Print to stdout
            print(executable_code)
        
        # Show additional information
        if args.verbose:
            print(f"\n📊 Pipeline Analysis:")
            print(f"   - Source: {source_name}")
            print(f"   - Output: {'File: ' + args.output if args.output else 'stdout'}")
            print(f"   - Preview mode: {args.preview}")
            
            # Parse and show pipeline structure
            parsed_steps = generator._parse_pipeline_code(pipeline_code)
            print(f"   - Pipeline steps: {len(parsed_steps)}")
            for i, step in enumerate(parsed_steps, 1):
                print(f"     Step {i}: {step['description']}")
                if step['input_dataframe']:
                    print(f"       Input: {step['input_dataframe']}")
                if step['result_variable']:
                    print(f"       Output: {step['result_variable']}")
        
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _read_pipeline_file(file_path: str) -> str:
    """Read pipeline code from a file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        raise FileNotFoundError(f"Could not read file {file_path}: {e}")


def _validate_pipeline_code(code: str) -> bool:
    """Basic validation of pipeline code."""
    if not code or not code.strip():
        return False
    
    # Check for basic pipeline patterns
    required_patterns = [
        r'from_dataframe',
        r'\.to_df\(\)',
        r'Pipe\.from_dataframe'
    ]
    
    for pattern in required_patterns:
        if not re.search(pattern, code):
            return False
    
    return True


if __name__ == "__main__":
    main()
