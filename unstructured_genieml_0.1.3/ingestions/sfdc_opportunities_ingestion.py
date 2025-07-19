"""
Pipeline for ingesting Salesforce Opportunity data that has been exported to CSV format.
This pipeline handles the extraction, processing, and storage of opportunity data and related metadata.
"""
import csv
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

import openai
from dagster import job, op, Array, Int
from tiktoken import encoding_for_model
from tqdm import tqdm

from app.schemas.document_schemas import DocumentType
from app.config.settings import get_settings
from app.services.vectorstore.documentstore import DocumentChromaStore
from app.services.database.dbservice import DatabaseService

# Import extraction pipeline components
from ingestions.extraction_pipeline import DocumentExtractor, ExtractionResult, ChunkResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the path to the CSV file for SFDC opportunity data
current_dir = Path(__file__).parent
project_root = current_dir.parent
csv_path = project_root / "example_data" / "salesforce_data" / "SFDCOpportunity.csv"

# Define the ChromaDB collection names
CHROMA_COLLECTION_NAME = "documents"
SFDC_INSIGHTS_COLLECTION_NAME = "gong_insights"
SFDC_CHUNKS_COLLECTION_NAME = "gong_chunks"

# OpenAI pricing (as of 2024) - prices per 1K tokens
OPENAI_PRICING = {
    "gpt-4o": {
        "input": 0.005,    # $0.005 per 1K input tokens
        "output": 0.015    # $0.015 per 1K output tokens
    }
}

def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate the cost of an LLM call in USD."""
    if model not in OPENAI_PRICING:
        logger.warning(f"Unknown model {model}, using gpt-3.5-turbo pricing")
        model = "gpt-3.5-turbo"
    
    pricing = OPENAI_PRICING[model]
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return input_cost + output_cost

def _format_llm_insights_as_summary(llm_insights: Dict[str, List[str]]) -> str:
    """Format LLM insights into a summary string similar to the old NLP summary format."""
    # Return empty string for None input
    if llm_insights is None:
        return ""
        
    summary_parts = []
    
    # Map insight types to prefixes
    type_prefixes = {
        "pain_points": "Pain Point: ",
        "product_features": "Product Feature: ",
        "objections": "Objection: ",
        "action_items": "Action: ",
        "competitors": "Competitor: ",
        "decision_criteria": "Decision Criteria: ",
        "use_cases": "Use Case: ",
        "loss_reasons": "Loss Reason: ",
        "opportunity_strengths": "Opportunity Strength: ",
        "risks": "Risk: "
    }
    
    # Add each insight with its prefix
    for insight_type, insights in llm_insights.items():
        if insights is None:  # Skip None insights
            continue
            
        prefix = type_prefixes.get(insight_type, f"{insight_type.replace('_', ' ').title()}: ")
        for insight in insights:
            if insight:  # Skip empty insights
                summary_parts.append(f"{prefix}{insight}")
    
    # Join with the separator used in NLP summaries
    return " | ".join(summary_parts)

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

def extract_sfdc_fields(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract all non-empty fields from a Salesforce opportunity record.
    
    Args:
        record: The record to extract fields from
        
    Returns:
        A tuple containing (extracted_fields_dict, full_data_dict)
    """
    # Create a copy of the record to avoid modifying the original
    data = record.copy()
    
    # Prepare the result dictionary with relevant fields
    result: Dict[str, Any] = {}
    
    # Extract all non-empty fields
    for key, value in data.items():
        # Check if value exists and is not just whitespace
        # Also keep '0' and '0.0' values as they are valid data points, not empty values
        is_zero_value = value in ['0', '0.0']
        
        if is_zero_value or (value and str(value).strip()):
            if key == "ID":
                result["opportunity_id"] = value
            elif key == "Stage Name":
                result["stage"] = value
            elif key == "Close Date":
                # Process date information
                try:
                    close_date = datetime.strptime(value, "%Y-%m-%d")
                    month = close_date.strftime('%B')  # Full month name
                    day = str(close_date.day)
                    year = str(close_date.year)
                    result["close_date"] = f"{month} {day}, {year}"
                    # Add timestamp for ChromaDB filtering
                    result["close_date_timestamp"] = close_date.timestamp()
                except (ValueError, TypeError):
                    # Handle any date parsing errors
                    result["close_date"] = value
                    result["close_date_timestamp"] = 0
            elif key == "Is Closed" or key == "Is Won":
                # Convert string boolean to actual boolean
                result[key.lower().replace(" ", "_")] = value.lower() == "true"
            else:
                # Use the original key name but convert to snake_case for consistency
                snake_case_key = key.lower().replace(" ", "_").replace("__c", "")
                result[snake_case_key] = value
    
    # Remove any null values from the result
    cleaned_result = remove_nulls(result)
    assert isinstance(cleaned_result, dict), "remove_nulls should return a dict when given a dict"
    
    return cleaned_result, data

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in the text."""
    encoder = encoding_for_model(model)
    return len(encoder.encode(text))

async def synthesize_document_insights(
    chunk_texts: List[str], 
    metadata: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate comprehensive insights from all chunk texts using GPT-4o.
    
    Args:
        chunk_texts: List of chunk text content
        metadata: Document metadata
        
    Returns:
        Tuple of (synthesized insights text, usage statistics)
    """
    settings = get_settings()
    
    # Configure the client
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    model = "gpt-4o"
    usage_stats = {
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0
    }
    
    # Check if we have any content at all
    if not chunk_texts or not any(chunk.strip() for chunk in chunk_texts):
        logger.warning("No chunk content found, skipping synthesis")
        return "## No Content Found\n\nNo meaningful content was available for analysis.", usage_stats
    
    # Combine all chunk texts with simple newlines
    combined_content = "\n\n".join(chunk_texts)
    
    # Basic opportunity info
    opportunity_name = metadata.get("sfdc_name", "")
    opportunity_stage = metadata.get("sfdc_stage", "")
    opportunity_amount = metadata.get("sfdc_amount", "")
    close_date = metadata.get("close_date", "")
    is_closed = metadata.get("is_closed", False)
    is_won = metadata.get("is_won", False)
    
    status = "closed-won" if is_closed and is_won else "closed-lost" if is_closed and not is_won else "open"
    
    prompt = f"""
    As a senior sales analyst, analyze this Salesforce opportunity data and extract comprehensive sales insights.
    
    OPPORTUNITY DETAILS:
    Name: {opportunity_name}
    Stage: {opportunity_stage}
    Amount: {opportunity_amount}
    Close Date: {close_date}
    Status: {status}
    
    OPPORTUNITY CONTENT:
    {combined_content}
    
    Analyze this opportunity data and provide a comprehensive report that includes:
    
    1. SALES INSIGHTS EXTRACTION:
       - Customer Pain Points: What problems or challenges are mentioned?
       - Product Features: What specific capabilities, functionalities, or technical characteristics are discussed?
       - Objections: What customer objections or concerns are raised?
       - Action Items: What are the next steps, demos, POCs, follow-up activities, or to-do items?
       - Competitors: What competitors or alternative solutions are mentioned?
       - Decision Criteria: What factors are influencing the buying decision?
       - Use Cases: What specific use cases or applications are mentioned?
       - Loss Reasons: If the deal was lost, what were the reasons?
       - Opportunity Strengths: What factors are working in our favor?
       - Risks: What risks or threats to closing the deal are mentioned?
    
    2. STRATEGIC ANALYSIS:
       - Top Loss Reasons (if applicable): Most significant factors contributing to deal loss
       - Repeating Traits: Patterns or recurring themes across this opportunity
       - Process Gaps: Process issues, missing steps, or areas for improvement
       - Timing Factors: Any timing-related issues that affected this opportunity
       - Recommendations: 2-3 specific, actionable recommendations for future opportunities
    
    3. SUMMARY INSIGHTS:
       - Key highlights and takeaways
       - Critical success/failure factors
       - Lessons learned
    
    Format your response with clear headings and bullet points. Be specific and data-driven where possible.
    Focus on actionable insights that can help improve future sales processes and outcomes.
    
    IMPORTANT: Extract complete phrases and sentences, not individual words. Provide concrete, specific insights based on the actual content provided.
    """
    
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert sales analyst specializing in Salesforce opportunity analysis. Provide comprehensive, actionable insights based on the opportunity data provided."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2500  # Increased for more comprehensive analysis
        )
        
        # Extract usage information
        if response and response.usage:
            usage_stats["input_tokens"] = response.usage.prompt_tokens
            usage_stats["output_tokens"] = response.usage.completion_tokens
            usage_stats["cost_usd"] = calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                model
            )
        
        # Get the synthesized content
        if response and response.choices and len(response.choices) > 0 and response.choices[0].message:
            message_content = response.choices[0].message.content
            if message_content:
                return message_content.strip(), usage_stats
        
        logger.error("Received empty or invalid response from LLM")
        return "## Failed to analyze opportunity\n\nPlease review the opportunity data manually.", usage_stats
    
    except Exception as e:
        logger.error(f"Error analyzing opportunity with LLM: {e}")
    
    # Return a basic fallback summary if LLM fails
    return "## Failed to analyze opportunity\n\nPlease review the opportunity data manually.", usage_stats

