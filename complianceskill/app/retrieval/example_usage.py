"""
CLI script to test retrieval service and query ingested framework data.

This script demonstrates how to:
1. Search for controls, requirements, risks, test cases, and scenarios
2. Get full context for specific artifacts
3. Perform cross-framework lookups
4. Search across all artifact types simultaneously
5. Filter by framework

Usage:
    python -m app.retrieval.example_usage --query "vulnerability scanning"
    python -m app.retrieval.example_usage --query "access control" --type controls --limit 5
    python -m app.retrieval.example_usage --control-id "cis_v8_1__VPM-2" --context
    python -m app.retrieval.example_usage --cross-framework "cis_v8_1__VPM-2" --targets hipaa soc2
"""

import argparse
import json
import logging
import sys
from typing import Optional, List

# Ensure .env is loaded by importing settings early
from app.core.settings import get_settings

# Import retrieval service
from app.retrieval import RetrievalService, RetrievedContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_results(context: RetrievedContext, detailed: bool = False):
    """Pretty print retrieval results."""
    print("\n" + "=" * 80)
    print(f"Query: {context.query}")
    print(f"Artifact Type: {context.artifact_type}")
    print(f"Total Hits: {context.total_hits}")
    if context.framework_filter:
        print(f"Framework Filter: {context.framework_filter}")
    if context.warnings:
        print(f"Warnings: {', '.join(context.warnings)}")
    print("=" * 80)
    
    # Print results by type
    if context.controls:
        print(f"\n📋 Controls ({len(context.controls)}):")
        for i, ctrl in enumerate(context.controls, 1):
            print(f"\n  {i}. {ctrl.name} ({ctrl.control_code})")
            print(f"     Framework: {ctrl.framework_name} ({ctrl.framework_id})")
            if ctrl.similarity_score:
                print(f"     Similarity: {ctrl.similarity_score:.4f}")
            if ctrl.domain:
                print(f"     Domain: {ctrl.domain}")
            if detailed and ctrl.description:
                print(f"     Description: {ctrl.description[:200]}...")
            if detailed and ctrl.mitigated_risks:
                print(f"     Mitigated Risks: {len(ctrl.mitigated_risks)}")
            if detailed and ctrl.satisfied_requirements:
                print(f"     Satisfied Requirements: {len(ctrl.satisfied_requirements)}")
    
    if context.requirements:
        print(f"\n📄 Requirements ({len(context.requirements)}):")
        for i, req in enumerate(context.requirements, 1):
            print(f"\n  {i}. {req.requirement_code}")
            if req.name:
                print(f"     Name: {req.name}")
            print(f"     Framework: {req.framework_name} ({req.framework_id})")
            if req.similarity_score:
                print(f"     Similarity: {req.similarity_score:.4f}")
            if detailed and req.description:
                print(f"     Description: {req.description[:200]}...")
            if detailed and req.satisfying_controls:
                print(f"     Satisfying Controls: {len(req.satisfying_controls)}")
    
    if context.risks:
        print(f"\n⚠️  Risks ({len(context.risks)}):")
        for i, risk in enumerate(context.risks, 1):
            print(f"\n  {i}. {risk.name} ({risk.risk_code})")
            print(f"     Framework: {risk.framework_name} ({risk.framework_id})")
            if risk.similarity_score:
                print(f"     Similarity: {risk.similarity_score:.4f}")
            if detailed and risk.description:
                print(f"     Description: {risk.description[:200]}...")
            if detailed and risk.mitigating_controls:
                print(f"     Mitigating Controls: {len(risk.mitigating_controls)}")
    
    if context.test_cases:
        print(f"\n🧪 Test Cases ({len(context.test_cases)}):")
        for i, tc in enumerate(context.test_cases, 1):
            print(f"\n  {i}. {tc.name}")
            print(f"     Framework: {tc.framework_name} ({tc.framework_id})")
            if tc.similarity_score:
                print(f"     Similarity: {tc.similarity_score:.4f}")
            if detailed and tc.objective:
                print(f"     Objective: {tc.objective[:200]}...")
    
    if context.scenarios:
        print(f"\n🎭 Scenarios ({len(context.scenarios)}):")
        for i, sc in enumerate(context.scenarios, 1):
            print(f"\n  {i}. {sc.name} ({sc.scenario_code})")
            print(f"     Framework: {sc.framework_name} ({sc.framework_id})")
            if sc.similarity_score:
                print(f"     Similarity: {sc.similarity_score:.4f}")
            if detailed and sc.description:
                print(f"     Description: {sc.description[:200]}...")
    
    if context.cross_framework_mappings:
        print(f"\n🔗 Cross-Framework Mappings ({len(context.cross_framework_mappings)}):")
        for i, mapping in enumerate(context.cross_framework_mappings, 1):
            print(f"\n  {i}. {mapping.source_framework_id} → {mapping.target_framework_id}")
            print(f"     Source: {mapping.source_control_code}")
            if mapping.target_control_code:
                print(f"     Target: {mapping.target_control_code}")
            elif mapping.target_raw_code:
                print(f"     Target (unresolved): {mapping.target_raw_code}")
            print(f"     Type: {mapping.mapping_type}")
            if mapping.confidence_score:
                print(f"     Confidence: {mapping.confidence_score:.4f}")
    
    # Print risk-control mappings if this is a mapping search
    if context.artifact_type == "risk_control_mapping":
        print(f"\n🔗 Risk-Control Mappings:")
        if context.risks and context.controls:
            # Show risks with their controls
            for risk in context.risks:
                print(f"\n  Risk: {risk.name} ({risk.risk_code})")
                print(f"     Framework: {risk.framework_name}")
                if risk.mitigating_controls:
                    print(f"     Mitigating Controls ({len(risk.mitigating_controls)}):")
                    for ctrl in risk.mitigating_controls[:5]:  # Show first 5
                        print(f"       - {ctrl.name} ({ctrl.control_code})")
                elif detailed:
                    print(f"     No controls found")
        
        if context.controls and context.risks:
            # Show controls with their risks
            for ctrl in context.controls:
                if ctrl.mitigated_risks:
                    print(f"\n  Control: {ctrl.name} ({ctrl.control_code})")
                    print(f"     Framework: {ctrl.framework_name}")
                    print(f"     Mitigated Risks ({len(ctrl.mitigated_risks)}):")
                    for risk in ctrl.mitigated_risks[:5]:  # Show first 5
                        print(f"       - {risk.name} ({risk.risk_code})")


