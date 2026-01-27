"""
Enhanced MDL Indexing Script with Consolidated LLM Extraction
===============================================================

This script indexes MDL files with enriched metadata extracted in ONE LLM call per table.
It extracts: category, business purpose, examples, features, metrics, instructions, and time concepts.

All extraction happens in a single pass to minimize LLM calls and cost.

Usage:
    python -m indexing_cli.index_mdl_enriched \
        --mdl-file path/to/mdl.json \
        --project-id "Snyk" \
        --product-name "Snyk" \
        --preview  # Optional: save preview files

Output Collections:
    - table_descriptions: Tables with category_name in metadata
    - column_metadata: Columns with time_dimension fields merged in
    - sql_pairs: Examples (natural question → SQL)
    - instructions: Product-specific instructions
    - entities: Products, categories, features, metrics (with mdl_entity_type discriminator)
    - contextual_edges: All relationships between entities
"""

import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.dependencies import (
    get_chromadb_client,
    get_embeddings_model,
    get_doc_store_provider,
    get_llm
)
from app.storage.documents import ChromaDBEmbeddingFunction, DocumentChromaStore
from app.services.contextual_graph_storage import ContextualEdge

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for LLM Output
# ============================================================================

class TimeConceptInfo(BaseModel):
    """Time dimension information for a column."""
    column_name: str
    is_time_dimension: bool = False
    time_granularity: Optional[str] = None  # "day", "hour", "month", etc.
    is_event_time: bool = False
    is_process_time: bool = False
    description: str = ""


class ExampleQuery(BaseModel):
    """Natural language query mapped to SQL."""
    natural_question: str
    sql_query: str
    complexity: str  # "simple", "moderate", "complex"
    description: str = ""


class Feature(BaseModel):
    """Business feature that can be computed from this table."""
    feature_name: str
    description: str
    calculation_logic: str
    use_cases: List[str] = []


class Metric(BaseModel):
    """Key metric or KPI related to this table."""
    metric_name: str
    description: str
    calculation: str
    category: str  # "performance", "security", "compliance", etc.


class Instruction(BaseModel):
    """Product-specific instruction or best practice."""
    instruction_type: str  # "query_pattern", "best_practice", "constraint", etc.
    content: str
    priority: str = "normal"  # "high", "normal", "low"


class EnrichedTableMetadata(BaseModel):
    """Complete metadata extracted for a table in ONE LLM call."""
    
    # Core identification
    table_name: str
    category: str  # Which of the 15 categories
    business_purpose: str  # Natural language description
    
    # Semantic enrichment
    key_insights: List[str] = Field(default_factory=list)
    common_use_cases: List[str] = Field(default_factory=list)
    
    # Time concepts (merged into column metadata)
    time_concepts: List[TimeConceptInfo] = Field(default_factory=list)
    
    # Examples
    example_queries: List[ExampleQuery] = Field(default_factory=list, max_length=3)
    
    # Features
    features: List[Feature] = Field(default_factory=list, max_length=5)
    
    # Metrics
    metrics: List[Metric] = Field(default_factory=list, max_length=5)
    
    # Instructions
    instructions: List[Instruction] = Field(default_factory=list, max_length=3)
    
    # Relationships context (extracted from MDL relationships)
    key_relationships: List[str] = Field(default_factory=list)


# ============================================================================
# Category Mapping (from index_mdl_contextual.py)
# ============================================================================

CATEGORY_MAPPING = {
    "AccessRequest": "access requests",
    "App": "application data",
    "Asset": "assets",
    "Project": "projects",
    "Risk": "risk management",
    "Integration": "integrations",
    "BrokerConnection": "integrations",
    "Vulnerability": "vulnerabilities",
    "Finding": "vulnerabilities",
    "Config": "configuration",
    "Settings": "configuration",
    "Audit": "audit logs",
    "Log": "audit logs",
    "Catalog": "audit logs",
    "Deploy": "deployment",
    "Group": "groups",
    "Org": "organizations",
    "Organization": "organizations",
    "Membership": "memberships and roles",
    "Role": "memberships and roles",
    "Member": "memberships and roles",
    "Issue": "issues",
    "Artifact": "artifacts",
}


