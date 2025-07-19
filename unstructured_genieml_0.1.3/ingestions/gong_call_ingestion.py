"""
Pipeline for ingesting Gong call documents that have been processed through Airbyte and stored in JSON format.
This pipeline handles the extraction, processing, and storage of Gong call transcripts and metadata.
"""
import json
import logging
import traceback
import argparse
import pprint
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import uuid
import asyncio
from collections import defaultdict
import re

from dagster import job, op, Array, Int
from tiktoken import encoding_for_model

from app.schemas.document_schemas import DocumentType
from app.config.settings import get_settings
from app.services.vectorstore.documentstore import DocumentChromaStore
from app.services.database.dbservice import DatabaseService

# Import extraction pipeline components
from ingestions.extraction_pipeline import DocumentExtractor, ExtractionResult, ChunkResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the path to the JSONL file for Gong call documents
current_dir = Path(__file__).parent
project_root = current_dir.parent
jsonl_path = project_root / "example_data" / "gong" / "2025_05_20_extensiveCalls.jsonl"

# Define the ChromaDB collection names
CHROMA_COLLECTION_NAME = "documents"
GONG_INSIGHTS_COLLECTION_NAME = "gong_insights"
GONG_CHUNKS_COLLECTION_NAME = "gong_chunks"

def get_nested_value(data, path):
    """Get a value from a nested dictionary using dot notation path."""
    parts = path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

def remove_nulls(obj: Any) -> Any:
    """Recursively remove null values from dictionaries and lists."""
    if isinstance(obj, dict):
        # Create a new dict with non-null values
        return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        # Create a new list with non-null values and process nested structures
        return [remove_nulls(item) for item in obj if item is not None]
    else:
        # Return the value as is if it's not a dict or list
        return obj

