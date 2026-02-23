"""
Ingest SAFE-MCP techniques and mitigations into LLM Safety collection.

This script indexes SAFE-MCP techniques and mitigations from markdown README files
into a Qdrant vector store for use by test generation and LLM agents.

Usage:
    python -m app.ingestion.ingest_llm_safety --safe-mcp-dir /path/to/safe-mcp
    python -m app.ingestion.ingest_llm_safety --safe-mcp-dir /path/to/safe-mcp --reinit-qdrant
"""

import argparse
import logging
import re
import sys
import uuid
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qdrant_client.http import models as qmodels

from app.ingestion.embedder import EmbeddingService
from app.storage.qdrant_framework_store import _get_underlying_qdrant_client, _vector_params
from app.storage.collections import LLMSafetyCollections

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _stable_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def extract_metadata_from_readme(content: str, file_path: Path) -> Dict[str, any]:
    """
    Extract metadata from README.md content.
    
    Returns:
        Dictionary with extracted metadata fields
    """
    metadata = {
        "title": "",
        "description": "",
        "keywords": [],
        "severity": None,
        "category": None,
        "tactic": None,
        "effectiveness": None,
        "implementation_complexity": None,
    }
    
    # Extract title (first line after #)
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()
    
    # Extract ID from title (e.g., "SAFE-T1001" or "SAFE-M-1")
    id_match = re.search(r'(SAFE-[TM]\d+[-\d]*)', metadata["title"])
    if id_match:
        metadata["id"] = id_match.group(1)
    else:
        # Fallback: extract from directory name
        metadata["id"] = file_path.parent.name
    
    # Extract description (first paragraph after "## Description" or "Description:")
    desc_patterns = [
        r'##\s+Description\s*\n\n(.+?)(?=\n##|\n###|\Z)',
        r'Description:\s*\n(.+?)(?=\n##|\n###|\Z)',
        r'##\s+Overview\s*\n(.+?)(?=\n##|\n###|\Z)',
    ]
    for pattern in desc_patterns:
        desc_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            desc = desc_match.group(1).strip()
            # Clean up markdown formatting
            desc = re.sub(r'\*\*([^*]+)\*\*', r'\1', desc)  # Remove bold
            desc = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', desc)  # Remove links
            metadata["description"] = desc[:500]  # Limit length
            break
    
    # Extract keywords from Overview section
    overview_match = re.search(r'##\s+Overview\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if overview_match:
        overview_text = overview_match.group(1)
        # Extract key-value pairs
        for line in overview_text.split('\n'):
            if '**' in line:
                # Extract field names and values
                field_match = re.search(r'\*\*([^:]+):\*\*\s*(.+)', line)
                if field_match:
                    field_name = field_match.group(1).strip().lower()
                    field_value = field_match.group(2).strip()
                    
                    if 'severity' in field_name:
                        metadata["severity"] = field_value
                    elif 'category' in field_name:
                        metadata["category"] = field_value
                    elif 'tactic' in field_name:
                        metadata["tactic"] = field_value
                    elif 'effectiveness' in field_name:
                        metadata["effectiveness"] = field_value
                    elif 'complexity' in field_name or 'implementation' in field_name:
                        metadata["implementation_complexity"] = field_value
    
    # Extract keywords from content (common security terms)
    keywords = set()
    keyword_patterns = [
        r'\b(prompt injection|tool poisoning|adversarial|attack|exploit|vulnerability|mitigation|defense|security|llm|mcp)\b',
        r'\b(SAFE-[TM]\d+[-\d]*)\b',  # Technique/mitigation IDs
        r'\b(ATK-TA\d+)\b',  # Tactic IDs
    ]
    for pattern in keyword_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        keywords.update([m.lower() if isinstance(m, str) else str(m).lower() for m in matches])
    
    # Add extracted metadata as keywords
    if metadata["category"]:
        keywords.add(metadata["category"].lower())
    if metadata["tactic"]:
        keywords.add(metadata["tactic"].lower())
    
    metadata["keywords"] = list(keywords)[:20]  # Limit to 20 keywords
    
    return metadata


def build_embedding_text(metadata: Dict, content: str) -> str:
    """
    Build text for embedding from metadata and content.
    
    This creates a searchable text representation that includes:
    - Title and ID
    - Description
    - Keywords
    - Key sections from content
    - Detection rule information (if available)
    """
    parts = []
    entity_type = metadata.get("entity_type", "")
    
    # Title and ID
    if metadata.get("title"):
        parts.append(metadata["title"])
    if metadata.get("id"):
        parts.append(f"ID: {metadata['id']}")
    
    # For detection rules, add technique context
    if entity_type == "detection_rule":
        if metadata.get("technique_id"):
            parts.append(f"Detection rule for technique: {metadata['technique_id']}")
        if metadata.get("technique_title"):
            parts.append(f"Technique: {metadata['technique_title']}")
    
    # Description
    if metadata.get("description"):
        parts.append(metadata["description"])
    
    # Keywords
    if metadata.get("keywords"):
        parts.append("Keywords: " + ", ".join(metadata["keywords"]))
    
    # For detection rules, include rule-specific information
    if entity_type == "detection_rule":
        if metadata.get("level"):
            parts.append(f"Detection Level: {metadata['level']}")
        if metadata.get("status"):
            parts.append(f"Status: {metadata['status']}")
        if metadata.get("tags"):
            parts.append("Tags: " + ", ".join(metadata["tags"]))
        if metadata.get("logsource"):
            logsource = metadata["logsource"]
            if isinstance(logsource, dict):
                logsource_str = ", ".join([f"{k}: {v}" for k, v in logsource.items()])
                parts.append(f"Log Source: {logsource_str}")
    
    # For techniques, include detection rule info if available
    if entity_type == "technique" and metadata.get("has_detection_rule"):
        detection_rule = metadata.get("detection_rule", {})
        if detection_rule:
            parts.append("\nDetection Rule Available:")
            if detection_rule.get("title"):
                parts.append(f"Rule Title: {detection_rule['title']}")
            if detection_rule.get("description"):
                parts.append(f"Rule Description: {detection_rule['description']}")
            if detection_rule.get("level"):
                parts.append(f"Detection Level: {detection_rule['level']}")
            # Include detection patterns for searchability
            detection = detection_rule.get("detection", {})
            # Handle case where detection might be a string (from partial extraction)
            if isinstance(detection, str):
                parts.append(f"Detection: {detection[:200]}")
            elif isinstance(detection, dict):
                selection = detection.get("selection", {})
                if selection:
                    parts.append("Detection Patterns: " + str(selection))
    
    # Extract key sections from content
    # Get first 2000 chars of content (excluding code blocks)
    content_clean = re.sub(r'```[\s\S]*?```', '', content)  # Remove code blocks
    content_clean = re.sub(r'`[^`]+`', '', content_clean)  # Remove inline code
    content_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content_clean)  # Remove links
    content_clean = re.sub(r'\n{3,}', '\n\n', content_clean)  # Normalize newlines
    
    # For detection rules, include the full YAML structure
    if entity_type == "detection_rule":
        # Include key parts of YAML for searchability
        parts.append("\nDetection Rule YAML:")
        parts.append(content[:1500])  # Include first 1500 chars of YAML
    else:
        # Get key sections for techniques/mitigations
        sections = []
        section_patterns = [
            r'##\s+(Attack Vectors|Technical Details|Mitigation|Detection|Examples?)(.*?)(?=\n##|\Z)',
            r'##\s+(Implementation|Benefits|Limitations)(.*?)(?=\n##|\Z)',
        ]
        for pattern in section_patterns:
            matches = re.findall(pattern, content_clean, re.DOTALL | re.IGNORECASE)
            for match in matches:
                section_text = match[1] if isinstance(match, tuple) else match
                section_text = section_text.strip()[:500]  # Limit section length
                if section_text:
                    sections.append(section_text)
        
        # Add first 1000 chars of main content if no sections found
        if not sections:
            main_content = content_clean.strip()[:1000]
            if main_content:
                sections.append(main_content)
        
        parts.extend(sections)
    
    return "\n\n".join(parts)