def categorize_table(table_name: str) -> str:
    """Categorize a table based on its name pattern."""
    for prefix, category in CATEGORY_MAPPING.items():
        if table_name.startswith(prefix):
            return category
    return "other"  # fallback


# ============================================================================
# LLM Extraction Prompt
# ============================================================================

EXTRACTION_PROMPT_TEMPLATE = """You are a data expert analyzing a database table for {product_name}.

Extract comprehensive metadata for this table in ONE response. Focus on practical, actionable information.

**Table Information:**
- Name: {table_name}
- Description: {table_description}
- Columns: {columns_info}
- Relationships: {relationships_info}

**Categories** (choose ONE that best fits):
{categories_list}

**Extract the following:**

1. **Category**: Which category above best describes this table?

2. **Business Purpose**: In 1-2 sentences, what business problem does this table help solve?

3. **Key Insights**: 2-3 important things to know about this table

4. **Common Use Cases**: 2-3 common ways this table is used

5. **Time Concepts**: Identify any time-related columns:
   - Column name
   - Is it a time dimension? (yes/no)
   - Time granularity (day, hour, month, year, etc.)
   - Is it event time or process time?
   - Brief description

6. **Example Queries**: Generate 2-3 realistic SQL query examples:
   - Natural language question
   - Corresponding SQL query
   - Complexity (simple/moderate/complex)

7. **Features**: Identify 2-5 business features that can be computed:
   - Feature name
   - Description
   - How to calculate it
   - Use cases

8. **Metrics**: Identify 2-5 key metrics or KPIs:
   - Metric name
   - Description
   - How to calculate
   - Category (performance/security/compliance/operational)

9. **Instructions**: 1-3 important instructions or best practices:
   - Type (query_pattern/best_practice/constraint)
   - Content
   - Priority (high/normal/low)

10. **Key Relationships**: Summarize important relationships (already provided, just confirm relevance)

Be concise and practical. Focus on information that helps users query and understand this table.

{format_instructions}
"""

# ============================================================================
# Main Indexing Logic
# ============================================================================

async def extract_enriched_metadata(
    table_name: str,
    table_description: str,
    columns: List[Dict[str, Any]],
    relationships: List[str],
    product_name: str,
    llm: Any
) -> EnrichedTableMetadata:
    """
    Extract all metadata for a table in ONE LLM call.
    
    Args:
        table_name: Name of the table
        table_description: Table description from MDL
        columns: List of column dictionaries
        relationships: List of relationship descriptions
        product_name: Product name (e.g., "Snyk")
        llm: LLM instance
    
    Returns:
        EnrichedTableMetadata with all extracted information
    """
    # Format columns info
    columns_str = "\n".join([
        f"  - {col['name']} ({col.get('type', 'unknown')}): {col.get('description', 'No description')}"
        for col in columns[:20]  # Limit to first 20 columns to fit in context
    ])
    if len(columns) > 20:
        columns_str += f"\n  ... and {len(columns) - 20} more columns"
    
    # Format relationships
    relationships_str = "\n".join([f"  - {rel}" for rel in relationships]) if relationships else "  No explicit relationships defined"
    
    # Categories list
    categories_list = """
- access requests: User access and permission requests
- application data: Application configurations and metadata (exclude AppRisk)
- assets: Asset inventory and tracking
- projects: Project/repository information
- risk management: Risk assessment and management
- integrations: Third-party integrations and connectors
- vulnerabilities: Security vulnerabilities and findings
- configuration: System configuration and settings
- audit logs: Audit trails and logging
- deployment: Deployment and release information
- groups: User groups and teams
- organizations: Organization hierarchy
- memberships and roles: User memberships and role assignments
- issues: Issue tracking and management
- artifacts: Build artifacts and packages
- other: Anything else
"""
    
    # Create prompt
    parser = JsonOutputParser(pydantic_object=EnrichedTableMetadata)
    prompt = ChatPromptTemplate.from_template(EXTRACTION_PROMPT_TEMPLATE)
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "product_name": product_name,
            "table_name": table_name,
            "table_description": table_description or "No description provided",
            "columns_info": columns_str,
            "relationships_info": relationships_str,
            "categories_list": categories_list,
            "format_instructions": parser.get_format_instructions()
        })
        
        return EnrichedTableMetadata(**result)
    
    except Exception as e:
        logger.warning(f"LLM extraction failed for {table_name}: {e}. Using fallback.")
        # Fallback: basic metadata with rule-based category
        return EnrichedTableMetadata(
            table_name=table_name,
            category=categorize_table(table_name),
            business_purpose=table_description or f"Table for {table_name} data",
            key_insights=[],
            common_use_cases=[],
            time_concepts=[],
            example_queries=[],
            features=[],
            metrics=[],
            instructions=[],
            key_relationships=relationships
        )