def search_example(service: RetrievalService, args):
    """Run semantic search examples."""
    query = args.query
    artifact_type = args.type or "all"
    limit = args.limit
    frameworks = args.frameworks if args.frameworks else None
    fetch_context = args.context
    
    logger.info(f"Searching for: '{query}'")
    logger.info(f"Type: {artifact_type}, Limit: {limit}, Frameworks: {frameworks}")
    
    if artifact_type == "all":
        context = service.search_all(
            query=query,
            limit_per_collection=limit,
            framework_filter=frameworks,
        )
    elif artifact_type == "controls":
        context = service.search_controls(
            query=query,
            limit=limit,
            framework_filter=frameworks,
            fetch_context=fetch_context,
        )
    elif artifact_type == "requirements":
        context = service.search_requirements(
            query=query,
            limit=limit,
            framework_filter=frameworks,
            fetch_context=fetch_context,
        )
    elif artifact_type == "risks":
        context = service.search_risks(
            query=query,
            limit=limit,
            framework_filter=frameworks,
            fetch_context=fetch_context,
        )
    elif artifact_type == "test_cases":
        context = service.search_test_cases(
            query=query,
            limit=limit,
            framework_filter=frameworks,
        )
    elif artifact_type == "scenarios":
        context = service.search_scenarios(
            query=query,
            limit=limit,
            framework_filter=frameworks,
        )
    elif artifact_type == "risk_control_mappings":
        search_by = getattr(args, "search_by", "risk")
        context = service.search_risk_control_mappings(
            query=query,
            limit=limit,
            framework_filter=frameworks,
            search_by=search_by,
        )
    else:
        logger.error(f"Unknown artifact type: {artifact_type}")
        return 1
    
    print_results(context, detailed=args.detailed)
    
    # JSON output if requested
    if args.json:
        result_dict = {
            "query": context.query,
            "artifact_type": context.artifact_type,
            "total_hits": context.total_hits,
            "framework_filter": context.framework_filter,
            "warnings": context.warnings,
            "controls": [
                {
                    "id": c.id,
                    "control_code": c.control_code,
                    "name": c.name,
                    "framework_id": c.framework_id,
                    "framework_name": c.framework_name,
                    "similarity_score": c.similarity_score,
                }
                for c in context.controls
            ],
            "requirements": [
                {
                    "id": r.id,
                    "requirement_code": r.requirement_code,
                    "name": r.name,
                    "framework_id": r.framework_id,
                    "framework_name": r.framework_name,
                    "similarity_score": r.similarity_score,
                }
                for r in context.requirements
            ],
            "risks": [
                {
                    "id": r.id,
                    "risk_code": r.risk_code,
                    "name": r.name,
                    "framework_id": r.framework_id,
                    "framework_name": r.framework_name,
                    "similarity_score": r.similarity_score,
                }
                for r in context.risks
            ],
        }
        print("\n" + "=" * 80)
        print("JSON Output:")
        print("=" * 80)
        print(json.dumps(result_dict, indent=2))
    
    return 0


def get_context_example(service: RetrievalService, args):
    """Get full context for a specific artifact."""
    if args.control_id:
        logger.info(f"Getting context for control: {args.control_id}")
        context = service.get_control_context(
            control_id=args.control_id,
            include_cross_framework=args.cross_framework,
        )
    elif args.risk_id:
        logger.info(f"Getting context for risk: {args.risk_id}")
        context = service.get_risk_context(risk_id=args.risk_id)
    elif args.requirement_id:
        logger.info(f"Getting context for requirement: {args.requirement_id}")
        context = service.get_requirement_context(requirement_id=args.requirement_id)
    else:
        logger.error("Must specify --control-id, --risk-id, or --requirement-id")
        return 1
    
    print_results(context, detailed=True)
    return 0


