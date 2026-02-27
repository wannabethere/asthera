"""
Generate project_metadata.json files from flat MDL files to make them compatible
with the existing ProjectReader indexing system.

This script:
1. Scans a directory for MDL files (e.g., leenmodels/)
2. Optionally scans for metrics files (e.g., leenmodelmetrics/)
3. Creates project directories with project_metadata.json files
4. Copies/links MDL files into the project structure
5. Optionally indexes them using the existing ProjectReaderQdrant system
"""
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse

logger = logging.getLogger("genieml-agents")


def extract_schema_info_from_mdl(mdl_file: Path) -> Dict[str, Any]:
    """Extract schema information from an MDL file."""
    try:
        with open(mdl_file, 'r') as f:
            mdl_dict = json.load(f)
        
        schema = mdl_dict.get('schema', 'unknown')
        catalog = mdl_dict.get('catalog', 'product_knowledge')
        models = mdl_dict.get('models', [])
        
        # Get primary model (first model or model with most columns)
        primary_model = None
        if models:
            primary_model = max(models, key=lambda m: len(m.get('columns', [])))
        
        return {
            'schema': schema,
            'catalog': catalog,
            'models': models,
            'primary_model': primary_model,
            'model_count': len(models)
        }
    except Exception as e:
        logger.error(f"Error reading MDL file {mdl_file}: {e}")
        return {}


def generate_project_metadata(
    mdl_file: Path,
    metrics_file: Optional[Path] = None,
    output_base: Path = None
) -> Dict[str, Any]:
    """
    Generate project_metadata.json structure for a single MDL file.
    
    Args:
        mdl_file: Path to MDL file
        metrics_file: Optional path to metrics JSON file
        output_base: Base directory where project structure will be created
    
    Returns:
        Dictionary with project_metadata.json structure
    """
    # Extract schema info
    mdl_info = extract_schema_info_from_mdl(mdl_file)
    if not mdl_info:
        return None
    
    schema = mdl_info['schema']
    primary_model = mdl_info['primary_model']
    
    # Extract layer from filename (e.g., "aws_guardduty_silver.mdl.json" -> "silver")
    base_name = mdl_file.stem  # e.g., "aws_guardduty_silver"
    layer = None
    if '_silver' in base_name:
        layer = 'silver'
    elif '_gold' in base_name:
        layer = 'gold'
    elif '_bronze' in base_name:
        layer = 'bronze'
    
    # Create project_id (e.g., "aws_guardduty.silver" or "aws_guardduty")
    if layer:
        project_id = f"{schema}.{layer}"
        project_key = f"{schema}_{layer}"
    else:
        project_id = schema
        project_key = schema
    
    # Generate description
    model_name = primary_model.get('name', '') if primary_model else ''
    model_desc = primary_model.get('properties', {}).get('description', '') if primary_model else ''
    description = f"MDL schema for {schema} catalog with {mdl_info['model_count']} models"
    if model_name:
        description += f". Primary model: {model_name}"
    if layer:
        description += f" ({layer} layer)"
    
    # Build project metadata structure
    metadata = {
        "project_id": project_id,
        "tables": [
            {
                "name": model_name or schema,
                "display_name": primary_model.get('properties', {}).get('displayName', model_name or schema) if primary_model else schema,
                "description": description,
                "mdl_file": mdl_file.name  # Just the filename, will be copied to project dir
            }
        ],
        "knowledge_base": [],
        "examples": []
    }
    
    # Add metrics file reference if available
    if metrics_file and metrics_file.exists():
        metadata["metrics_file"] = metrics_file.name
    
    return {
        'project_id': project_id,
        'project_key': project_key,
        'metadata': metadata,
        'mdl_file': mdl_file,
        'metrics_file': metrics_file,
        'layer': layer,
        'schema': schema
    }


