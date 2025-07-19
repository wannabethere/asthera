#!/usr/bin/env python3
"""
Utility functions extracted from query_insights.py for use in other modules.

This module contains key functionality from query_insights.py that has been 
refactored for reuse in other parts of the application, particularly in the
GongAgent. The main features include:

1. LLM-based query analysis to extract relevant search terms and metadata fields
2. Improved chunk retrieval that tries multiple parent document ID formats
3. Participant and mention extraction from document content

These utilities help ensure consistent behavior between the standalone 
query_insights.py script and the integrated GongAgent functionality.
"""

import json
import re
from typing import Dict, List, Any, Optional, cast, Tuple
from chromadb.api.types import Include

def analyze_query_with_llm(query: str, document_structure: Dict, user_topics: Optional[List[str]] = None) -> Dict:
    """
    Use LLM to analyze the query and determine relevant metadata fields based on the document structure.
    If user_topics are provided, they are used directly as search terms without LLM analysis.
    
    Args:
        query: The user's query
        document_structure: Example document structure showing available fields
        user_topics: Optional list of user-provided topics to respect
        
    Returns:
        Dict with search_terms and relevant_metadata_fields
    """
    import openai
    
    # If user topics are provided, we'll still need to determine relevant metadata fields
    # but we'll use the provided topics directly as search terms
    
    # Create a prompt that explains the document structure and asks for analysis
    topics_info = ""
    if user_topics:
        topics_info = f"\nThe user has specified these topics of interest: {', '.join(user_topics)}.\nYou MUST respect these topics in your analysis."
    
    prompt = f"""
You are an AI assistant helping to analyze a query for searching in a database of conversation insights.

The query is: "{query}"{topics_info}

Here's the structure of documents in the database:
```
{json.dumps(document_structure, indent=2)}
```

Based on the query, please analyze:
1. Which metadata fields are most relevant to this query? (e.g., topics, buyer_roles, pain_points)
2. Are there any specific sections in the document content that would be most relevant?

Respond in JSON format with these fields:
- relevant_metadata_fields: List of metadata fields that are most relevant
- relevant_sections: List of document sections that are most relevant
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes queries and provides structured JSON responses."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            result = json.loads(response.choices[0].message.content)
        else:
            # Fallback if response structure is unexpected
            result = {
                "relevant_metadata_fields": ["topics", "buyer_roles", "pain_points"],
                "relevant_sections": []
            }
        
        # If user provided topics, ensure they're included in the relevant metadata fields
        if user_topics and "relevant_metadata_fields" in result:
            if "topics" not in result["relevant_metadata_fields"]:
                result["relevant_metadata_fields"].append("topics")
        
        # Add search_terms to the result - use user_topics if provided, otherwise default
        result["search_terms"] = user_topics if user_topics else ["default"]
                
        return result
    except Exception as e:
        print(f"Error analyzing query with LLM: {e}")
        # Return default values if LLM analysis fails
        return {
            "search_terms": user_topics if user_topics else ["default"],
            "relevant_metadata_fields": ["topics", "buyer_roles", "pain_points"],
            "relevant_sections": []
        }

def get_example_document_structure():
    """Return an example document structure for LLM analysis."""
    return {
        "metadata": {
            "action_items": "List of action items from the call",
            "buyer_roles": "List of participants and their roles",
            "competitors": "Mentioned competitors",
            "gong_date": "Date of the call",
            "date_timestamp": "Timestamp of the call date",
            "deal_stage": "Current stage of the deal",
            "decision_criteria": "Criteria for decision making",
            "document_type": "Type of document (e.g., gong_call_insights)",
            "objections": "Objections raised during the call",
            "pain_points": "Customer pain points mentioned",
            "product_features": "Product features discussed",
            "gong_title": "Title of the call",
            "topics": "Topics covered in the call",
            "url": "URL to the original call",
            "use_cases": "Use cases discussed"
        },
        "content": "The document content is structured with sections like: Customer Pain Points, Product Features, Objections, Action Items, etc."
    }

def safely_parse_json_field(field_value, default_value=None):
    """
    Safely parse a JSON field that might be a string representation of JSON.
    
    Args:
        field_value: The field value to parse
        default_value: Default value to return if parsing fails
        
    Returns:
        Parsed JSON object or default value
    """
    if not field_value:
        return default_value
    
    # If it's already a dict or list, return it
    if isinstance(field_value, (dict, list)):
        return field_value
    
    # Try to parse as JSON
    try:
        # Remove any leading/trailing whitespace
        field_str = str(field_value).strip()
        return json.loads(field_str)
    except Exception:
        # If it's not valid JSON, return the original string
        return field_value

def get_related_chunks(chroma_client, doc_id, chunks_collection_name="chunks", debug=False):
    """
    Get related chunks for a document ID using the approach from view_gong_document.py.
    
    Args:
        chroma_client: ChromaDB client
        doc_id: Document ID to find chunks for
        chunks_collection_name: Name of the chunks collection (default: "chunks")
        debug: Whether to print debug information
        
    Returns:
        List of chunks or None if no chunks found
    """
    # Try different possible parent_document_id formats
    possible_parent_ids = [
        doc_id,
        # Remove _insight suffix if present (for backward compatibility)
        doc_id.replace("_insight", "") if doc_id.endswith("_insight") else doc_id,
        # Try with gong_ prefix
        f"gong_{doc_id}" if not doc_id.startswith("gong_") else doc_id,
        # Try without gong_ prefix
        doc_id.replace("gong_", "", 1) if doc_id.startswith("gong_") else doc_id,
        # Try removing both gong_ prefix and _insight suffix
        doc_id.replace("gong_", "", 1).replace("_insight", "") if doc_id.startswith("gong_") and doc_id.endswith("_insight") else doc_id
    ]
    
    # Remove duplicates while preserving order
    unique_parent_ids = []
    for pid in possible_parent_ids:
        if pid not in unique_parent_ids:
            unique_parent_ids.append(pid)
    possible_parent_ids = unique_parent_ids
    
    if debug:
        print(f"Looking for chunks with parent IDs: {possible_parent_ids}")
    
    try:
        # Check if client is None and initialize if needed
        if chroma_client is None:
            # Import here to avoid circular imports
            from app.utils.chromadb import ChromaDB
            chroma_db = ChromaDB()
            chroma_db._connect_client()
            chroma_client = chroma_db.client
            if chroma_client is None:
                raise Exception("Failed to initialize ChromaDB client connection")
        
        # Get the chunks collection
        chunks_collection = chroma_client.get_collection(chunks_collection_name)
        
        chunks_found = False
        chunks_data = []
        
        for parent_id in possible_parent_ids:
            if debug:
                print(f"Trying to find chunks with parent_document_id: {parent_id}")
            
            try:
                # First try with parent_document_id
                chunks_results = chunks_collection.get(
                    where={"parent_document_id": parent_id},
                    include=cast(Include, ["metadatas", "documents"]),
                    limit=100  # Set a high limit to get all available chunks
                )
                
                # If no results, try with consistent_doc_id
                if not chunks_results or not chunks_results.get("ids"):
                    if debug:
                        print(f"  No chunks found with parent_document_id, trying consistent_doc_id: {parent_id}")
                    chunks_results = chunks_collection.get(
                        where={"consistent_doc_id": parent_id},
                        include=cast(Include, ["metadatas", "documents"]),
                        limit=100  # Set a high limit to get all available chunks
                    )
                
                if chunks_results and chunks_results.get("ids"):
                    chunks_found = True
                    chunk_ids = chunks_results["ids"]
                    chunk_metadatas = chunks_results["metadatas"]
                    chunk_contents = chunks_results["documents"]
                    
                    if debug:
                        print(f"Found {len(chunk_ids)} chunks with parent ID: {parent_id}")
                    
                    for i, chunk_id in enumerate(chunk_ids):
                        metadata = chunk_metadatas[i] if chunk_metadatas and i < len(chunk_metadatas) else {}
                        content = chunk_contents[i] if chunk_contents and i < len(chunk_contents) else ""
                        
                        chunks_data.append({
                            "id": chunk_id,
                            "metadata": metadata,
                            "content": content
                        })
                    
                    # Stop after finding chunks with one parent_id format
                    break
            except Exception as e:
                if debug:
                    print(f"Error querying with parent_doc_id {parent_id}: {e}")
                continue
        
        if chunks_found:
            return chunks_data
        else:
            if debug:
                print(f"No chunks found for document ID: {doc_id}")
            return None
    
    except Exception as e:
        if debug:
            print(f"Error getting related chunks: {e}")
            import traceback
            traceback.print_exc()
        return None

def extract_participants_and_mentions(content, search_terms):
    """
    Extract participants and their mentions of the specified terms using semantic patterns.
    
    Args:
        content: The document content to search
        search_terms: List of terms to look for
    """
    # Create regex pattern with all search terms joined by '|'
    search_pattern = '|'.join([re.escape(term) for term in search_terms])
    
    # Look for patterns like "Name mentioned/discussed/talked about [any search term]"
    patterns = [
        rf'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)(?:\s+(?:mentioned|discussed|talked about|referred to|spoke about|introduced|presented|highlighted|described|explained|suggested|proposed|recommended|showcased|demonstrated|reviewed|analyzed))(?:[^.]*?\b(?:{search_pattern})\b)',
        rf'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:from|of|at|with)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:[^.]*?\b(?:{search_pattern})\b)',
    ]
    
    results = []
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            name = match.group(1)
            context = content[max(0, match.start() - 50):min(len(content), match.end() + 50)]
            results.append((name, context))
    
    # Also look for people's names that appear near search terms
    # This pattern looks for capitalized words (potential names) within 30 chars of search terms
    name_pattern = rf'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)(?:.{{0,30}}\b(?:{search_pattern})\b|\b(?:{search_pattern})\b.{{0,30}})'
    name_matches = re.finditer(name_pattern, content, re.IGNORECASE)
    for match in name_matches:
        name = match.group(1)
        # Skip common words that might be capitalized but aren't names
        if name.lower() in ['the', 'a', 'an', 'this', 'that', 'these', 'those', 'product', 'feature', 'service']:
            continue
        context = content[max(0, match.start() - 50):min(len(content), match.end() + 50)]
        results.append((name, context))
    
    return results 

def query_insights_collection(chroma_client, query_text, user_topics=None, insights_collection_name="insights", n_results=20, debug=False):
    """
    Query the insights collection using the approach from query_insights.py.
    
    Args:
        chroma_client: ChromaDB client or ChromaDB instance
        query_text: The query text to search for
        user_topics: Optional list of user-provided topics to filter by and use as search terms
        insights_collection_name: Name of the insights collection (default: "insights")
        n_results: Maximum number of results to return
        debug: Whether to print debug information
        
    Returns:
        List of filtered insight documents
    """
    # Import logging here to avoid circular imports
    import logging
    logger = logging.getLogger("query_insights")
    
    # Set logger level based on debug parameter
    if debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Querying collection: {insights_collection_name}")
    logger.info(f"Query text: {query_text}")
    if user_topics:
        logger.info(f"Topics filter: {user_topics}")
    else:
        logger.info("No user topics provided")
    
    # Get example document structure for LLM analysis
    document_structure = get_example_document_structure()
    
    # Always analyze the query to determine relevant metadata fields
    # but use user_topics directly as search terms if provided
    logger.info("Analyzing query to determine relevant metadata fields...")
    
    llm_analysis = analyze_query_with_llm(query_text, document_structure, user_topics)
    
    # Get search terms from LLM analysis or user topics
    search_terms = llm_analysis.get("search_terms", ["default"])  # Default fallback
    
    logger.info(f"Analysis results:")
    # Comment out detailed analysis results to reduce log verbosity
    # logger.info(f"- Search terms: {search_terms}")
    # logger.info(f"- Relevant metadata fields: {llm_analysis.get('relevant_metadata_fields', [])}")
    # logger.info(f"- Relevant sections: {llm_analysis.get('relevant_sections', [])}")
    
    # If topics are provided, enhance the query
    enhanced_query = query_text
    if user_topics:
        topics_str = ' '.join(user_topics)
        enhanced_query = f"{query_text} {topics_str}"
        logger.info(f"Enhanced query with topics: '{enhanced_query}'")
    
    try:
        # Check if we're dealing with a ChromaDB instance or a raw client
        # If it's a ChromaDB instance, use its query_collection_with_relevance_scores method
        # If it's a raw client, create a ChromaDB instance and use that
        from app.utils.chromadb import ChromaDB
        
        if isinstance(chroma_client, ChromaDB):
            # It's already a ChromaDB instance, use it directly
            logger.info(f"Using provided ChromaDB instance")
            chroma_db = chroma_client
        else:
            # It's a raw client, create a ChromaDB instance
            logger.info(f"Creating new ChromaDB instance from provided client")
            chroma_db = ChromaDB(log_level="WARNING")
            # Initialize the connection before setting the client
            chroma_db._connect_client()
            chroma_db.client = chroma_client
        
        # Query the collection with relevance scores
        logger.info(f"Executing ChromaDB query with n_results={n_results}...")
        results = chroma_db.query_collection_with_relevance_scores(
            collection_name=insights_collection_name,
            query_texts=[enhanced_query],
            n_results=n_results
        )
        
        logger.info(f"ChromaDB returned {len(results)} raw results")
        
        # Count how many results are within the 120-day window
        from datetime import datetime, timedelta
        now = datetime.now()
        max_range_timestamp = (now - timedelta(days=120)).timestamp()
        
        within_120_days = 0
        outside_120_days = 0
        
        for result in results:
            metadata = result.get('metadata', {})
            date_timestamp = metadata.get('date_timestamp')
            
            try:
                if isinstance(date_timestamp, str):
                    date_timestamp = float(date_timestamp)
                
                if date_timestamp is not None:
                    if float(date_timestamp) >= max_range_timestamp:
                        within_120_days += 1
                    else:
                        outside_120_days += 1
            except (ValueError, TypeError):
                # Count documents with invalid timestamps as outside the window
                outside_120_days += 1
        
        logger.info(f"Time window analysis: {within_120_days} insights within 120 days, {outside_120_days} insights outside 120 days")
        
        # Filter results based on topics
        filtered_results = []
        
        for result in results:
            content = result.get('content', '').lower()
            metadata = result.get('metadata', {})
            
            # For semantic matching, we rely on the relevance score from ChromaDB
            # and don't filter by exact term matching
            content_match = True
            
            # Check if any of the specified topics are in the metadata or content
            topic_match = True  # Default to True if no topics specified
            
            # We don't need to filter by topics because:
            # 1. The topics in metadata are section headers, not actual topic values
            # 2. We're already using the topics in the semantic search query
            # 3. The ChromaDB query already handles semantic matching
            
            # Log metadata for debugging
            if debug and 'topics' in metadata:
                topics_json = safely_parse_json_field(metadata.get('topics'), [])
                # logger.info(f"Document {result.get('document_id', 'unknown')}: metadata topics = {topics_json}")
            
            # Add to filtered results if both conditions are met
            if content_match and topic_match:
                filtered_results.append(result)
        
        if user_topics:
            logger.info(f"Found {len(filtered_results)} results matching query and topics {user_topics} out of {len(results)} total results")
        else:
            logger.info(f"Found {len(filtered_results)} results matching query out of {len(results)} total results")
        
        # Log first few results for debugging
        if filtered_results:
            logger.info("Top results:")
            # Comment out detailed results to reduce log verbosity
            # for i, result in enumerate(filtered_results[:3]):
            #     doc_id = result.get('document_id', 'unknown')
            #     score = result.get('relevance_score', 0)
            #     metadata = result.get('metadata', {})
            #     title = metadata.get('title', metadata.get('gong_title', 'No title'))
            #     logger.info(f"  {i+1}. '{title}' (ID: {doc_id}, score: {score:.4f})")
        else:
            logger.info("No results found after filtering")
        
        return filtered_results, llm_analysis
    
    except Exception as e:
        logger.error(f"Error querying collection: {e}")
        import traceback
        traceback.print_exc()
        return [], llm_analysis 