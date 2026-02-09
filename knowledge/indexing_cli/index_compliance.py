"""
CLI for indexing compliance documents with flags for different document types.

Document Storage Locations:
===========================

1. Policy Documents (--index-policies):
   Policy documents are split by extraction types and routed to general stores with type="policy" in metadata:
   - context -> domain_knowledge (type="policy", framework in metadata)
   - entities -> entities (type="policy", framework in metadata)
   - requirement -> domain_knowledge (type="policy", framework in metadata)
   - full_content -> domain_knowledge (type="policy", framework in metadata)
   - evidence -> evidence (type="policy", framework in metadata)
   - fields -> fields (type="policy", framework in metadata)
   - control -> controls (type="policy", framework in metadata)

2. SOC2 Controls (--index-soc2):
   SOC2 controls are stored in the compliance_controls collection:
   - All documents -> compliance_controls (framework="SOC2" in metadata)
   - Framework is stored in metadata, not in collection name

3. Risk Controls (--index-risk-controls):
   Risk controls are routed to general stores based on extraction_type with type="risk_*" in metadata:
   - control -> controls (type="risk_control", framework in metadata)
   - entities -> entities (type="risk_entities", framework in metadata)
   - fields -> fields (type="risk_fields", framework in metadata)
   - evidence -> evidence (type="risk_evidence", framework in metadata)
   - requirements -> domain_knowledge (type="risk_requirements", framework in metadata)
   - context -> domain_knowledge (type="risk_context", framework in metadata)
   - base -> domain_knowledge (type="risk_base", framework in metadata)

Note: All stores use metadata.type and metadata.framework for filtering, not separate collections.
"""
import asyncio
import argparse
import logging
from pathlib import Path