def extract_gong_fields(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract specific fields from a Gong call record using the new parsing methodology.
    
    Args:
        record: The record to extract fields from
        
    Returns:
        A tuple containing (extracted_fields_dict, full_data_dict)
    """
    # Get the _airbyte_data if present
    if "_airbyte_data" in record:
        data = record["_airbyte_data"]
    else:
        data = record  # Assume we already have the data
    
    # Ensure data is a dictionary
    if not isinstance(data, dict):
        data = {}
    
    # Extract the required fields
    result: Dict[str, Any] = {}
    
    # Get metadata and content
    metadata = data.get("metaData", {})
    content = data.get("content", {})
    
    # Process date from the started timestamp
    if 'started' in metadata:
        started_datetime = datetime.fromisoformat(metadata['started'])
        month = started_datetime.strftime('%B')  # Full month name
        day = str(started_datetime.day)
        year = str(started_datetime.year)
        result["date"] = f"{month} {day}, {year}"
        # Add timestamp for ChromaDB filtering
        result["date_timestamp"] = started_datetime.timestamp()
    
    # Extract basic metadata
    result["title"] = metadata.get("title")
    result["purpose"] = metadata.get("purpose")
    
    # Extract brief
    result["brief"] = content.get("brief")
    
    # Process outline
    outline = []
    if content.get("outline"):
        for section in content.get("outline", []):
            if isinstance(section, dict):
                section_text = section.get("section", "")
                items = section.get("items", [])
                item_texts = [item.get("text", "") for item in items]
                if section_text and item_texts:
                    outline.append({
                        "section": section_text,
                        "items": item_texts
                    })
    result["outline"] = outline
    
    # Process highlights
    highlights = []
    if content.get("highlights"):
        for highlight in content.get("highlights", []):
            if isinstance(highlight, dict):
                title = highlight.get("title", "")
                items = highlight.get("items", [])
                item_texts = [item.get("text", "") for item in items]
                if title and item_texts:
                    highlights.append({
                        "title": title,
                        "items": item_texts
                    })
    result["highlights"] = highlights
    
    # Process key points
    key_points = []
    if content.get("keyPoints"):
        for point in content.get("keyPoints", []):
            if isinstance(point, dict) and "text" in point:
                key_points.append(point.get("text"))
    result["keyPoints"] = key_points
    
    # Process topics
    topics = []
    if content.get("topics"):
        for topic in content.get("topics", []):
            if isinstance(topic, dict):
                # Extract both name and duration if available
                topic_data = {
                    "name": topic.get("name", ""),
                    "duration": topic.get("duration", "")
                }
                if topic_data["name"]:  # Only add if there's a name
                    topics.append(topic_data)
    result["topics"] = topics
    
    # Process questions
    questions = []
    if content.get("questions"):
        for question in content.get("questions", []):
            if isinstance(question, dict):
                question_data = {
                    "text": question.get("text", ""),
                    "speaker": question.get("speaker", ""),
                    "timestamp": question.get("timestamp", "")
                }
                if question_data["text"]:  # Only add if there's question text
                    questions.append(question_data)
    result["questions"] = questions
    
    # Process action items
    action_items = []
    points_of_interest = content.get("pointsOfInterest", {})
    if points_of_interest.get("actionItems"):
        for item in points_of_interest.get("actionItems", []):
            if isinstance(item, dict) and "text" in item:
                action_items.append(item.get("text"))
    result["actionItems"] = action_items
    
    # Process parties
    parties = []
    for party in data.get("parties", []):
        if party.get("name"):
            parties.append({
                "name": party.get("name"),
                "role": party.get("role")
            })
    result["parties"] = parties
    
    # Remove any null values from the result
    cleaned_result = remove_nulls(result)
    assert isinstance(cleaned_result, dict), "remove_nulls should return a dict when given a dict"
    
    return cleaned_result, data

@op(config_schema={"test_mode": bool, "test_line_indices": Array(Int)})
def load_gong_jsonl(context) -> List[Dict[str, Any]]:
    """Load Gong call documents from JSONL file."""
    test_mode = context.op_config["test_mode"]
    test_line_indices = context.op_config["test_line_indices"]
    
    records = []
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL file not found at {jsonl_path}")
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        if test_mode:
            # In test mode, read only the specified lines
            for i, line in enumerate(f):
                if i in test_line_indices and line.strip():
                    record = json.loads(line.strip())
                    records.append(record)
            logger.info(f"Loaded {len(records)} Gong call records (test mode, lines {test_line_indices})")
        else:
            # Normal mode - read all lines
            for line in f:
                if line.strip():
                    record = json.loads(line.strip())
                    records.append(record)
    
    if not test_mode:
        logger.info(f"Loaded {len(records)} Gong call records from JSONL file")
    
    return records

@op(config_schema={"test_mode": bool})
def prepare_gong_documents(context, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepare Gong call documents for processing."""
    test_mode = context.op_config["test_mode"]
    documents = []
    
    for record in records:
        try:
            # Extract fields and get the full data
            extracted_fields, full_data = extract_gong_fields(record)
            
            # Continue with existing logic but use extracted_fields data
            metadata = full_data.get("metaData", {})
            
            # Format the extracted fields as a structured content block
            formatted_content = []
            
            # Add title and high-level metadata first
            if extracted_fields.get("title"):
                formatted_content.append(f"Title: {extracted_fields['title']}")
            
            if extracted_fields.get("date"):
                formatted_content.append(f"Date: {extracted_fields['date']}")
            
            # Add brief summary if available
            if extracted_fields.get("brief"):
                formatted_content.append(f"Brief summary: {extracted_fields['brief']}")
            
            # Add key points in a more readable format
            if extracted_fields.get("keyPoints"):
                key_points_text = "Key points:\n"
                for i, point in enumerate(extracted_fields["keyPoints"], 1):
                    key_points_text += f"  {i}. {point}\n"
                formatted_content.append(key_points_text)
            
            # Add action items in a readable format
            if extracted_fields.get("actionItems"):
                action_items_text = "Action items:\n"
                for i, item in enumerate(extracted_fields["actionItems"], 1):
                    action_items_text += f"  {i}. {item}\n"
                formatted_content.append(action_items_text)
            
            # Add highlights in a cleaner format
            if extracted_fields.get("highlights"):
                for highlight in extracted_fields["highlights"]:
                    title = highlight.get("title", "Highlights")
                    items = highlight.get("items", [])
                    if items:
                        highlights_text = f"{title}:\n"
                        for i, item in enumerate(items, 1):
                            highlights_text += f"  {i}. {item}\n"
                        formatted_content.append(highlights_text)
            
            # Add topics if available
            if extracted_fields.get("topics"):
                topics_text = "Topics discussed: " + ", ".join(f"{topic['name']} ({topic['duration']})" for topic in extracted_fields["topics"])
                formatted_content.append(topics_text)
            
            # Add outline in a more readable format
            if extracted_fields.get("outline"):
                outline_text = "Call outline:\n"
                for section in extracted_fields["outline"]:
                    section_name = section.get("section", "")
                    items = section.get("items", [])
                    if section_name and items:
                        outline_text += f"  • {section_name}:\n"
                        for item in items:
                            outline_text += f"    - {item}\n"
                formatted_content.append(outline_text)
            
            # Format parties data specially
            if extracted_fields.get("parties"):
                parties_text = "Participants:\n"
                for party in extracted_fields.get("parties", []):
                    role_info = f" ({party.get('role')})" if party.get('role') else ""
                    parties_text += f"  - {party.get('name', 'Unknown')}{role_info}\n"
                formatted_content.append(parties_text)
            
            # Join everything into a content string
            content_text = "\n\n".join(formatted_content)
            
            if not content_text:
                logger.warning(f"Skipping Gong call {extracted_fields.get('title', 'Untitled')} - no content available")
                continue
            
            # Create document structure
            doc_id = metadata.get("id", str(uuid.uuid4()))
            doc = {
                "document": {
                    "content": content_text,
                    "metadata": {
                        "document_id": doc_id,
                        "document_type": DocumentType.GONG_TRANSCRIPT.value,
                        "title": extracted_fields.get("title", "Untitled Call"),
                        "date": extracted_fields.get("date", ""),
                        "date_timestamp": extracted_fields.get("date_timestamp", 0),  # Add timestamp for filtering
                        "source_type": "gong",
                        "event_type": "import"
                    }
                },
                "document_id": doc_id,
                "source_type": "gong",
                "document_type": DocumentType.GONG_TRANSCRIPT.value,
                "event_type": "import",
                "gong_data": {
                    "title": extracted_fields.get("title", ""),
                    "date": extracted_fields.get("date", ""),
                    "parties": extracted_fields.get("parties", []),
                    "topics": extracted_fields.get("topics", []),
                    "brief": extracted_fields.get("brief", ""),
                    "highlights": extracted_fields.get("highlights", []) if isinstance(extracted_fields.get("highlights"), list) else [],
                    "keyPoints": extracted_fields.get("keyPoints", []) if isinstance(extracted_fields.get("keyPoints"), list) else [],
                    "outline": extracted_fields.get("outline", []) if isinstance(extracted_fields.get("outline"), list) else [],
                    "actionItems": extracted_fields.get("actionItems", []) if isinstance(extracted_fields.get("actionItems"), list) else []
                }
            }
            
            # Ensure all null values are removed from metadata
            doc["document"]["metadata"] = remove_nulls(doc["document"]["metadata"])
            
            documents.append(doc)
                
        except Exception as e:
            logger.error(f"Error preparing Gong document: {e}")
            traceback.print_exc()
    
    if test_mode:
        logger.info(f"Prepared {len(documents)} Gong call document for testing")
    else:
        logger.info(f"Prepared {len(documents)} Gong call documents for processing")
    
    return documents

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a text string using the specified model's tokenizer."""
    try:
        enc = encoding_for_model(model)
        return len(enc.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens: {e}")
        return 0

@op(config_schema={"test_mode": bool, "use_postgres": bool, "extraction": bool})
async def process_gong_documents(context, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process Gong call documents and store in either ChromaDB or PostgreSQL based on configuration."""
    test_mode = context.op_config["test_mode"]
    use_postgres = context.op_config["use_postgres"]
    extraction_mode = context.op_config["extraction"]
    
    # Initialize storage services based on configuration
    if extraction_mode:
        # In extraction mode, initialize both chunks and insights stores + extractor
        settings = get_settings()
        chunks_store = DocumentChromaStore(collection_name=GONG_CHUNKS_COLLECTION_NAME)
        insights_store = DocumentChromaStore(collection_name=GONG_INSIGHTS_COLLECTION_NAME)
        
        # Initialize extractor with advanced NLP and custom settings
        doc_extractor = DocumentExtractor(
            use_advanced_nlp=True  # Enable advanced NLP features
        )
        
        logger.info(f"[EXTRACTION MODE] Initialized collections: {GONG_CHUNKS_COLLECTION_NAME} and {GONG_INSIGHTS_COLLECTION_NAME}")
        logger.info("[EXTRACTION MODE] Initialized document extractor with advanced NLP")
        
        # Allow extraction processing in test mode
        if test_mode:
            logger.info("[TEST MODE] Extraction processing enabled")
    elif use_postgres:
        db_service = DatabaseService()
        logger.info("Initialized PostgreSQL database service")
    else:
        settings = get_settings()
        chroma_store = DocumentChromaStore(collection_name=CHROMA_COLLECTION_NAME)
        logger.info(f"Initialized ChromaDB collection: {CHROMA_COLLECTION_NAME}")
    
    results = []
    
    if extraction_mode:
        # Prepare batch of documents for extraction
        extraction_batch = []
        for doc in documents:
            try:
                # Get the parsed Gong data
                gong_data = doc.get("gong_data", {})
                content_text = doc["document"]["content"]
                doc_id = doc["document"]["metadata"]["document_id"]
                metadata = doc["document"]["metadata"]
                
                # Create extraction metadata
                extraction_metadata = {
                    "gong_call_id": doc_id,
                    "gong_title": gong_data.get("title", ""),
                    "gong_date": gong_data.get("date", ""),
                    "source_type": "gong",
                    # Add Gong-specific metadata for better extraction
                    "call_type": gong_data.get("purpose", ""),
                    "participants": [p.get("name", "") for p in gong_data.get("parties", [])],
                    "topics_discussed": [topic["name"] for topic in gong_data.get("topics", []) if topic.get("name")],
                    "key_points": gong_data.get("keyPoints", []),
                    "action_items": gong_data.get("actionItems", []),
                    "highlights": [h.get("title", "") for h in gong_data.get("highlights", [])]
                }
                
                # Add any existing insights from Gong
                existing_insights = []
                if gong_data.get("keyPoints"):
                    existing_insights.extend([f"Key point: {kp}" for kp in gong_data["keyPoints"]])
                if gong_data.get("actionItems"):
                    existing_insights.extend([f"Action: {ai}" for ai in gong_data["actionItems"]])
                if gong_data.get("highlights"):
                    for highlight in gong_data["highlights"]:
                        if highlight.get("items"):
                            existing_insights.extend([f"Highlight: {item}" for item in highlight["items"]])
                
                extraction_batch.append({
                    "id": f"gong_{doc_id}",
                    "content": content_text,
                    "categories": [topic["name"] for topic in gong_data.get("topics", []) if topic.get("name")],
                    "metadata": extraction_metadata,
                    "existing_insights": existing_insights  # Pass existing insights to help with extraction
                })
                
                # Log document stats
                content_size = len(content_text.encode('utf-8'))
                metadata_size = len(json.dumps(metadata).encode('utf-8'))
                total_size = content_size + metadata_size
                content_tokens = count_tokens(content_text)
                metadata_tokens = count_tokens(json.dumps(metadata))
                total_tokens = content_tokens + metadata_tokens
                
                logger.info(f"Processing document {doc_id} for CHROMADB")
                logger.info(f"Document sizes - Content: {content_size/1024:.2f}KB, Metadata: {metadata_size/1024:.2f}KB, Total: {total_size/1024:.2f}KB")
                logger.info(f"Token counts - Content: {content_tokens}, Metadata: {metadata_tokens}, Total: {total_tokens}")
            except Exception as e:
                logger.error(f"Error preparing document for extraction: {e}\n{traceback.format_exc()}")
                continue
        
        try:
            # Process documents in parallel batches
            logger.info(f"[EXTRACTION MODE] Processing {len(extraction_batch)} documents through extraction pipeline with dynamic chunking")
            all_chunk_results = await doc_extractor.process_documents_batch(
                documents=extraction_batch,
                chunk_size=None,  # Use dynamic chunking
                overlap=None,     # Use dynamic overlap
                max_workers=4     # Adjust based on system capabilities
            )
            
            # Group chunks by parent document
            chunks_by_doc = defaultdict(list)
            for chunk in all_chunk_results:
                chunks_by_doc[chunk.parent_doc_id].append(chunk)
            
            # Store chunks and create results
            for doc in documents:
                try:
                    doc_id = doc["document"]["metadata"]["document_id"]
                    batch_doc_id = f"gong_{doc_id}"
                    doc_chunks = chunks_by_doc.get(batch_doc_id, [])
                    
                    if not test_mode:
                        # Store chunks in gong_chunks collection
                        for chunk in doc_chunks:
                            chunk_metadata = {
                                "chunk_id": chunk.chunk_id,
                                "parent_doc_id": chunk.parent_doc_id,
                                "chunk_index": chunk.chunk_index,
                                "start_position": chunk.start_position,
                                "end_position": chunk.end_position,
                                "document_type": "gong_chunk",
                                "source_type": "gong",
                                "event_type": "extraction",
                                "gong_title": doc["gong_data"].get("title", ""),
                                "gong_date": doc["gong_data"].get("date", ""),
                                "date_timestamp": doc["document"]["metadata"].get("date_timestamp"),
                                "overlap_info": chunk.overlap_info
                            }
                            
                            chunks_store.collection.add(
                                ids=[chunk.chunk_id],
                                documents=[chunk.text],
                                metadatas=[chunk_metadata]
                            )
                        
                        # Store single aggregated insights document per call
                        doc_id = doc["document"]["metadata"]["document_id"]
                        
                        # Extract and organize insights by type (using the same logic as the summary)
                        extracted_action_items = []
                        extracted_decisions = []
                        extracted_issues = []
                        extracted_key_points = []
                        extracted_pain_points = []
                        extracted_product_features = []
                        extracted_objections = []
                        extracted_competitors = []
                        extracted_decision_criteria = []
                        extracted_buyer_roles = []
                        extracted_deal_stages = []
                        extracted_use_cases = []
                        
                        all_entities = set()
                        all_keywords = set()
                        all_topics = set()
                        all_categories = set()
                        
                        for chunk in doc_chunks:
                            if chunk.extraction.summary:
                                # Split insights by | separator
                                insights = [insight.strip() for insight in chunk.extraction.summary.split('|')]
                                for insight in insights:
                                    if insight.startswith("Action:"):
                                        action_text = insight[7:].strip()  # Remove "Action:" prefix
                                        if action_text and len(action_text) > 10:
                                            extracted_action_items.append(action_text)
                                    elif insight.startswith("Decision:"):
                                        decision_text = insight[9:].strip()  # Remove "Decision:" prefix
                                        if decision_text and len(decision_text) > 10:
                                            extracted_decisions.append(decision_text)
                                    elif insight.startswith("Issue:"):
                                        issue_text = insight[6:].strip()  # Remove "Issue:" prefix
                                        if issue_text and len(issue_text) > 10:
                                            extracted_issues.append(issue_text)
                                    elif insight.startswith("Key point:"):
                                        key_point_text = insight[10:].strip()  # Remove "Key point:" prefix
                                        if key_point_text and len(key_point_text) > 10:
                                            extracted_key_points.append(key_point_text)
                                    elif insight.startswith("Pain Point:"):
                                        pain_text = insight[11:].strip()  # Remove "Pain Point:" prefix
                                        if pain_text and len(pain_text) > 10:
                                            extracted_pain_points.append(pain_text)
                                    elif insight.startswith("Product Feature:"):
                                        feature_text = insight[16:].strip()  # Remove "Product Feature:" prefix
                                        if feature_text and len(feature_text) > 10:
                                            extracted_product_features.append(feature_text)
                                    elif insight.startswith("Objection:"):
                                        objection_text = insight[10:].strip()  # Remove "Objection:" prefix
                                        if objection_text and len(objection_text) > 10:
                                            extracted_objections.append(objection_text)
                                    elif insight.startswith("Competitor:"):
                                        competitor_text = insight[11:].strip()  # Remove "Competitor:" prefix
                                        if competitor_text and len(competitor_text) > 10:
                                            extracted_competitors.append(competitor_text)
                                    elif insight.startswith("Decision Criteria:"):
                                        criteria_text = insight[18:].strip()  # Remove "Decision Criteria:" prefix
                                        if criteria_text and len(criteria_text) > 10:
                                            extracted_decision_criteria.append(criteria_text)
                                    elif insight.startswith("Buyer Role:"):
                                        role_text = insight[11:].strip()  # Remove "Buyer Role:" prefix
                                        if role_text and len(role_text) > 10:
                                            extracted_buyer_roles.append(role_text)
                                    elif insight.startswith("Deal Stage:"):
                                        stage_text = insight[11:].strip()  # Remove "Deal Stage:" prefix
                                        if stage_text and len(stage_text) > 10:
                                            extracted_deal_stages.append(stage_text)
                                    elif insight.startswith("Use Case:"):
                                        usecase_text = insight[9:].strip()  # Remove "Use Case:" prefix
                                        if usecase_text and len(usecase_text) > 10:
                                            extracted_use_cases.append(usecase_text)
                            
                            # Aggregate other extraction data
                            all_entities.update(chunk.extraction.entities)
                            all_keywords.update(chunk.extraction.keywords)
                            all_topics.update(chunk.extraction.topics)
                            all_categories.update(chunk.extraction.categories)
                        
                        # Remove duplicates while preserving order
                        extracted_action_items = list(dict.fromkeys(extracted_action_items))
                        extracted_decisions = list(dict.fromkeys(extracted_decisions))
                        extracted_issues = list(dict.fromkeys(extracted_issues))
                        extracted_key_points = list(dict.fromkeys(extracted_key_points))
                        extracted_pain_points = list(dict.fromkeys(extracted_pain_points))
                        extracted_product_features = list(dict.fromkeys(extracted_product_features))
                        extracted_objections = list(dict.fromkeys(extracted_objections))
                        extracted_competitors = list(dict.fromkeys(extracted_competitors))
                        extracted_decision_criteria = list(dict.fromkeys(extracted_decision_criteria))
                        extracted_buyer_roles = list(dict.fromkeys(extracted_buyer_roles))
                        extracted_deal_stages = list(dict.fromkeys(extracted_deal_stages))
                        extracted_use_cases = list(dict.fromkeys(extracted_use_cases))
                        
                        # Create organized content format (like the log output)
                        content_sections = []
                        
                        if extracted_pain_points:
                            pain_section = f"Customer Pain Points ({len(extracted_pain_points)}):\n"
                            for i, item in enumerate(extracted_pain_points, 1):
                                pain_section += f"{i}. {item}\n"
                            content_sections.append(pain_section.strip())
                        
                        if extracted_product_features:
                            feature_section = f"Product Features Discussed ({len(extracted_product_features)}):\n"
                            for i, item in enumerate(extracted_product_features, 1):
                                feature_section += f"{i}. {item}\n"
                            content_sections.append(feature_section.strip())
                        
                        if extracted_objections:
                            objection_section = f"Objections Raised ({len(extracted_objections)}):\n"
                            for i, item in enumerate(extracted_objections, 1):
                                objection_section += f"{i}. {item}\n"
                            content_sections.append(objection_section.strip())
                        
                        if extracted_action_items:
                            action_section = f"Next Steps / Action Items ({len(extracted_action_items)}):\n"
                            for i, item in enumerate(extracted_action_items, 1):
                                action_section += f"{i}. {item}\n"
                            content_sections.append(action_section.strip())
                        
                        if extracted_competitors:
                            competitor_section = f"Competitors Mentioned ({len(extracted_competitors)}):\n"
                            for i, item in enumerate(extracted_competitors, 1):
                                competitor_section += f"{i}. {item}\n"
                            content_sections.append(competitor_section.strip())
                        
                        if extracted_decision_criteria:
                            criteria_section = f"Decision Criteria ({len(extracted_decision_criteria)}):\n"
                            for i, item in enumerate(extracted_decision_criteria, 1):
                                criteria_section += f"{i}. {item}\n"
                            content_sections.append(criteria_section.strip())
                        
                        if extracted_buyer_roles:
                            role_section = f"Buyer Roles / Personas ({len(extracted_buyer_roles)}):\n"
                            for i, item in enumerate(extracted_buyer_roles, 1):
                                role_section += f"{i}. {item}\n"
                            content_sections.append(role_section.strip())
                        
                        if extracted_deal_stages:
                            stage_section = f"Deal Stage / Intent ({len(extracted_deal_stages)}):\n"
                            for i, item in enumerate(extracted_deal_stages, 1):
                                stage_section += f"{i}. {item}\n"
                            content_sections.append(stage_section.strip())
                        
                        if extracted_use_cases:
                            usecase_section = f"Use Cases Mentioned ({len(extracted_use_cases)}):\n"
                            for i, item in enumerate(extracted_use_cases, 1):
                                usecase_section += f"{i}. {item}\n"
                            content_sections.append(usecase_section.strip())
                        
                        if extracted_decisions:
                            decision_section = f"Decisions ({len(extracted_decisions)}):\n"
                            for i, item in enumerate(extracted_decisions, 1):
                                decision_section += f"{i}. {item}\n"
                            content_sections.append(decision_section.strip())
                        
                        if extracted_issues:
                            issue_section = f"Issues ({len(extracted_issues)}):\n"
                            for i, item in enumerate(extracted_issues, 1):
                                issue_section += f"{i}. {item}\n"
                            content_sections.append(issue_section.strip())
                        
                        if extracted_key_points:
                            key_points_section = f"Key Points ({len(extracted_key_points)}):\n"
                            for i, item in enumerate(extracted_key_points, 1):
                                key_points_section += f"{i}. {item}\n"
                            content_sections.append(key_points_section.strip())
                        
                        # Join all sections with double newlines
                        organized_content = "\n\n".join(content_sections) if content_sections else ""
                        
                        insights_metadata = {
                            "document_id": doc_id,
                            "document_type": "gong_call_insights", 
                            "source_type": "gong",
                            "event_type": "extraction",
                            "gong_title": doc["gong_data"].get("title", ""),
                            "gong_date": doc["gong_data"].get("date", ""),
                            "date_timestamp": doc["document"]["metadata"].get("date_timestamp"),
                            "total_chunks": len(doc_chunks),
                            "entities": list(all_entities)[:50],  # Limit for storage
                            "keywords": list(all_keywords)[:30],  # Limit for storage  
                            "topics": list(all_topics),
                            "categories": list(all_categories),
                            "chunk_collection": GONG_CHUNKS_COLLECTION_NAME
                        }
                        
                        insights_store.collection.add(
                            ids=[doc_id],  # Use document ID, not chunk ID
                            documents=[organized_content],
                            metadatas=[insights_metadata]
                        )
                        
                        logger.info(f"Stored {len(doc_chunks)} chunks in {GONG_CHUNKS_COLLECTION_NAME} collection")
                        logger.info(f"Stored 1 aggregated insights document in {GONG_INSIGHTS_COLLECTION_NAME} collection")
                    else:
                        logger.info(f"[TEST MODE] Skipping storage of {len(doc_chunks)} chunks and insights")
                    
                    # Add to results
                    # Extract action items from all chunks for aggregation
                    extracted_action_items = []
                    extracted_decisions = []
                    extracted_issues = []
                    extracted_key_points = []
                    extracted_pain_points = []
                    extracted_product_features = []
                    extracted_objections = []
                    extracted_competitors = []
                    extracted_decision_criteria = []
                    extracted_buyer_roles = []
                    extracted_deal_stages = []
                    extracted_use_cases = []
                    
                    for chunk in doc_chunks:
                        summary = chunk.extraction.summary
                        if summary:
                            # Split insights by | separator
                            insights = [insight.strip() for insight in summary.split('|')]
                            for insight in insights:
                                if insight.startswith("Action:"):
                                    action_text = insight[7:].strip()  # Remove "Action:" prefix
                                    if action_text and len(action_text) > 10:
                                        extracted_action_items.append(action_text)
                                elif insight.startswith("Decision:"):
                                    decision_text = insight[9:].strip()  # Remove "Decision:" prefix
                                    if decision_text and len(decision_text) > 10:
                                        extracted_decisions.append(decision_text)
                                elif insight.startswith("Issue:"):
                                    issue_text = insight[6:].strip()  # Remove "Issue:" prefix
                                    if issue_text and len(issue_text) > 10:
                                        extracted_issues.append(issue_text)
                                elif insight.startswith("Key point:"):
                                    key_point_text = insight[10:].strip()  # Remove "Key point:" prefix
                                    if key_point_text and len(key_point_text) > 10:
                                        extracted_key_points.append(key_point_text)
                                elif insight.startswith("Pain Point:"):
                                    pain_text = insight[11:].strip()  # Remove "Pain Point:" prefix
                                    if pain_text and len(pain_text) > 10:
                                        extracted_pain_points.append(pain_text)
                                elif insight.startswith("Product Feature:"):
                                    feature_text = insight[16:].strip()  # Remove "Product Feature:" prefix
                                    if feature_text and len(feature_text) > 10:
                                        extracted_product_features.append(feature_text)
                                elif insight.startswith("Objection:"):
                                    objection_text = insight[10:].strip()  # Remove "Objection:" prefix
                                    if objection_text and len(objection_text) > 10:
                                        extracted_objections.append(objection_text)
                                elif insight.startswith("Competitor:"):
                                    competitor_text = insight[11:].strip()  # Remove "Competitor:" prefix
                                    if competitor_text and len(competitor_text) > 10:
                                        extracted_competitors.append(competitor_text)
                                elif insight.startswith("Decision Criteria:"):
                                    criteria_text = insight[18:].strip()  # Remove "Decision Criteria:" prefix
                                    if criteria_text and len(criteria_text) > 10:
                                        extracted_decision_criteria.append(criteria_text)
                                elif insight.startswith("Buyer Role:"):
                                    role_text = insight[11:].strip()  # Remove "Buyer Role:" prefix
                                    if role_text and len(role_text) > 10:
                                        extracted_buyer_roles.append(role_text)
                                elif insight.startswith("Deal Stage:"):
                                    stage_text = insight[11:].strip()  # Remove "Deal Stage:" prefix
                                    if stage_text and len(stage_text) > 10:
                                        extracted_deal_stages.append(stage_text)
                                elif insight.startswith("Use Case:"):
                                    usecase_text = insight[9:].strip()  # Remove "Use Case:" prefix
                                    if usecase_text and len(usecase_text) > 10:
                                        extracted_use_cases.append(usecase_text)
                    
                    # Remove duplicates while preserving order
                    extracted_action_items = list(dict.fromkeys(extracted_action_items))
                    extracted_decisions = list(dict.fromkeys(extracted_decisions))
                    extracted_issues = list(dict.fromkeys(extracted_issues))
                    extracted_key_points = list(dict.fromkeys(extracted_key_points))
                    extracted_pain_points = list(dict.fromkeys(extracted_pain_points))
                    extracted_product_features = list(dict.fromkeys(extracted_product_features))
                    extracted_objections = list(dict.fromkeys(extracted_objections))
                    extracted_competitors = list(dict.fromkeys(extracted_competitors))
                    extracted_decision_criteria = list(dict.fromkeys(extracted_decision_criteria))
                    extracted_buyer_roles = list(dict.fromkeys(extracted_buyer_roles))
                    extracted_deal_stages = list(dict.fromkeys(extracted_deal_stages))
                    extracted_use_cases = list(dict.fromkeys(extracted_use_cases))
                    
                    result = {
                        "success": True,
                        "document_id": doc_id,
                        "content": doc["document"]["content"],
                        "metadata": doc["document"]["metadata"],
                        "extraction_processed": True,
                        "regular_storage_skipped": True,
                        "chunks_created": len(doc_chunks),
                        # Enhanced extraction summary with sales-focused insights
                        "extracted_insights": {
                            "pain_points": extracted_pain_points,
                            "product_features": extracted_product_features,
                            "objections": extracted_objections,
                            "action_items": extracted_action_items,
                            "competitors": extracted_competitors,
                            "decision_criteria": extracted_decision_criteria,
                            "buyer_roles": extracted_buyer_roles,
                            "deal_stages": extracted_deal_stages,
                            "use_cases": extracted_use_cases,
                            "decisions": extracted_decisions,
                            "issues": extracted_issues,
                            "key_points": extracted_key_points,
                            "original_gong_action_items": doc["gong_data"].get("actionItems", []),
                            "original_gong_key_points": doc["gong_data"].get("keyPoints", [])
                        },
                        "extraction_results": [
                            {
                                "chunk_id": chunk.chunk_id,
                                "chunk_text": chunk.text,
                                "chunk_index": chunk.chunk_index,
                                "start_position": chunk.start_position,
                                "end_position": chunk.end_position,
                                "extraction": {
                                    "entities": chunk.extraction.entities,
                                    "keywords": chunk.extraction.keywords,
                                    "topics": chunk.extraction.topics,
                                    "categories": chunk.extraction.categories,
                                    "summary": chunk.extraction.summary,
                                    "metadata": chunk.extraction.metadata
                                }
                            }
                            for chunk in doc_chunks
                        ]
                    }
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing chunks for document: {e}\n{traceback.format_exc()}")
                    results.append({
                        "success": False,
                        "document_id": doc["document"]["metadata"].get("document_id", "unknown"),
                        "error": str(e),
                        "extraction_processed": False,
                        "regular_storage_skipped": True
                    })
        except Exception as e:
            logger.error(f"Error in batch processing: {e}\n{traceback.format_exc()}")
            # Add error results for all documents
            for doc in documents:
                results.append({
                    "success": False,
                    "document_id": doc["document"]["metadata"].get("document_id", "unknown"),
                    "error": str(e),
                    "extraction_processed": False,
                    "regular_storage_skipped": True
                })
    else:
        # Store documents based on configuration (original logic) - ONLY if NOT in extraction mode
        for doc in documents:
            doc_id = doc["document"]["metadata"]["document_id"]
            content_text = doc["document"]["content"]
            metadata = doc["document"]["metadata"]
            
            if not test_mode:
                if use_postgres:
                    logger.info(f"Storing document {doc_id} in PostgreSQL")
                    db_service.store_document(
                        content=content_text,
                        metadata=metadata,
                        source_type="gong",
                        document_type=DocumentType.GONG_TRANSCRIPT.value
                    )
                    logger.info(f"Successfully stored document {doc_id} in PostgreSQL")
                else:
                    logger.info(f"Storing document {doc_id} in ChromaDB collection '{CHROMA_COLLECTION_NAME}'")
                    chroma_store.collection.add(
                        ids=[doc_id],
                        documents=[content_text],
                        metadatas=[metadata]
                    )
                    logger.info(f"Successfully stored document {doc_id} in ChromaDB")
            else:
                logger.info(f"[TEST MODE] Skipping storage for document {doc_id}")
                # Only create regular document structure if not in extraction mode
                if not extraction_mode:
                    result = {
                        "success": True,
                        "document_id": doc_id,
                        "content": content_text,
                        "metadata": metadata,
                        "extraction_processed": False,
                        "regular_storage_skipped": False
                    }
    
    return results

@op(config_schema={"test_mode": bool})
def summarize_gong_results(context, results: List[Dict[str, Any]]) -> None:
    """Summarize the results of Gong call document processing."""
    test_mode = context.op_config["test_mode"]
    
    success_count = sum(1 for r in results if r.get("success", False))
    failure_count = len(results) - success_count
    extraction_processed_count = sum(1 for r in results if r.get("extraction_processed", False))
    regular_storage_skipped_count = sum(1 for r in results if r.get("regular_storage_skipped", False))
    
    logger.info("\nGong Call Processing Summary:")
    logger.info(f"Total calls processed: {len(results)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failure_count}")
    
    if extraction_processed_count > 0:
        logger.info(f"Processed through extraction pipeline: {extraction_processed_count}")
        logger.info(f"Regular document storage skipped: {regular_storage_skipped_count}")
        
        # Calculate extraction statistics
        total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("extraction_processed", False))
        total_entities = sum(len(r.get("extraction_results", [{}])[0].get("extraction", {}).get("entities", [])) for r in results if r.get("extraction_processed", False))
        total_keywords = sum(len(r.get("extraction_results", [{}])[0].get("extraction", {}).get("keywords", [])) for r in results if r.get("extraction_processed", False))
        total_topics = sum(len(r.get("extraction_results", [{}])[0].get("extraction", {}).get("topics", [])) for r in results if r.get("extraction_processed", False))
        
        # Calculate aggregated insights statistics
        total_extracted_actions = sum(len(r.get("extracted_insights", {}).get("action_items", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_decisions = sum(len(r.get("extracted_insights", {}).get("decisions", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_issues = sum(len(r.get("extracted_insights", {}).get("issues", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_key_points = sum(len(r.get("extracted_insights", {}).get("key_points", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_pain_points = sum(len(r.get("extracted_insights", {}).get("pain_points", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_product_features = sum(len(r.get("extracted_insights", {}).get("product_features", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_objections = sum(len(r.get("extracted_insights", {}).get("objections", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_competitors = sum(len(r.get("extracted_insights", {}).get("competitors", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_decision_criteria = sum(len(r.get("extracted_insights", {}).get("decision_criteria", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_buyer_roles = sum(len(r.get("extracted_insights", {}).get("buyer_roles", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_deal_stages = sum(len(r.get("extracted_insights", {}).get("deal_stages", [])) for r in results if r.get("extraction_processed", False))
        total_extracted_use_cases = sum(len(r.get("extracted_insights", {}).get("use_cases", [])) for r in results if r.get("extraction_processed", False))
        
        logger.info(f"Total chunks created: {total_chunks}")
        logger.info(f"Total entities extracted: {total_entities}")
        logger.info(f"Total keywords extracted: {total_keywords}")
        logger.info(f"Total topics identified: {total_topics}")
        logger.info("SALES-FOCUSED INSIGHTS EXTRACTED:")
        logger.info(f"  Customer Pain Points: {total_extracted_pain_points}")
        logger.info(f"  Product Features Discussed: {total_extracted_product_features}")
        logger.info(f"  Objections Raised: {total_extracted_objections}")
        logger.info(f"  Next Steps / Action Items: {total_extracted_actions}")
        logger.info(f"  Competitors Mentioned: {total_extracted_competitors}")
        logger.info(f"  Decision Criteria: {total_extracted_decision_criteria}")
        logger.info(f"  Buyer Roles / Personas: {total_extracted_buyer_roles}")
        logger.info(f"  Deal Stage / Intent: {total_extracted_deal_stages}")
        logger.info(f"  Use Cases Mentioned: {total_extracted_use_cases}")
        logger.info(f"  Decisions: {total_extracted_decisions}")
        logger.info(f"  Issues: {total_extracted_issues}")
        logger.info(f"  Key Points: {total_extracted_key_points}")
        logger.info(f"Chunk content stored in collection: {GONG_CHUNKS_COLLECTION_NAME}")
        logger.info(f"Extracted insights stored in collection: {GONG_INSIGHTS_COLLECTION_NAME}")
        
        # Show aggregated insights for the first result
        if results and results[0].get("extracted_insights"):
            insights = results[0]["extracted_insights"]
            print("\nAGGREGATED SALES-FOCUSED EXTRACTION INSIGHTS:")
            
            if insights.get('pain_points'):
                print(f"\nCustomer Pain Points ({len(insights.get('pain_points', []))}):")
                for i, item in enumerate(insights.get('pain_points', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('product_features'):
                print(f"\nProduct Features Discussed ({len(insights.get('product_features', []))}):")
                for i, item in enumerate(insights.get('product_features', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('objections'):
                print(f"\nObjections Raised ({len(insights.get('objections', []))}):")
                for i, item in enumerate(insights.get('objections', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('action_items'):
                print(f"\nNext Steps / Action Items ({len(insights.get('action_items', []))}):")
                for i, item in enumerate(insights.get('action_items', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('competitors'):
                print(f"\nCompetitors Mentioned ({len(insights.get('competitors', []))}):")
                for i, item in enumerate(insights.get('competitors', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('decision_criteria'):
                print(f"\nDecision Criteria ({len(insights.get('decision_criteria', []))}):")
                for i, item in enumerate(insights.get('decision_criteria', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('buyer_roles'):
                print(f"\nBuyer Roles / Personas ({len(insights.get('buyer_roles', []))}):")
                for i, item in enumerate(insights.get('buyer_roles', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('deal_stages'):
                print(f"\nDeal Stage / Intent ({len(insights.get('deal_stages', []))}):")
                for i, item in enumerate(insights.get('deal_stages', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('use_cases'):
                print(f"\nUse Cases Mentioned ({len(insights.get('use_cases', []))}):")
                for i, item in enumerate(insights.get('use_cases', []), 1):
                    print(f"  {i}. {item}")
            
            print(f"\nOriginal Gong Action Items: {len(insights.get('original_gong_action_items', []))}")
            for i, item in enumerate(insights.get('original_gong_action_items', []), 1):
                print(f"  {i}. {item}")
            
            if insights.get('decisions'):
                print(f"\nExtracted Decisions ({len(insights.get('decisions', []))}):")
                for i, item in enumerate(insights.get('decisions', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('issues'):
                print(f"\nExtracted Issues ({len(insights.get('issues', []))}):")
                for i, item in enumerate(insights.get('issues', []), 1):
                    print(f"  {i}. {item}")
            
            if insights.get('key_points'):
                print(f"\nExtracted Key Points ({len(insights.get('key_points', []))}):")
                for i, item in enumerate(insights.get('key_points', []), 1):
                    print(f"  {i}. {item}")
    else:
        logger.info("Documents stored in regular storage (documents collection or PostgreSQL)")
    
    if failure_count > 0:
        logger.info("\nFailed calls:")
        for result in results:
            if not result.get("success", False):
                logger.info(f"- {result.get('document_id', 'Unknown')}: {result.get('error', 'Unknown error')}")
    
    # In test mode, print the document structure that would go to ChromaDB
    if test_mode and results and len(results) > 0:
        result = results[0]  # Get the first result
        
        if result.get("extraction_processed"):
            # Show example chunk document
            if result.get("extraction_results"):
                print("\nEXTRACTION RESULTS SUMMARY:")
                print(f"Total chunks created: {len(result['extraction_results'])}")
                
                # Only show detailed chunk information in test mode
                if test_mode:
                    print("\nChunk Details:")
                    for i, chunk in enumerate(result["extraction_results"]):
                        print(f"\nChunk {i+1}/{len(result['extraction_results'])}:")
                        print(f"ID: {chunk['chunk_id']}")
                        print(f"Index: {chunk['chunk_index']}")
                        print(f"Text Length: {len(chunk['chunk_text'])} chars")
                        print(f"Entities: {len(chunk['extraction']['entities'])} found")
                        print(f"Keywords: {len(chunk['extraction']['keywords'])} found")
                        print(f"Topics: {len(chunk['extraction']['topics'])} identified")
                        print(f"Insights/Summary: {chunk['extraction']['summary']}")
                        
                        # Print detailed insights if available
                        summary = chunk['extraction']['summary']
                        if '|' in summary:  # Check if we have structured insights
                            print("\nDetailed Insights:")
                            for insight in summary.split('|'):
                                insight = insight.strip()
                                if insight.startswith(('Action:', 'Decision:', 'Issue:', 'Metric:', 'Key point:', 'Summary:')):
                                    print(f"  • {insight}")
                
                # Show example documents
                first_chunk = result["extraction_results"][0]
                print("\nEXAMPLE DOCUMENTS (First Chunk):")
                print("\nGONG_CHUNKS COLLECTION DOCUMENT STRUCTURE")
                print(json.dumps({
                    "id": first_chunk["chunk_id"],
                    "content": first_chunk["chunk_text"],
                    "metadata": {
                        "chunk_id": first_chunk["chunk_id"],
                        "parent_doc_id": result["document_id"],
                        "chunk_index": first_chunk["chunk_index"],
                        "start_position": first_chunk["start_position"],
                        "end_position": first_chunk["end_position"],
                        "document_type": "gong_chunk",
                        "source_type": "gong",
                        "event_type": "extraction",
                        "gong_title": result["metadata"]["title"],
                        "gong_date": result["metadata"]["date"],
                        "date_timestamp": result["metadata"]["date_timestamp"]
                    }
                }, indent=2))
                
                print("\nGONG_INSIGHTS COLLECTION DOCUMENT STRUCTURE")
                
                # Create sample organized content for test display (matching the storage logic)
                test_action_items = []
                test_decisions = []
                test_issues = []
                test_key_points = []
                test_metrics = []
                
                for chunk in result["extraction_results"]:
                    if chunk["extraction"]["summary"]:
                        insights = [insight.strip() for insight in chunk["extraction"]["summary"].split('|')]
                        for insight in insights:
                            if insight.startswith("Action:"):
                                action_text = insight[7:].strip()
                                if action_text and len(action_text) > 10:
                                    test_action_items.append(action_text)
                            elif insight.startswith("Decision:"):
                                decision_text = insight[9:].strip()
                                if decision_text and len(decision_text) > 10:
                                    test_decisions.append(decision_text)
                            elif insight.startswith("Issue:"):
                                issue_text = insight[6:].strip()
                                if issue_text and len(issue_text) > 10:
                                    test_issues.append(issue_text)
                            elif insight.startswith("Key point:"):
                                key_point_text = insight[10:].strip()
                                if key_point_text and len(key_point_text) > 10:
                                    test_key_points.append(key_point_text)
                            elif insight.startswith("Metric:"):
                                metric_text = insight[7:].strip()
                                if metric_text and len(metric_text) > 10:
                                    test_metrics.append(metric_text)
                
                # Remove duplicates
                test_action_items = list(dict.fromkeys(test_action_items))
                test_decisions = list(dict.fromkeys(test_decisions))
                test_issues = list(dict.fromkeys(test_issues))
                test_key_points = list(dict.fromkeys(test_key_points))
                test_metrics = list(dict.fromkeys(test_metrics))
                
                # Create organized content format
                test_content_sections = []
                
                if test_action_items:
                    action_section = f"Action Items ({len(test_action_items)}):\n"
                    for i, item in enumerate(test_action_items, 1):
                        action_section += f"{i}. {item}\n"
                    test_content_sections.append(action_section.strip())
                
                if test_decisions:
                    decision_section = f"Decisions ({len(test_decisions)}):\n"
                    for i, item in enumerate(test_decisions, 1):
                        decision_section += f"{i}. {item}\n"
                    test_content_sections.append(decision_section.strip())
                
                if test_issues:
                    issue_section = f"Issues ({len(test_issues)}):\n"
                    for i, item in enumerate(test_issues, 1):
                        issue_section += f"{i}. {item}\n"
                    test_content_sections.append(issue_section.strip())
                
                if test_key_points:
                    key_points_section = f"Key Points ({len(test_key_points)}):\n"
                    for i, item in enumerate(test_key_points, 1):
                        key_points_section += f"{i}. {item}\n"
                    test_content_sections.append(key_points_section.strip())
                
                if test_metrics:
                    metrics_section = f"Metrics ({len(test_metrics)}):\n"
                    for i, item in enumerate(test_metrics, 1):
                        metrics_section += f"{i}. {item}\n"
                    test_content_sections.append(metrics_section.strip())
                
                organized_test_content = "\n\n".join(test_content_sections) if test_content_sections else ""
                
                # Aggregate entities, keywords, topics, categories for test display
                test_entities = set()
                test_keywords = set()
                test_topics = set()
                test_categories = set()
                
                for chunk in result["extraction_results"]:
                    test_entities.update(chunk["extraction"]["entities"])
                    test_keywords.update(chunk["extraction"]["keywords"])
                    test_topics.update(chunk["extraction"]["topics"])
                    test_categories.update(chunk["extraction"]["categories"])
                
                print(json.dumps({
                    "id": result["document_id"],
                    "content": organized_test_content,  # Organized insights format
                    "metadata": {
                        "document_id": result["document_id"],
                        "document_type": "gong_call_insights",
                        "source_type": "gong",
                        "event_type": "extraction",
                        "gong_title": result["metadata"]["title"],
                        "gong_date": result["metadata"]["date"],
                        "date_timestamp": result["metadata"]["date_timestamp"],
                        "total_chunks": len(result["extraction_results"]),
                        "entities": list(test_entities)[:50],  # Limit for display
                        "keywords": list(test_keywords)[:30],  # Limit for display
                        "topics": list(test_topics),
                        "categories": list(test_categories),
                        "chunk_collection": GONG_CHUNKS_COLLECTION_NAME
                    }
                }, indent=2))
        else:
            print("\nCHROMADB STORAGE STRUCTURE (documents collection)")
            print(json.dumps({
                "id": result["document_id"],
                "content": result["content"],  # No truncation
                "metadata": result["metadata"]
            }, indent=2))

@job
def gong_call_ingestion_pipeline():
    """Pipeline to process Gong call documents from JSONL files."""
    # Use context.op_config to access run configuration values inside ops
    records = load_gong_jsonl()
    documents = prepare_gong_documents(records)
    results = process_gong_documents(documents)
    summarize_gong_results(results)

# When running as a script, execute the pipeline
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Gong call ingestion pipeline")
    parser.add_argument("--test", action="store_true", help="Run in test mode (don't write to storage)")
    parser.add_argument("--line", type=int, default=0, help="Single line index to process in test mode (default: 0)")
    parser.add_argument("--lines", type=str, help="Comma-separated list of line indices to process in test mode (e.g. '0,1,2')")
    parser.add_argument("--postgres", action="store_true", help="Store documents in PostgreSQL instead of ChromaDB")
    parser.add_argument("--extraction", action="store_true", help="Enable extraction pipeline processing - stores chunk content in gong_chunks and insights in gong_insights collections (skips regular document storage)")
    args = parser.parse_args()
    
    # Handle line indices for test mode
    test_line_indices = []
    if args.test:
        if args.lines:
            try:
                test_line_indices = [int(x.strip()) for x in args.lines.split(',')]
                logger.info(f"Running in TEST MODE, processing lines {test_line_indices}")
            except ValueError:
                logger.error("Invalid line indices format. Please use comma-separated integers (e.g. '0,1,2')")
                exit(1)
        else:
            test_line_indices = [args.line]
            logger.info(f"Running in TEST MODE, processing line {args.line} only")
    
    # Prepare configuration based on arguments
    run_config = {
        "ops": {
            "load_gong_jsonl": {
                "config": {
                    "test_mode": args.test,
                    "test_line_indices": test_line_indices
                }
            },
            "prepare_gong_documents": {
                "config": {
                    "test_mode": args.test
                }
            },
            "process_gong_documents": {
                "config": {
                    "test_mode": args.test,
                    "use_postgres": args.postgres,
                    "extraction": args.extraction
                }
            },
            "summarize_gong_results": {
                "config": {
                    "test_mode": args.test
                }
            }
        }
    }
    
    if args.extraction:
        logger.info("EXTRACTION MODE enabled - will process documents through extraction pipeline")
        logger.info(f"Chunk content will be stored in ChromaDB collection: {GONG_CHUNKS_COLLECTION_NAME}")
        logger.info(f"Extracted insights will be stored in ChromaDB collection: {GONG_INSIGHTS_COLLECTION_NAME}")
        logger.info("Regular document storage (documents collection/PostgreSQL) will be SKIPPED")
    elif args.postgres:
        logger.info("Using PostgreSQL for document storage")
    else:
        logger.info("Using ChromaDB for document storage")
    
    # Execute with our configuration
    gong_call_ingestion_pipeline.execute_in_process(
        run_config=run_config,
        raise_on_error=True
    ) 