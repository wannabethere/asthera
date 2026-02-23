"""
Comprehensive Collection Validation and Testing Script

This script validates and tests all collections and retrieval services:
- Framework Knowledge Base (controls, requirements, risks, test_cases, scenarios)
- MDL Collections (db_schema, table_description, project_meta, metrics_registry)
- XSOAR Enriched Collection
- LLM Safety Collection (techniques, mitigations, detection rules)

Usage:
    python -m app.retrieval.test_collections
    python -m app.retrieval.test_collections --collection llm_safety
    python -m app.retrieval.test_collections --collection xsoar_enriched --entity-type playbook
    python -m app.retrieval.test_collections --detailed --json
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Dict, List, Optional, Any

# Ensure .env is loaded by importing settings early
from app.core.settings import get_settings

# Import all retrieval services
from app.retrieval.service import RetrievalService
from app.retrieval.mdl_service import MDLRetrievalService
from app.retrieval.xsoar_service import XSOARRetrievalService
from app.retrieval.llm_safety_service import LLMSafetyRetrievalService
from app.storage.collections import (
    FrameworkCollections,
    MDLCollections,
    XSOARCollections,
    LLMSafetyCollections,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class CollectionValidator:
    """Validates and tests all collections."""
    
    def __init__(self):
        self.results = {
            "framework_kb": {},
            "mdl": {},
            "xsoar": {},
            "llm_safety": {},
        }
        self.errors = []
    
    async def test_framework_kb(self, detailed: bool = False) -> Dict[str, Any]:
        """Test Framework Knowledge Base collections."""
        logger.info("=" * 80)
        logger.info("Testing Framework Knowledge Base Collections")
        logger.info("=" * 80)
        
        service = RetrievalService()
        results = {
            "collections": [],
            "frameworks": [],
            "sample_queries": {},
        }
        
        # List all frameworks
        try:
            frameworks = service.list_frameworks()
            results["frameworks"] = [fw["id"] for fw in frameworks]
            logger.info(f"Found {len(frameworks)} frameworks: {', '.join(results['frameworks'])}")
            
            # Get stats for each framework
            for fw in frameworks:
                stats = service.get_framework_summary(fw["id"])
                if "error" not in stats:
                    logger.info(f"  {fw['id']}: {stats.get('counts', {})}")
        except Exception as e:
            logger.error(f"Error listing frameworks: {e}")
            self.errors.append(f"Framework listing: {e}")
        
        # Test each collection type
        test_queries = {
            "controls": "access control authentication",
            "requirements": "data encryption requirements",
            "risks": "data breach risk",
            "test_cases": "vulnerability scanning test",
            "scenarios": "attack scenario",
        }
        
        for collection_type, query in test_queries.items():
            try:
                logger.info(f"\nTesting {collection_type} collection...")
                
                if collection_type == "controls":
                    context = service.search_controls(query=query, limit=3)
                elif collection_type == "requirements":
                    context = service.search_requirements(query=query, limit=3)
                elif collection_type == "risks":
                    context = service.search_risks(query=query, limit=3)
                elif collection_type == "test_cases":
                    context = service.search_test_cases(query=query, limit=3)
                elif collection_type == "scenarios":
                    context = service.search_scenarios(query=query, limit=3)
                else:
                    continue
                
                results["sample_queries"][collection_type] = {
                    "query": query,
                    "total_hits": context.total_hits,
                    "results_count": len(getattr(context, collection_type, [])),
                    "sample_ids": [
                        getattr(item, "id", "")[:50] 
                        for item in getattr(context, collection_type, [])[:3]
                    ],
                }
                
                logger.info(f"  ✓ {collection_type}: {context.total_hits} total hits, {len(getattr(context, collection_type, []))} results")
                
                if detailed and getattr(context, collection_type, []):
                    sample = getattr(context, collection_type, [])[0]
                    logger.info(f"    Sample: {getattr(sample, 'name', getattr(sample, 'control_code', 'N/A'))}")
                    
            except Exception as e:
                logger.error(f"  ✗ {collection_type}: {e}")
                self.errors.append(f"{collection_type}: {e}")
                results["sample_queries"][collection_type] = {"error": str(e)}
        
        results["collections"] = FrameworkCollections.ALL
        self.results["framework_kb"] = results
        return results
    
    async def test_mdl(self, detailed: bool = False) -> Dict[str, Any]:
        """Test MDL collections."""
        logger.info("\n" + "=" * 80)
        logger.info("Testing MDL Collections")
        logger.info("=" * 80)
        
        try:
            # Use vector store client directly for more reliable testing
            from app.storage.vector_store import get_vector_store_client
            from app.core.settings import get_settings
            
            settings = get_settings()
            vector_store_config = settings.get_vector_store_config()
            vector_client = get_vector_store_client(config=vector_store_config)
            await vector_client.initialize()
            
            results = {
                "collections": MDLCollections.ALL,
                "sample_queries": {},
            }
            
            test_queries = {
                "db_schema": "database schema table structure",
                "table_description": "table description columns",
                "project_meta": "project metadata configuration",
                "metrics_registry": "metrics registry definitions",
            }
            
            collection_name_map = {
                "db_schema": MDLCollections.DB_SCHEMA,
                "table_description": MDLCollections.TABLE_DESCRIPTION,
                "project_meta": MDLCollections.PROJECT_META,
                "metrics_registry": MDLCollections.METRICS_REGISTRY,
            }
            
            for collection_key, query in test_queries.items():
                try:
                    logger.info(f"\nTesting {collection_key} collection...")
                    collection_name = collection_name_map[collection_key]
                    
                    # Use vector store client to query the collection directly
                    query_result = await vector_client.query(
                        collection_name=collection_name,
                        query_texts=[query],
                        n_results=3
                    )
                    
                    # Extract results (handle nested list format from ChromaDB/Qdrant)
                    documents = query_result.get("documents", [])
                    metadatas = query_result.get("metadatas", [])
                    ids = query_result.get("ids", [])
                    
                    # Flatten nested lists (ChromaDB/Qdrant returns lists of lists)
                    if documents and len(documents) > 0 and isinstance(documents[0], list):
                        documents = [doc[0] if doc and len(doc) > 0 else "" for doc in documents]
                    if metadatas and len(metadatas) > 0 and isinstance(metadatas[0], list):
                        metadatas = [meta[0] if meta and len(meta) > 0 else {} for meta in metadatas]
                    if ids and len(ids) > 0 and isinstance(ids[0], list):
                        ids = [id_list[0] if id_list and len(id_list) > 0 else "" for id_list in ids]
                    
                    count = len(documents)
                    
                    results["sample_queries"][collection_key] = {
                        "query": query,
                        "results_count": count,
                        "sample_ids": [id_val[:50] if id_val else "unknown" for id_val in ids[:3]],
                    }
                    
                    logger.info(f"  ✓ {collection_key}: {count} results")
                    
                    if detailed and metadatas:
                        # Try to extract a name from metadata
                        sample_meta = metadatas[0] if metadatas else {}
                        sample_name = (
                            sample_meta.get("name") or
                            sample_meta.get("table_name") or
                            sample_meta.get("schema_name") or
                            sample_meta.get("project_name") or
                            sample_meta.get("metric_name") or
                            "N/A"
                        )
                        logger.info(f"    Sample: {sample_name}")
                        
                except Exception as e:
                    logger.error(f"  ✗ {collection_key}: {e}", exc_info=True)
                    self.errors.append(f"MDL {collection_key}: {e}")
                    results["sample_queries"][collection_key] = {"error": str(e)}
            
            self.results["mdl"] = results
            return results
            
        except Exception as e:
            logger.error(f"MDL testing failed: {e}", exc_info=True)
            self.errors.append(f"MDL testing: {e}")
            return {"error": str(e)}
    
    async def test_xsoar(self, detailed: bool = False, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Test XSOAR enriched collection using vector store client."""
        logger.info("\n" + "=" * 80)
        logger.info("Testing XSOAR Enriched Collection")
        logger.info("=" * 80)
        
        try:
            from app.storage.vector_store import get_vector_store_client
            from app.core.settings import get_settings
            
            settings = get_settings()
            vector_store_config = settings.get_vector_store_config()
            vector_client = get_vector_store_client(config=vector_store_config)
            await vector_client.initialize()
            
            collection_name = XSOARCollections.ENRICHED
            
            results = {
                "collection": collection_name,
                "entity_types": {
                    "playbook": XSOARCollections.EntityType.PLAYBOOK,
                    "dashboard": XSOARCollections.EntityType.DASHBOARD,
                    "script": XSOARCollections.EntityType.SCRIPT,
                    "integration": XSOARCollections.EntityType.INTEGRATION,
                    "indicator": XSOARCollections.EntityType.INDICATOR,
                },
                "sample_queries": {},
            }
            
            # First, check if collection has any data at all (without filters)
            try:
                logger.info(f"\nChecking collection '{collection_name}' for any data...")
                test_query_result = await vector_client.query(
                    collection_name=collection_name,
                    query_texts=["test"],
                    n_results=10  # Get more samples to check entity types
                )
                total_docs = len(test_query_result.get("documents", []))
                if total_docs == 0:
                    logger.warning(f"  ⚠ Collection '{collection_name}' appears to be empty or query returned no results")
                else:
                    logger.info(f"  ✓ Collection '{collection_name}' has data (test query returned {total_docs} result)")
                    
                    # Check what entity_types actually exist in the collection
                    metadatas = test_query_result.get("metadatas", [])
                    if metadatas:
                        # Flatten nested lists
                        if metadatas and len(metadatas) > 0 and isinstance(metadatas[0], list):
                            metadatas = [meta[0] if meta and len(meta) > 0 else {} for meta in metadatas]
                        
                        entity_types_found = {}
                        for meta in metadatas:
                            if isinstance(meta, dict):
                                # Check both top-level and nested metadata
                                entity_type = meta.get("entity_type") or (meta.get("metadata", {}).get("entity_type") if isinstance(meta.get("metadata"), dict) else None)
                                if entity_type:
                                    entity_types_found[entity_type] = entity_types_found.get(entity_type, 0) + 1
                        
                        if entity_types_found:
                            logger.info(f"  Found entity types in sample: {dict(sorted(entity_types_found.items()))}")
                        else:
                            logger.warning(f"  ⚠ No 'entity_type' field found in sample metadata. Metadata keys: {[list(m.keys())[:5] if isinstance(m, dict) else 'not_dict' for m in metadatas[:3]]}")
            except Exception as e:
                logger.warning(f"  ⚠ Could not verify collection data: {e}")
            
            entity_types_to_test = [entity_type] if entity_type else [
                "playbook",
                "dashboard",
                "script",
                "integration",
                "indicator",
            ]
            
            test_queries = {
                "playbook": "automated response playbook",
                "dashboard": "security dashboard visualization",
                "script": "python automation script",
                "integration": "API integration connector",
                "indicator": "threat indicator IOC",
            }
            
            for et in entity_types_to_test:
                if et not in test_queries:
                    continue
                    
                try:
                    logger.info(f"\nTesting {et} entity type...")
                    query = test_queries[et]
                    
                    # Build where filter for entity_type
                    # Use direct format (vector store client will normalize based on backend)
                    # For ChromaDB: will be normalized to {"entity_type": {"$eq": et}}
                    # For Qdrant: will be used as {"entity_type": et}
                    where_filter = {"entity_type": et}
                    
                    # Use vector store client to query with entity_type filter
                    query_result = await vector_client.query(
                        collection_name=collection_name,
                        query_texts=[query],
                        n_results=3,
                        where=where_filter
                    )
                    
                    # Extract results (handle nested list format)
                    documents = query_result.get("documents", [])
                    metadatas = query_result.get("metadatas", [])
                    ids = query_result.get("ids", [])
                    
                    # Flatten nested lists
                    if documents and len(documents) > 0 and isinstance(documents[0], list):
                        documents = [doc[0] if doc and len(doc) > 0 else "" for doc in documents]
                    if metadatas and len(metadatas) > 0 and isinstance(metadatas[0], list):
                        metadatas = [meta[0] if meta and len(meta) > 0 else {} for meta in metadatas]
                    if ids and len(ids) > 0 and isinstance(ids[0], list):
                        ids = [id_list[0] if id_list and len(id_list) > 0 else "" for id_list in ids]
                    
                    count = len(documents)
                    
                    results["sample_queries"][et] = {
                        "query": query,
                        "results_count": count,
                        "sample_ids": [id_val[:50] if id_val else "unknown" for id_val in ids[:3]],
                    }
                    
                    logger.info(f"  ✓ {et}: {count} results")
                    
                    if detailed and metadatas:
                        # Try to extract a name from metadata
                        # Metadata might be nested or at top level depending on how it was stored
                        sample_meta = metadatas[0] if metadatas else {}
                        
                        # Check if metadata is nested (from DocumentQdrantStore format)
                        if isinstance(sample_meta, dict) and "metadata" in sample_meta:
                            actual_meta = sample_meta.get("metadata", {})
                        else:
                            actual_meta = sample_meta
                        
                        # Try multiple possible name fields
                        sample_name = (
                            actual_meta.get("name") or
                            actual_meta.get("playbook_name") or
                            actual_meta.get("dashboard_name") or
                            actual_meta.get("script_name") or
                            actual_meta.get("integration_name") or
                            actual_meta.get("indicator_name") or
                            # Fallback: try to extract from content if it's a dict
                            (documents[0] if documents and isinstance(documents[0], dict) and documents[0].get("name") else None) or
                            "N/A"
                        )
                        logger.info(f"    Sample: {sample_name}")
                        if detailed:
                            entity_type = actual_meta.get('entity_type') or sample_meta.get('entity_type', 'N/A')
                            logger.info(f"    Entity type in metadata: {entity_type}")
                            # Show a few metadata keys for debugging
                            if isinstance(actual_meta, dict) and len(actual_meta) > 0:
                                keys = list(actual_meta.keys())[:5]
                                logger.info(f"    Metadata keys: {', '.join(keys)}")
                        
                except Exception as e:
                    logger.error(f"  ✗ {et}: {e}", exc_info=True)
                    self.errors.append(f"XSOAR {et}: {e}")
                    results["sample_queries"][et] = {"error": str(e)}
            
            self.results["xsoar"] = results
            return results
            
        except Exception as e:
            logger.error(f"XSOAR testing failed: {e}", exc_info=True)
            self.errors.append(f"XSOAR testing: {e}")
            return {"error": str(e)}
    
    async def test_llm_safety(self, detailed: bool = False) -> Dict[str, Any]:
        """Test LLM Safety collection."""
        logger.info("\n" + "=" * 80)
        logger.info("Testing LLM Safety Collection")
        logger.info("=" * 80)
        
        try:
            service = LLMSafetyRetrievalService()
            results = {
                "collection": LLMSafetyCollections.SAFETY,
                "entity_types": {
                    "technique": LLMSafetyCollections.EntityType.TECHNIQUE,
                    "mitigation": LLMSafetyCollections.EntityType.MITIGATION,
                    "detection_rule": LLMSafetyCollections.EntityType.DETECTION_RULE,
                },
                "sample_queries": {},
            }
            
            test_queries = {
                "technique": "tool poisoning prompt injection",
                "mitigation": "defense architectural control",
                "detection_rule": "detection rule template YAML",
            }
            
            for entity_type, query in test_queries.items():
                try:
                    logger.info(f"\nTesting {entity_type} entity type...")
                    
                    if entity_type == "technique":
                        result = await service.search_techniques(query=query, limit=3)
                    elif entity_type == "mitigation":
                        result = await service.search_mitigations(query=query, limit=3)
                    elif entity_type == "detection_rule":
                        result = await service.search_detection_rules(query=query, limit=3)
                    else:
                        continue
                    
                    # Ensure result is a list (handle None case)
                    if result is None:
                        result = []
                    
                    results["sample_queries"][entity_type] = {
                        "query": query,
                        "results_count": len(result),
                        "sample_ids": [
                            getattr(item, "id", "")[:50] if getattr(item, "id", "") else "unknown"
                            for item in result[:3]
                        ],
                        "sample_titles": [
                            getattr(item, "title", "")[:50] if getattr(item, "title", "") else "N/A"
                            for item in result[:3]
                        ],
                    }
                    
                    logger.info(f"  ✓ {entity_type}: {len(result)} results")
                    
                    if detailed and result:
                        sample = result[0]
                        logger.info(f"    Sample: {getattr(sample, 'title', getattr(sample, 'technique_id', getattr(sample, 'mitigation_id', getattr(sample, 'rule_id', 'N/A'))))}")
                        
                        # For detection rules, show technique link
                        if entity_type == "detection_rule" and hasattr(sample, "technique_id"):
                            logger.info(f"    Linked to technique: {sample.technique_id}")
                            
                except Exception as e:
                    logger.error(f"  ✗ {entity_type}: {e}", exc_info=True)
                    self.errors.append(f"LLM Safety {entity_type}: {e}")
                    results["sample_queries"][entity_type] = {"error": str(e)}
            
            # Test detection rule lookup by technique
            try:
                logger.info("\nTesting detection rule lookup by technique...")
                techniques = await service.search_techniques(query="tool poisoning", limit=1)
                if techniques:
                    technique_id = techniques[0].technique_id
                    rules = await service.search_detection_rules_by_technique(
                        technique_id=technique_id,
                        limit=1
                    )
                    results["detection_rule_lookup"] = {
                        "technique_id": technique_id,
                        "rules_found": len(rules),
                    }
                    logger.info(f"  ✓ Found {len(rules)} detection rule(s) for {technique_id}")
            except Exception as e:
                logger.warning(f"  Detection rule lookup test failed: {e}")
            
            self.results["llm_safety"] = results
            return results
            
        except Exception as e:
            logger.error(f"LLM Safety service initialization failed: {e}")
            self.errors.append(f"LLM Safety service: {e}")
            return {"error": str(e)}
    
    async def test_all(self, detailed: bool = False, collection_filter: Optional[str] = None, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Test all collections."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE COLLECTION VALIDATION")
        logger.info("=" * 80)
        
        if collection_filter:
            logger.info(f"Filtering to: {collection_filter}")
        
        # Test Framework KB
        if not collection_filter or collection_filter == "framework_kb":
            await self.test_framework_kb(detailed=detailed)
        
        # Test MDL
        if not collection_filter or collection_filter == "mdl":
            await self.test_mdl(detailed=detailed)
        
        # Test XSOAR
        if not collection_filter or collection_filter == "xsoar":
            await self.test_xsoar(detailed=detailed, entity_type=entity_type)
        
        # Test LLM Safety
        if not collection_filter or collection_filter == "llm_safety":
            await self.test_llm_safety(detailed=detailed)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)
        
        total_collections = 0
        total_errors = len(self.errors)
        
        for category, results in self.results.items():
            if results and "error" not in results:
                collections = results.get("collections", [])
                if isinstance(collections, list):
                    total_collections += len(collections)
                elif isinstance(collections, str):
                    total_collections += 1
                logger.info(f"✓ {category}: {len(collections) if isinstance(collections, list) else 1} collection(s)")
            else:
                logger.warning(f"✗ {category}: Failed or not tested")
        
        logger.info(f"\nTotal collections tested: {total_collections}")
        logger.info(f"Total errors: {total_errors}")
        
        if self.errors:
            logger.warning("\nErrors encountered:")
            for error in self.errors:
                logger.warning(f"  - {error}")
        
        return {
            "results": self.results,
            "summary": {
                "total_collections": total_collections,
                "total_errors": total_errors,
                "errors": self.errors,
            },
        }


