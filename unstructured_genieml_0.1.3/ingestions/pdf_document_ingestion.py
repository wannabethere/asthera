import json
import os
import tempfile
import logging
import traceback
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO
from datetime import datetime
import uuid
import asyncio
from collections import defaultdict
import re

from dagster import job, op, Array, Int
from langchain_openai import ChatOpenAI
from unstructured.partition.auto import partition
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from tiktoken import encoding_for_model
import spacy 

# Import the extraction pipeline components
from ingestions.extraction_pipeline import DocumentExtractor, ExtractionResult, ChunkResult

from app.config.extraction_config import get_questions_for_document_type
from ingestions.doc_extraction import DocumentInsightPipeline
from ingestions.doc_insight_extraction import DocumentChunk
from app.services.document_processor import DocumentProcessor
from app.schemas.document_schemas import DocumentType
from app.config.settings import get_settings
from app.models.dbmodels import DocumentInsight
from app.utils.chromadb import ChromaDB
from app.services.database.dbservice import DatabaseService
from app.services.vectorstore.documentstore import DocumentChromaStore

logger = logging.getLogger("pdf_document_ingestion")

# Only configure the logger if it hasn't been configured already
if not logger.handlers:
    # Set the level
    logger.setLevel(logging.INFO)
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler('pdf_ingestion.log')
    
    # Create formatter and add to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Ensure the logger propagates to the root logger (important for API integration)
logger.propagate = True

# Find the project root more robustly
def find_project_root() -> Path:
    """Find the project root directory from the current file"""
    current_dir = Path(__file__).resolve().parent
    
    # Try to find the project root by looking for key files/directories
    potential_root = current_dir
    while potential_root != potential_root.parent:
        # Check for common project root indicators
        if (potential_root / "app").exists() and (potential_root / "ingestions").exists():
            return potential_root
        potential_root = potential_root.parent
    
    # Fallback to a relative path from current directory
    return current_dir.parent

# Define the path to the JSONL file for PDF documents
project_root = find_project_root()
jsonl_path = project_root / "example_data" / "Tellius One Pager.pdf.pdf"

logger.info(f"Project root identified as: {project_root}")
logger.info(f"Example PDF path: {jsonl_path}")

# Define ChromaDB collection names
DOCUMENTS_COLLECTION = "documents"

try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("Successfully loaded spaCy model 'en_core_web_sm'")
except Exception as e:
    logger.warning(f"Could not load spaCy model: {e}. Simple extraction methods will be used.")
    nlp = None

@op
def load_pdf_jsonl() -> List[Dict[str, Any]]:
    """Load PDF documents from JSONL file or directly from PDF."""
    records = []
    logger.info(f"Loading PDF documents from path: {jsonl_path}")
    
    if not jsonl_path.exists():
        logger.error(f"File not found at {jsonl_path}")
        raise FileNotFoundError(f"File not found at {jsonl_path}")
    
    # Check if the file is a PDF
    if str(jsonl_path).lower().endswith('.pdf'):
        try:
            logger.info(f"Processing PDF file directly: {jsonl_path}")
            # Read the PDF file as binary
            with open(jsonl_path, 'rb') as pdf_file:
                pdf_binary = pdf_file.read()
                logger.info(f"Successfully read PDF binary data of size: {len(pdf_binary)} bytes")
            
            # Extract text from the PDF
            logger.info(f"Extracting text from binary PDF: {jsonl_path.name}")
            text_content = extract_text_from_binary_pdf(pdf_binary, jsonl_path.name)
            logger.info(f"Text extraction complete. Extracted {len(text_content)} characters")
            
            # Create a record with the extracted text
            record = {
                "content": text_content,
                "document_key": jsonl_path.name,
                "_ab_source_file_last_modified": datetime.now().isoformat(),
                "_ab_source_file_url": str(jsonl_path)
            }
            records.append(record)
            logger.info(f"Successfully created record for PDF: {jsonl_path.name}")
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}\n{traceback.format_exc()}")
            raise
    else:
        # Original JSONL processing
        logger.info(f"Processing as JSONL file: {jsonl_path}")
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            line_count = 0
            for line in f:
                if line.strip():
                    line_count += 1
                    logger.debug(f"Processing JSONL line {line_count}")
                    record = json.loads(line.strip())
                    records.append(record)
        logger.info(f"Loaded {len(records)} records from JSONL file")
    
    return records