def cross_framework_example(service: RetrievalService, args):
    """Get cross-framework mappings."""
    control_id = args.cross_framework
    target_frameworks = args.targets if args.targets else None
    
    logger.info(f"Finding cross-framework equivalents for: {control_id}")
    if target_frameworks:
        logger.info(f"Target frameworks: {target_frameworks}")
    
    context = service.get_cross_framework_equivalents(
        control_id=control_id,
        target_frameworks=target_frameworks,
        resolved_only=args.resolved_only,
    )
    
    print_results(context, detailed=True)
    return 0


def list_frameworks_example(service: RetrievalService):
    """List all ingested frameworks."""
    frameworks = service.list_frameworks()
    
    print("\n" + "=" * 80)
    print("Ingested Frameworks")
    print("=" * 80)
    
    if not frameworks:
        print("No frameworks found. Run ingestion first.")
        return 0
    
    for fw in frameworks:
        print(f"\n  • {fw['id']}")
        print(f"    Name: {fw['name']}")
        print(f"    Version: {fw['version']}")
        if fw.get('description'):
            print(f"    Description: {fw['description'][:100]}...")
    
    # Get stats for each framework
    print("\n" + "=" * 80)
    print("Framework Statistics")
    print("=" * 80)
    
    for fw in frameworks:
        stats = service.get_framework_summary(fw['id'])
        if 'error' not in stats:
            print(f"\n  {fw['id']}:")
            for artifact_type, count in stats.get('counts', {}).items():
                print(f"    {artifact_type}: {count}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Test retrieval service and query ingested framework data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Semantic search across all artifact types
  python -m app.retrieval.example_usage --query "vulnerability scanning"

  # Search specific artifact type
  python -m app.retrieval.example_usage --query "access control" --type controls --limit 5

  # Search with framework filter
  python -m app.retrieval.example_usage --query "data encryption" --frameworks cis_v8_1 hipaa

  # Get full context for a control
  python -m app.retrieval.example_usage --control-id "cis_v8_1__VPM-2" --context

  # Cross-framework lookup
  python -m app.retrieval.example_usage --cross-framework "cis_v8_1__VPM-2" --targets hipaa soc2

  # Search risk-control mappings (by risk)
  python -m app.retrieval.example_usage --query "data breach" --type risk_control_mappings --search-by risk

  # Search risk-control mappings (by control)
  python -m app.retrieval.example_usage --query "access control" --type risk_control_mappings --search-by control

  # List all frameworks
  python -m app.retrieval.example_usage --list-frameworks
        """
    )
    
    # Search arguments
    parser.add_argument(
        "--query",
        type=str,
        help="Natural language query for semantic search",
    )
    parser.add_argument(
        "--type",
        choices=["all", "controls", "requirements", "risks", "test_cases", "scenarios", "risk_control_mappings"],
        default="all",
        help="Type of artifact to search (default: all)",
    )
    parser.add_argument(
        "--search-by",
        choices=["risk", "control"],
        default="risk",
        help="For risk_control_mappings: search by 'risk' (returns risks with controls) or 'control' (returns controls with risks) (default: risk)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )
    parser.add_argument(
        "--frameworks",
        nargs="*",
        help="Filter by framework IDs (e.g., cis_v8_1 hipaa)",
    )
    parser.add_argument(
        "--context",
        action="store_true",
        help="Fetch full context (related risks, requirements, etc.)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed information for each result",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    # Context lookup arguments
    parser.add_argument(
        "--control-id",
        type=str,
        help="Get full context for a specific control ID",
    )
    parser.add_argument(
        "--risk-id",
        type=str,
        help="Get full context for a specific risk ID",
    )
    parser.add_argument(
        "--requirement-id",
        type=str,
        help="Get full context for a specific requirement ID",
    )
    
    # Cross-framework arguments
    parser.add_argument(
        "--cross-framework",
        type=str,
        help="Find cross-framework equivalents for a control ID",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        help="Target framework IDs for cross-framework lookup",
    )
    parser.add_argument(
        "--resolved-only",
        action="store_true",
        help="Only return resolved cross-framework mappings",
    )
    
    # List frameworks
    parser.add_argument(
        "--list-frameworks",
        action="store_true",
        help="List all ingested frameworks with statistics",
    )
    
    args = parser.parse_args()
    
    # Load settings early to ensure .env is loaded
    settings = get_settings()
    logger.info("Environment configuration loaded from .env file")
    
    # Initialize retrieval service
    logger.info("Initializing RetrievalService...")
    service = RetrievalService()
    
    # Route to appropriate function
    if args.list_frameworks:
        return list_frameworks_example(service)
    elif args.cross_framework:
        return cross_framework_example(service, args)
    elif args.control_id or args.risk_id or args.requirement_id:
        return get_context_example(service, args)
    elif args.query:
        return search_example(service, args)
    else:
        parser.print_help()
        logger.error("\nMust specify one of: --query, --control-id, --risk-id, --requirement-id, --cross-framework, or --list-frameworks")
        return 1


if __name__ == "__main__":
    sys.exit(main())