from app.indexing.comprehensive_indexing_service import ComprehensiveIndexingService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Index compliance documents (SOC2, policies, risk controls)"
    )
    
    # File paths
    parser.add_argument(
        "--policy-pdf",
        type=str,
        help="Path to policy PDF file"
    )
    parser.add_argument(
        "--risk-controls-excel",
        type=str,
        help="Path to risk controls Excel file"
    )
    parser.add_argument(
        "--soc2-pdf",
        type=str,
        help="Path to SOC2 controls PDF file"
    )
    parser.add_argument(
        "--soc2-excel",
        type=str,
        help="Path to SOC2 controls Excel file"
    )
    
    # Flags for document types
    parser.add_argument(
        "--index-policies",
        action="store_true",
        help="Index policy documents"
    )
    parser.add_argument(
        "--index-risk-controls",
        action="store_true",
        help="Index risk controls"
    )
    parser.add_argument(
        "--index-soc2",
        action="store_true",
        help="Index SOC2 controls"
    )
    parser.add_argument(
        "--comprehensive",
        action="store_true",
        help="Index all document types (comprehensive mode)"
    )
    
    # Options
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview mode: save to files instead of indexing in database"
    )
    parser.add_argument(
        "--preview-dir",
        type=str,
        default="indexing_preview",
        help="Directory for preview files (default: indexing_preview)"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="compliance",
        help="Domain filter (default: compliance)"
    )
    parser.add_argument(
        "--vector-store",
        type=str,
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    args = parser.parse_args()
    
    # Initialize indexing service
    persistent_client = get_chromadb_client() if args.vector_store == "chroma" else None
    embeddings = get_embeddings_model()
    llm = get_llm(temperature=0.2)
    
    indexing_service = ComprehensiveIndexingService(
        vector_store_type=args.vector_store,
        persistent_client=persistent_client,
        embeddings_model=embeddings,
        llm=llm,
        collection_prefix="compliance_baseline",
        preview_mode=args.preview,
        preview_output_dir=args.preview_dir
    )
    
    results = {}
    
    # Determine what to index
    if args.comprehensive:
        # Index everything that has files provided
        logger.info("Running in comprehensive mode - indexing all document types with provided files")
        # Only enable indexing for document types that have files
        if args.policy_pdf:
            args.index_policies = True
        if args.risk_controls_excel:
            args.index_risk_controls = True
        if args.soc2_pdf or args.soc2_excel:
            args.index_soc2 = True
        
        # Warn if no files provided at all
        if not (args.policy_pdf or args.risk_controls_excel or args.soc2_pdf or args.soc2_excel):
            logger.warning("--comprehensive specified but no file paths provided. Please provide at least one file:")
            logger.warning("  --policy-pdf <path>")
            logger.warning("  --risk-controls-excel <path>")
            logger.warning("  --soc2-pdf <path> or --soc2-excel <path>")
    
    # Index policies
    if args.index_policies:
        if args.policy_pdf:
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Policy Document")
            logger.info(f"{'='*50}")
            logger.info(f"Policy document will be split by policy sections from table of contents")
            logger.info(f"Each policy section will be processed with extraction types: context, entities, evidence, fields, controls, requirements, full_content")
            logger.info(f"\nStorage locations:")
            logger.info(f"  - context, requirement, full_content -> domain_knowledge (type='policy')")
            logger.info(f"  - entities -> entities (type='policy')")
            logger.info(f"  - evidence -> evidence (type='policy')")
            logger.info(f"  - fields -> fields (type='policy')")
            logger.info(f"  - control -> controls (type='policy')")
            try:
                result = await indexing_service.index_policy_document(
                    file_path=args.policy_pdf,
                    domain=args.domain,
                    metadata={"source": "cli", "comprehensive": args.comprehensive}
                )
                results["policy"] = result
                logger.info(f"Policy indexing result: {result}")
                
                # Log breakdown if available
                if result.get("breakdown"):
                    logger.info(f"Policy sections breakdown:")
                    for ext_type, count in result["breakdown"].items():
                        if isinstance(count, dict) and count.get("count"):
                            logger.info(f"  {ext_type}: {count['count']} documents")
                        elif isinstance(count, int):
                            logger.info(f"  {ext_type}: {count} documents")
            except Exception as e:
                logger.error(f"Error indexing policy document: {e}")
                results["policy"] = {"error": str(e)}
        else:
            logger.warning("--index-policies specified but --policy-pdf not provided (skipping)")
    
    # Index risk controls
    if args.index_risk_controls:
        if args.risk_controls_excel:
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Risk Controls")
            logger.info(f"{'='*50}")
            logger.info(f"\nStorage locations (based on extraction_type):")
            logger.info(f"  - control -> controls (type='risk_control')")
            logger.info(f"  - entities -> entities (type='risk_entities')")
            logger.info(f"  - fields -> fields (type='risk_fields')")
            logger.info(f"  - evidence -> evidence (type='risk_evidence')")
            logger.info(f"  - requirements, context, base -> domain_knowledge (type='risk_*')")
            try:
                result = await indexing_service.index_risk_controls(
                    file_path=args.risk_controls_excel,
                    domain=args.domain,
                    metadata={"source": "cli", "comprehensive": args.comprehensive}
                )
                results["risk_controls"] = result
                logger.info(f"Risk controls indexing result: {result}")
            except Exception as e:
                logger.error(f"Error indexing risk controls: {e}")
                results["risk_controls"] = {"error": str(e)}
        else:
            logger.warning("--index-risk-controls specified but --risk-controls-excel not provided (skipping)")
    
    # Index SOC2 controls
    if args.index_soc2:
        soc2_file = args.soc2_pdf or args.soc2_excel
        if soc2_file:
            logger.info(f"\n{'='*50}")
            logger.info("Indexing SOC2 Controls")
            logger.info(f"{'='*50}")
            logger.info(f"\nStorage location:")
            logger.info(f"  - All documents -> compliance_controls (framework='SOC2' in metadata)")
            try:
                result = await indexing_service.index_soc2_controls(
                    file_path=soc2_file,
                    domain=args.domain,
                    metadata={"source": "cli", "comprehensive": args.comprehensive}
                )
                results["soc2_controls"] = result
                logger.info(f"SOC2 controls indexing result: {result}")
            except Exception as e:
                logger.error(f"Error indexing SOC2 controls: {e}")
                results["soc2_controls"] = {"error": str(e)}
        else:
            logger.warning("--index-soc2 specified but --soc2-pdf or --soc2-excel not provided (skipping)")
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("Indexing Summary")
    logger.info(f"{'='*50}")
    for doc_type, result in results.items():
        if result.get("preview_mode"):
            logger.info(f"{doc_type}: Preview mode - saved to {result.get('file_storage', {}).get('file_path', 'N/A')}")
        elif result.get("success"):
            logger.info(f"{doc_type}: Successfully indexed {result.get('documents_indexed', 0)} documents")
        else:
            logger.error(f"{doc_type}: Error - {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())