@op
def prepare_pdf_documents(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepare PDF documents for processing."""
    logger.info(f"Preparing {len(records)} PDF document records for processing")
    documents = []
    for i, record in enumerate(records):
        # Ensure content is properly structured
        content = record.get("content", "")
        doc_key = record.get("document_key", "Untitled_PDF")
        
        if not content:
            logger.warning(f"Skipping document {doc_key} ({i+1}/{len(records)}) - no content")
            continue
        
        # Generate a document ID if not present
        doc_id = record.get("document_id", str(uuid.uuid4()))
        
        # Create properly structured document with metadata
        doc = {
            "document": {
                "content": content,
                "metadata": {
                    "document_id": doc_id,
                    "document_key": doc_key,
                    "filename": doc_key,
                    "document_type": DocumentType.GENERIC.value,
                    "source_type": "pdf",
                    "source_file_last_modified": record.get("_ab_source_file_last_modified", ""),
                    "source_file_url": record.get("_ab_source_file_url", "")
                }
            }
        }
        
        content_length = len(content)
        token_count = count_tokens(content)
        logger.info(f"Prepared document {doc_key} ({i+1}/{len(records)}) - {content_length} chars, ~{token_count} tokens")
        logger.info(f"Document ID: {doc_id}")
        documents.append(doc)
    
    logger.info(f"Successfully prepared {len(documents)} documents for processing")
    return documents

def extract_text_from_binary_pdf(pdf_binary: bytes, filename: str) -> str:
    """
    Extract text from a binary PDF file using Unstructured library with OCR.
    
    Args:
        pdf_binary: The binary content of the PDF file
        filename: The name of the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If text extraction fails
    """
    # Create a temporary file to store the binary PDF
    temp_path = None
    logger.info(f"Starting text extraction from PDF: {filename} ({len(pdf_binary)} bytes)")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(pdf_binary)
            temp_path = temp_pdf.name
            logger.info(f"Created temporary file at: {temp_path}")
        
        # Use the Unstructured library with "auto" strategy to parse the PDF
        # This automatically applies OCR where needed
        try:
            logger.info(f"Attempting to extract text from PDF using 'auto' strategy")
            start_time = datetime.now()
            elements = partition(
                filename=temp_path, 
                strategy="auto",  # Automatically selects the best strategy including OCR
                include_page_breaks=True
            )
            extraction_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Text extraction completed in {extraction_time:.2f} seconds, got {len(elements)} elements")
            
            # Extract text from the elements
            text_content = "\n\n".join([str(element) for element in elements])
            text_length = len(text_content)
            logger.info(f"Joined {len(elements)} elements into text content of {text_length} characters")
            
            if not text_content.strip():
                logger.error("No text content extracted from PDF")
                raise ValueError("No text content extracted from PDF")
            
            # Log a preview of the extracted text
            preview_length = min(200, len(text_content))
            logger.info(f"Text preview: {text_content[:preview_length]}...")
            return text_content
            
        except ImportError as e:
            # Handle import errors gracefully (missing optional dependencies)
            logger.warning(f"Unable to use full Unstructured features: {e}")
            # Try with a more basic strategy that uses fewer dependencies
            try:
                logger.info(f"Attempting to extract text using 'fast' strategy as fallback")
                start_time = datetime.now()
                elements = partition(
                    filename=temp_path,
                    strategy="fast",  # Use a faster method with fewer dependencies
                    include_page_breaks=True,
                    ocr_languages="eng"  # Specify English for OCR
                )
                extraction_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Fallback extraction completed in {extraction_time:.2f} seconds, got {len(elements)} elements")
                
                text_content = "\n\n".join([str(element) for element in elements])
                text_length = len(text_content)
                logger.info(f"Joined {len(elements)} elements into text content of {text_length} characters")
                
                if not text_content.strip():
                    logger.error("No text content extracted from PDF using fallback strategy")
                    raise ValueError("No text content extracted from PDF using fallback strategy")
                
                # Log a preview of the extracted text
                preview_length = min(200, len(text_content))
                logger.info(f"Text preview from fallback method: {text_content[:preview_length]}...")
                return text_content
            except Exception as inner_e:
                logger.error(f"Fallback strategy failed: {inner_e}\n{traceback.format_exc()}")
                raise ValueError(f"Failed to extract text from PDF: {inner_e}")
        except Exception as e:
            logger.error(f"Error in Unstructured partition: {e}\n{traceback.format_exc()}")
            raise ValueError(f"Failed to extract text from PDF: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in PDF text extraction: {e}\n{traceback.format_exc()}")
        raise ValueError(f"Unexpected error in PDF text extraction: {e}")
    finally:
        # Clean up the temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")

def summarize_pdf_content(content: str, document_id: str, filename: str, document_type: str, 
                         llm: Optional[ChatOpenAI] = None) -> str:
    """
    Generate a markdown summary of PDF content directly.
    Uses a recursive chunking approach to handle large documents without hitting token limits.
    
    Args:
        content: The PDF text content
        document_id: The document identifier
        filename: The name of the PDF file
        document_type: The type of document
        llm: Optional LLM instance to use
        
    Returns:
        Markdown formatted summary
    """
    logger.info(f"Starting PDF summarization (document: {filename})")
    content_length = len(content)
    token_count = count_tokens(content)
    logger.info(f"Content size: {content_length} characters, ~{token_count} tokens")
    
    if llm is None:
        settings = get_settings()
        llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
    
    output_parser = StrOutputParser()
    
    # Create the prompt template for summarizing content
    content_summary_prompt = PromptTemplate.from_template(
        """You are an expert technical writer and document summarization specialist. Your goal is to produce a single, highly polished summarizes the document.

Input Document:
Document Type: {document_type}
Document Name: {filename}

Content:
{content}

Your tasks:
1. Create a title that reflects the nature of the document (e.g., "Invoice Summary", "Contract Analysis").
2. Use Markdown features:
   - **Bold** for important labels and key findings
   - `Inline code` for exact values and identifiers
   - Bullet and numbered lists as appropriate
6. Handle newlines in the following way:
   - Remove literal \n characters from the text
   - Use a single newline (Enter/Return) to separate paragraphs
   - Use \n only when you need a hard line break within a paragraph
7. Ensure the final output:
   - Is concise yet comprehensive
   - Highlights the most important information
   - Uses proper Markdown formatting
   - Does **not** wrap the entire Markdown in triple backticks

Output only the summary.
"""
    )
    
    # Create the summarization chain
    summarization_chain = (
        RunnablePassthrough()
        | content_summary_prompt
        | llm
        | output_parser
    )
    
    # Handle large documents by chunking
    MAX_CHUNK_SIZE = 12000  # Characters per chunk to avoid token limits
    
    # If content is small enough, summarize directly
    if len(content) <= MAX_CHUNK_SIZE:
        logger.info(f"Content size below threshold, summarizing directly")
        summary = summarization_chain.invoke({
            "content": content,
            "document_type": document_type,
            "filename": filename,
            "document_id": document_id
        })
        logger.info(f"Direct summarization completed")
        return summary
    
    # For larger documents, use a hierarchical summarization approach
    chunks = []
    for i in range(0, len(content), MAX_CHUNK_SIZE):
        chunk = content[i:i + MAX_CHUNK_SIZE]
        chunks.append(chunk)
    
    logger.info(f"Document too large ({len(content)} chars), splitting into {len(chunks)} chunks")
    
    # First level: Summarize each chunk
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
        chunk_summary = summarization_chain.invoke({
            "content": chunk,
            "document_type": f"{document_type} - Part {i+1}",
            "filename": f"{filename} (Section {i+1})",
            "document_id": f"{document_id}-chunk-{i+1}"
        })
        chunk_summaries.append(chunk_summary)
    
    # Second level: Combine and summarize the summaries
    combined_summaries = "\n\n".join(chunk_summaries)
    logger.info(f"Generating final summary from {len(chunks)} chunk summaries")
    
    final_summary = summarization_chain.invoke({
        "content": f"This is a combined summary of multiple document sections:\n\n{combined_summaries}",
        "document_type": document_type,
        "filename": filename,
        "document_id": document_id
    })
    
    logger.info(f"Hierarchical summarization completed")
    return final_summary

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count the number of tokens in a text string using the specified model's tokenizer."""
    try:
        enc = encoding_for_model(model)
        return len(enc.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens: {e}")
        return 0

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

def deduplicate_extractions(items: List[str], similarity_threshold: float = 0.9) -> List[str]:
    """
    Deduplicate extraction items by removing similar items.
    Uses a simple string similarity approach to detect near-duplicates.
    
    Args:
        items: List of extracted items (entities, keywords, etc.)
        similarity_threshold: Threshold for considering items as similar (0-1)
        
    Returns:
        Deduplicated list of items
    """
    if not items:
        return []
    
    # Convert to lowercase for better matching
    items = [item.lower() for item in items]
    
    # Sort by length (descending) to prefer longer, more specific terms
    sorted_items = sorted(items, key=len, reverse=True)
    
    # Initialize result with the first item
    deduplicated = [sorted_items[0]]
    
    # Helper function to calculate string similarity
    def similarity(a, b):
        """Calculate simple string similarity ratio between 0-1"""
        a_set = set(a)
        b_set = set(b)
        # Jaccard similarity
        if not a_set or not b_set:
            return 0
        return len(a_set.intersection(b_set)) / len(a_set.union(b_set))
    
    # Check each item against already included items
    for item in sorted_items[1:]:
        # Skip if item is too short (likely noise or abbreviation)
        if len(item) < 3:
            continue
            
        # Check if this item is too similar to any already included item
        is_duplicate = False
        for existing in deduplicated:
            # If it's a substring of an existing item, it's a duplicate
            if item in existing:
                is_duplicate = True
                break
                
            # Or if it's very similar
            if similarity(item, existing) > similarity_threshold:
                is_duplicate = True
                break
                
        if not is_duplicate:
            deduplicated.append(item)
    
    # Restore original case from input if possible, or keep as is
    result = []
    for deduped_item in deduplicated:
        # Try to find the original case version
        original_case = next((original for original in items if original.lower() == deduped_item.lower()), deduped_item)
        result.append(original_case)
    
    return result

async def process_document_chunks(
    doc_id: str, 
    doc_chunks: List[Any], 
    documents: List[Dict[str, Any]], 
    chroma_store: DocumentChromaStore, 
    test_mode: bool = False,
    user_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single document's chunks with NLP using spaCy only.
    
    Args:
        doc_id: The document ID (with prefix)
        doc_chunks: List of chunks for this document
        documents: Original documents list
        chroma_store: ChromaDB store instance
        test_mode: Whether we're in test mode
        user_context: Optional user context to guide insight extraction
        
    Returns:
        dict: Processing result
    """
    logger.info(f"Processing document {doc_id} with {len(doc_chunks)} chunks")
    start_time = datetime.now()
    
    # Find the original document that matches this ID
    original_doc_id = doc_id.replace("pdf_", "")
    matching_docs = [d for d in documents if d["document"]["metadata"]["document_id"] == original_doc_id]
    
    if not matching_docs:
        logger.warning(f"Could not find original document for {doc_id}")
        return {
            "success": False,
            "document_id": original_doc_id,
            "error": "Original document not found",
            "extraction_processed": False
        }
    
    doc = matching_docs[0]
    original_doc_id = doc["document"]["metadata"]["document_id"]
    filename = doc["document"]["metadata"].get("filename", "unnamed_document.pdf")
    document_type = doc["document"]["metadata"].get("document_type", "generic")
    logger.info(f"Processing document: {filename} (ID: {original_doc_id})")
    
    try:
        # Run summarize_pdf_content at the beginning of each call
        document_content = doc["document"]["content"]
        logger.info("Generating general PDF summary")
        summary_start_time = datetime.now()
        summary_content = summarize_pdf_content(
            content=document_content,
            document_id=original_doc_id,
            filename=filename,
            document_type=document_type
        )
        summary_time = (datetime.now() - summary_start_time).total_seconds()
        logger.info(f"Generated document summary in {summary_time:.2f} seconds ({len(summary_content)} characters)")
        
        # Log the full summary without truncation
        logger.info(f"SUMMARY CONTENT:\n{summary_content}")
        
        # Initialize collection of entities, keywords, topics, categories
        all_entities = []
        all_keywords = []
        all_topics = []
        all_categories = []
        
        # Verify that we're using paragraph-aware chunking
        chunking_strategies = []
        for chunk in doc_chunks:
            if hasattr(chunk, 'overlap_info') and isinstance(chunk.overlap_info, dict):
                strategy = chunk.overlap_info.get('chunk_strategy', 'unknown')
                chunking_strategies.append(strategy)
        
        # Count occurrences of each strategy
        strategy_counts = {}
        for strategy in chunking_strategies:
            if strategy in strategy_counts:
                strategy_counts[strategy] += 1
            else:
                strategy_counts[strategy] = 1
        
        # Log the chunking strategy information in a consolidated format
        strategy_info = ", ".join([f"{strategy}: {count} chunks" for strategy, count in strategy_counts.items()])
        logger.info(f"Chunking strategies: {strategy_info}")
        
        # Process each chunk to collect NLP data - with minimal logging
        logger.info(f"Extracting NLP data from {len(doc_chunks)} chunks")
        
        # Store all chunk texts to concatenate later
        all_chunk_texts = []
        
        # Process chunks with less verbose logging
        for i, chunk in enumerate(doc_chunks):
            # Extract entities, keywords, topics, categories from NLP processing with spaCy
            chunk_entities = chunk.extraction.entities if hasattr(chunk.extraction, 'entities') else []
            chunk_keywords = chunk.extraction.keywords if hasattr(chunk.extraction, 'keywords') else []
            chunk_topics = chunk.extraction.topics if hasattr(chunk.extraction, 'topics') else []
            chunk_categories = chunk.extraction.categories if hasattr(chunk.extraction, 'categories') else []
            
            # Update overall collections
            all_entities.extend(chunk_entities)
            all_keywords.extend(chunk_keywords)
            all_topics.extend(chunk_topics)
            all_categories.extend(chunk_categories)
            
            # Store chunk text
            all_chunk_texts.append(chunk.text)
        
        logger.info(f"Extracted data from {len(doc_chunks)} chunks successfully")
        
        # Deduplicate the aggregated extractions
        logger.info("Deduplicating aggregated NLP extractions")
        
        pre_dedup_counts = {
            "entities": len(all_entities),
            "keywords": len(all_keywords),
            "topics": len(all_topics),
            "categories": len(all_categories)
        }
        
        # Deduplicate each type of extraction
        deduplicated_entities = deduplicate_extractions(all_entities)
        deduplicated_keywords = deduplicate_extractions(all_keywords)
        deduplicated_topics = deduplicate_extractions(all_topics)
        deduplicated_categories = deduplicate_extractions(all_categories)
        
        post_dedup_counts = {
            "entities": len(deduplicated_entities),
            "keywords": len(deduplicated_keywords),
            "topics": len(deduplicated_topics),
            "categories": len(deduplicated_categories)
        }
        
        # Log deduplication results in a consolidated format
        dedup_info = [
            f"Entities: {pre_dedup_counts['entities']} → {post_dedup_counts['entities']} ({pre_dedup_counts['entities'] - post_dedup_counts['entities']} removed)",
            f"Keywords: {pre_dedup_counts['keywords']} → {post_dedup_counts['keywords']} ({pre_dedup_counts['keywords'] - post_dedup_counts['keywords']} removed)",
            f"Topics: {pre_dedup_counts['topics']} → {post_dedup_counts['topics']} ({pre_dedup_counts['topics'] - post_dedup_counts['topics']} removed)",
            f"Categories: {pre_dedup_counts['categories']} → {post_dedup_counts['categories']} ({pre_dedup_counts['categories'] - post_dedup_counts['categories']} removed)"
        ]
        logger.info("Deduplication results: " + " | ".join(dedup_info))
        
        # Generate a single consolidated insight document using LLM
        logger.info("Generating consolidated insights document")
        
        if user_context:
            logger.info(f"Using provided user context for insights: {user_context}")
        else:
            logger.info("Using default general context for insights")
            user_context = "Provide a comprehensive overview of this document, highlighting key points, entities, and main insights without focusing on any specific aspect."
        
        insights_start_time = datetime.now()
        insights_content = generate_insights_with_context(document_content, user_context)
        insights_time = (datetime.now() - insights_start_time).total_seconds()
        logger.info(f"Generated insights in {insights_time:.2f} seconds ({len(insights_content)} characters)")
        
        # Log the full insights without truncation
        logger.info(f"INSIGHTS CONTENT:\n{insights_content}")
        
        # Create a single concatenated content from all chunks
        concatenated_content = "\n\n".join(all_chunk_texts)
        logger.info(f"Created concatenated content from {len(all_chunk_texts)} chunks ({len(concatenated_content)} characters)")
        
        # Prepare the document metadata structure
        document_metadata = {
            "document_id": original_doc_id,
            "document_type": "pdf",
            "source_type": "generic",
            "event_type": "upload",
            "filename": filename,
            "entities": json.dumps(deduplicated_entities),
            "keywords": json.dumps(deduplicated_keywords),
            "topics": json.dumps(deduplicated_topics),
            "categories": json.dumps(deduplicated_categories),
            "summary": summary_content,
            "insights": insights_content,
            "user_context": user_context if user_context else "general_overview"
        }
        
        # Clean metadata (remove nulls)
        document_metadata = remove_nulls(document_metadata)
        
        # Also log to the logger
        logger.info("="*80)
        logger.info("                ACTUAL CHROMADB STORAGE STRUCTURE                  ")
        logger.info("="*80)
        logger.info(f"Document ID: {original_doc_id}")
        logger.info(f"Content: Full text content - {len(concatenated_content)} characters")
        logger.info("Content Preview (first 150 chars): " + concatenated_content[:150] + "...")
        logger.info("Metadata (EXACTLY as it will be stored):")
        
        # Log a condensed version of metadata first for overview
        for key, value in document_metadata.items():
            if key in ["entities", "keywords", "topics", "categories"]:
                extracted_items = json.loads(value)
                logger.info(f"  - {key}: {len(extracted_items)} items")
            elif key in ["summary", "insights"]:
                logger.info(f"  - {key}: {len(value)} characters")
            else:
                logger.info(f"  - {key}: {value}")
        
        # Now log the full entities/keywords/topics/categories
        logger.info("-"*80)
        logger.info("FULL EXTRACTED METADATA CONTENT:")
        
        for key in ["entities", "keywords", "topics", "categories"]:
            if key in document_metadata:
                extracted_items = json.loads(document_metadata[key])
                logger.info(f"\n{key.upper()} ({len(extracted_items)} items):")
                if extracted_items:
                    # Show all items, not just samples
                    for i, item in enumerate(extracted_items):
                        logger.info(f"  {i+1}. {item}")
        
        logger.info("="*80)
        
        # Store a single document in ChromaDB with all chunks concatenated and NLP extractions in metadata
        if not test_mode:
            logger.info(f"Storing concatenated document in ChromaDB")
            try:
                # Store the single document with concatenated content and all metadata
                chroma_store.collection.add(
                    ids=[original_doc_id],
                    documents=[concatenated_content],
                    metadatas=[document_metadata]
                )
                logger.info(f"Successfully stored document in ChromaDB")
            except Exception as e:
                logger.error(f"Error storing document in ChromaDB: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.info("Test mode enabled - document structure shown but not stored in ChromaDB")
        
        total_processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Total document processing time: {total_processing_time:.2f} seconds")
        
        # Return processing results
        return {
            "success": True,
            "document_id": original_doc_id,
            "chunks_processed": len(doc_chunks),
            "entities": deduplicated_entities[:10],
            "keywords": deduplicated_keywords[:10],
            "topics": deduplicated_topics[:10],
            "categories": deduplicated_categories[:10],
            "summary_content": summary_content,
            "insights_content": insights_content,
            "deduplication_stats": {
                "entities": {"before": pre_dedup_counts["entities"], "after": post_dedup_counts["entities"]},
                "keywords": {"before": pre_dedup_counts["keywords"], "after": post_dedup_counts["keywords"]},
                "topics": {"before": pre_dedup_counts["topics"], "after": post_dedup_counts["topics"]},
                "categories": {"before": pre_dedup_counts["categories"], "after": post_dedup_counts["categories"]}
            },
            "processing_time_seconds": total_processing_time,
            "chunking_strategies": chunking_strategies
        }
    except Exception as e:
        error_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Error processing document {original_doc_id} after {error_time:.2f} seconds: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "document_id": original_doc_id,
            "error": str(e),
            "extraction_processed": False
        }

def generate_insights_with_context(content: str, user_context: str) -> str:
    """
    Generate insights from document content based on user-provided context.
    If no specific user context is provided, generate general insights.
    
    Args:
        content: The document content
        user_context: User-provided context to guide insight extraction,
                     or general instructions if no specific context provided
        
    Returns:
        Markdown formatted insights
    """
    logger.info(f"Starting insights generation with context ({len(user_context)} characters)")
    settings = get_settings()
    llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)
    
    output_parser = StrOutputParser()
    
    # Determine if this is a general or specific context
    is_general = "comprehensive overview" in user_context and "without focusing on any specific aspect" in user_context
    
    # Create the appropriate prompt template based on context type
    if is_general:
        logger.info("Using general insights prompt template")
        # More detailed prompt for general insights
        context_aware_prompt = PromptTemplate.from_template(
            """You are an expert document analyst tasked with extracting comprehensive insights from a document.

Document Content:
{content}

Your task is to create a well-structured Markdown document that:

1. Creates a title that reflects the nature of the document
2. Generates **Analysis & Insights** (main points, themes, implications)
3. Uses Markdown features effectively:
   - **Bold** for important labels and key findings
   - `Inline code` for exact values and identifiers
   - Bullet list

Ensure the final output is concise yet comprehensive, highlights the most important information, and uses proper Markdown formatting.

Do **not** wrap the entire Markdown in triple backticks

Output only the insights.
"""
        )
    else:
        logger.info("Using specific insights prompt template")
        # Original prompt for specific context
        context_aware_prompt = PromptTemplate.from_template(
            """You are an expert document analyst focusing on the aspects specified in the user's context. 
            Your task is to analyze the document and extract insights that align with what the user is looking for.

User Context:
{user_context}

Document Content:
{content}

Based on the user's context, extract and organize relevant insights from the document. 
Format your response in Markdown with appropriate headers and sections.
Focus specifically on what the user is interested in, while still providing a comprehensive analysis.

Your insights should be:
1. Directly relevant to the user's context
2. Factually accurate based on the document content
3. Organized with clear headers and bullet points
4. Concise yet informative
5. Uses Markdown features effectively:
   - **Bold** for important labels and key findings
   - `Inline code` for exact values and identifiers
   - Bullet list

Does **not** wrap the entire Markdown in triple backticks

Output only the Markdown insights.
"""
        )
    
    # Create the insight generation chain
    insight_chain = (
        RunnablePassthrough()
        | context_aware_prompt
        | llm
        | output_parser
    )
    
    try:
        logger.info("Executing insights generation chain")
        # Generate insights
        insights = insight_chain.invoke({
            "content": content,
            "user_context": user_context
        })
        
        logger.info(f"Insights generation completed successfully")
        
        return insights
    except Exception as e:
        logger.error(f"Error generating insights with context: {e}")
        # Return a simple error message formatted as Markdown
        return f"""# Error Generating Document Insights

Unfortunately, an error occurred while generating insights for this document:

```
{str(e)}
```

Please try again or contact support if the issue persists.
"""

@op(config_schema={"test_mode": bool})
async def process_pdf_documents(context, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process PDF documents with NLP and insights using a single ChromaDB collection."""
    test_mode = context.op_config["test_mode"]
    
    logger.info(f"Starting document processing with {len(documents)} documents")
    logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    start_time = datetime.now()
    
    # Initialize settings
    settings = get_settings()
    
    results = []
    
    # Initialize the DocumentExtractor for NLP processing
    logger.info("Initializing DocumentExtractor with advanced NLP")
    doc_extractor = DocumentExtractor(use_advanced_nlp=True)
    
    # Initialize the ChromaDB instance using DocumentChromaStore wrapper
    logger.info(f"Initializing ChromaDB connection for collection: {DOCUMENTS_COLLECTION}")
    chroma_store = DocumentChromaStore(collection_name=DOCUMENTS_COLLECTION)
    
    # Initialize PostgreSQL database service for document storage
    logger.info("Initializing PostgreSQL database service")
    db_service = DatabaseService()
    
    logger.info(f"Processing {len(documents)} documents with enhanced NLP")
    
    # Prepare documents for extraction in batches
    extraction_batch = []
    batch_size = 5  # Process 5 documents at a time
    total_docs = len(documents)
    
    logger.info(f"Preparing {total_docs} documents for processing")
    doc_prep_start = datetime.now()
    
    # Prepare all documents for extraction
    for doc_index, doc in enumerate(documents, 1):
        try:
            # Ensure document is in the expected format
            if "document" not in doc:
                logger.info(f"Document {doc_index}/{total_docs} needs restructuring")
                doc = {
                    "document": {
                        "content": doc.get("content", ""),
                        "metadata": {
                            "document_id": str(uuid.uuid4()),
                            "document_key": doc.get("document_key", ""),
                            "document_type": DocumentType.GENERIC.value,
                            "filename": doc.get("document_key", "unnamed_document.pdf"),
                            "source_type": "pdf"
                        }
                    }
                }
            
            # Get content and metadata
            content_text = doc["document"]["content"]
            doc_id = doc["document"]["metadata"]["document_id"]
            metadata = doc["document"]["metadata"]
        
            # Determine categories based on document data
            categories = []
            if metadata.get("document_type"):
                categories.append(f"type_{metadata['document_type']}")
            
            if metadata.get("filename"):
                file_type = metadata["filename"].split(".")[-1].lower() if "." in metadata["filename"] else "unknown"
                categories.append(f"file_{file_type}")
            
            # Extract user context if provided
            user_context = metadata.get("user_context", "")
            
            # Create extraction metadata
            extraction_metadata = {
                "document_id": doc_id,
                "document_type": metadata.get("document_type", DocumentType.GENERIC.value),
                "source_type": "pdf",
                "filename": metadata.get("filename", "unnamed_document.pdf"),
                "event_type": "upload",
                "user_context": user_context
            }
            
            # Add to extraction batch
            extraction_batch.append({
                "id": f"pdf_{doc_id}",
                "content": content_text,
                "categories": categories,
                "metadata": extraction_metadata
            })
            
            # Log document stats
            content_size = len(content_text.encode('utf-8'))
            metadata_size = len(json.dumps(metadata).encode('utf-8'))
            total_size = content_size + metadata_size
            content_tokens = count_tokens(content_text)
            
            logger.info(f"[PREP] [{doc_index}/{total_docs}] Prepared document {doc_id} - Size: {total_size/1024:.2f}KB, Tokens: {content_tokens}, Categories: {categories}")
        except Exception as e:
            logger.error(f"Error preparing document {doc_index}/{total_docs} for extraction: {e}\n{traceback.format_exc()}")
            results.append({
                "success": False,
                "document_id": doc.get("document", {}).get("metadata", {}).get("document_id", "unknown"),
                "error": f"Document preparation failed: {str(e)}"
            })
    
    doc_prep_time = (datetime.now() - doc_prep_start).total_seconds()
    logger.info(f"Document preparation completed in {doc_prep_time:.2f} seconds")
    
    # Process documents with NLP extraction
    try:
        logger.info(f"Processing {len(extraction_batch)} documents with NLP extraction")
        extraction_start = datetime.now()
        
        # Process all documents with paragraph-aware chunking
        logger.info("Starting batch document processing with paragraph-aware chunking")
        
        # Define a custom paragraph-aware chunking function to override the default
        async def paragraph_aware_chunking(doc_extractor, documents):
            """Process documents using only paragraph-aware chunking"""
            all_results = []
            
            for doc in documents:
                doc_id = doc.get('id', '')
                content = doc.get('content', '')
                categories = doc.get('categories', [])
                metadata = doc.get('metadata', {})
                
                logger.info(f"Processing document {doc_id} with paragraph-aware chunking")
                
                # Split content into paragraphs
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                
                if len(paragraphs) <= 1:
                    # If no paragraph breaks, create artificial ones based on sentences
                    logger.info(f"Document {doc_id} has no paragraph breaks, creating artificial ones")
                    sentences = re.split(r'(?<=[.!?])\s+', content)
                    # Group sentences into pseudo-paragraphs of ~5 sentences each
                    pseudo_paragraphs = []
                    for i in range(0, len(sentences), 5):
                        pseudo_paragraph = " ".join(sentences[i:i+5])
                        if pseudo_paragraph.strip():
                            pseudo_paragraphs.append(pseudo_paragraph)
                    paragraphs = pseudo_paragraphs
                    
                logger.info(f"Document {doc_id} split into {len(paragraphs)} paragraphs")
                
                # Create document with forced paragraph chunking
                chunk_size = 1000  # Default chunk size, will be adjusted based on paragraph size
                overlap = 50       # Small overlap between chunks
                
                # Calculate better chunk size based on average paragraph length
                if paragraphs:
                    avg_paragraph_length = sum(len(p) for p in paragraphs) / len(paragraphs)
                    # If paragraphs are very short, group multiple together
                    if avg_paragraph_length < 200:
                        chunk_size = max(chunk_size, int(avg_paragraph_length * 5))
                    # If paragraphs are very long, chunk them
                    elif avg_paragraph_length > 1500:
                        chunk_size = min(chunk_size, 1200)
                    else:
                        chunk_size = int(avg_paragraph_length * 1.5)
                    
                    logger.info(f"Adjusted chunk size to {chunk_size} based on avg paragraph length {avg_paragraph_length:.1f}")
                
                # Process with paragraph-aware chunking
                chunk_results = await doc_extractor.process_document_async(
                    doc_id=doc_id,
                    content=content,
                    categories=categories,
                    metadata=metadata,
                    chunk_size=chunk_size,
                    overlap=overlap
                )
                
                # Log the results of paragraph chunking
                logger.info(f"Created {len(chunk_results)} paragraph-aware chunks for document {doc_id}")
                all_results.extend(chunk_results)
            
            return all_results
        
        # Use our custom paragraph-aware chunking instead of the default process_documents_batch
        batch_chunk_results = await paragraph_aware_chunking(doc_extractor, extraction_batch)
        extraction_time = (datetime.now() - extraction_start).total_seconds()
        logger.info(f"Paragraph-aware document processing completed in {extraction_time:.2f} seconds, generated {len(batch_chunk_results)} chunks")
        
        # Group chunks by parent document
        chunks_by_doc = defaultdict(list)
        for chunk in batch_chunk_results:
            chunks_by_doc[chunk.parent_doc_id].append(chunk)
        
        num_docs_with_chunks = len(chunks_by_doc)
        logger.info(f"Grouped chunks into {num_docs_with_chunks} documents")
        
        # Process each document's chunks in parallel
        logger.info("Setting up parallel document processing tasks")
        doc_tasks = []
        for doc_id, doc_chunks in chunks_by_doc.items():
            # Extract user context from metadata if available
            user_context = None
            for doc in extraction_batch:
                if doc.get('id') == doc_id and doc.get('metadata'):
                    user_context = doc.get('metadata').get('user_context')
                    break
            
            task = process_document_chunks(
                doc_id=doc_id,
                doc_chunks=doc_chunks,
                documents=documents,
                chroma_store=chroma_store,
                test_mode=test_mode,
                user_context=user_context
            )
            doc_tasks.append(task)
        
        # Execute all document processing tasks in parallel
        logger.info(f"Processing {len(doc_tasks)} documents in parallel")
        parallel_start = datetime.now()
        document_results = await asyncio.gather(*doc_tasks)
        parallel_time = (datetime.now() - parallel_start).total_seconds()
        logger.info(f"Parallel document processing completed in {parallel_time:.2f} seconds")
        
        # Log success/failure stats
        success_count = sum(1 for r in document_results if r["success"])
        failure_count = len(document_results) - success_count
        logger.info(f"Processing results: {success_count} successful, {failure_count} failed")
        
        # Store documents in PostgreSQL
        if not test_mode:
            logger.info(f"Storing {success_count} documents in PostgreSQL")
            for result in document_results:
                if result.get("success", False):
                    doc_id = result["document_id"]
                    # Find the original document
                    for doc in documents:
                        if doc["document"]["metadata"].get("document_id") == doc_id:
                            content_text = doc["document"]["content"]
                            metadata = doc["document"]["metadata"]
                            
                            # Add NLP extraction results to metadata
                            metadata.update({
                                "entities": json.dumps(result.get("entities", [])),
                                "keywords": json.dumps(result.get("keywords", [])),
                                "topics": json.dumps(result.get("topics", [])),
                                "categories": json.dumps(result.get("categories", [])),
                                "summary": result.get("summary_content", ""),
                                "insights": result.get("insights_content", ""),
                                "extraction_processed": True
                            })
                            
                            # Store in PostgreSQL
                            try:
                                logger.info(f"Storing document {doc_id} in PostgreSQL")
                                db_service.store_document(
                                    content=content_text,
                                    metadata=metadata,
                                    source_type="pdf",
                                    document_type=DocumentType.GENERIC.value
                                )
                                logger.info(f"Successfully stored document {doc_id} in PostgreSQL")
                                
                                # Update result to indicate postgres storage
                                result["postgres_stored"] = True
                            except Exception as e:
                                logger.error(f"Error storing document {doc_id} in PostgreSQL: {e}")
                                result["postgres_stored"] = False
                                result["postgres_error"] = str(e)
                            break
        else:
            logger.info(f"Test mode - skipping PostgreSQL storage for {success_count} documents")
        
        # Add results
        results.extend(document_results)
        logger.info(f"Completed processing {len(document_results)} documents")
    except Exception as e:
        logger.error(f"Error in NLP extraction batch processing: {e}\n{traceback.format_exc()}")
        for doc in documents:
            doc_id = doc["document"]["metadata"].get("document_id", "unknown")
            results.append({
                "success": False,
                "document_id": doc_id,
                "error": f"Batch processing error: {str(e)}"
            })
    
    total_processing_time = (datetime.now() - start_time).total_seconds()
    success_count = sum(1 for r in results if r.get("success", False))
    failure_count = len(results) - success_count
    postgres_stored_count = sum(1 for r in results if r.get("postgres_stored", False))
    logger.info(f"Document processing completed in {total_processing_time:.2f} seconds")
    logger.info(f"Final results: {success_count} successful, {failure_count} failed, {postgres_stored_count} stored in PostgreSQL")
    
    return results

@op
def summarize_pdf_results(results: List[Dict[str, Any]]) -> None:
    """Summarize the results of PDF document processing."""
    success_count = sum(1 for r in results if r["success"])
    failure_count = len(results) - success_count
    extraction_count = sum(1 for r in results if r.get("success") and r.get("extraction_processed"))
    summary_count = sum(1 for r in results if r.get("success") and r.get("summary_generated"))
    postgres_stored_count = sum(1 for r in results if r.get("postgres_stored", False))
    
    # Calculate average processing times
    processing_times = [r.get("processing_time_seconds", 0) for r in results if r.get("processing_time_seconds")]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    # Calculate average summary and insights lengths
    summary_lengths = [r.get("summary_length", 0) for r in results if r.get("summary_length")]
    insights_lengths = [r.get("insights_length", 0) for r in results if r.get("insights_length")]
    avg_summary_length = sum(summary_lengths) / len(summary_lengths) if summary_lengths else 0
    avg_insights_length = sum(insights_lengths) / len(insights_lengths) if insights_lengths else 0
    
    # Calculate deduplication stats
    dedup_stats = [r.get("deduplication_stats", {}) for r in results if r.get("deduplication_stats")]
    if dedup_stats:
        total_entity_before = sum(stats.get("entities", {}).get("before", 0) for stats in dedup_stats)
        total_entity_after = sum(stats.get("entities", {}).get("after", 0) for stats in dedup_stats)
        total_keyword_before = sum(stats.get("keywords", {}).get("before", 0) for stats in dedup_stats)
        total_keyword_after = sum(stats.get("keywords", {}).get("after", 0) for stats in dedup_stats)
        total_topic_before = sum(stats.get("topics", {}).get("before", 0) for stats in dedup_stats)
        total_topic_after = sum(stats.get("topics", {}).get("after", 0) for stats in dedup_stats)
        
        entity_reduction = total_entity_before - total_entity_after
        keyword_reduction = total_keyword_before - total_keyword_after
        topic_reduction = total_topic_before - total_topic_after
        
        entity_reduction_pct = (entity_reduction / total_entity_before * 100) if total_entity_before else 0
        keyword_reduction_pct = (keyword_reduction / total_keyword_before * 100) if total_keyword_before else 0
        topic_reduction_pct = (topic_reduction / total_topic_before * 100) if total_topic_before else 0
    
    # Calculate percentages safely
    success_pct = (success_count / len(results) * 100) if results else 0
    failure_pct = (failure_count / len(results) * 100) if results else 0
    
    logger.info("=" * 60)
    logger.info("PDF DOCUMENT PROCESSING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total documents processed: {len(results)}")
    logger.info(f"Successful: {success_count} ({success_pct:.1f}%)")
    logger.info(f"  - Using spaCy NLP extraction: {extraction_count}")
    logger.info(f"  - Summaries generated: {summary_count}")
    logger.info(f"  - Stored in PostgreSQL: {postgres_stored_count}")
    logger.info(f"  - Avg. summary length: {avg_summary_length:.0f} chars")
    logger.info(f"  - Avg. insights length: {avg_insights_length:.0f} chars")
    logger.info(f"Failed: {failure_count} ({failure_pct:.1f}%)")
    logger.info(f"Average processing time: {avg_processing_time:.2f} seconds per document")
    
    print("\nPDF Document Processing Summary:")
    print(f"Total documents processed: {len(results)}")
    print(f"Successful: {success_count} ({success_pct:.1f}%)")
    print(f"  - Using spaCy NLP extraction: {extraction_count}")
    print(f"  - Summaries generated: {summary_count}")
    print(f"  - Stored in PostgreSQL: {postgres_stored_count}")
    print(f"  - Avg. summary length: {avg_summary_length:.0f} chars")
    print(f"  - Avg. insights length: {avg_insights_length:.0f} chars")
    print(f"Failed: {failure_count} ({failure_pct:.1f}%)")
    print(f"Average processing time: {avg_processing_time:.2f} seconds per document")
    
    # Print deduplication stats if available
    if dedup_stats:
        logger.info("\nDeduplication Statistics:")
        logger.info(f"Entities: {total_entity_before} → {total_entity_after} ({entity_reduction} removed, {entity_reduction_pct:.1f}%)")
        logger.info(f"Keywords: {total_keyword_before} → {total_keyword_after} ({keyword_reduction} removed, {keyword_reduction_pct:.1f}%)")
        logger.info(f"Topics: {total_topic_before} → {total_topic_after} ({topic_reduction} removed, {topic_reduction_pct:.1f}%)")
        
        print("\nDeduplication Statistics:")
        print(f"Entities: {total_entity_before} → {total_entity_after} ({entity_reduction} removed, {entity_reduction_pct:.1f}%)")
        print(f"Keywords: {total_keyword_before} → {total_keyword_after} ({keyword_reduction} removed, {keyword_reduction_pct:.1f}%)")
        print(f"Topics: {total_topic_before} → {total_topic_after} ({topic_reduction} removed, {topic_reduction_pct:.1f}%)")
    
    # Print chunking strategy information
    if extraction_count > 0:
        # Collect chunking strategy information
        all_chunking_strategies = []
        for r in results:
            if r.get("chunking_strategies"):
                all_chunking_strategies.extend(r.get("chunking_strategies", []))
        
        # Count strategy occurrences
        strategy_counts = {}
        for strategy in all_chunking_strategies:
            if strategy in strategy_counts:
                strategy_counts[strategy] += 1
            else:
                strategy_counts[strategy] = 1
        
        if strategy_counts:
            logger.info("\nChunking Strategies Used:")
            for strategy, count in strategy_counts.items():
                logger.info(f"  - {strategy}: {count} chunks")
            
            print("\nChunking Strategies Used:")
            for strategy, count in strategy_counts.items():
                print(f"  - {strategy}: {count} chunks")
            
            # Calculate percentage of paragraph-aware chunks
            paragraph_aware_count = strategy_counts.get("paragraph_aware", 0)
            total_chunks = sum(strategy_counts.values())
            if total_chunks > 0:
                paragraph_pct = (paragraph_aware_count / total_chunks) * 100
                logger.info(f"\nParagraph-aware chunking: {paragraph_aware_count}/{total_chunks} chunks ({paragraph_pct:.1f}%)")
                print(f"\nParagraph-aware chunking: {paragraph_aware_count}/{total_chunks} chunks ({paragraph_pct:.1f}%)")
    
    # Print PostgreSQL storage results
    postgres_success = sum(1 for r in results if r.get("postgres_stored", False) == True)
    postgres_failure = sum(1 for r in results if r.get("postgres_stored", False) == False and "postgres_error" in r)
    
    if postgres_success > 0 or postgres_failure > 0:
        logger.info("\nPostgreSQL Storage Results:")
        logger.info(f"Successfully stored in PostgreSQL: {postgres_success}")
        logger.info(f"Failed to store in PostgreSQL: {postgres_failure}")
        
        print("\nPostgreSQL Storage Results:")
        print(f"Successfully stored in PostgreSQL: {postgres_success}")
        print(f"Failed to store in PostgreSQL: {postgres_failure}")
        
        if postgres_failure > 0:
            logger.info("\nPostgreSQL Storage Errors:")
            for r in results:
                if r.get("postgres_stored", False) == False and "postgres_error" in r:
                    logger.info(f"  - {r['document_id']}: {r.get('postgres_error', 'Unknown error')}")
    
    # Print NLP extraction stats if available
    if extraction_count > 0:
        total_chunks = sum(r.get("chunks_processed", 0) for r in results if r.get("extraction_processed"))
        avg_chunks = total_chunks / extraction_count if extraction_count else 0
        
        logger.info("\nNLP Extraction Stats:")
        logger.info(f"Total chunks processed: {total_chunks} (avg: {avg_chunks:.1f} per document)")
        
        print("\nNLP Extraction Stats:")
        print(f"Total chunks processed: {total_chunks} (avg: {avg_chunks:.1f} per document)")
        
        # Find a result with entities/keywords to show as example
        for r in results:
            if r.get("extraction_processed") and r.get("entities"):
                logger.info("\nExample Extracted Entities:")
                for entity in r.get("entities", [])[:5]:
                    logger.info(f"  - {entity}")
                
                logger.info("\nExample Keywords:")
                for keyword in r.get("keywords", [])[:5]:
                    logger.info(f"  - {keyword}")
                
                logger.info("\nExample Topics:")
                for topic in r.get("topics", [])[:5]:
                    logger.info(f"  - {topic}")
                
                logger.info("\nExample Categories:")
                for category in r.get("categories", [])[:5]:
                    logger.info(f"  - {category}")
                
                print("\nExample Extracted Entities:")
                for entity in r.get("entities", [])[:5]:
                    print(f"  - {entity}")
                
                print("\nExample Keywords:")
                for keyword in r.get("keywords", [])[:5]:
                    print(f"  - {keyword}")
                
                print("\nExample Topics:")
                for topic in r.get("topics", [])[:5]:
                    print(f"  - {topic}")
                
                print("\nExample Categories:")
                for category in r.get("categories", [])[:5]:
                    print(f"  - {category}")
                
                break
    
    if failure_count > 0:
        logger.info("\nFailed documents:")
        for result in results:
            if not result["success"]:
                logger.info(f"- {result['document_id']}: {result['error']}")
        
        print("\nFailed documents:")
        for result in results:
            if not result["success"]:
                print(f"- {result['document_id']}: {result['error']}")
    
    logger.info("=" * 60)
    logger.info("END OF PROCESSING SUMMARY")
    logger.info("=" * 60)

@job
def pdf_document_ingestion_pipeline():
    """Pipeline to process PDF documents from JSONL files."""
    logger.info("Starting PDF document ingestion pipeline")
    records = load_pdf_jsonl()
    documents = prepare_pdf_documents(records)
    results = process_pdf_documents(documents)
    summarize_pdf_results(results) 
    logger.info("PDF document ingestion pipeline completed")

# When running directly as a module, log a startup message
if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("PDF DOCUMENT INGESTION MODULE STARTED")
    logger.info("=" * 80)
    logger.info("Module location: ingestions.pdf_document_ingestion")

# When running as a script, execute the pipeline with command line arguments
if __name__ == "__main__":
    import argparse
    import sys
    
    logger.info("=" * 80)
    logger.info("PDF DOCUMENT INGESTION PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Starting at: {datetime.now().isoformat()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Running from: {os.getcwd()}")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PDF document ingestion pipeline")
    parser.add_argument("--test", action="store_true", help="Run in test mode (don't write to storage)")
    args = parser.parse_args()
    
    # Prepare configuration based on arguments
    run_config = {
        "ops": {
            "process_pdf_documents": {
                "config": {
                    "test_mode": args.test
                }
            }
        }
    }
    
    # Print mode information
    logger.info(f"Command line arguments: {args}")
    if args.test:
        logger.info("TEST MODE enabled - will not write to storage")
        print("TEST MODE enabled - will not write to storage")
    else:
        logger.info("PRODUCTION MODE - will write to storage (ChromaDB and PostgreSQL)")
        print("PRODUCTION MODE - will write to storage (ChromaDB and PostgreSQL)")
    
    # Execute with our configuration
    start_time = datetime.now()
    logger.info(f"Starting pipeline execution at {start_time.isoformat()}")
    
    try:
        pdf_document_ingestion_pipeline.execute_in_process(
            run_config=run_config,
            raise_on_error=True
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Pipeline execution completed successfully in {duration:.2f} seconds")
        logger.info(f"Finished at: {end_time.isoformat()}")
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.error(f"Pipeline execution failed after {duration:.2f} seconds: {e}")
        logger.error(traceback.format_exc())
        logger.info(f"Failed at: {end_time.isoformat()}")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("PDF DOCUMENT INGESTION PIPELINE COMPLETED")
    logger.info("=" * 80) 