async def main_async(args):
    """Async main function."""
    validator = CollectionValidator()
    
    result = await validator.test_all(
        detailed=args.detailed,
        collection_filter=args.collection,
        entity_type=args.entity_type
    )
    
    if args.json:
        print("\n" + "=" * 80)
        print("JSON OUTPUT")
        print("=" * 80)
        print(json.dumps(result, indent=2, default=str))
    
    return 0 if result["summary"]["total_errors"] == 0 else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate and test all collections and retrieval services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all collections
  python -m app.retrieval.test_collections

  # Test specific collection category
  python -m app.retrieval.test_collections --collection llm_safety

  # Test XSOAR with specific entity type
  python -m app.retrieval.test_collections --collection xsoar --entity-type playbook

  # Detailed output with JSON
  python -m app.retrieval.test_collections --detailed --json
        """
    )
    
    parser.add_argument(
        "--collection",
        choices=["framework_kb", "mdl", "xsoar", "llm_safety"],
        help="Test specific collection category (default: all)",
    )
    parser.add_argument(
        "--entity-type",
        choices=["playbook", "dashboard", "script", "integration", "indicator"],
        help="For XSOAR: test specific entity type",
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
    
    args = parser.parse_args()
    
    # Load settings early to ensure .env is loaded
    settings = get_settings()
    logger.info("Environment configuration loaded from .env file")
    
    # Run async main
    try:
        exit_code = asyncio.run(main_async(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