async def index_mdl_enriched(
    mdl_file_path: str,
    project_id: str,
    product_name: Optional[str] = None,
    domain: Optional[str] = None,
    preview: bool = False,
    preview_dir: Optional[str] = None
):
    """
    Index MDL file with enriched metadata extracted via ONE LLM call per table.
    
    Args:
        mdl_file_path: Path to MDL JSON file
        project_id: Project ID
        product_name: Product name (defaults to project_id)
        domain: Domain filter (optional)
        preview: Whether to save preview files
        preview_dir: Directory for preview files (defaults to indexing_preview)
    """
    mdl_path = Path(mdl_file_path)
    if not mdl_path.exists():
        raise FileNotFoundError(f"MDL file not found: {mdl_file_path}")
    
    product_name = product_name or project_id
    
    logger.info("=" * 80)
    logger.info("MDL Enriched Indexing (Consolidated LLM Extraction)")
    logger.info("=" * 80)
    logger.info(f"MDL File: {mdl_file_path}")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Product Name: {product_name}")
    logger.info(f"Preview Mode: {preview}")
    logger.info("")
    
    # Load MDL
    logger.info(f"Loading MDL file: {mdl_path}")
    with open(mdl_path, "r", encoding="utf-8") as f:
        mdl_data = json.load(f)
    
    logger.info(f"Loaded MDL with {len(mdl_data.get('models', []))} models")
    logger.info("")
    
    # Initialize dependencies
    persistent_client = get_chromadb_client()
    embeddings = get_embeddings_model()
    doc_store_provider = get_doc_store_provider()
    llm = get_llm()
    
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
    
    # Prepare preview directory
    if preview:
        preview_path = Path(preview_dir or "indexing_preview") / "mdl_enriched"
        preview_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # ========================================================================
    # PHASE 1: Extract enriched metadata for each table (ONE LLM call per table)
    # ========================================================================
    logger.info("=" * 80)
    logger.info("PHASE 1: Extracting Enriched Metadata (ONE LLM call per table)")
    logger.info("=" * 80)
    
    enriched_tables = []
    models = mdl_data.get("models", [])
    
    for idx, model in enumerate(models, 1):
        table_name = model.get("name", "")
        if not table_name:
            continue
        
        logger.info(f"[{idx}/{len(models)}] Processing {table_name}...")
        
        # Extract metadata in ONE LLM call
        metadata = await extract_enriched_metadata(
            table_name=table_name,
            table_description=model.get("description", ""),
            columns=model.get("columns", []),
            relationships=relationships_map.get(table_name, []),
            product_name=product_name,
            llm=llm
        )
        
        enriched_tables.append({
            "model": model,
            "metadata": metadata
        })
        
        logger.info(f"  ✓ Category: {metadata.category}")
        logger.info(f"  ✓ Examples: {len(metadata.example_queries)}")
        logger.info(f"  ✓ Features: {len(metadata.features)}")
        logger.info(f"  ✓ Metrics: {len(metadata.metrics)}")
        logger.info(f"  ✓ Instructions: {len(metadata.instructions)}")
        logger.info(f"  ✓ Time Concepts: {len(metadata.time_concepts)}")
    
    logger.info("")
    logger.info(f"✓ Extracted metadata for {len(enriched_tables)} tables")
    logger.info("")
    
    # Save preview if requested
    if preview:
        preview_file = preview_path / f"enriched_metadata_{timestamp}_{product_name}.json"
        with open(preview_file, "w", encoding="utf-8") as f:
            json.dump(
                [{"table": e["model"]["name"], "metadata": e["metadata"].dict()} for e in enriched_tables],
                f,
                indent=2
            )
        logger.info(f"✓ Saved enriched metadata preview: {preview_file}")
        logger.info("")
    
    # ========================================================================
    # PHASE 2: Index to ChromaDB Collections
    # ========================================================================
    logger.info("=" * 80)
    logger.info("PHASE 2: Indexing to ChromaDB Collections")
    logger.info("=" * 80)
    
    results = {}
    
    # 2.1: Index table_descriptions with category_name
    logger.info("\n[1/6] Indexing table_descriptions with category_name...")
    try:
        table_store = doc_store_provider.get_store("table_descriptions")
        table_docs = []
        
        for item in enriched_tables:
            model = item["model"]
            metadata = item["metadata"]
            
            # Create document with category in metadata
            table_content = {
                "name": model["name"],
                "description": model.get("description", ""),
                "columns": [col["name"] for col in model.get("columns", [])],
                "category": metadata.category,
                "business_purpose": metadata.business_purpose,
                "key_insights": metadata.key_insights,
                "relationships": metadata.key_relationships
            }
            
            doc = Document(
                page_content=json.dumps(table_content, indent=2),
                metadata={
                    "type": "TABLE_DESCRIPTION",
                    "table_name": model["name"],
                    "project_id": project_id,
                    "product_name": product_name,
                    "category_name": metadata.category,  # ⭐ CATEGORY FOR FILTERING
                    "indexed_at": datetime.utcnow().isoformat()
                }
            )
            table_docs.append(doc)
        
        table_store.add_documents(table_docs)
        logger.info(f"  ✓ Indexed {len(table_docs)} tables with category metadata")
        results["table_descriptions"] = {"success": True, "count": len(table_docs)}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing table_descriptions: {e}")
        results["table_descriptions"] = {"success": False, "error": str(e)}
    
    # 2.2: Index column_metadata with time concepts merged in
    logger.info("\n[2/6] Indexing column_metadata with time concepts...")
    try:
        column_store = doc_store_provider.get_store("column_metadata")
        column_docs = []
        
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
                
                # Column content with time info merged in
                column_content = {
                    "column_name": column_name,
                    "table_name": table_name,
                    "type": column.get("type", ""),
                    "description": column.get("description", ""),
                    "is_calculated": column.get("isCalculated", False),
                    "is_primary_key": column_name == model.get("primaryKey", ""),
                    "is_foreign_key": bool(column.get("relationship")),
                    # ⭐ TIME CONCEPTS MERGED IN
                    "is_time_dimension": time_info.is_time_dimension if time_info else False,
                    "time_granularity": time_info.time_granularity if time_info else None,
                    "is_event_time": time_info.is_event_time if time_info else False,
                    "is_process_time": time_info.is_process_time if time_info else False,
                }
                
                doc = Document(
                    page_content=json.dumps(column_content, indent=2),
                    metadata={
                        "type": "COLUMN_METADATA",
                        "column_name": column_name,
                        "table_name": table_name,
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,  # Inherit category from table
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                column_docs.append(doc)
        
        column_store.add_documents(column_docs)
        logger.info(f"  ✓ Indexed {len(column_docs)} columns with time dimensions")
        results["column_metadata"] = {"success": True, "count": len(column_docs)}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing column_metadata: {e}")
        results["column_metadata"] = {"success": False, "error": str(e)}
    
    # 2.3: Index sql_pairs (examples)
    logger.info("\n[3/6] Indexing sql_pairs (examples)...")
    try:
        sql_pairs_store = doc_store_provider.get_store("sql_pairs")
        example_docs = []
        
        for item in enriched_tables:
            metadata = item["metadata"]
            table_name = item["model"]["name"]
            
            for example in metadata.example_queries:
                example_content = {
                    "question": example.natural_question,
                    "sql": example.sql_query,
                    "complexity": example.complexity,
                    "description": example.description,
                    "table_name": table_name
                }
                
                doc = Document(
                    page_content=json.dumps(example_content, indent=2),
                    metadata={
                        "type": "SQL_PAIR",
                        "table_name": table_name,
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,
                        "complexity": example.complexity,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                example_docs.append(doc)
        
        if example_docs:
            sql_pairs_store.add_documents(example_docs)
            logger.info(f"  ✓ Indexed {len(example_docs)} SQL examples")
            results["sql_pairs"] = {"success": True, "count": len(example_docs)}
        else:
            logger.info(f"  ⚠ No SQL examples to index")
            results["sql_pairs"] = {"success": True, "count": 0}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing sql_pairs: {e}")
        results["sql_pairs"] = {"success": False, "error": str(e)}
    
    # 2.4: Index instructions
    logger.info("\n[4/6] Indexing instructions...")
    try:
        instructions_store = doc_store_provider.get_store("instructions")
        instruction_docs = []
        
        for item in enriched_tables:
            metadata = item["metadata"]
            table_name = item["model"]["name"]
            
            for instruction in metadata.instructions:
                instruction_content = {
                    "instruction_type": instruction.instruction_type,
                    "content": instruction.content,
                    "priority": instruction.priority,
                    "table_name": table_name
                }
                
                doc = Document(
                    page_content=json.dumps(instruction_content, indent=2),
                    metadata={
                        "type": "INSTRUCTION",
                        "table_name": table_name,
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,
                        "instruction_type": instruction.instruction_type,
                        "priority": instruction.priority,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                instruction_docs.append(doc)
        
        if instruction_docs:
            instructions_store.add_documents(instruction_docs)
            logger.info(f"  ✓ Indexed {len(instruction_docs)} instructions")
            results["instructions"] = {"success": True, "count": len(instruction_docs)}
        else:
            logger.info(f"  ⚠ No instructions to index")
            results["instructions"] = {"success": True, "count": 0}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing instructions: {e}")
        results["instructions"] = {"success": False, "error": str(e)}
    
    # 2.5: Index entities (features, metrics) with type discriminator
    logger.info("\n[5/6] Indexing entities (features, metrics, categories)...")
    try:
        entities_store = doc_store_provider.get_store("entities")
        entity_docs = []
        
        # Index categories as entities
        categories_seen = set()
        for item in enriched_tables:
            metadata = item["metadata"]
            if metadata.category not in categories_seen:
                categories_seen.add(metadata.category)
                category_content = {
                    "entity_type": "category",
                    "name": metadata.category,
                    "product_name": product_name,
                    "tables": [e["model"]["name"] for e in enriched_tables if e["metadata"].category == metadata.category]
                }
                doc = Document(
                    page_content=json.dumps(category_content, indent=2),
                    metadata={
                        "type": "ENTITY",
                        "mdl_entity_type": "category",  # ⭐ DISCRIMINATOR
                        "entity_name": metadata.category,
                        "project_id": project_id,
                        "product_name": product_name,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                entity_docs.append(doc)
        
        # Index features
        for item in enriched_tables:
            metadata = item["metadata"]
            table_name = item["model"]["name"]
            
            for feature in metadata.features:
                feature_content = {
                    "entity_type": "feature",
                    "name": feature.feature_name,
                    "description": feature.description,
                    "calculation_logic": feature.calculation_logic,
                    "use_cases": feature.use_cases,
                    "table_name": table_name
                }
                doc = Document(
                    page_content=json.dumps(feature_content, indent=2),
                    metadata={
                        "type": "ENTITY",
                        "mdl_entity_type": "feature",  # ⭐ DISCRIMINATOR
                        "entity_name": feature.feature_name,
                        "table_name": table_name,
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                entity_docs.append(doc)
        
        # Index metrics
        for item in enriched_tables:
            metadata = item["metadata"]
            table_name = item["model"]["name"]
            
            for metric in metadata.metrics:
                metric_content = {
                    "entity_type": "metric",
                    "name": metric.metric_name,
                    "description": metric.description,
                    "calculation": metric.calculation,
                    "metric_category": metric.category,
                    "table_name": table_name
                }
                doc = Document(
                    page_content=json.dumps(metric_content, indent=2),
                    metadata={
                        "type": "ENTITY",
                        "mdl_entity_type": "metric",  # ⭐ DISCRIMINATOR
                        "entity_name": metric.metric_name,
                        "table_name": table_name,
                        "project_id": project_id,
                        "product_name": product_name,
                        "category_name": metadata.category,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                entity_docs.append(doc)
        
        if entity_docs:
            entities_store.add_documents(entity_docs)
            logger.info(f"  ✓ Indexed {len(entity_docs)} entities (categories, features, metrics)")
            results["entities"] = {"success": True, "count": len(entity_docs)}
        else:
            logger.info(f"  ⚠ No entities to index")
            results["entities"] = {"success": True, "count": 0}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing entities: {e}")
        results["entities"] = {"success": False, "error": str(e)}
    
    # 2.6: Index contextual_edges (relationships)
    logger.info("\n[6/6] Indexing contextual_edges (relationships)...")
    try:
        # Note: This would use ContextualGraphStorage, but for now just document the approach
        logger.info(f"  ⚠ Contextual edges indexing not yet implemented")
        logger.info(f"  → Use index_mdl_contextual.py for full contextual graph indexing")
        results["contextual_edges"] = {"success": True, "count": 0, "note": "Use index_mdl_contextual.py"}
    
    except Exception as e:
        logger.error(f"  ✗ Error indexing contextual_edges: {e}")
        results["contextual_edges"] = {"success": False, "error": str(e)}
    
    # ========================================================================
    # Summary
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("Indexing Summary")
    logger.info("=" * 80)
    for collection, result in results.items():
        if result.get("success"):
            logger.info(f"✓ {collection}: {result.get('count', 0)} documents indexed")
            if "note" in result:
                logger.info(f"  Note: {result['note']}")
        else:
            logger.error(f"✗ {collection}: Error - {result.get('error', 'Unknown error')}")
    logger.info("=" * 80)
    
    return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Index MDL files with enriched metadata (ONE LLM call per table)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--mdl-file",
        required=True,
        help="Path to MDL JSON file"
    )
    
    parser.add_argument(
        "--project-id",
        required=True,
        help="Project ID"
    )
    
    parser.add_argument(
        "--product-name",
        help="Product name (defaults to project_id)"
    )
    
    parser.add_argument(
        "--domain",
        help="Domain filter (optional)"
    )
    
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save preview files of extracted metadata"
    )
    
    parser.add_argument(
        "--preview-dir",
        help="Directory for preview files (defaults to indexing_preview)"
    )
    
    args = parser.parse_args()
    
    # Run async indexing
    asyncio.run(index_mdl_enriched(
        mdl_file_path=args.mdl_file,
        project_id=args.project_id,
        product_name=args.product_name,
        domain=args.domain,
        preview=args.preview,
        preview_dir=args.preview_dir
    ))


if __name__ == "__main__":
    main()