@op(config_schema={"test_mode": bool, "test_line_indices": Array(Int)})
def load_sfdc_csv(context) -> List[Dict[str, Any]]:
    """Load Salesforce opportunity records from CSV file."""
    test_mode = context.op_config["test_mode"]
    test_line_indices = context.op_config["test_line_indices"]
    
    records = []
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at {csv_path}")
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            if test_mode:
                # In test mode, read only the specified lines
                for i, record in enumerate(reader):
                    if i in test_line_indices:
                        records.append(record)
                logger.info(f"Loaded {len(records)} SFDC opportunity records (test mode, lines {test_line_indices})")
            else:
                # Normal mode - read all lines
                records = list(reader)
                logger.info(f"Loaded {len(records)} SFDC opportunity records from CSV file")
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        traceback.print_exc()
        
    return records 

@op(config_schema={"test_mode": bool})
def prepare_sfdc_documents(context, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepare Salesforce opportunity records for processing."""
    test_mode = context.op_config["test_mode"]
    documents = []
    
    for record in records:
        try:
            # Extract fields and get the full data
            extracted_fields, full_data = extract_sfdc_fields(record)
            
            # Skip records without essential information
            if not extracted_fields.get("opportunity_id") or not extracted_fields.get("name"):
                logger.warning(f"Skipping record with missing essential data: {extracted_fields.get('opportunity_id', 'unknown')}")
                continue
            
            # Format the extracted fields as a structured content block
            formatted_content = []
            
            # Add opportunity name and basic information first
            formatted_content.append(f"Opportunity: {extracted_fields.get('name', 'Unnamed Opportunity')}")
            
            # Add all fields from extracted_fields to the formatted content
            for key, value in extracted_fields.items():
                if key != "name" and key != "description":  # Skip name (already added) and description (will add separately)
                    # Format the key into readable form
                    readable_key = key.replace("_", " ").title()
                    formatted_content.append(f"{readable_key}: {value}")
            
            # Add detailed description if available (after all other fields for better readability)
            if extracted_fields.get("description"):
                formatted_content.append(f"\nDescription:\n{extracted_fields.get('description')}")
            
            # Join everything into a content string
            content_text = "\n".join(formatted_content)
            
            if not content_text.strip():
                logger.warning(f"Skipping opportunity {extracted_fields.get('name', 'Unnamed')} - no content available")
                continue
            
            # Create document structure
            sfdc_id = extracted_fields.get("opportunity_id", "")
            doc_id = str(uuid.uuid4())  # Generate UUID for document ID
            doc = {
                "document": {
                    "content": content_text,
                    "metadata": {
                        "document_id": doc_id,
                        "sfdc_opportunity_id": sfdc_id,  # Keep original Salesforce ID
                        "document_type": "salesforce_opportunity",
                        "opportunity_name": extracted_fields.get("name", "Unnamed Opportunity"),
                        "source_type": "salesforce",
                        "event_type": "import"
                    }
                },
                "document_id": doc_id,
                "source_type": "salesforce",
                "document_type": "salesforce_opportunity",
                "event_type": "import",
                "sfdc_data": extracted_fields  # Store all extracted fields
            }
            
            # Ensure all null values are removed from metadata
            doc["document"]["metadata"] = remove_nulls(doc["document"]["metadata"])
            
            documents.append(doc)
                
        except Exception as e:
            logger.error(f"Error preparing SFDC document: {e}")
            traceback.print_exc()
    
    if test_mode:
        logger.info(f"Prepared {len(documents)} SFDC opportunity document for testing")
    else:
        logger.info(f"Prepared {len(documents)} SFDC opportunity documents for processing")
    
    return documents 

async def process_document(doc_id, doc_chunks, documents, batch_index, total_batches, batch_doc_count, batch_docs_count, test_mode, chunks_store, insights_store):
    """Process a single document asynchronously.
    
    This function handles the entire document processing flow including:
    - Collecting chunk texts
    - Running GPT-4o analysis
    - Storing chunks and insights
    - Preparing result data
    
    Args:
        doc_id: The document ID
        doc_chunks: List of chunks for this document
        documents: Original documents list
        batch_index: Current batch index
        total_batches: Total number of batches
        batch_doc_count: Current document count in batch
        batch_docs_count: Total documents in batch
        test_mode: Whether we're in test mode
        chunks_store: ChromaDB store for chunks
        insights_store: ChromaDB store for insights
        
    Returns:
        dict: Processing result
    """
    logger.info(f"[BATCH {batch_index}/{total_batches}] [{batch_doc_count}/{batch_docs_count}] Processing document with {len(doc_chunks)} chunks")
    
    # Find the original document that matches this ID
    matching_docs = [d for d in documents if f"sfdc_{d['document']['metadata']['document_id']}" == doc_id]
    if not matching_docs:
        logger.warning(f"Could not find original document for {doc_id}")
        return {
            "success": False,
            "document_id": "unknown",
            "error": "Original document not found",
            "extraction_processed": False,
            "regular_storage_skipped": True,
            "extracted_insights": {
                "pain_points": [],
                "product_features": [],
                "objections": [],
                "action_items": [],
                "competitors": [],
                "decision_criteria": [],
                "use_cases": [],
                "decisions": [],
                "issues": [],
                "key_points": []
            },
            "usage_stats": {}
        }
    
    doc = matching_docs[0]
    original_doc_id = doc["document"]["metadata"]["document_id"]
    sfdc_id = doc["document"]["metadata"].get("sfdc_opportunity_id", "")
    
    try:
        # Initialize LLM-based insights collection
        all_chunk_texts = []
        
        # Initialize extraction variables (these will be populated from the single GPT-4o analysis)
        extracted_action_items = []
        extracted_decisions = []
        extracted_issues = []
        extracted_key_points = []
        extracted_pain_points = []
        extracted_product_features = []
        extracted_objections = []
        extracted_competitors = []
        extracted_decision_criteria = []
        extracted_use_cases = []
        
        all_entities = set()
        all_keywords = set()
        all_topics = set()
        all_categories = set()
        
        # Process each chunk to collect text and NLP data
        logger.debug(f"[BATCH {batch_index}] Processing {len(doc_chunks)} chunks for document {original_doc_id}")
        for chunk in doc_chunks:
            # Collect chunk text for GPT-4o analysis
            all_chunk_texts.append(chunk.text)
            
            # Basic chunk metadata
            chunk_metadata = {
                "chunk_id": chunk.chunk_id,
                "parent_doc_id": chunk.parent_doc_id,
                "document_id": original_doc_id,
                "sfdc_opportunity_id": sfdc_id,
                "chunk_index": chunk.chunk_index,
                "start_position": chunk.start_position,
                "end_position": chunk.end_position,
                "document_type": "sfdc_chunk",
                "source_type": "salesforce",
                "event_type": "extraction",
                "sfdc_name": doc["sfdc_data"].get("name", ""),
                "close_date": doc["sfdc_data"].get("close_date", ""),
                "close_date_timestamp": doc["document"]["metadata"].get("close_date_timestamp"),
                "is_closed": doc["sfdc_data"].get("is_closed", False),
                "is_won": doc["sfdc_data"].get("is_won", False),
                "overlap_info": json.dumps(chunk.overlap_info) if chunk.overlap_info else None,  # Convert dict to JSON string
                "insights_document_id": original_doc_id  # Add reference to the insights document
            }
            
            # Clean metadata to remove None values
            chunk_metadata = remove_nulls(chunk_metadata)
            
            # Still gather NLP extraction data for metadata enrichment
            all_entities.update(chunk.extraction.entities)
            all_keywords.update(chunk.extraction.keywords)
            all_topics.update(chunk.extraction.topics)
            all_categories.update(chunk.extraction.categories)
            
            # Store the chunk in non-test mode
            if not test_mode:
                chunks_store.collection.add(
                    ids=[chunk.chunk_id],
                    documents=[chunk.text],
                    metadatas=[chunk_metadata]
                )
        
        # Generate comprehensive insights using single GPT-4o call
        logger.info(f"[BATCH {batch_index}/{total_batches}] [{batch_doc_count}/{batch_docs_count}] ANALYZING: Running GPT-4o analysis")
        
        # Create document metadata for analysis
        analysis_metadata = {
            "sfdc_name": doc["sfdc_data"].get("name", ""),
            "sfdc_stage": doc["sfdc_data"].get("stage", ""),
            "sfdc_amount": doc["sfdc_data"].get("amount", ""),
            "close_date": doc["sfdc_data"].get("close_date", ""),
            "is_closed": doc["sfdc_data"].get("is_closed", False),
            "is_won": doc["sfdc_data"].get("is_won", False),
        }
        
        # Generate comprehensive analysis
        synthesized_content, synthesis_usage_stats = await synthesize_document_insights(
            all_chunk_texts, 
            analysis_metadata
        )
        
        logger.info(f"[BATCH {batch_index}/{total_batches}] [{batch_doc_count}/{batch_docs_count}] ANALYSIS COMPLETE: GPT-4o processing finished")
        
        # Store the document in non-test mode
        if not test_mode:
            # Store the synthesized insights
            insights_metadata = {
                "document_id": original_doc_id,
                "sfdc_opportunity_id": sfdc_id if sfdc_id else "",
                "document_type": "sfdc_opportunity_insights", 
                "source_type": "salesforce",
                "event_type": "extraction",
                "sfdc_name": doc["sfdc_data"].get("name", ""),
                "close_date": doc["sfdc_data"].get("close_date", ""),
                "close_date_timestamp": doc["document"]["metadata"].get("close_date_timestamp", 0),
                "is_closed": doc["sfdc_data"].get("is_closed", False),
                "is_won": doc["sfdc_data"].get("is_won", False),
                "total_chunks": len(doc_chunks),
                # Convert all lists to JSON strings
                "entities": json.dumps(list(all_entities)[:50]) if all_entities else "[]",
                "keywords": json.dumps(list(all_keywords)[:30]) if all_keywords else "[]",
                "topics": json.dumps(list(all_topics)) if all_topics else "[]",
                "categories": json.dumps(list(all_categories)) if all_categories else "[]",
                "chunk_collection": SFDC_CHUNKS_COLLECTION_NAME
            }
            
            # Log the insights_metadata to inspect
            logger.info(f"[BATCH {batch_index}/{total_batches}] [{batch_doc_count}/{batch_docs_count}] INSIGHTS METADATA: {json.dumps(insights_metadata, default=str)}")
            
            # Replace any None values with appropriate defaults
            for key, value in insights_metadata.items():
                if value is None:
                    logger.warning(f"Found None value for key '{key}' in insights_metadata")
                    if isinstance(value, list):
                        insights_metadata[key] = "[]"  # Empty JSON array
                    elif isinstance(value, dict):
                        insights_metadata[key] = "{}"  # Empty JSON object
                    elif isinstance(value, bool):
                        insights_metadata[key] = False
                    elif isinstance(value, int):
                        insights_metadata[key] = 0
                    elif isinstance(value, float):
                        insights_metadata[key] = 0.0
                    else:
                        insights_metadata[key] = ""
            
            # Store the synthesized content as the document
            insights_store.collection.add(
                ids=[original_doc_id],  # Use document ID, not chunk ID
                documents=[synthesized_content],  # Use the LLM synthesized content
                metadatas=[insights_metadata]
            )
            
            logger.info(f"[BATCH {batch_index}/{total_batches}] [{batch_doc_count}/{batch_docs_count}] STORAGE COMPLETE: Stored {len(doc_chunks)} chunks and 1 insights document")
        else:
            logger.info(f"[TEST MODE] Skipping storage of {len(doc_chunks)} chunks and insights")
        
        # Add to results
        result = {
            "success": True,
            "document_id": original_doc_id,
            "content": doc["document"]["content"],
            "metadata": doc["document"]["metadata"],
            "extraction_processed": True,
            "regular_storage_skipped": True,
            "chunks_created": len(doc_chunks),
            "synthesized_content": synthesized_content,  # Add the synthesized content to results
            "extracted_insights": {
                "pain_points": extracted_pain_points,
                "product_features": extracted_product_features,
                "objections": extracted_objections,
                "action_items": extracted_action_items,
                "competitors": extracted_competitors,
                "decision_criteria": extracted_decision_criteria,
                "use_cases": extracted_use_cases,
                "decisions": extracted_decisions,
                "issues": extracted_issues,
                "key_points": extracted_key_points
            },
            "llm_costs": {
                "total_synthesis_cost_usd": synthesis_usage_stats.get("cost_usd", 0.0),
                "total_cost_usd": synthesis_usage_stats.get("cost_usd", 0.0),
                "synthesis_usage": synthesis_usage_stats
            } if test_mode else {}
        }
        
        # Add extraction results in test mode
        if test_mode:
            extraction_results = []
            for chunk_idx, chunk in enumerate(doc_chunks):
                chunk_extraction = getattr(chunk, 'extraction', None)
                
                # Extract NLP data safely
                entities = []
                keywords = []
                topics = []
                categories = []
                metadata = {}
                
                if chunk_extraction is not None:
                    entities = chunk_extraction.entities if hasattr(chunk_extraction, 'entities') else []
                    keywords = chunk_extraction.keywords if hasattr(chunk_extraction, 'keywords') else []
                    topics = chunk_extraction.topics if hasattr(chunk_extraction, 'topics') else []
                    categories = chunk_extraction.categories if hasattr(chunk_extraction, 'categories') else []
                    metadata = chunk_extraction.metadata if hasattr(chunk_extraction, 'metadata') else {}
                
                extraction_results.append({
                    "chunk_id": chunk.chunk_id,
                    "chunk_text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                    "start_position": chunk.start_position,
                    "end_position": chunk.end_position,
                    "extraction": {
                        # Keep NLP extraction for entity, keyword, topic data
                        "entities": entities,
                        "keywords": keywords,
                        "topics": topics,
                        "categories": categories,
                        # Use LLM insights for summary
                        "summary": _format_llm_insights_as_summary({
                            "pain_points": extracted_pain_points,
                            "product_features": extracted_product_features,
                            "objections": extracted_objections,
                            "action_items": extracted_action_items,
                            "competitors": extracted_competitors,
                            "decision_criteria": extracted_decision_criteria,
                            "use_cases": extracted_use_cases
                        }),
                        "metadata": metadata,
                        # Include raw LLM insights
                        "llm_insights": {
                            "pain_points": extracted_pain_points,
                            "product_features": extracted_product_features,
                            "objections": extracted_objections,
                            "action_items": extracted_action_items,
                            "competitors": extracted_competitors,
                            "decision_criteria": extracted_decision_criteria,
                            "use_cases": extracted_use_cases
                        }
                    }
                })
            result["extraction_results"] = extraction_results
        
        return result
    except Exception as e:
        logger.error(f"Error processing chunks for document: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "document_id": original_doc_id,
            "error": str(e),
            "extraction_processed": False,
            "regular_storage_skipped": True,
            "extracted_insights": {
                "pain_points": [],
                "product_features": [],
                "objections": [],
                "action_items": [],
                "competitors": [],
                "decision_criteria": [],
                "use_cases": [],
                "decisions": [],
                "issues": [],
                "key_points": []
            },
            "usage_stats": {}
        }

@op(config_schema={"test_mode": bool, "use_postgres": bool, "extraction": bool})
async def process_sfdc_documents(context, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process Salesforce opportunity documents and store in either ChromaDB or PostgreSQL based on configuration."""
    test_mode = context.op_config["test_mode"]
    use_postgres = context.op_config["use_postgres"]
    extraction_mode = context.op_config["extraction"]
    
    # Initialize storage services based on configuration
    if extraction_mode:
        # In extraction mode, initialize both chunks and insights stores + extractor
        settings = get_settings()
        chunks_store = DocumentChromaStore(collection_name=SFDC_CHUNKS_COLLECTION_NAME)
        insights_store = DocumentChromaStore(collection_name=SFDC_INSIGHTS_COLLECTION_NAME)
        
        # Initialize extractor with advanced NLP and custom settings
        doc_extractor = DocumentExtractor(
            use_advanced_nlp=True  # Enable advanced NLP features
        )
        
        logger.info(f"[EXTRACTION MODE] Initialized collections: {SFDC_CHUNKS_COLLECTION_NAME} and {SFDC_INSIGHTS_COLLECTION_NAME}")
        logger.info("[EXTRACTION MODE] Initialized document extractor with advanced NLP")
        
        # Allow extraction processing in test mode
        if test_mode:
            logger.info("[TEST MODE] Extraction processing enabled")
    elif use_postgres:
        db_service = DatabaseService()
        logger.info("Initialized PostgreSQL database service")
        
        # If we're using PostgreSQL, initialize ChromaDB connection to check for existing docs
        settings = get_settings()
        chroma_store = DocumentChromaStore(collection_name=CHROMA_COLLECTION_NAME)
        logger.info(f"Initialized ChromaDB collection: {CHROMA_COLLECTION_NAME} for ID retrieval")
    else:
        settings = get_settings()
        chroma_store = DocumentChromaStore(collection_name=CHROMA_COLLECTION_NAME)
        logger.info(f"Initialized ChromaDB collection: {CHROMA_COLLECTION_NAME}")
    
    results = []
    
    if extraction_mode:
        # Prepare documents for extraction (all documents)
        extraction_batches = []
        batch_size = 5  # Process 5 documents at a time
        current_batch = []
        total_docs = len(documents)
        
        logger.info(f"[EXTRACTION MODE] Processing {total_docs} documents in batches of {batch_size}")
        
        # Prepare all documents for extraction first
        logger.info("[PREP] Preparing documents for extraction")
        for doc_index, doc in tqdm(enumerate(documents, 1), total=total_docs, desc="Preparing documents"):
            try:
                # Get the parsed SFDC data
                sfdc_data = doc.get("sfdc_data", {})
                content_text = doc["document"]["content"]
                doc_id = doc["document"]["metadata"]["document_id"]
                sfdc_id = doc["document"]["metadata"].get("sfdc_opportunity_id", "")
                metadata = doc["document"]["metadata"]
                
                # Create extraction metadata
                extraction_metadata = {
                    "document_id": doc_id,
                    "sfdc_opportunity_id": sfdc_id,
                    "sfdc_name": sfdc_data.get("name", ""),
                    "sfdc_stage": sfdc_data.get("stage", ""),
                    "sfdc_amount": sfdc_data.get("amount", ""),
                    "source_type": "salesforce",
                    # Add SFDC-specific metadata for better extraction
                    "is_closed": sfdc_data.get("is_closed", False),
                    "is_won": sfdc_data.get("is_won", False),
                    "pain_points": sfdc_data.get("pain_points", ""),
                    "objectives": sfdc_data.get("objectives", ""),
                    "business_value": sfdc_data.get("business_value", "")
                }
                
                # Add any existing insights from the data
                existing_insights = []
                if sfdc_data.get("key_highlights"):
                    highlights = sfdc_data["key_highlights"].split("\n")
                    existing_insights.extend([f"Key point: {h.strip()}" for h in highlights if h.strip()])
                
                # For opportunities that are closed-lost, add the loss reason as an insight
                if sfdc_data.get("is_closed") and not sfdc_data.get("is_won") and sfdc_data.get("loss_reason"):
                    existing_insights.append(f"Loss Reason: {sfdc_data['loss_reason']}")
                
                # Determine categories based on opportunity data
                categories = []
                if sfdc_data.get("stage"):
                    categories.append(f"stage_{sfdc_data['stage'].lower().replace(' ', '_')}")
                
                if sfdc_data.get("type"):
                    categories.append(f"type_{sfdc_data['type'].lower().replace(' ', '_')}")
                
                if sfdc_data.get("lead_source"):
                    categories.append(f"source_{sfdc_data['lead_source'].lower().replace(' ', '_')}")
                
                # Add to extraction batch
                doc_for_extraction = {
                    "id": f"sfdc_{doc_id}",  # Use UUID-based document ID
                    "sfdc_id": sfdc_id,       # Include original Salesforce ID 
                    "content": content_text,
                    "categories": categories,
                    "metadata": extraction_metadata,
                    "existing_insights": existing_insights
                }
                
                current_batch.append(doc_for_extraction)
                
                # If we've reached batch size or this is the last document, add batch to batches
                if len(current_batch) >= batch_size or doc_index == total_docs:
                    extraction_batches.append(current_batch)
                    current_batch = []
                
                # Log document stats
                content_size = len(content_text.encode('utf-8'))
                metadata_size = len(json.dumps(metadata).encode('utf-8'))
                total_size = content_size + metadata_size
                content_tokens = count_tokens(content_text)
                metadata_tokens = count_tokens(json.dumps(metadata))
                total_tokens = content_tokens + metadata_tokens
                
                logger.debug(f"[PREP] [{doc_index}/{total_docs}] Prepared document {doc_id} - Size: {total_size/1024:.2f}KB, Tokens: {total_tokens}")
            except Exception as e:
                logger.error(f"Error preparing document for extraction: {e}\n{traceback.format_exc()}")
                continue
        
        # Process documents in batches
        try:
            # Track processing metrics
            total_batches = len(extraction_batches)
            total_chunks = 0
            total_docs_processed = 0
            
            logger.info(f"[EXTRACTION MODE] Processing {total_batches} batches with {sum(len(batch) for batch in extraction_batches)} documents total")
            
            # Process each batch separately
            for batch_index, extraction_batch in enumerate(extraction_batches, 1):
                batch_docs_count = len(extraction_batch)
                logger.info(f"[BATCH {batch_index}/{total_batches}] Starting processing of {batch_docs_count} documents with parallel workers")
                
                # Process this batch with parallel workers
                batch_chunk_results = await doc_extractor.process_documents_batch(
                    documents=extraction_batch,
                    chunk_size=None,  # Use dynamic chunking
                    overlap=None,     # Use dynamic overlap
                    max_workers=4     # Adjust based on system capabilities
                )
                
                # Group chunks by parent document
                chunks_by_doc = defaultdict(list)
                for chunk in batch_chunk_results:
                    chunks_by_doc[chunk.parent_doc_id].append(chunk)
                
                batch_chunks_count = len(batch_chunk_results)
                total_chunks += batch_chunks_count
                logger.info(f"[BATCH {batch_index}/{total_batches}] CHUNKING COMPLETE: {batch_chunks_count} chunks created")
                
                # Process documents in parallel within this batch
                # Prepare the tasks for concurrent processing
                doc_tasks = []
                for batch_doc_count, (doc_id, doc_chunks) in enumerate(chunks_by_doc.items(), 1):
                    task = process_document(
                        doc_id=doc_id,
                        doc_chunks=doc_chunks,
                        documents=documents,
                        batch_index=batch_index,
                        total_batches=total_batches,
                        batch_doc_count=batch_doc_count,
                        batch_docs_count=batch_docs_count,
                        test_mode=test_mode,
                        chunks_store=chunks_store,
                        insights_store=insights_store
                    )
                    doc_tasks.append(task)
                
                # Run all document processing tasks concurrently
                logger.info(f"[BATCH {batch_index}/{total_batches}] Running {len(doc_tasks)} document processing tasks in parallel")
                batch_results = await asyncio.gather(*doc_tasks)
                
                # Add batch results to overall results
                results.extend(batch_results)
                total_docs_processed += len(batch_results)
                
                logger.info(f"[BATCH {batch_index}/{total_batches}] BATCH COMPLETE: Processed {len(batch_results)} documents, {batch_chunks_count} chunks")
            
            # Final summary log
            logger.info(f"[EXTRACTION MODE] PROCESSING COMPLETE: {total_docs_processed} documents, {total_chunks} chunks, {total_batches} batches")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}\n{traceback.format_exc()}")
            # Add error results for all documents
            for doc in documents:
                results.append({
                    "success": False,
                    "document_id": doc["document"]["metadata"].get("document_id", "unknown"),
                    "error": str(e),
                    "extraction_processed": False,
                    "regular_storage_skipped": True,
                    "extracted_insights": {
                        "pain_points": [],
                        "product_features": [],
                        "objections": [],
                        "action_items": [],
                        "competitors": [],
                        "decision_criteria": [],
                        "use_cases": [],
                        "decisions": [],
                        "issues": [],
                        "key_points": []
                    },
                    "usage_stats": {}
                })
    else:
        # Store documents based on configuration (original logic) - ONLY if NOT in extraction mode
        for doc in documents:
            doc_id = doc["document"]["metadata"]["document_id"]
            content_text = doc["document"]["content"]
            metadata = doc["document"]["metadata"]
            sfdc_id = doc["document"]["metadata"].get("sfdc_opportunity_id", "")
            
            if not test_mode:
                if use_postgres:
                    # Check if this opportunity already exists in ChromaDB by SFDC ID
                    existing_doc_id = None
                    if sfdc_id:
                        try:
                            # Query ChromaDB to find if this SFDC opportunity is already stored
                            query_results = chroma_store.collection.get(
                                where={"sfdc_opportunity_id": sfdc_id},
                                limit=1
                            )
                            if query_results and query_results['ids'] and len(query_results['ids']) > 0:
                                existing_doc_id = query_results['ids'][0]
                                logger.info(f"Found existing document in ChromaDB with ID {existing_doc_id} for SFDC opportunity {sfdc_id}")
                        except Exception as e:
                            logger.warning(f"Error querying ChromaDB for existing document: {e}")
                    
                    # If we found an existing ID in ChromaDB, use it for PostgreSQL
                    if existing_doc_id:
                        logger.info(f"Using existing ChromaDB document ID {existing_doc_id} for PostgreSQL storage")
                        db_service.store_document(
                            content=content_text,
                            metadata={**metadata, "document_id": existing_doc_id},
                            source_type="salesforce",
                            document_type="salesforce_opportunity"
                        )
                        # Update doc_id to the existing one for consistency in results
                        doc_id = existing_doc_id
                    else:
                        # No existing document, proceed with normal storage
                        logger.info(f"Storing document {doc_id} in PostgreSQL")
                        db_service.store_document(
                            content=content_text,
                            metadata=metadata,
                            source_type="salesforce",
                            document_type="salesforce_opportunity"
                        )
                    logger.info(f"Successfully stored document {doc_id} in PostgreSQL")
                else:
                    logger.info(f"Storing document {doc_id} in ChromaDB collection '{CHROMA_COLLECTION_NAME}'")
                    # Clean metadata to remove None values
                    metadata = remove_nulls(metadata)
                    chroma_store.collection.add(
                        ids=[doc_id],
                        documents=[content_text],
                        metadatas=[metadata]
                    )
                    logger.info(f"Successfully stored document {doc_id} in ChromaDB")
            else:
                logger.info(f"[TEST MODE] Skipping storage for document {doc_id}")
            
            result = {
                "success": True,
                "document_id": doc_id,
                "content": content_text,
                "metadata": metadata,
                "extraction_processed": False,
                "regular_storage_skipped": False,
                "usage_stats": {}
            }
            results.append(result)
    
    return results 