def create_project_structure(
    project_info: Dict[str, Any],
    output_base: Path,
    copy_files: bool = True
) -> Path:
    """
    Create project directory structure with project_metadata.json and copy files.
    
    Args:
        project_info: Dictionary from generate_project_metadata
        output_base: Base directory for projects (e.g., sql_meta/)
        copy_files: If True, copy files; if False, create symlinks
    
    Returns:
        Path to created project directory
    """
    project_key = project_info['project_key']
    project_dir = output_base / project_key
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Write project_metadata.json
    metadata_file = project_dir / "project_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(project_info['metadata'], f, indent=2)
    logger.info(f"Created {metadata_file}")
    
    # Copy/link MDL file
    mdl_source = project_info['mdl_file']
    mdl_dest = project_dir / mdl_source.name
    if copy_files:
        shutil.copy2(mdl_source, mdl_dest)
        logger.info(f"Copied MDL file: {mdl_dest}")
    else:
        if mdl_dest.exists():
            mdl_dest.unlink()
        mdl_dest.symlink_to(mdl_source.resolve())
        logger.info(f"Linked MDL file: {mdl_dest} -> {mdl_source}")
    
    # Copy/link metrics file if available
    if project_info.get('metrics_file') and project_info['metrics_file'].exists():
        metrics_source = project_info['metrics_file']
        metrics_dest = project_dir / metrics_source.name
        if copy_files:
            shutil.copy2(metrics_source, metrics_dest)
            logger.info(f"Copied metrics file: {metrics_dest}")
        else:
            if metrics_dest.exists():
                metrics_dest.unlink()
            metrics_dest.symlink_to(metrics_source.resolve())
            logger.info(f"Linked metrics file: {metrics_dest} -> {metrics_source}")
    
    return project_dir


