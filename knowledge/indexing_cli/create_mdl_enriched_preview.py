"""
Create MDL Enriched Preview Files
==================================

Creates preview files for MDL enriched entities that can be ingested later.
Includes organization configuration (static, not stored in chroma).

Preview files created:
- table_definitions: Table schemas with enriched metadata
- table_descriptions: Table descriptions with categories
- column_definitions: Column metadata with time concepts
- knowledgebase: Features, metrics, instructions, examples
- contextual_edges: Relationships between all entities

Usage:
    python -m indexing_cli.create_mdl_enriched_preview \
        --mdl-file ../data/cvedata/snyk_mdl1.json \
        --product-name "Snyk" \
        --preview-dir indexing_preview
"""

import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from langchain_core.documents import Document

from app.core.dependencies import get_llm
from app.config.organization_config import get_product_organization, get_organization_metadata
from app.services.contextual_graph_storage import ContextualEdge
from indexing_cli.index_mdl_enriched import (
    extract_enriched_metadata,
    EnrichedTableMetadata,
    categorize_table
)
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MDLEnrichedPreviewGenerator:
    """Generates preview files for MDL enriched entities."""
    
    def __init__(
        self,
        mdl_file_path: str,
        product_name: str,
        preview_dir: str = "indexing_preview",
        project_id: Optional[str] = None,
        batch_size: Optional[int] = None
    ):
        """
        Initialize preview generator.
        
        Args:
            mdl_file_path: Path to MDL JSON file
            product_name: Product name (e.g., "Snyk")
            preview_dir: Directory for preview files
            project_id: Optional project ID (defaults to product_name)
            batch_size: Optional batch size for parallel LLM extraction (None = all at once)
        """
        self.mdl_file_path = Path(mdl_file_path)
        self.product_name = product_name
        self.project_id = project_id or product_name
        self.preview_dir = Path(preview_dir)
        self.batch_size = batch_size
        
        # Get organization config (static, not stored in chroma)
        self.organization = get_product_organization(product_name)
        self.organization_metadata = get_organization_metadata(product_name)
        
        logger.info(f"Organization: {self.organization.organization_name} ({self.organization.organization_id})")
        logger.info(f"Organization metadata will be included but NOT stored in chroma")
    
    async def generate_all_previews(self) -> Dict[str, Any]:
        """
        Generate all preview files.
        
        Returns:
            Dictionary with generation results
        """
        logger.info("=" * 80)
        logger.info("MDL Enriched Preview Generation")
        logger.info("=" * 80)
        logger.info(f"MDL File: {self.mdl_file_path}")
        logger.info(f"Product: {self.product_name}")
        logger.info(f"Project ID: {self.project_id}")
        logger.info(f"Organization: {self.organization.organization_name}")
        logger.info(f"Preview Dir: {self.preview_dir}")
        logger.info("")
        
        # Load MDL
        if not self.mdl_file_path.exists():
            raise FileNotFoundError(f"MDL file not found: {self.mdl_file_path}")
        
        logger.info(f"Loading MDL file...")
        with open(self.mdl_file_path, "r", encoding="utf-8") as f:
            mdl_data = json.load(f)
        
        logger.info(f"Loaded MDL with {len(mdl_data.get('models', []))} models")
        
        # Build relationships map
        relationships_map = {}
        for rel in mdl_data.get("relationships", []):
            models = rel.get("models", [])
            if len(models) >= 2:
                source = models[0]
                target = models[1]
                rel_desc = f"{source} -> {target} ({rel.get('joinType', 'UNKNOWN')})"
                relationships_map.setdefault(source, []).append(rel_desc)
                relationships_map.setdefault(target, []).append(rel_desc)
        
        # Extract enriched metadata for all tables
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Extracting Enriched Metadata (BATCHED)")
        logger.info("=" * 80)
        
        llm = get_llm()
        models = mdl_data.get("models", [])
        
        # Create extraction tasks for all tables
        extraction_tasks = []
        valid_models = []
        
        for idx, model in enumerate(models, 1):
            table_name = model.get("name", "")
            if not table_name:
                continue
            
            valid_models.append(model)
            
            # Create extraction task (don't await yet)
            task = extract_enriched_metadata(
                table_name=table_name,
                table_description=model.get("description", ""),
                columns=model.get("columns", []),
                relationships=relationships_map.get(table_name, []),
                product_name=self.product_name,
                llm=llm
            )
            extraction_tasks.append(task)
        
        logger.info(f"Created {len(extraction_tasks)} extraction tasks")
        
        # Execute extraction tasks in batches (if batch_size specified) or all at once
        metadata_results = []
        
        if self.batch_size and self.batch_size > 0:
            logger.info(f"Running LLM extraction in batches of {self.batch_size}...")
            
            # Process in batches
            for i in range(0, len(extraction_tasks), self.batch_size):
                batch_end = min(i + self.batch_size, len(extraction_tasks))
                batch = extraction_tasks[i:batch_end]
                
                logger.info(f"Processing batch {i // self.batch_size + 1}/{(len(extraction_tasks) + self.batch_size - 1) // self.batch_size} ({len(batch)} tables)...")
                
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                metadata_results.extend(batch_results)
                
                logger.info(f"  ✓ Completed batch {i // self.batch_size + 1}")
        else:
            logger.info(f"Running LLM extraction in parallel (all {len(extraction_tasks)} tables at once)...")
            logger.info(f"This may take a few minutes...")
            
            # Execute all at once
            metadata_results = await asyncio.gather(*extraction_tasks, return_exceptions=True)
        
        # Combine models with their extracted metadata
        enriched_tables = []
        success_count = 0
        error_count = 0
        
        for idx, (model, metadata) in enumerate(zip(valid_models, metadata_results), 1):
            table_name = model.get("name", "")
            
            if isinstance(metadata, Exception):
                logger.warning(f"[{idx}/{len(valid_models)}] ✗ Failed to extract metadata for {table_name}: {metadata}")
                # Use fallback metadata
                from indexing_cli.index_mdl_enriched import categorize_table, EnrichedTableMetadata
                metadata = EnrichedTableMetadata(
                    table_name=table_name,
                    category=categorize_table(table_name),
                    business_purpose=model.get("description", f"Table for {table_name} data"),
                    key_insights=[],
                    common_use_cases=[],
                    time_concepts=[],
                    example_queries=[],
                    features=[],
                    metrics=[],
                    instructions=[],
                    key_relationships=relationships_map.get(table_name, [])
                )
                error_count += 1
            else:
                logger.info(f"[{idx}/{len(valid_models)}] ✓ Extracted metadata for {table_name} (category: {metadata.category})")
                success_count += 1
            
            enriched_tables.append({
                "model": model,
                "metadata": metadata
            })
        
        logger.info(f"\n✓ Extracted metadata for {len(enriched_tables)} tables")
        logger.info(f"  Success: {success_count}, Errors: {error_count} (using fallback)")
        
        # Generate preview files
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: Generating Preview Files")
        logger.info("=" * 80)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        results = {}
        
        # 1. Table Definitions
        results["table_definitions"] = await self._generate_table_definitions_preview(
            enriched_tables, timestamp
        )
        
        # 2. Table Descriptions
        results["table_descriptions"] = await self._generate_table_descriptions_preview(
            enriched_tables, timestamp
        )
        
        # 3. Column Definitions
        results["column_definitions"] = await self._generate_column_definitions_preview(
            enriched_tables, timestamp
        )
        
        # 4. Knowledgebase (features, metrics, instructions, examples)
        results["knowledgebase"] = await self._generate_knowledgebase_preview(
            enriched_tables, timestamp
        )
        
        # 5. Contextual Edges (relationships between entities)
        results["contextual_edges"] = await self._generate_contextual_edges_preview(
            enriched_tables, timestamp
        )
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Preview Generation Summary")
        logger.info("=" * 80)
        for content_type, result in results.items():
            if result.get("success"):
                logger.info(f"✓ {content_type}: {result['count']} documents → {result['file']}")
            else:
                logger.error(f"✗ {content_type}: {result.get('error', 'Unknown error')}")
        logger.info("=" * 80)
        
        return results
    
    async def _generate_table_definitions_preview(
        self,
        enriched_tables: List[Dict[str, Any]],
        timestamp: str
    ) -> Dict[str, Any]:
        """Generate table_definitions preview file."""
        try:
            logger.info("\n[1/4] Generating table_definitions preview...")
            
            documents = []
            
            for idx, item in enumerate(enriched_tables):
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                
                # Table definition content
                table_content = {
                    "name": table_name,
                    "mdl_type": "TABLE_SCHEMA",
                    "type": "TABLE_DESCRIPTION",
                    "description": metadata.business_purpose,
                    "columns": ", ".join([col["name"] for col in model.get("columns", [])]),
                    "semantic_description": metadata.business_purpose,
                    "table_purpose": metadata.business_purpose,
                    "business_context": " ".join(metadata.common_use_cases),
                    "key_insights": metadata.key_insights,
                }
                
                # Metadata (includes organization but not stored in chroma)
                doc_metadata = {
                    "content_type": "table_definition",
                    "table_name": table_name,
                    "schema": "public",
                    "product_name": self.product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "column_count": len(model.get("columns", [])),
                    "categories": [metadata.category],
                    "source_file": str(self.mdl_file_path),
                    "mdl_catalog": "api",
                    "mdl_schema": "public",
                    "type": "TABLE_DESCRIPTION",
                    "mdl_type": "TABLE_SCHEMA",
                    "name": table_name,
                    "description": metadata.business_purpose,
                    # Organization metadata (for reference, not stored in chroma)
                    **self.organization_metadata
                }
                
                doc = {
                    "index": idx,
                    "page_content": str(table_content),
                    "metadata": doc_metadata,
                    "content_length": len(str(table_content)),
                    "metadata_keys": list(doc_metadata.keys())
                }
                documents.append(doc)
            
            # Save preview file
            preview_path = self.preview_dir / "table_definitions"
            preview_path.mkdir(parents=True, exist_ok=True)
            
            preview_file = preview_path / f"table_definitions_{timestamp}_{self.product_name}.json"
            
            preview_data = {
                "metadata": {
                    "content_type": "table_definitions",
                    "domain": None,
                    "product_name": self.product_name,
                    "document_count": len(documents),
                    "timestamp": timestamp,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source_file": str(self.mdl_file_path),
                    "source": "mdl",
                    # Organization metadata
                    **self.organization_metadata
                },
                "documents": documents
            }
            
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(preview_data, f, indent=2)
            
            # Save summary
            summary_file = preview_path / f"table_definitions_summary_{timestamp}.txt"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"Table Definitions Preview\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Product: {self.product_name}\n")
                f.write(f"Organization: {self.organization.organization_name}\n")
                f.write(f"Document Count: {len(documents)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Source: {self.mdl_file_path}\n")
            
            logger.info(f"  ✓ Generated {len(documents)} table definitions")
            logger.info(f"  ✓ Saved to: {preview_file}")
            
            return {
                "success": True,
                "count": len(documents),
                "file": str(preview_file)
            }
        
        except Exception as e:
            logger.error(f"  ✗ Error generating table_definitions: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_table_descriptions_preview(
        self,
        enriched_tables: List[Dict[str, Any]],
        timestamp: str
    ) -> Dict[str, Any]:
        """Generate table_descriptions preview file."""
        try:
            logger.info("\n[2/4] Generating table_descriptions preview...")
            
            documents = []
            
            for idx, item in enumerate(enriched_tables):
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                
                # Table description content
                table_content = {
                    "name": table_name,
                    "mdl_type": "TABLE_SCHEMA",
                    "type": "TABLE_DESCRIPTION",
                    "description": metadata.business_purpose,
                    "columns": ", ".join([col["name"] for col in model.get("columns", [])]),
                }
                
                # Metadata
                doc_metadata = {
                    "type": "TABLE_DESCRIPTION",
                    "mdl_type": "TABLE_SCHEMA",
                    "name": table_name,
                    "description": metadata.business_purpose,
                    "relationships": metadata.key_relationships,
                    "content_type": "table_description",
                    "indexed_at": datetime.utcnow().isoformat(),
                    "project_id": self.project_id,
                    "product_name": self.product_name,
                    "source_file": str(self.mdl_file_path),
                    "categories": [metadata.category],
                    "category_name": metadata.category,  # For filtering
                    # Organization metadata
                    **self.organization_metadata
                }
                
                doc = {
                    "index": idx,
                    "page_content": str(table_content),
                    "metadata": doc_metadata,
                    "content_length": len(str(table_content)),
                    "metadata_keys": list(doc_metadata.keys())
                }
                documents.append(doc)
            
            # Save preview file
            preview_path = self.preview_dir / "table_descriptions"
            preview_path.mkdir(parents=True, exist_ok=True)
            
            preview_file = preview_path / f"table_descriptions_{timestamp}_{self.product_name}.json"
            
            preview_data = {
                "metadata": {
                    "content_type": "table_descriptions",
                    "domain": None,
                    "product_name": self.product_name,
                    "document_count": len(documents),
                    "timestamp": timestamp,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source_file": str(self.mdl_file_path),
                    "source": "mdl",
                    **self.organization_metadata
                },
                "documents": documents
            }
            
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(preview_data, f, indent=2)
            
            # Save summary
            summary_file = preview_path / f"table_descriptions_summary_{timestamp}.txt"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"Table Descriptions Preview\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Product: {self.product_name}\n")
                f.write(f"Organization: {self.organization.organization_name}\n")
                f.write(f"Document Count: {len(documents)}\n")
                f.write(f"Timestamp: {timestamp}\n")
            
            logger.info(f"  ✓ Generated {len(documents)} table descriptions")
            logger.info(f"  ✓ Saved to: {preview_file}")
            
            return {
                "success": True,
                "count": len(documents),
                "file": str(preview_file)
            }
        
        except Exception as e:
            logger.error(f"  ✗ Error generating table_descriptions: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_column_definitions_preview(
        self,
        enriched_tables: List[Dict[str, Any]],
        timestamp: str
    ) -> Dict[str, Any]:
        """Generate column_definitions preview file."""
        try:
            logger.info("\n[3/4] Generating column_definitions preview...")
            
            documents = []
            
            for item in enriched_tables:
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                
                # Build time concepts map
                time_map = {tc.column_name: tc for tc in metadata.time_concepts}
                
                for column in model.get("columns", []):
                    if column.get("isHidden"):
                        continue
                    
                    column_name = column["name"]
                    time_info = time_map.get(column_name)
                    
                    # Column content
                    column_content = {
                        "column_name": column_name,
                        "table_name": table_name,
                        "type": column.get("type", ""),
                        "description": column.get("description", ""),
                        "properties": {
                            "description": column.get("description", ""),
                            "business_significance": column.get("description", ""),
                        },
                        # Time concepts merged in
                        "is_time_dimension": time_info.is_time_dimension if time_info else False,
                        "time_granularity": time_info.time_granularity if time_info else None,
                        "is_event_time": time_info.is_event_time if time_info else False,
                        "is_process_time": time_info.is_process_time if time_info else False,
                    }
                    
                    # Metadata
                    doc_metadata = {
                        "content_type": "column_definition",
                        "column_name": column_name,
                        "table_name": table_name,
                        "schema": "public",
                        "data_type": column.get("type", ""),
                        "product_name": self.product_name,
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source_file": str(self.mdl_file_path),
                        "mdl_catalog": "api",
                        "mdl_schema": "public",
                        "type": "COLUMN_DEFINITION",
                        "categories": [metadata.category],
                        "category_name": metadata.category,  # Inherit from table
                        # Organization metadata
                        **self.organization_metadata
                    }
                    
                    doc = {
                        "index": len(documents),
                        "page_content": str(column_content),
                        "metadata": doc_metadata,
                        "content_length": len(str(column_content)),
                        "metadata_keys": list(doc_metadata.keys())
                    }
                    documents.append(doc)
            
            # Save preview file
            preview_path = self.preview_dir / "column_definitions"
            preview_path.mkdir(parents=True, exist_ok=True)
            
            preview_file = preview_path / f"column_definitions_{timestamp}_{self.product_name}.json"
            
            preview_data = {
                "metadata": {
                    "content_type": "column_definitions",
                    "domain": None,
                    "product_name": self.product_name,
                    "document_count": len(documents),
                    "timestamp": timestamp,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source_file": str(self.mdl_file_path),
                    "source": "mdl",
                    **self.organization_metadata
                },
                "documents": documents
            }
            
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(preview_data, f, indent=2)
            
            # Save summary
            summary_file = preview_path / f"column_definitions_summary_{timestamp}.txt"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"Column Definitions Preview\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Product: {self.product_name}\n")
                f.write(f"Organization: {self.organization.organization_name}\n")
                f.write(f"Document Count: {len(documents)}\n")
                f.write(f"Timestamp: {timestamp}\n")
            
            logger.info(f"  ✓ Generated {len(documents)} column definitions")
            logger.info(f"  ✓ Saved to: {preview_file}")
            
            return {
                "success": True,
                "count": len(documents),
                "file": str(preview_file)
            }
        
        except Exception as e:
            logger.error(f"  ✗ Error generating column_definitions: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_knowledgebase_preview(
        self,
        enriched_tables: List[Dict[str, Any]],
        timestamp: str
    ) -> Dict[str, Any]:
        """Generate knowledgebase preview file (features, metrics, instructions, examples)."""
        try:
            logger.info("\n[4/4] Generating knowledgebase preview...")
            
            documents = []
            
            # Generate knowledgebase entities
            for item in enriched_tables:
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                
                # 1. Features
                for feature in metadata.features:
                    feature_content = {
                        "entity_type": "feature",
                        "name": feature.feature_name,
                        "description": feature.description,
                        "calculation_logic": feature.calculation_logic,
                        "use_cases": feature.use_cases,
                        "table_name": table_name,
                        "category": metadata.category,
                    }
                    
                    doc_metadata = {
                        "content_type": "knowledgebase",
                        "entity_type": "feature",
                        "mdl_entity_type": "feature",
                        "entity_name": feature.feature_name,
                        "table_name": table_name,
                        "product_name": self.product_name,
                        "project_id": self.project_id,
                        "category_name": metadata.category,
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source_file": str(self.mdl_file_path),
                        **self.organization_metadata
                    }
                    
                    doc = {
                        "index": len(documents),
                        "page_content": str(feature_content),
                        "metadata": doc_metadata,
                        "content_length": len(str(feature_content)),
                        "metadata_keys": list(doc_metadata.keys())
                    }
                    documents.append(doc)
                
                # 2. Metrics
                for metric in metadata.metrics:
                    metric_content = {
                        "entity_type": "metric",
                        "name": metric.metric_name,
                        "description": metric.description,
                        "calculation": metric.calculation,
                        "metric_category": metric.category,
                        "table_name": table_name,
                        "category": metadata.category,
                    }
                    
                    doc_metadata = {
                        "content_type": "knowledgebase",
                        "entity_type": "metric",
                        "mdl_entity_type": "metric",
                        "entity_name": metric.metric_name,
                        "table_name": table_name,
                        "product_name": self.product_name,
                        "project_id": self.project_id,
                        "category_name": metadata.category,
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source_file": str(self.mdl_file_path),
                        **self.organization_metadata
                    }
                    
                    doc = {
                        "index": len(documents),
                        "page_content": str(metric_content),
                        "metadata": doc_metadata,
                        "content_length": len(str(metric_content)),
                        "metadata_keys": list(doc_metadata.keys())
                    }
                    documents.append(doc)
                
                # 3. Instructions
                for instruction in metadata.instructions:
                    instruction_content = {
                        "entity_type": "instruction",
                        "instruction_type": instruction.instruction_type,
                        "content": instruction.content,
                        "priority": instruction.priority,
                        "table_name": table_name,
                        "category": metadata.category,
                    }
                    
                    doc_metadata = {
                        "content_type": "knowledgebase",
                        "entity_type": "instruction",
                        "instruction_type": instruction.instruction_type,
                        "table_name": table_name,
                        "product_name": self.product_name,
                        "project_id": self.project_id,
                        "category_name": metadata.category,
                        "priority": instruction.priority,
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source_file": str(self.mdl_file_path),
                        **self.organization_metadata
                    }
                    
                    doc = {
                        "index": len(documents),
                        "page_content": str(instruction_content),
                        "metadata": doc_metadata,
                        "content_length": len(str(instruction_content)),
                        "metadata_keys": list(doc_metadata.keys())
                    }
                    documents.append(doc)
                
                # 4. Examples
                for example in metadata.example_queries:
                    example_content = {
                        "entity_type": "example",
                        "question": example.natural_question,
                        "sql": example.sql_query,
                        "complexity": example.complexity,
                        "description": example.description,
                        "table_name": table_name,
                        "category": metadata.category,
                    }
                    
                    doc_metadata = {
                        "content_type": "knowledgebase",
                        "entity_type": "example",
                        "table_name": table_name,
                        "product_name": self.product_name,
                        "project_id": self.project_id,
                        "category_name": metadata.category,
                        "complexity": example.complexity,
                        "indexed_at": datetime.utcnow().isoformat(),
                        "source_file": str(self.mdl_file_path),
                        **self.organization_metadata
                    }
                    
                    doc = {
                        "index": len(documents),
                        "page_content": str(example_content),
                        "metadata": doc_metadata,
                        "content_length": len(str(example_content)),
                        "metadata_keys": list(doc_metadata.keys())
                    }
                    documents.append(doc)
            
            # Save preview file
            preview_path = self.preview_dir / "knowledgebase"
            preview_path.mkdir(parents=True, exist_ok=True)
            
            preview_file = preview_path / f"knowledgebase_{timestamp}_{self.product_name}.json"
            
            preview_data = {
                "metadata": {
                    "content_type": "knowledgebase",
                    "domain": None,
                    "product_name": self.product_name,
                    "document_count": len(documents),
                    "timestamp": timestamp,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source_file": str(self.mdl_file_path),
                    "source": "mdl",
                    "description": "Knowledge base entities: features, metrics, instructions, examples",
                    **self.organization_metadata
                },
                "documents": documents
            }
            
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(preview_data, f, indent=2)
            
            # Save summary
            summary_file = preview_path / f"knowledgebase_summary_{timestamp}.txt"
            
            # Count entity types
            entity_counts = {}
            for doc in documents:
                entity_type = doc["metadata"].get("entity_type", "unknown")
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
            
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"Knowledgebase Preview\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Product: {self.product_name}\n")
                f.write(f"Organization: {self.organization.organization_name}\n")
                f.write(f"Total Documents: {len(documents)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"\nEntity Type Breakdown:\n")
                for entity_type, count in sorted(entity_counts.items()):
                    f.write(f"  - {entity_type}: {count}\n")
            
            logger.info(f"  ✓ Generated {len(documents)} knowledgebase entities")
            logger.info(f"  ✓ Entity breakdown:")
            for entity_type, count in sorted(entity_counts.items()):
                logger.info(f"    - {entity_type}: {count}")
            logger.info(f"  ✓ Saved to: {preview_file}")
            
            return {
                "success": True,
                "count": len(documents),
                "file": str(preview_file),
                "entity_counts": entity_counts
            }
        
        except Exception as e:
            logger.error(f"  ✗ Error generating knowledgebase: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_contextual_edges_preview(
        self,
        enriched_tables: List[Dict[str, Any]],
        timestamp: str
    ) -> Dict[str, Any]:
        """Generate contextual_edges preview file (relationships between entities)."""
        try:
            logger.info(f"\n[5/5] Generating contextual_edges preview...")
            
            edges = []
            
            # Track unique edges to avoid duplicates
            edge_keys = set()
            
            def create_edge(source_id, source_type, target_id, target_type, edge_type, document):
                """Helper to create a unique edge."""
                edge_key = f"{source_id}|{target_id}|{edge_type}"
                if edge_key in edge_keys:
                    return None
                edge_keys.add(edge_key)
                
                return {
                    "edge_id": f"edge_{uuid.uuid4().hex[:12]}",
                    "source_entity_id": source_id,
                    "source_entity_type": source_type,
                    "target_entity_id": target_id,
                    "target_entity_type": target_type,
                    "edge_type": edge_type,
                    "document": document,
                    "context_id": self.product_name.lower().replace(" ", "_"),
                    "relevance_score": 1.0
                }
            
            # Generate edges for each table
            for item in enriched_tables:
                model = item["model"]
                metadata = item["metadata"]
                table_name = model["name"]
                table_id = f"table_{table_name.lower()}"
                category_id = f"category_{metadata.category.lower().replace(' ', '_')}"
                product_id = f"product_{self.product_name.lower().replace(' ', '_')}"
                
                # 1. Product -> Category -> Table hierarchy
                # Product HAS Category
                edge = create_edge(
                    product_id, "product",
                    category_id, "category",
                    "PRODUCT_HAS_CATEGORY",
                    f"{self.product_name} product has {metadata.category} category"
                )
                if edge:
                    edges.append(edge)
                
                # Category HAS Table
                edge = create_edge(
                    category_id, "category",
                    table_id, "table",
                    "CATEGORY_HAS_TABLE",
                    f"{metadata.category} category contains {table_name} table"
                )
                if edge:
                    edges.append(edge)
                
                # Table BELONGS TO Category
                edge = create_edge(
                    table_id, "table",
                    category_id, "category",
                    "TABLE_BELONGS_TO_CATEGORY",
                    f"{table_name} table belongs to {metadata.category} category"
                )
                if edge:
                    edges.append(edge)
                
                # 2. Table -> Column relationships
                for column in model.get("columns", []):
                    if column.get("isHidden"):
                        continue
                    
                    column_name = column["name"]
                    column_id = f"column_{table_name.lower()}_{column_name.lower()}"
                    
                    # Table HAS Column
                    edge = create_edge(
                        table_id, "table",
                        column_id, "column",
                        "TABLE_HAS_COLUMN",
                        f"{table_name} table has {column_name} column"
                    )
                    if edge:
                        edges.append(edge)
                    
                    # Column BELONGS TO Table
                    edge = create_edge(
                        column_id, "column",
                        table_id, "table",
                        "COLUMN_BELONGS_TO_TABLE",
                        f"{column_name} column belongs to {table_name} table"
                    )
                    if edge:
                        edges.append(edge)
                
                # 3. Table -> Feature relationships
                for feature in metadata.features:
                    feature_id = f"feature_{feature.feature_name.lower().replace(' ', '_')}"
                    
                    # Table HAS Feature
                    edge = create_edge(
                        table_id, "table",
                        feature_id, "feature",
                        "TABLE_HAS_FEATURE",
                        f"{table_name} table provides {feature.feature_name} feature"
                    )
                    if edge:
                        edges.append(edge)
                    
                    # Feature USES Table
                    edge = create_edge(
                        feature_id, "feature",
                        table_id, "table",
                        "FEATURE_USES_TABLE",
                        f"{feature.feature_name} feature is computed from {table_name} table"
                    )
                    if edge:
                        edges.append(edge)
                
                # 4. Table -> Metric relationships
                for metric in metadata.metrics:
                    metric_id = f"metric_{metric.metric_name.lower().replace(' ', '_')}"
                    
                    # Table HAS Metric
                    edge = create_edge(
                        table_id, "table",
                        metric_id, "metric",
                        "TABLE_HAS_METRIC",
                        f"{table_name} table provides {metric.metric_name} metric"
                    )
                    if edge:
                        edges.append(edge)
                    
                    # Metric USES Table
                    edge = create_edge(
                        metric_id, "metric",
                        table_id, "table",
                        "METRIC_USES_TABLE",
                        f"{metric.metric_name} metric is calculated from {table_name} table"
                    )
                    if edge:
                        edges.append(edge)
                
                # 5. Table -> Instruction relationships
                for instruction in metadata.instructions:
                    instruction_id = f"instruction_{table_name.lower()}_{uuid.uuid4().hex[:8]}"
                    
                    # Table FOLLOWS Instruction
                    edge = create_edge(
                        table_id, "table",
                        instruction_id, "instruction",
                        "TABLE_FOLLOWS_INSTRUCTION",
                        f"{table_name} table follows instruction: {instruction.content[:100]}"
                    )
                    if edge:
                        edges.append(edge)
                
                # 6. Example -> Table relationships
                for example in metadata.example_queries:
                    example_id = f"example_{table_name.lower()}_{uuid.uuid4().hex[:8]}"
                    
                    # Example USES Table
                    edge = create_edge(
                        example_id, "example",
                        table_id, "table",
                        "EXAMPLE_USES_TABLE",
                        f"Example query '{example.natural_question[:50]}...' uses {table_name} table"
                    )
                    if edge:
                        edges.append(edge)
                
                # 7. Table -> Table relationships (from MDL relationships)
                for relationship_desc in metadata.key_relationships:
                    # Parse relationship like "Vulnerability -> Project (MANY_TO_ONE)"
                    if " -> " in relationship_desc:
                        parts = relationship_desc.split(" -> ")
                        if len(parts) >= 2:
                            source_table = parts[0].strip()
                            target_parts = parts[1].split(" (")
                            target_table = target_parts[0].strip()
                            
                            source_table_id = f"table_{source_table.lower()}"
                            target_table_id = f"table_{target_table.lower()}"
                            
                            # Table RELATES TO Table
                            edge = create_edge(
                                source_table_id, "table",
                                target_table_id, "table",
                                "TABLE_RELATES_TO_TABLE",
                                f"{source_table} table relates to {target_table} table"
                            )
                            if edge:
                                edges.append(edge)
            
            # Convert edges to document format
            documents = []
            for idx, edge in enumerate(edges):
                edge_content = {
                    "edge_id": edge["edge_id"],
                    "source_entity_id": edge["source_entity_id"],
                    "source_entity_type": edge["source_entity_type"],
                    "target_entity_id": edge["target_entity_id"],
                    "target_entity_type": edge["target_entity_type"],
                    "edge_type": edge["edge_type"],
                    "document": edge["document"]
                }
                
                doc_metadata = {
                    "content_type": "contextual_edges",
                    "edge_id": edge["edge_id"],
                    "source_entity_id": edge["source_entity_id"],
                    "source_entity_type": edge["source_entity_type"],
                    "target_entity_id": edge["target_entity_id"],
                    "target_entity_type": edge["target_entity_type"],
                    "edge_type": edge["edge_type"],
                    "context_id": edge["context_id"],
                    "relevance_score": edge["relevance_score"],
                    "product_name": self.product_name,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source": "mdl_enriched_preview",
                    **self.organization_metadata
                }
                
                doc = {
                    "index": idx,
                    "page_content": json.dumps(edge_content, indent=2),
                    "metadata": doc_metadata,
                    "content_length": len(json.dumps(edge_content)),
                    "metadata_keys": list(doc_metadata.keys())
                }
                documents.append(doc)
            
            # Save preview file
            preview_path = self.preview_dir / "contextual_edges"
            preview_path.mkdir(parents=True, exist_ok=True)
            
            preview_file = preview_path / f"contextual_edges_{timestamp}_{self.product_name}.json"
            
            preview_data = {
                "metadata": {
                    "content_type": "contextual_edges",
                    "product_name": self.product_name,
                    "document_count": len(documents),
                    "timestamp": timestamp,
                    "indexed_at": datetime.utcnow().isoformat(),
                    "source_file": str(self.mdl_file_path),
                    "source": "mdl_enriched_preview",
                    "description": "Contextual edges representing relationships between MDL entities",
                    **self.organization_metadata
                },
                "documents": documents
            }
            
            with open(preview_file, "w", encoding="utf-8") as f:
                json.dump(preview_data, f, indent=2)
            
            # Save summary
            summary_file = preview_path / f"contextual_edges_summary_{timestamp}.txt"
            
            # Count edge types
            edge_type_counts = {}
            for edge in edges:
                edge_type = edge["edge_type"]
                edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
            
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"Contextual Edges Preview\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Product: {self.product_name}\n")
                f.write(f"Organization: {self.organization.organization_name}\n")
                f.write(f"Total Edges: {len(documents)}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"\nEdge Type Breakdown:\n")
                for edge_type, count in sorted(edge_type_counts.items()):
                    f.write(f"  - {edge_type}: {count}\n")
            
            logger.info(f"  ✓ Generated {len(documents)} contextual edges")
            logger.info(f"  ✓ Edge type breakdown:")
            for edge_type, count in sorted(edge_type_counts.items()):
                logger.info(f"    - {edge_type}: {count}")
            logger.info(f"  ✓ Saved to: {preview_file}")
            
            return {
                "success": True,
                "count": len(documents),
                "file": str(preview_file),
                "edge_type_counts": edge_type_counts
            }
        
        except Exception as e:
            logger.error(f"  ✗ Error generating contextual_edges: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Create MDL enriched preview files with organization support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--product-name",
        required=True,
        help="Product name (e.g., 'Snyk')"
    )
    
    parser.add_argument(
        "--project-id",
        help="Project ID (defaults to product_name)"
    )
    
    parser.add_argument(
        "--preview-dir",
        default="indexing_preview",
        help="Directory for preview files (defaults to 'indexing_preview')"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Batch size for parallel LLM extraction (default: all at once). Use smaller batches (e.g., 10-50) to avoid rate limits."
    )
    
    args = parser.parse_args()
    
    # Create generator
    generator = MDLEnrichedPreviewGenerator(
        mdl_file_path=args.mdl_file,
        product_name=args.product_name,
        preview_dir=args.preview_dir,
        project_id=args.project_id,
        batch_size=args.batch_size
    )
    
    # Generate all previews
    await generator.generate_all_previews()


if __name__ == "__main__":
    asyncio.run(main())