@op(config_schema={"test_mode": bool})
def summarize_sfdc_results(context, results: List[Dict[str, Any]]) -> None:
    """Summarize the results of Salesforce opportunity document processing."""
    test_mode = context.op_config["test_mode"]
    
    success_count = sum(1 for r in results if r.get("success", False))
    failure_count = len(results) - success_count
    extraction_processed_count = sum(1 for r in results if r.get("extraction_processed", False))
    regular_storage_skipped_count = sum(1 for r in results if r.get("regular_storage_skipped", False))
    
    logger.info("\nSalesforce Opportunity Processing Summary:")
    logger.info(f"Total opportunities processed: {len(results)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failure_count}")
    
    if extraction_processed_count > 0:
        logger.info(f"Processed through extraction pipeline: {extraction_processed_count}")
        logger.info(f"Regular document storage skipped: {regular_storage_skipped_count}")
        
        # Calculate extraction statistics
        total_chunks = sum(r.get("chunks_created", 0) for r in results if r.get("extraction_processed", False))
        
        # Calculate aggregated insights statistics for the first successful result
        successful_results = [r for r in results if r.get("success", False) and r.get("extraction_processed", False)]
        if successful_results:
            first_result = successful_results[0]
            
            # Extract insights from synthesized content if available
            if first_result.get("synthesized_content"):
                # Parse the synthesized content to extract insights
                content = first_result.get("synthesized_content", "")
                extracted_insights = parse_insights_from_content(content)
                
                # Update the first result with parsed insights
                first_result["extracted_insights"] = extracted_insights
                
                # Update any other results with same structure
                for result in successful_results:
                    if result.get("synthesized_content") and not result.get("extracted_insights"):
                        result["extracted_insights"] = parse_insights_from_content(result.get("synthesized_content", ""))
            
            insights = first_result.get("extracted_insights", {})
            
            total_extracted_actions = sum(len(r.get("extracted_insights", {}).get("action_items", [])) for r in successful_results)
            total_extracted_decisions = sum(len(r.get("extracted_insights", {}).get("decisions", [])) for r in successful_results)
            total_extracted_issues = sum(len(r.get("extracted_insights", {}).get("issues", [])) for r in successful_results)
            total_extracted_key_points = sum(len(r.get("extracted_insights", {}).get("key_points", [])) for r in successful_results)
            total_extracted_pain_points = sum(len(r.get("extracted_insights", {}).get("pain_points", [])) for r in successful_results)
            total_extracted_product_features = sum(len(r.get("extracted_insights", {}).get("product_features", [])) for r in successful_results)
            total_extracted_objections = sum(len(r.get("extracted_insights", {}).get("objections", [])) for r in successful_results)
            total_extracted_competitors = sum(len(r.get("extracted_insights", {}).get("competitors", [])) for r in successful_results)
            total_extracted_decision_criteria = sum(len(r.get("extracted_insights", {}).get("decision_criteria", [])) for r in successful_results)
            total_extracted_use_cases = sum(len(r.get("extracted_insights", {}).get("use_cases", [])) for r in successful_results)
            
            logger.info(f"Total chunks created: {total_chunks}")
            logger.info("SALES-FOCUSED INSIGHTS EXTRACTED:")
            logger.info(f"  Customer Pain Points: {total_extracted_pain_points}")
            logger.info(f"  Product Features Discussed: {total_extracted_product_features}")
            logger.info(f"  Objections Raised: {total_extracted_objections}")
            logger.info(f"  Next Steps / Action Items: {total_extracted_actions}")
            logger.info(f"  Competitors Mentioned: {total_extracted_competitors}")
            logger.info(f"  Decision Criteria: {total_extracted_decision_criteria}")
            logger.info(f"  Use Cases Mentioned: {total_extracted_use_cases}")
            logger.info(f"  Decisions: {total_extracted_decisions}")
            logger.info(f"  Issues: {total_extracted_issues}")
            logger.info(f"  Key Points: {total_extracted_key_points}")
            logger.info(f"Chunk content stored in collection: {SFDC_CHUNKS_COLLECTION_NAME}")
            logger.info(f"Extracted insights stored in collection: {SFDC_INSIGHTS_COLLECTION_NAME}")
            
            # Show LLM costs in test mode
            if test_mode and successful_results:
                first_result = successful_results[0]
                llm_costs = first_result.get("llm_costs", {})
                if llm_costs:
                    print(f"\nLLM COST BREAKDOWN (USD):")
                    print(f"  Document Analysis (gpt-4o): ${llm_costs.get('total_synthesis_cost_usd', 0.0):.4f}")
                    print(f"  TOTAL COST: ${llm_costs.get('total_cost_usd', 0.0):.4f}")
                    
                    synthesis_usage = llm_costs.get('synthesis_usage', {})
                    if synthesis_usage:
                        print(f"  Single GPT-4o call: {synthesis_usage.get('input_tokens', 0)} input + {synthesis_usage.get('output_tokens', 0)} output tokens")
            
            # Show aggregated insights for the first result
            if test_mode and insights:
                print("\nAGGREGATED SALES-FOCUSED EXTRACTION INSIGHTS:")
                
                if insights.get('pain_points'):
                    print(f"\nCustomer Pain Points ({len(insights.get('pain_points', []))}):")
                    for i, item in enumerate(insights.get('pain_points', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('product_features'):
                    print(f"\nProduct Features Discussed ({len(insights.get('product_features', []))}):")
                    for i, item in enumerate(insights.get('product_features', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('objections'):
                    print(f"\nObjections Raised ({len(insights.get('objections', []))}):")
                    for i, item in enumerate(insights.get('objections', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('action_items'):
                    print(f"\nNext Steps / Action Items ({len(insights.get('action_items', []))}):")
                    for i, item in enumerate(insights.get('action_items', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('competitors'):
                    print(f"\nCompetitors Mentioned ({len(insights.get('competitors', []))}):")
                    for i, item in enumerate(insights.get('competitors', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('decision_criteria'):
                    print(f"\nDecision Criteria ({len(insights.get('decision_criteria', []))}):")
                    for i, item in enumerate(insights.get('decision_criteria', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('use_cases'):
                    print(f"\nUse Cases Mentioned ({len(insights.get('use_cases', []))}):")
                    for i, item in enumerate(insights.get('use_cases', [])[:3], 1):
                        print(f"  {i}. {item}")
                        
                if insights.get('decisions'):
                    print(f"\nExtracted Decisions ({len(insights.get('decisions', []))}):")
                    for i, item in enumerate(insights.get('decisions', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('issues'):
                    print(f"\nExtracted Issues ({len(insights.get('issues', []))}):")
                    for i, item in enumerate(insights.get('issues', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                if insights.get('key_points'):
                    print(f"\nExtracted Key Points ({len(insights.get('key_points', []))}):")
                    for i, item in enumerate(insights.get('key_points', [])[:3], 1):
                        print(f"  {i}. {item}")
                
                # Add detailed chunk information in test mode
                if test_mode and first_result and first_result.get("extraction_results"):
                    print("\nEXTRACTION RESULTS SUMMARY:")
                    print(f"Total chunks created: {first_result.get('chunks_created', 0)}")
                    
                    # Show detailed chunk information
                    print("\nChunk Details:")
                    extraction_results = first_result.get("extraction_results", [])
                    for i, chunk in enumerate(extraction_results, 1):
                        if not chunk:
                            continue
                        print(f"\nChunk {i}/{len(extraction_results)}:")
                        print(f"ID: {chunk.get('chunk_id', 'unknown')}")
                        print(f"Index: {chunk.get('chunk_index', 'unknown')}")
                        chunk_text = chunk.get('chunk_text', '')
                        print(f"Text Length: {len(chunk_text)} chars")
                        print(f"Text Sample: {chunk_text}" if chunk_text else "No text available")
                        
                        extraction = chunk.get('extraction', {})
                        if extraction:
                            print(f"Entities: {len(extraction.get('entities', []))} found")
                            print(f"Keywords: {len(extraction.get('keywords', []))} found")
                            print(f"Topics: {len(extraction.get('topics', []))} identified")
                            print(f"Insights/Summary: {extraction.get('summary', 'None')}")
                            
                            # Print detailed insights if available
                            summary = extraction.get('summary', '')
                            if summary and '|' in summary:  # Check if we have structured insights
                                print("\nDetailed Insights:")
                                for insight in summary.split('|'):
                                    insight = insight.strip()
                                    if insight.startswith(('Action:', 'Decision:', 'Issue:', 'Key point:', 'Pain Point:', 'Product Feature:', 'Objection:')):
                                        print(f"  • {insight}")
                    
                    # Show example documents
                    if extraction_results:
                        first_chunk = extraction_results[0]
                        if first_chunk:
                            print("\nEXAMPLE DOCUMENT STRUCTURES:")
                            print("\nSFDC_CHUNKS COLLECTION DOCUMENT STRUCTURE:")
                            chunk_text = first_chunk.get("chunk_text", "")
                            print(json.dumps({
                                "id": first_chunk.get("chunk_id", "unknown"),
                                "content": chunk_text if chunk_text else "",
                                "metadata": {
                                    "chunk_id": first_chunk.get("chunk_id", "unknown"),
                                    "parent_doc_id": first_result.get("document_id", "unknown"),
                                    "chunk_index": first_chunk.get("chunk_index", 0),
                                    "start_position": first_chunk.get("start_position", 0),
                                    "end_position": first_chunk.get("end_position", 0),
                                    "document_type": "sfdc_chunk",
                                    "source_type": "salesforce",
                                    "event_type": "extraction",
                                    "sfdc_name": first_result.get("metadata", {}).get("opportunity_name", "")
                                }
                            }, indent=2))
                            
                            print("\nSFDC_INSIGHTS COLLECTION DOCUMENT STRUCTURE:")
                            
                            # Parse JSON strings to arrays for display
                            metadata_display = {}
                            if first_result.get("metadata"):
                                metadata_display = first_result["metadata"].copy()
                                
                                # Parse entities, keywords, topics, categories from JSON string to array for display
                                for field in ["entities", "keywords", "topics", "categories"]:
                                    if field in metadata_display and isinstance(metadata_display[field], str) and metadata_display[field].startswith("["):
                                        try:
                                            metadata_display[field] = json.loads(metadata_display[field])
                                        except:
                                            metadata_display[field] = []
                            
                            # For the sample display, use the synthesized content (if available)
                            # or extract sections from insights
                            sample_content = first_result.get("synthesized_content", "No content available")
                            
                            # Get entities, keywords, topics, and categories from extracted data or empty lists
                            entities = []
                            keywords = []
                            topics = []
                            categories = []
                            
                            for chunk in extraction_results:
                                if chunk and chunk.get('extraction'):
                                    extraction = chunk.get('extraction', {})
                                    entities.extend(extraction.get('entities', []))
                                    keywords.extend(extraction.get('keywords', []))
                                    topics.extend(extraction.get('topics', []))
                                    categories.extend(extraction.get('categories', []))
                            
                            # Remove duplicates
                            entities = list(dict.fromkeys(entities))[:10]
                            keywords = list(dict.fromkeys(keywords))[:10]
                            topics = list(dict.fromkeys(topics))[:10]
                            categories = list(dict.fromkeys(categories))[:10]
                            
                            print(json.dumps({
                                "id": first_result.get("document_id", "unknown"),
                                "content": sample_content[:1000] + "..." if len(sample_content) > 1000 else sample_content,  # Truncate for display
                                "metadata": {
                                    "document_id": first_result.get("document_id", "unknown"),
                                    "document_type": "sfdc_opportunity_insights",
                                    "source_type": "salesforce",
                                    "event_type": "extraction",
                                    "sfdc_name": first_result.get("metadata", {}).get("opportunity_name", ""),
                                    "total_chunks": len(extraction_results),
                                    "entities": entities,
                                    "keywords": keywords,
                                    "topics": topics,
                                    "categories": categories,
                                    "chunk_collection": SFDC_CHUNKS_COLLECTION_NAME
                                }
                            }, indent=2))
    else:
        logger.info("Documents stored in regular storage (documents collection or PostgreSQL)")
    
    if failure_count > 0:
        logger.info("\nFailed opportunities:")
        for result in results:
            if not result.get("success", False):
                logger.info(f"- {result.get('document_id', 'Unknown')}: {result.get('error', 'Unknown error')}")
    
    # In test mode, print a sample document structure for non-extraction mode
    if test_mode and results and len(results) > 0 and not results[0].get("extraction_processed"):
        result = results[0]  # Get the first result
        print("\nCHROMADB STORAGE STRUCTURE (documents collection)")
        print(json.dumps({
            "id": result.get("document_id", ""),
            "content": result.get("content", ""),
            "metadata": result.get("metadata", {})
        }, indent=2))

def parse_insights_from_content(content: str) -> Dict[str, List[str]]:
    """Parse insights from the synthesized content."""
    insights = {
        "pain_points": [],
        "product_features": [],
        "objections": [],
        "action_items": [],
        "competitors": [],
        "decision_criteria": [],
        "use_cases": [],
        "decisions": [],
        "issues": [],
        "key_points": []
    }
    
    # Simple parsing based on section headers
    # Note: This is a basic implementation and might need refinement
    current_section = None
    content_lines = content.split('\n')
    
    for line in content_lines:
        line = line.strip()
        
        # Check for section headers
        if "Customer Pain Points" in line:
            current_section = "pain_points"
        elif "Product Features" in line or "Product Feature" in line:
            current_section = "product_features"
        elif "Objections" in line:
            current_section = "objections"
        elif "Action Items" in line or "Next Steps" in line:
            current_section = "action_items"
        elif "Competitors" in line:
            current_section = "competitors"
        elif "Decision Criteria" in line:
            current_section = "decision_criteria"
        elif "Use Cases" in line or "Use Case" in line:
            current_section = "use_cases"
        elif "Decisions" in line:
            current_section = "decisions"
        elif "Issues" in line:
            current_section = "issues"
        elif "Key Points" in line:
            current_section = "key_points"
        # Check for new major section that would end the current section
        elif line.startswith('##'):
            current_section = None
        
        # Extract items (lines starting with - or * after a section header)
        elif current_section and (line.startswith('-') or line.startswith('*')):
            # Clean up the bullet point and any markdown formatting
            item = line.lstrip('-* ').strip()
            item = re.sub(r'\*\*(.*?)\*\*', r'\1', item)  # Remove bold markdown
            
            # Skip very short items or ones that are just subheaders
            if len(item) > 5 and not item.endswith(':'):
                insights[current_section].append(item)
    
    return insights

@job
def sfdc_opportunities_ingestion_pipeline():
    """Pipeline to process Salesforce opportunity data from CSV files."""
    # Use context.op_config to access run configuration values inside ops
    records = load_sfdc_csv()
    documents = prepare_sfdc_documents(records)
    results = process_sfdc_documents(documents)
    summarize_sfdc_results(results)

# When running as a script, execute the pipeline
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Salesforce opportunity ingestion pipeline")
    parser.add_argument("--test", action="store_true", help="Run in test mode (don't write to storage)")
    parser.add_argument("--line", type=int, default=0, help="Single line index to process in test mode (default: 0)")
    parser.add_argument("--lines", type=str, help="Comma-separated list of line indices to process in test mode (e.g. '0,1,2')")
    parser.add_argument("--postgres", action="store_true", help="Store documents in PostgreSQL instead of ChromaDB")
    parser.add_argument("--extraction", action="store_true", help="Enable extraction pipeline processing - stores chunk content in sfdc_chunks and insights in sfdc_insights collections (skips regular document storage)")
    parser.add_argument("--debug", action="store_true", help="Debug mode - process a single batch without test mode to debug issues")
    args = parser.parse_args()
    
    # Handle line indices for test mode
    test_line_indices = []
    if args.test or args.debug:
        if args.lines:
            try:
                test_line_indices = [int(x.strip()) for x in args.lines.split(',')]
                logger.info(f"Running in {'DEBUG' if args.debug else 'TEST'} MODE, processing lines {test_line_indices}")
            except ValueError:
                logger.error("Invalid line indices format. Please use comma-separated integers (e.g. '0,1,2')")
                exit(1)
        else:
            test_line_indices = [args.line]
            logger.info(f"Running in {'DEBUG' if args.debug else 'TEST'} MODE, processing line {args.line} only")
    
    # Prepare configuration based on arguments
    run_config = {
        "ops": {
            "load_sfdc_csv": {
                "config": {
                    "test_mode": args.test or args.debug,
                    "test_line_indices": test_line_indices
                }
            },
            "prepare_sfdc_documents": {
                "config": {
                    "test_mode": args.test or args.debug
                }
            },
            "process_sfdc_documents": {
                "config": {
                    "test_mode": args.test and not args.debug,  # Only true test mode if not debug
                    "use_postgres": args.postgres,
                    "extraction": args.extraction
                }
            },
            "summarize_sfdc_results": {
                "config": {
                    "test_mode": args.test or args.debug
                }
            }
        }
    }
    
    if args.debug:
        logger.info("DEBUG MODE enabled - will process a single batch with actual storage")
    
    if args.extraction:
        logger.info("EXTRACTION MODE enabled - will process documents through extraction pipeline")
        logger.info(f"Chunk content will be stored in ChromaDB collection: {SFDC_CHUNKS_COLLECTION_NAME}")
        logger.info(f"Extracted insights will be stored in ChromaDB collection: {SFDC_INSIGHTS_COLLECTION_NAME}")
        logger.info("Regular document storage (documents collection/PostgreSQL) will be SKIPPED")
    elif args.postgres:
        logger.info("Using PostgreSQL for document storage")
    else:
        logger.info("Using ChromaDB for document storage")
    
    # Execute with our configuration
    sfdc_opportunities_ingestion_pipeline.execute_in_process(
        run_config=run_config,
        raise_on_error=True
    ) 