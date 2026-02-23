"""
Prepare MDL files for ingestion by ProjectReaderQdrant.

This script:
1. Reads MDL files from mdl_schemas/ (qualys/, sentinel/, snyk/, wiz/)
2. Creates separate project folders in sql_meta/ (e.g., qualys_assets/)
3. Generates project_metadata.json for each MDL file
4. Copies MDL files to their respective project folders

Project ID format: {folder}.{filename} (e.g., qualys.assets)
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def extract_mdl_metadata(mdl_path: Path) -> Dict[str, Any]:
    """Extract metadata from MDL file to generate project description."""
    try:
        with open(mdl_path, "r", encoding="utf-8") as f:
            mdl_data = json.load(f)
        
        catalog = mdl_data.get("catalog", "unknown")
        schema = mdl_data.get("schema", "unknown")
        models = mdl_data.get("models", [])
        enums = mdl_data.get("enums", [])
        metrics = mdl_data.get("metrics", [])
        views = mdl_data.get("views", [])
        
        # Count models and get first model name for description
        model_count = len(models)
        first_model_name = models[0].get("name", "") if models else ""
        
        # Generate description
        parts = []
        if model_count > 0:
            parts.append(f"{model_count} model{'s' if model_count > 1 else ''}")
        if len(enums) > 0:
            parts.append(f"{len(enums)} enum{'s' if len(enums) > 1 else ''}")
        if len(metrics) > 0:
            parts.append(f"{len(metrics)} metric{'s' if len(metrics) > 1 else ''}")
        if len(views) > 0:
            parts.append(f"{len(views)} view{'s' if len(views) > 1 else ''}")
        
        description = f"MDL schema for {schema} catalog with {', '.join(parts)}"
        if first_model_name:
            description += f". Primary model: {first_model_name}"
        
        return {
            "catalog": catalog,
            "schema": schema,
            "model_count": model_count,
            "enum_count": len(enums),
            "metric_count": len(metrics),
            "view_count": len(views),
            "description": description,
        }
    except Exception as e:
        logger.warning(f"Could not extract metadata from {mdl_path}: {e}")
        return {
            "catalog": "unknown",
            "schema": "unknown",
            "model_count": 0,
            "enum_count": 0,
            "metric_count": 0,
            "view_count": 0,
            "description": f"MDL schema from {mdl_path.name}",
        }


def generate_project_metadata(
    folder_name: str,
    mdl_filename: str,
    project_id: str,
    mdl_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate project_metadata.json content."""
    # Extract table name from filename (remove .mdl.json)
    table_name = mdl_filename.replace(".mdl.json", "").replace("_", " ")
    # Capitalize first letter of each word
    display_name = " ".join(word.capitalize() for word in table_name.split())
    
    # Use schema from MDL if available, otherwise use folder name
    schema_name = mdl_metadata.get("schema", folder_name)
    
    return {
        "project_id": project_id,
        "tables": [
            {
                "name": table_name.replace(" ", "_"),
                "display_name": display_name,
                "description": mdl_metadata["description"],
                "mdl_file": mdl_filename,
            }
        ],
        "knowledge_base": [],
        "examples": [],
    }


def process_mdl_file(
    mdl_path: Path,
    output_base: Path,
    folder_name: str,
) -> Optional[str]:
    """
    Process a single MDL file.
    
    Args:
        mdl_path: Path to the MDL file
        output_base: Base directory for output (sql_meta/)
        folder_name: Source folder name (qualys, sentinel, etc.)
    
    Returns:
        Project ID if successful, None otherwise
    """
    mdl_filename = mdl_path.name
    
    # Generate project_id: folder.filename (without .mdl.json)
    project_id_base = mdl_filename.replace(".mdl.json", "")
    project_id = f"{folder_name}.{project_id_base}"
    
    # Create project folder name: folder_filename (e.g., qualys_assets)
    project_folder_name = f"{folder_name}_{project_id_base}"
    project_folder = output_base / project_folder_name
    
    logger.info(f"Processing: {mdl_path.name} -> {project_id} ({project_folder_name})")
    
    # Extract metadata from MDL
    mdl_metadata = extract_mdl_metadata(mdl_path)
    
    # Create project folder
    project_folder.mkdir(parents=True, exist_ok=True)
    
    # Generate project_metadata.json
    project_metadata = generate_project_metadata(
        folder_name=folder_name,
        mdl_filename=mdl_filename,
        project_id=project_id,
        mdl_metadata=mdl_metadata,
    )
    
    # Write project_metadata.json
    metadata_path = project_folder / "project_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(project_metadata, f, indent=2, ensure_ascii=False)
    logger.info(f"  Created: {metadata_path}")
    
    # Copy MDL file to project folder
    target_mdl_path = project_folder / mdl_filename
    shutil.copy2(mdl_path, target_mdl_path)
    logger.info(f"  Copied: {target_mdl_path}")
    
    return project_id