def generate_all_project_metadata(
    mdl_dir: str,
    metrics_dir: Optional[str] = None,
    output_dir: str = None,
    copy_files: bool = True,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate project metadata for all MDL files in a directory.
    
    Args:
        mdl_dir: Directory containing MDL files
        metrics_dir: Optional directory containing metrics JSON files
        output_dir: Directory where project structures will be created (default: mdl_dir/../sql_meta)
        copy_files: If True, copy files; if False, create symlinks
        dry_run: If True, don't create files, just return metadata
    
    Returns:
        List of project info dictionaries
    """
    mdl_path = Path(mdl_dir)
    if not mdl_path.exists():
        logger.error(f"MDL directory does not exist: {mdl_path}")
        return []
    
    # Determine output directory
    if output_dir:
        output_base = Path(output_dir)
    else:
        # Default to sql_meta directory next to mdl_dir
        output_base = mdl_path.parent / "sql_meta"
    
    # Load metrics files if metrics_dir provided
    metrics_map = {}
    if metrics_dir:
        metrics_path = Path(metrics_dir)
        if metrics_path.exists():
            metrics_files = list(metrics_path.glob("*_metrics.json"))
            logger.info(f"Found {len(metrics_files)} metrics file(s)")
            for metrics_file in metrics_files:
                # Extract schema name (e.g., "aws_guardduty_metrics.json" -> "aws_guardduty")
                schema_name = metrics_file.stem.replace('_metrics', '')
                metrics_map[schema_name] = metrics_file
    
    # Find all MDL files
    mdl_files = list(mdl_path.glob("*.mdl.json"))
    if not mdl_files:
        logger.warning(f"No MDL files found in {mdl_path}")
        return []
    
    logger.info(f"Found {len(mdl_files)} MDL file(s)")
    
    projects = []
    for mdl_file in mdl_files:
        try:
            # Extract schema name to match with metrics
            base_name = mdl_file.stem
            if '_' in base_name:
                parts = base_name.split('_')
                if parts[-1] in ['silver', 'gold', 'bronze']:
                    schema_name = '_'.join(parts[:-1])
                else:
                    schema_name = base_name
            else:
                schema_name = base_name
            
            # Find matching metrics file
            metrics_file = metrics_map.get(schema_name)
            
            # Generate project metadata
            project_info = generate_project_metadata(
                mdl_file=mdl_file,
                metrics_file=metrics_file,
                output_base=output_base
            )
            
            if not project_info:
                logger.warning(f"Failed to generate metadata for {mdl_file.name}")
                continue
            
            projects.append(project_info)
            
            if not dry_run:
                # Create project structure
                project_dir = create_project_structure(
                    project_info=project_info,
                    output_base=output_base,
                    copy_files=copy_files
                )
                logger.info(f"Created project: {project_dir}")
            else:
                logger.info(f"[DRY RUN] Would create project: {project_info['project_key']}")
            
        except Exception as e:
            logger.error(f"Error processing {mdl_file.name}: {e}", exc_info=True)
    
    return projects


async def index_generated_projects(
    sql_meta_dir: str,
    host: Optional[str] = None,
    port: int = 6333,
    delete_existing: bool = True,
    project_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Index all generated projects using the existing ProjectReaderQdrant system.
    
    Args:
        sql_meta_dir: Directory containing generated project structures
        host: Qdrant host
        port: Qdrant port
        delete_existing: Delete existing data before re-indexing
        project_prefix: Optional prefix to filter projects
    
    Returns:
        Summary dictionary from ingest_all_projects_from_sql_meta
    """
    from app.indexing.project_reader_qdrant import ingest_all_projects_from_sql_meta
    
    logger.info("Indexing generated projects into Qdrant...")
    summary = await ingest_all_projects_from_sql_meta(
        base_path=sql_meta_dir,
        project_name_prefix=project_prefix,
        delete_existing=delete_existing,
        fail_fast=False,
        host=host,
        port=port,
    )
    
    return summary


async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate project_metadata.json files from flat MDL files"
    )
    parser.add_argument(
        "--mdl-dir",
        type=str,
        required=True,
        help="Directory containing MDL files (e.g., leenmodels/)"
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default=None,
        help="Directory containing metrics JSON files (e.g., leenmodelmetrics/)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for project structures (default: mdl_dir/../sql_meta)"
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Create symlinks instead of copying files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't create files, just show what would be created"
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Index generated projects into Qdrant after creation"
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Don't delete existing project data before indexing (only used with --index)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Qdrant host (default: from settings or localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6333,
        help="Qdrant port (default: from settings or 6333)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Filter projects by prefix when indexing (only used with --index)"
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Generate project metadata
    logger.info("=" * 60)
    logger.info("Generating project metadata from MDL files")
    logger.info("=" * 60)
    
    projects = generate_all_project_metadata(
        mdl_dir=args.mdl_dir,
        metrics_dir=args.metrics_dir,
        output_dir=args.output_dir,
        copy_files=not args.symlink,
        dry_run=args.dry_run
    )
    
    if not projects:
        logger.error("No projects generated")
        return
    
    logger.info(f"\nGenerated {len(projects)} project(s)")
    
    # Show summary
    logger.info("\n" + "=" * 60)
    logger.info("GENERATED PROJECTS SUMMARY")
    logger.info("=" * 60)
    for project in projects:
        logger.info(f"  {project['project_key']}: {project['project_id']} ({project.get('layer', 'no layer')})")
    
    # Index projects if requested
    if args.index and not args.dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("Indexing projects into Qdrant")
        logger.info("=" * 60)
        
        output_base = Path(args.output_dir) if args.output_dir else Path(args.mdl_dir).parent / "sql_meta"
        
        summary = await index_generated_projects(
            sql_meta_dir=str(output_base),
            host=args.host,
            port=args.port,
            delete_existing=not args.no_delete,
            project_prefix=args.prefix
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("INDEXING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total: {summary['total']}")
        logger.info(f"Succeeded: {len(summary['succeeded'])}")
        if summary['failed']:
            logger.warning(f"Failed: {len(summary['failed'])}")
            for failed in summary['failed'][:5]:
                logger.warning(f"  - {failed}: {summary['errors'].get(failed, 'Unknown error')}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