def load_detection_rule(rule_path: Path, technique_id: str) -> Optional[Dict]:
    """
    Load and parse detection-rule.yml file.
    
    Handles:
    - Multi-document YAML files (takes first document)
    - Malformed YAML (attempts to fix common issues)
    - Invalid characters (strips problematic content)
    
    Returns:
        Dictionary with detection rule data, or None if file doesn't exist or is invalid
    """
    if not rule_path.exists():
        return None
    
    try:
        # Read file content
        with open(rule_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to fix common YAML issues
        # Remove backticks that might be in comments or strings
        # (but preserve them if they're in quoted strings)
        lines = content.split('\n')
        cleaned_lines = []
        in_quoted_string = False
        quote_char = None
        
        for line in lines:
            # Simple heuristic: if line starts with backtick and isn't in a string, skip it
            stripped = line.lstrip()
            if stripped.startswith('`') and not in_quoted_string:
                # Skip lines that start with backticks (likely markdown code blocks)
                continue
            
            # Track quoted strings (simple heuristic)
            for char in line:
                if char in ('"', "'") and (not in_quoted_string or quote_char == char):
                    in_quoted_string = not in_quoted_string
                    quote_char = char if in_quoted_string else None
            
            cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Try to parse as single document first
        try:
            rule_data = yaml.safe_load(cleaned_content)
        except yaml.YAMLError:
            # If that fails, try multi-document YAML (take first document)
            try:
                documents = list(yaml.safe_load_all(cleaned_content))
                if documents and isinstance(documents[0], dict):
                    rule_data = documents[0]
                else:
                    logger.warning(f"Could not parse {rule_path}: no valid YAML document found")
                    return None
            except yaml.YAMLError as e:
                logger.warning(f"YAML parsing error in {rule_path}: {e}")
                # Try to extract at least some information from the file
                # Look for key fields even if YAML is malformed
                rule_data = {}
                in_multiline_value = False
                current_key = None
                current_value = []
                
                for line in cleaned_lines[:100]:  # Check first 100 lines
                    stripped = line.strip()
                    
                    # Skip comments and empty lines
                    if not stripped or stripped.startswith('#'):
                        continue
                    
                    # Check if this is a key-value pair
                    if ':' in line and not in_multiline_value:
                        try:
                            # Handle multiline values (lines starting with spaces after a key)
                            if line[0] in (' ', '\t'):
                                if current_key:
                                    current_value.append(stripped)
                                continue
                            
                            # Split key and value
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip().strip('"').strip("'")
                                value = parts[1].strip().strip('"').strip("'")
                                
                                # Save previous multiline value if any
                                if current_key and current_value:
                                    rule_data[current_key] = ' '.join(current_value)
                                    current_value = []
                                
                                # Check if value continues on next line (starts with | or >)
                                if value in ('|', '>', '|-', '>+'):
                                    in_multiline_value = True
                                    current_key = key
                                    current_value = []
                                elif value:
                                    rule_data[key] = value
                                    current_key = None
                                else:
                                    current_key = key
                                    current_value = []
                        except (ValueError, IndexError):
                            # If we're in a multiline value, continue collecting
                            if current_key:
                                current_value.append(stripped)
                            continue
                    elif in_multiline_value or current_key:
                        # Continue collecting multiline value
                        if current_key:
                            current_value.append(stripped)
                
                # Save final multiline value
                if current_key and current_value:
                    rule_data[current_key] = ' '.join(current_value)
                
                # If we extracted at least a title or id, use it
                if rule_data.get('title') or rule_data.get('id'):
                    logger.info(f"  Extracted partial data from {rule_path.name}: {list(rule_data.keys())}")
                elif not rule_data:
                    return None
        
        if not isinstance(rule_data, dict):
            return None
        
        # Extract key fields with defaults
        detection_rule = {
            "title": rule_data.get("title", ""),
            "rule_id": rule_data.get("id", ""),
            "status": rule_data.get("status", ""),
            "description": rule_data.get("description", ""),
            "author": rule_data.get("author", ""),
            "date": rule_data.get("date", ""),
            "level": rule_data.get("level", ""),
            "logsource": rule_data.get("logsource", {}),
            "detection": rule_data.get("detection", {}),
            "falsepositives": rule_data.get("falsepositives", []),
            "tags": rule_data.get("tags", []),
            "references": rule_data.get("references", []),
        }
        
        # Try to generate YAML dump, but fallback to original content if it fails
        try:
            detection_rule["raw_yaml"] = yaml.dump(rule_data, default_flow_style=False)
        except Exception:
            # If we can't dump, use cleaned content (truncated if too long)
            detection_rule["raw_yaml"] = cleaned_content[:5000]  # Limit to 5000 chars
        
        return detection_rule
        
    except Exception as e:
        logger.warning(f"Error loading detection rule {rule_path}: {e}")
        return None


def load_techniques_and_mitigations(safe_mcp_dir: Path) -> List[Tuple[Dict, str, str]]:
    """
    Load all techniques and mitigations from safe-mcp directory.
    Also loads detection-rule.yml files as separate documents.
    
    Returns:
        List of tuples: (metadata, content, entity_type)
    """
    results = []
    
    # Load techniques
    techniques_dir = safe_mcp_dir / "techniques"
    if techniques_dir.exists():
        for technique_dir in sorted(techniques_dir.iterdir()):
            if not technique_dir.is_dir() or technique_dir.name.startswith('.'):
                continue
            
            readme_path = technique_dir / "README.md"
            if not readme_path.exists():
                logger.warning(f"No README.md found in {technique_dir.name}")
                continue
            
            try:
                content = readme_path.read_text(encoding='utf-8')
                metadata = extract_metadata_from_readme(content, readme_path)
                technique_id = metadata.get("id", technique_dir.name)
                metadata["entity_type"] = "technique"
                metadata["source_path"] = str(readme_path.relative_to(safe_mcp_dir))
                
                # Load detection rule if it exists
                detection_rule_path = technique_dir / "detection-rule.yml"
                detection_rule = load_detection_rule(detection_rule_path, technique_id)
                if detection_rule:
                    metadata["has_detection_rule"] = True
                    metadata["detection_rule"] = detection_rule
                else:
                    metadata["has_detection_rule"] = False
                
                results.append((metadata, content, "technique"))
                logger.debug(f"Loaded technique: {technique_id}")
                
                # Also index detection rule as a separate document (template/example)
                if detection_rule:
                    rule_metadata = {
                        "id": f"{technique_id}-detection-rule",
                        "title": detection_rule.get("title", f"Detection Rule for {technique_id}"),
                        "description": detection_rule.get("description", ""),
                        "entity_type": "detection_rule",
                        "technique_id": technique_id,
                        "technique_title": metadata.get("title", ""),
                        "source_path": str(detection_rule_path.relative_to(safe_mcp_dir)),
                        "rule_id": detection_rule.get("rule_id", ""),
                        "status": detection_rule.get("status", ""),
                        "level": detection_rule.get("level", ""),
                        "tags": detection_rule.get("tags", []),
                        "logsource": detection_rule.get("logsource", {}),
                    }
                    # Use YAML content as the main content for detection rules
                    rule_content = detection_rule.get("raw_yaml", "")
                    results.append((rule_metadata, rule_content, "detection_rule"))
                    logger.debug(f"Loaded detection rule: {technique_id}-detection-rule")
                    
            except Exception as e:
                logger.error(f"Error loading {readme_path}: {e}")
                continue
    
    # Load mitigations
    mitigations_dir = safe_mcp_dir / "mitigations"
    if mitigations_dir.exists():
        for mitigation_dir in sorted(mitigations_dir.iterdir()):
            if not mitigation_dir.is_dir() or mitigation_dir.name.startswith('.'):
                continue
            
            readme_path = mitigation_dir / "README.md"
            if not readme_path.exists():
                logger.warning(f"No README.md found in {mitigation_dir.name}")
                continue
            
            try:
                content = readme_path.read_text(encoding='utf-8')
                metadata = extract_metadata_from_readme(content, readme_path)
                metadata["entity_type"] = "mitigation"
                metadata["source_path"] = str(readme_path.relative_to(safe_mcp_dir))
                results.append((metadata, content, "mitigation"))
                logger.debug(f"Loaded mitigation: {metadata.get('id', mitigation_dir.name)}")
            except Exception as e:
                logger.error(f"Error loading {readme_path}: {e}")
                continue
    
    return results


def ensure_collection(name: str, recreate: bool = False) -> None:
    """Create collection if it doesn't exist; optionally recreate."""
    client = _get_underlying_qdrant_client()
    exists = False
    try:
        client.get_collection(name)
        exists = True
    except Exception:
        exists = False

    if exists and recreate:
        client.delete_collection(name)
        exists = False
        logger.info(f"Collection '{name}' deleted for recreation.")

    if not exists:
        client.create_collection(
            collection_name=name,
            vectors_config=_vector_params(),
        )
        logger.info(f"Collection '{name}' created.")
    else:
        logger.debug(f"Collection '{name}' already exists, skipping.")


def ingest_llm_safety(
    safe_mcp_dir: Path,
    recreate_collection: bool = False,
) -> int:
    """
    Ingest SAFE-MCP techniques and mitigations into Qdrant.
    
    Args:
        safe_mcp_dir: Path to safe-mcp directory
        recreate_collection: If True, delete and recreate collection
        
    Returns:
        Number of documents indexed
    """
    safe_mcp_dir = Path(safe_mcp_dir)
    if not safe_mcp_dir.exists():
        raise FileNotFoundError(f"Safe-MCP directory not found: {safe_mcp_dir}")
    
    # Initialize collection
    collection_name = LLMSafetyCollections.SAFETY
    ensure_collection(collection_name, recreate=recreate_collection)
    
    # Load all techniques and mitigations
    logger.info("Loading techniques and mitigations...")
    items = load_techniques_and_mitigations(safe_mcp_dir)
    technique_count = sum(1 for _, _, et in items if et == 'technique')
    mitigation_count = sum(1 for _, _, et in items if et == 'mitigation')
    detection_rule_count = sum(1 for _, _, et in items if et == 'detection_rule')
    logger.info(
        f"Loaded {len(items)} items: "
        f"{technique_count} techniques, "
        f"{mitigation_count} mitigations, "
        f"{detection_rule_count} detection rules"
    )
    
    if not items:
        logger.warning("No techniques or mitigations found to index")
        return 0
    
    # Initialize embedder
    embedder = EmbeddingService()
    
    # Build embedding texts and metadata
    embedding_texts = []
    all_metadata = []
    for metadata, content, entity_type in items:
        embedding_text = build_embedding_text(metadata, content)
        embedding_texts.append(embedding_text)
        all_metadata.append((metadata, content, entity_type))
    
    # Generate embeddings
    logger.info("Generating embeddings...")
    vectors = embedder.embed(embedding_texts)
    logger.info(f"Generated {len(vectors)} embeddings")
    
    # Build Qdrant points
    client = _get_underlying_qdrant_client()
    points = []
    
    for i, ((metadata, content, entity_type), vector) in enumerate(zip(all_metadata, vectors)):
        artifact_id = metadata.get("id", f"unknown_{i}")
        qdrant_id = _stable_uuid(f"llm_safety_{artifact_id}")
        
        # Build payload
        payload = {
            "artifact_type": entity_type,
            "artifact_id": artifact_id,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "keywords": metadata.get("keywords", []),
            "source_path": metadata.get("source_path", ""),
        }
        
        # Add optional fields for techniques/mitigations
        if metadata.get("severity"):
            payload["severity"] = metadata["severity"]
        if metadata.get("category"):
            payload["category"] = metadata["category"]
        if metadata.get("tactic"):
            payload["tactic"] = metadata["tactic"]
        if metadata.get("effectiveness"):
            payload["effectiveness"] = metadata["effectiveness"]
        if metadata.get("implementation_complexity"):
            payload["implementation_complexity"] = metadata["implementation_complexity"]
        
        # Add detection rule fields
        if entity_type == "detection_rule":
            if metadata.get("technique_id"):
                payload["technique_id"] = metadata["technique_id"]
            if metadata.get("technique_title"):
                payload["technique_title"] = metadata["technique_title"]
            if metadata.get("rule_id"):
                payload["rule_id"] = metadata["rule_id"]
            if metadata.get("status"):
                payload["status"] = metadata["status"]
            if metadata.get("level"):
                payload["level"] = metadata["level"]
            if metadata.get("tags"):
                payload["tags"] = metadata["tags"]
            if metadata.get("logsource"):
                payload["logsource"] = metadata["logsource"]
        
        # For techniques, indicate if they have detection rules
        if entity_type == "technique" and metadata.get("has_detection_rule"):
            payload["has_detection_rule"] = True
            detection_rule = metadata.get("detection_rule", {})
            # Handle case where detection_rule might be a string (from partial extraction)
            if isinstance(detection_rule, dict):
                payload["detection_rule_title"] = detection_rule.get("title", "")
                payload["detection_rule_level"] = detection_rule.get("level", "")
            elif isinstance(detection_rule, str):
                # If it's a string, try to extract title from it
                payload["detection_rule_title"] = detection_rule[:100]  # Use first 100 chars
        
        points.append(qmodels.PointStruct(
            id=qdrant_id,
            vector=vector,
            payload=payload,
        ))
    
    # Upsert to Qdrant
    logger.info(f"Upserting {len(points)} points to '{collection_name}'...")
    client.upsert(
        collection_name=collection_name,
        points=points,
    )
    logger.info(f"✓ Successfully indexed {len(points)} documents to '{collection_name}'")
    
    return len(points)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest SAFE-MCP techniques and mitigations into LLM Safety collection"
    )
    parser.add_argument(
        "--safe-mcp-dir",
        type=str,
        required=True,
        help="Path to safe-mcp directory containing techniques/ and mitigations/ folders",
    )
    parser.add_argument(
        "--reinit-qdrant",
        action="store_true",
        help="Delete and recreate Qdrant collection (destructive)",
    )
    
    args = parser.parse_args()
    
    try:
        count = ingest_llm_safety(
            safe_mcp_dir=Path(args.safe_mcp_dir),
            recreate_collection=args.reinit_qdrant,
        )
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Ingestion complete: {count} documents indexed")
        logger.info(f"{'=' * 50}")
        return 0
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