def process_mdl_schemas(
    mdl_schemas_dir: Path,
    output_base: Path,
    folders: Optional[list] = None,
) -> Dict[str, list]:
    """
    Process all MDL files from specified folders.
    
    Args:
        mdl_schemas_dir: Directory containing MDL schema folders (qualys/, sentinel/, etc.)
        output_base: Base directory for output projects (sql_meta/)
        folders: List of folder names to process (None = all)
    
    Returns:
        Dictionary mapping folder names to list of project IDs created
    """
    results = {}
    
    # Default folders if not specified
    if folders is None:
        folders = ["qualys", "sentinel", "snyk", "wiz"]
    
    for folder_name in folders:
        folder_path = mdl_schemas_dir / folder_name
        if not folder_path.exists() or not folder_path.is_dir():
            logger.warning(f"Folder not found: {folder_path}")
            continue
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing folder: {folder_name}")
        logger.info(f"{'=' * 60}")
        
        project_ids = []
        
        # Find all .mdl.json files
        mdl_files = sorted(folder_path.glob("*.mdl.json"))
        if not mdl_files:
            logger.warning(f"No MDL files found in {folder_path}")
            continue
        
        for mdl_path in mdl_files:
            try:
                project_id = process_mdl_file(mdl_path, output_base, folder_name)
                if project_id:
                    project_ids.append(project_id)
            except Exception as e:
                logger.error(f"Failed to process {mdl_path}: {e}", exc_info=True)
        
        results[folder_name] = project_ids
        logger.info(f"\nProcessed {len(project_ids)} projects from {folder_name}")
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare MDL files for ingestion by ProjectReaderQdrant"
    )
    parser.add_argument(
        "--mdl-schemas-dir",
        type=str,
        default="../../mdl_schemas",
        help="Directory containing MDL schema folders (default: ../../mdl_schemas)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="../../../genieml/data/sql_meta",
        help="Output directory for project folders (default: ../../../genieml/data/sql_meta)",
    )
    parser.add_argument(
        "--folders",
        nargs="*",
        default=None,
        help="Specific folders to process (default: all: qualys, sentinel, snyk, wiz)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    
    args = parser.parse_args()
    
    mdl_schemas_dir = Path(args.mdl_schemas_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    
    if not mdl_schemas_dir.exists():
        logger.error(f"MDL schemas directory not found: {mdl_schemas_dir}")
        return 1
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info(f"MDL schemas directory: {mdl_schemas_dir}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Folders to process: {args.folders or ['qualys', 'sentinel', 'snyk', 'wiz']}")
        return 0
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process MDL files
    results = process_mdl_schemas(
        mdl_schemas_dir=mdl_schemas_dir,
        output_base=output_dir,
        folders=args.folders,
    )
    
    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info("SUMMARY")
    logger.info(f"{'=' * 60}")
    total_projects = 0
    for folder_name, project_ids in results.items():
        count = len(project_ids)
        total_projects += count
        logger.info(f"  {folder_name}: {count} projects")
        if project_ids:
            logger.info(f"    Examples: {', '.join(project_ids[:3])}")
            if len(project_ids) > 3:
                logger.info(f"    ... and {len(project_ids) - 3} more")
    
    logger.info(f"\nTotal projects created: {total_projects}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("\nYou can now use ProjectReaderQdrant to index these projects:")
    logger.info("  from app.indexing.project_reader_qdrant import ProjectReaderQdrant")
    logger.info(f"  reader = ProjectReaderQdrant(base_path='{output_dir}')")
    logger.info("  await reader.index_project('qualys.assets')")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
