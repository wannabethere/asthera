"""
CLI for indexing feature knowledge JSON files.
"""
import argparse
import logging
from pathlib import Path

from app.indexing.feature_indexing_service import FeatureIndexingService
from app.indexing.feature_feedback_service import FeatureFeedbackService
from app.core.dependencies import get_chromadb_client, get_embeddings_model, get_llm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Index feature knowledge JSON files or add feature feedback"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Index command
    index_parser = subparsers.add_parser("index", help="Index feature knowledge files")
    index_parser.add_argument(
        "--file",
        type=str,
        help="Path to feature knowledge JSON file"
    )
    index_parser.add_argument(
        "--directory",
        type=str,
        help="Path to directory containing feature knowledge JSON files"
    )
    index_parser.add_argument(
        "--compliance",
        type=str,
        help="Override compliance framework (SOC2, HIPAA, etc.)"
    )
    
    # Feedback command
    feedback_parser = subparsers.add_parser("feedback", help="Add feature feedback")
    feedback_parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Natural language question for the feature"
    )
    feedback_parser.add_argument(
        "--type",
        type=str,
        required=True,
        choices=["control", "risk", "impact", "likelihood", "evidence", "effectiveness"],
        help="Type of feature"
    )
    feedback_parser.add_argument(
        "--compliance",
        type=str,
        required=True,
        help="Compliance framework (SOC2, HIPAA, etc.)"
    )
    feedback_parser.add_argument(
        "--control",
        type=str,
        help="Optional control identifier"
    )
    feedback_parser.add_argument(
        "--description",
        type=str,
        help="Optional description of the feature"
    )
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search for features")
    search_parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Search query"
    )
    search_parser.add_argument(
        "--type",
        type=str,
        choices=["control", "risk", "impact", "likelihood", "evidence", "effectiveness"],
        help="Filter by feature type"
    )
    search_parser.add_argument(
        "--compliance",
        type=str,
        help="Filter by compliance framework"
    )
    search_parser.add_argument(
        "--control",
        type=str,
        help="Filter by control"
    )
    search_parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Number of results (default: 10)"
    )
    
    # Common options
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
        "--vector-store",
        type=str,
        choices=["chroma", "qdrant"],
        default="chroma",
        help="Vector store type (default: chroma)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize services
    persistent_client = get_chromadb_client() if args.vector_store == "chroma" else None
    embeddings = get_embeddings_model()
    
    if args.command == "index":
        # Indexing service
        indexing_service = FeatureIndexingService(
            vector_store_type=args.vector_store,
            persistent_client=persistent_client,
            embeddings_model=embeddings,
            collection_prefix="feature_store",
            preview_mode=args.preview,
            preview_output_dir=args.preview_dir
        )
        
        if args.file:
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Feature Knowledge File")
            logger.info(f"{'='*50}")
            logger.info(f"File: {args.file}")
            try:
                result = indexing_service.index_feature_knowledge_file(
                    file_path=args.file,
                    compliance=args.compliance
                )
                logger.info(f"Indexing result: {result}")
                
                if result.get("success"):
                    logger.info(f"Successfully indexed {result.get('features_indexed', 0)} features")
                    if result.get("by_type"):
                        logger.info("Features by type:")
                        for feature_type, count in result["by_type"].items():
                            logger.info(f"  {feature_type}: {count}")
                    if result.get("by_category"):
                        logger.info("Features by category:")
                        for category, count in result["by_category"].items():
                            logger.info(f"  {category}: {count}")
                else:
                    logger.error(f"Indexing failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Error indexing feature knowledge file: {e}")
        
        elif args.directory:
            logger.info(f"\n{'='*50}")
            logger.info("Indexing Feature Knowledge Directory")
            logger.info(f"{'='*50}")
            logger.info(f"Directory: {args.directory}")
            try:
                result = indexing_service.index_feature_knowledge_directory(
                    directory_path=args.directory,
                    compliance=args.compliance
                )
                logger.info(f"Indexing result: {result}")
                
                logger.info(f"Processed {result.get('files_processed', 0)} files")
                logger.info(f"  Succeeded: {result.get('files_succeeded', 0)}")
                logger.info(f"  Failed: {result.get('files_failed', 0)}")
                logger.info(f"Total features indexed: {result.get('total_features_indexed', 0)}")
                
                if result.get("file_results"):
                    logger.info("\nFile results:")
                    for file_result in result["file_results"]:
                        status = "✓" if file_result.get("success") else "✗"
                        logger.info(f"  {status} {file_result.get('file')}: {file_result.get('features_indexed', 0)} features")
            except Exception as e:
                logger.error(f"Error indexing feature knowledge directory: {e}")
        else:
            logger.error("Either --file or --directory must be specified")
    
    elif args.command == "feedback":
        # Feedback service
        feedback_service = FeatureFeedbackService(
            vector_store_type=args.vector_store,
            persistent_client=persistent_client,
            embeddings_model=embeddings,
            collection_prefix="feature_store"
        )
        
        logger.info(f"\n{'='*50}")
        logger.info("Adding Feature Feedback")
        logger.info(f"{'='*50}")
        try:
            result = feedback_service.add_feature(
                question=args.question,
                feature_type=args.type,
                compliance=args.compliance,
                control=args.control,
                description=args.description
            )
            
            if result.get("success"):
                logger.info(f"Successfully added feature feedback")
                logger.info(f"  Feature ID: {result.get('feature_id')}")
                logger.info(f"  Question: {result.get('question')}")
                logger.info(f"  Type: {result.get('feature_type')}")
                logger.info(f"  Compliance: {result.get('compliance')}")
                if result.get("control"):
                    logger.info(f"  Control: {result.get('control')}")
            else:
                logger.error(f"Failed to add feature feedback: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error adding feature feedback: {e}")
    
    elif args.command == "search":
        # Feedback service (for search)
        feedback_service = FeatureFeedbackService(
            vector_store_type=args.vector_store,
            persistent_client=persistent_client,
            embeddings_model=embeddings,
            collection_prefix="feature_store"
        )
        
        logger.info(f"\n{'='*50}")
        logger.info("Searching Features")
        logger.info(f"{'='*50}")
        logger.info(f"Query: {args.query}")
        try:
            result = feedback_service.search_features(
                query=args.query,
                feature_type=args.type,
                compliance=args.compliance,
                control=args.control,
                k=args.k
            )
            
            if result.get("success"):
                logger.info(f"Found {result.get('count', 0)} results")
                for i, feature in enumerate(result.get("results", []), 1):
                    logger.info(f"\n{i}. {feature.get('question', 'N/A')}")
                    logger.info(f"   Type: {feature.get('feature_type', 'N/A')}")
                    logger.info(f"   Compliance: {feature.get('compliance', 'N/A')}")
                    if feature.get("control"):
                        logger.info(f"   Control: {feature.get('control')}")
                    logger.info(f"   Score: {feature.get('score', 0):.4f}")
            else:
                logger.error(f"Search failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error searching features: {e}")


if __name__ == "__main__":
    main()

