#!/usr/bin/env python3
"""
Standalone script to run the Gold Model Plan Generator.

This script allows you to generate a gold model plan from metrics and schemas
without running the full DT workflow.

Usage:
    python scripts/run_gold_model_planner.py \
        --metrics-file tests/outputs/leen_use_case_1_metrics_help/20260301_170904/outputs/metric_recommendations.json \
        --schemas-file tests/outputs/leen_use_case_1_metrics_help/20260301_170904/outputs/resolved_schemas.json \
        --user-query "What metrics should I track for SOC2 vulnerability management compliance?" \
        --output gold_model_plan.json
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path
base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))

from dotenv import load_dotenv

# Load .env file
env_file = base_dir / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✓ Loaded .env file from: {env_file}")
else:
    print("⚠️  No .env file found. Using default environment variables.")

from app.agents.gold_model_plan_generator import (
    GoldModelPlanGenerator,
    GoldModelPlanGeneratorInput,
    SilverTableInfo,
)


def load_json_file(file_path: Path) -> Any:
    """Load JSON from file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        return json.load(f)


def convert_schemas_to_silver_tables_info(schemas: List[Dict[str, Any]]) -> List[SilverTableInfo]:
    """Convert MDL schemas to SilverTableInfo format."""
    silver_tables_info = []
    
    for schema in schemas:
        if isinstance(schema, dict):
            table_name = schema.get("table_name") or schema.get("name", "")
            if not table_name:
                continue
            
            silver_tables_info.append(
                SilverTableInfo(
                    table_name=table_name,
                    reason="From MDL schema retrieval",
                    schema_info=schema,
                    relevant_columns=[],
                    relevant_columns_reasoning="Columns from MDL schema",
                )
            )
    
    return silver_tables_info


async def generate_gold_model_plan(
    metrics: List[Dict[str, Any]],
    schemas: List[Dict[str, Any]],
    user_query: str = "",
    kpis: List[Dict[str, Any]] = None,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """Generate gold model plan from metrics and schemas."""
    
    # Convert schemas to SilverTableInfo
    silver_tables_info = convert_schemas_to_silver_tables_info(schemas)
    
    if not silver_tables_info:
        raise ValueError("No valid schemas found. Need at least one schema with table_name.")
    
    # Initialize generator
    generator = GoldModelPlanGenerator(temperature=temperature)
    
    # Prepare input
    input_data = GoldModelPlanGeneratorInput(
        metrics=metrics,
        silver_tables_info=silver_tables_info,
        user_request=user_query,
        kpis=kpis or [],
        medallion_context={
            "silver_tables": [t.table_name for t in silver_tables_info],
            "gold_tables": [],  # To be created
        },
    )
    
    # Generate plan
    gold_model_plan = await generator.generate(input_data)
    
    # Convert to dict for JSON serialization
    return gold_model_plan.model_dump()


def main():
    parser = argparse.ArgumentParser(
        description="Generate gold model plan from metrics and schemas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--metrics-file",
        type=Path,
        required=True,
        help="Path to JSON file containing metrics (metric_recommendations.json or resolved_metrics.json)",
    )
    
    parser.add_argument(
        "--schemas-file",
        type=Path,
        required=True,
        help="Path to JSON file containing schemas (resolved_schemas.json)",
    )
    
    parser.add_argument(
        "--user-query",
        type=str,
        default="",
        help="Original user query for context",
    )
    
    parser.add_argument(
        "--kpis-file",
        type=Path,
        help="Optional path to JSON file containing KPIs",
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("gold_model_plan.json"),
        help="Output file path (default: gold_model_plan.json)",
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (default: 0.3)",
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Gold Model Plan Generator")
    print("=" * 80)
    print()
    
    # Load metrics
    print(f"Loading metrics from: {args.metrics_file}")
    metrics_data = load_json_file(args.metrics_file)
    
    # Handle different formats
    if isinstance(metrics_data, list):
        metrics = metrics_data
    elif isinstance(metrics_data, dict):
        # Try common keys
        metrics = (
            metrics_data.get("dt_metric_recommendations") or
            metrics_data.get("metric_recommendations") or
            metrics_data.get("resolved_metrics") or
            metrics_data.get("metrics") or
            []
        )
        if not metrics:
            raise ValueError(f"Could not find metrics in file. Keys: {list(metrics_data.keys())}")
    else:
        raise ValueError(f"Unexpected metrics file format: {type(metrics_data)}")
    
    print(f"  ✓ Loaded {len(metrics)} metrics")
    
    # Load schemas
    print(f"Loading schemas from: {args.schemas_file}")
    schemas_data = load_json_file(args.schemas_file)
    
    if isinstance(schemas_data, list):
        schemas = schemas_data
    elif isinstance(schemas_data, dict):
        schemas = (
            schemas_data.get("dt_resolved_schemas") or
            schemas_data.get("resolved_schemas") or
            schemas_data.get("schemas") or
            []
        )
        if not schemas:
            raise ValueError(f"Could not find schemas in file. Keys: {list(schemas_data.keys())}")
    else:
        raise ValueError(f"Unexpected schemas file format: {type(schemas_data)}")
    
    print(f"  ✓ Loaded {len(schemas)} schemas")
    
    # Load KPIs if provided
    kpis = None
    if args.kpis_file:
        print(f"Loading KPIs from: {args.kpis_file}")
        kpis_data = load_json_file(args.kpis_file)
        if isinstance(kpis_data, list):
            kpis = kpis_data
        elif isinstance(kpis_data, dict):
            kpis = kpis_data.get("kpis", [])
        print(f"  ✓ Loaded {len(kpis) if kpis else 0} KPIs")
    
    print()
    print("Generating gold model plan...")
    
    # Generate plan
    try:
        plan = asyncio.run(
            generate_gold_model_plan(
                metrics=metrics,
                schemas=schemas,
                user_query=args.user_query,
                kpis=kpis,
                temperature=args.temperature,
            )
        )
        
        # Save output
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(plan, f, indent=2, default=str)
        
        print(f"  ✓ Gold model plan generated successfully!")
        print()
        print(f"Results:")
        print(f"  - Requires gold model: {plan['requires_gold_model']}")
        print(f"  - Specifications: {len(plan.get('specifications', []))}")
        print(f"  - Reasoning: {plan.get('reasoning', '')[:100]}...")
        print()
        print(f"Output saved to: {args.output}")
        
        # Print specifications summary
        if plan.get('specifications'):
            print()
            print("Gold Model Specifications:")
            for i, spec in enumerate(plan['specifications'], 1):
                print(f"  {i}. {spec['name']}")
                print(f"     Materialization: {spec['materialization']}")
                print(f"     Columns: {len(spec.get('expected_columns', []))}")
                print(f"     Description: {spec.get('description', '')[:80]}...")
                print()
        
    except Exception as e:
        print(f"  ✗ Error generating plan: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
